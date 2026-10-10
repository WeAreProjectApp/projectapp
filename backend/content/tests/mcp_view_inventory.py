"""Read-only AST inventory of the documents/projects MCP-to-Panel boundary.

No view, helper or serializer validation is executed. Only serializer field
construction runs; relational choices are deliberately never evaluated. Opaque
paths are reported rather than guessed. Helper expansion stops after one hop.
"""

import ast
import inspect
import json
import sys
import textwrap
from collections import Counter
from copy import deepcopy
from importlib import import_module

from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from rest_framework import serializers

from content.mcp.schemas.projects_bridge import PANEL_ONLY_FIELDS
from content.tests.mcp_schema_rules import CONNECTORS, schema_problems

_CHANNELS = {'query_params': 'query', 'GET': 'query', 'data': 'data', 'FILES': 'files'}
_MISSING = object()


def _literal(node, bindings):
    if isinstance(node, ast.Name):
        return bindings.get(node.id, _MISSING)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = [_literal(item, bindings) for item in node.elts]
        return values if all(item is not _MISSING for item in values) else _MISSING
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return _MISSING


def _symbol(node, namespace):
    if isinstance(node, ast.Name):
        return namespace.get(node.id)
    if isinstance(node, ast.Attribute):
        parent = _symbol(node.value, namespace)
        return getattr(parent, node.attr, None)
    return None


def _field_description(field):
    result = {
        'type': type(field).__name__, 'required': field.required,
        'read_only': field.read_only, 'allow_null': field.allow_null,
    }
    if isinstance(field, serializers.ChoiceField):
        result['choices'] = list(field.choices)
    if isinstance(field, serializers.BaseSerializer):
        child = getattr(field, 'child', field)
        result['fields'] = {name: _field_description(value) for name, value in child.fields.items()}
    elif isinstance(field, (serializers.ListField, serializers.DictField)):
        result['child'] = _field_description(field.child)
    return result


class _ReadCollector(ast.NodeVisitor):
    def __init__(self, result, *, function, source_tree, namespace, method, bindings,
                 request_name='request', depth=0, line_offset=0):
        self.result = result
        self.function = function
        self.source_tree = source_tree
        self.namespace = dict(namespace)
        self.method = method
        self.bindings = dict(bindings)
        self.request_name = request_name
        self.depth = depth
        self.line_offset = line_offset
        self.aliases = {}

    def opaque(self, node, reason):
        self.result['opaque'].append({
            'function': self.function, 'line': node.lineno + self.line_offset,
            'reason': reason,
        })

    def channel(self, node):
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id)
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == self.request_name):
            return _CHANNELS.get(node.attr)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'copy'):
            return self.channel(node.func.value)
        return None

    def read(self, channel, key, node):
        value = _literal(key, {**self.namespace, **self.bindings})
        if isinstance(value, str):
            self.result[f'{channel}_reads'].add(value)
        else:
            self.opaque(node, f'Dynamic {channel} key: {ast.unparse(key)}')

    def _condition(self, node):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left = node.left
            if (isinstance(left, ast.Attribute) and isinstance(left.value, ast.Name)
                    and left.value.id == self.request_name and left.attr == 'method'):
                right = _literal(node.comparators[0], self.bindings)
                if isinstance(node.ops[0], ast.Eq) and isinstance(right, str):
                    return self.method == right
                if isinstance(node.ops[0], ast.NotEq) and isinstance(right, str):
                    return self.method != right
                if isinstance(node.ops[0], ast.In) and isinstance(right, list):
                    return self.method in right
        if isinstance(node, ast.BoolOp):
            values = [self._condition(item) for item in node.values]
            if isinstance(node.op, ast.And) and False in values:
                return False
            if isinstance(node.op, ast.Or) and True in values:
                return True
            if all(item is not None for item in values):
                return all(values) if isinstance(node.op, ast.And) else any(values)
        return None

    def _terminates(self, node):
        if isinstance(node, (ast.Return, ast.Raise)):
            return True
        if isinstance(node, (ast.With, ast.AsyncWith)):
            return any(self._terminates(child) for child in node.body)
        if isinstance(node, ast.If):
            condition = self._condition(node.test)
            if condition is not None:
                branch = node.body if condition else node.orelse
                return any(self._terminates(child) for child in branch)
            return (any(self._terminates(child) for child in node.body)
                    and any(self._terminates(child) for child in node.orelse))
        return False

    def visit_body(self, body):
        for child in body:
            self.visit(child)
            if self._terminates(child):
                break

    def visit_With(self, node):
        for item in node.items:
            self.visit(item.context_expr)
        self.visit_body(node.body)

    def visit_If(self, node):
        self.visit(node.test)
        condition = self._condition(node.test)
        branches = node.body if condition is True else node.orelse if condition is False else [*node.body, *node.orelse]
        if condition is None:
            self.visit_body(node.body)
            self.visit_body(node.orelse)
        else:
            self.visit_body(branches)

    def visit_Assign(self, node):
        self.visit(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                channel = self.channel(node.value)
                if channel:
                    self.aliases[target.id] = channel
                else:
                    self.aliases.pop(target.id, None)
                value = _literal(node.value, {**self.namespace, **self.bindings})
                if value is not _MISSING:
                    self.bindings[target.id] = value
                else:
                    self.bindings.pop(target.id, None)

    def visit_ImportFrom(self, node):
        try:
            package = self.namespace.get('__package__')
            module = import_module('.' * node.level + (node.module or ''), package)
            for alias in node.names:
                self.namespace[alias.asname or alias.name] = getattr(module, alias.name)
        except (ImportError, AttributeError, TypeError) as exc:
            self.opaque(node, f'Unresolved local import: {type(exc).__name__}')

    def visit_For(self, node):
        self.visit(node.iter)
        if self.channel(node.iter):
            self.opaque(node, f'Iteration over the whole {self.channel(node.iter)} mapping')
        values = _literal(node.iter, {**self.namespace, **self.bindings})
        if isinstance(node.target, ast.Name) and isinstance(values, (list, tuple, set, dict)):
            previous = self.bindings.get(node.target.id, _MISSING)
            for value in values:
                self.bindings[node.target.id] = value
                for child in node.body:
                    self.visit(child)
            if previous is _MISSING:
                self.bindings.pop(node.target.id, None)
            else:
                self.bindings[node.target.id] = previous
        else:
            for child in node.body:
                self.visit(child)
        for child in node.orelse:
            self.visit(child)

    def visit_Compare(self, node):
        left = node.left
        for op, right in zip(node.ops, node.comparators, strict=True):
            channel = self.channel(right)
            if channel and isinstance(op, (ast.In, ast.NotIn)):
                self.read(channel, left, node)
            left = right
        self.generic_visit(node)

    def visit_Subscript(self, node):
        channel = self.channel(node.value)
        if channel:
            self.read(channel, node.slice, node)
        self.generic_visit(node)

    def _serializer(self, node, channel):
        serializer_class = _symbol(node.func, self.namespace)
        if not inspect.isclass(serializer_class) or not issubclass(serializer_class, serializers.BaseSerializer):
            return False
        try:
            serializer = serializer_class()
            fields = {name: _field_description(field) for name, field in serializer.fields.items()}
        except Exception as exc:  # noqa: BLE001 -- Dynamic fields must leave an opaque inventory entry.
            self.opaque(node, f'Serializer fields unavailable: {ast.unparse(node.func)} ({type(exc).__name__})')
            return True
        self.result['serializers'].append({
            'class': f'{serializer_class.__module__}.{serializer_class.__qualname__}',
            'channel': channel, 'fields': fields,
        })
        self.result[f'{channel}_reads'].update(name for name, field in fields.items() if not field['read_only'])
        return True

    def _helper(self, node):
        call_name = node.func.id if isinstance(node.func, ast.Name) else None
        definition = next((child for child in self.source_tree.body
                           if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == call_name), None)
        runtime = _symbol(node.func, self.namespace)
        helper_tree, line_offset = self.source_tree, self.line_offset
        if (definition is None and inspect.isfunction(runtime)
                and runtime.__module__ == self.namespace.get('__name__')):
            source, start = inspect.getsourcelines(inspect.unwrap(runtime))
            helper_tree = ast.parse(textwrap.dedent(''.join(source)))
            definition = helper_tree.body[0]
            line_offset = start - 1
        if definition is None or not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.opaque(node, f'Request passed to unresolved/external helper: {ast.unparse(node.func)}')
            return
        if self.depth >= 1:
            self.opaque(node, f'Helper exceeds one-hop limit: {call_name}')
            return
        parameters = [arg.arg for arg in (*definition.args.posonlyargs, *definition.args.args)]
        supplied = {name: value for name, value in zip(parameters, node.args)}
        supplied.update({kw.arg: kw.value for kw in node.keywords if kw.arg})
        request_name = next((name for name, value in supplied.items()
                             if isinstance(value, ast.Name) and value.id == self.request_name), None)
        if request_name is None:
            self.opaque(node, f'Request cannot be bound to helper: {call_name}')
            return
        bindings = {}
        for name, value in zip(parameters[-len(definition.args.defaults):], definition.args.defaults):
            bindings[name] = _literal(value, self.bindings)
        for name, value in supplied.items():
            bindings[name] = _literal(value, {**self.namespace, **self.bindings})
        self.result['helpers'].add(definition.name)
        visitor = _ReadCollector(self.result, function=definition.name, source_tree=helper_tree,
                                 namespace=self.namespace, method=self.method, bindings=bindings,
                                 request_name=request_name, depth=self.depth + 1, line_offset=line_offset)
        visitor.visit_body(definition.body)

    def visit_Call(self, node):
        handled = False
        if isinstance(node.func, ast.Attribute):
            channel = self.channel(node.func.value)
            if channel and node.func.attr in ('get', 'getlist', 'pop'):
                if node.args:
                    self.read(channel, node.args[0], node)
                else:
                    self.opaque(node, f'{channel}.{node.func.attr} has no literal key')
                handled = True
            elif channel and node.func.attr not in ('copy',):
                self.opaque(node, f'Unresolved {channel} method: {node.func.attr}')
                handled = True
        input_channels = [(kw, self.channel(kw.value)) for kw in node.keywords if kw.arg == 'data']
        for _kw, channel in input_channels:
            if channel and self._serializer(node, channel):
                handled = True
        values = [*node.args, *(kw.value for kw in node.keywords)]
        if any(isinstance(value, ast.Name) and value.id == self.request_name for value in values):
            self._helper(node)
            handled = True
        if not handled:
            for value in values:
                channel = self.channel(value)
                if channel:
                    self.opaque(node, f'Whole {channel} mapping passed to {ast.unparse(node.func)}')
        self.generic_visit(node)


def collect_view_reads(source, *, function_name=None, namespace=None, method='GET', line_offset=0):
    """Collect literal reads from a source string (also usable by synthetic tests)."""
    result = {
        'query_reads': set(), 'data_reads': set(), 'files_reads': set(),
        'serializers': [], 'helpers': set(), 'opaque': [],
    }
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError as exc:
        result['opaque'].append({'function': function_name, 'line': exc.lineno, 'reason': 'Source cannot be parsed'})
        tree = ast.Module(body=[], type_ignores=[])
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    definition = next((node for node in functions if function_name is None or node.name == function_name), None)
    if definition:
        request_name = definition.args.args[0].arg
        visitor = _ReadCollector(result, function=definition.name, source_tree=tree,
                                 namespace=namespace or {}, method=method.upper(), bindings={},
                                 request_name=request_name, line_offset=line_offset)
        visitor.visit_body(definition.body)
    elif not result['opaque']:
        result['opaque'].append({'function': function_name, 'line': None, 'reason': 'View function is absent from source'})
    for key in ('query_reads', 'data_reads', 'files_reads', 'helpers'):
        result[key] = sorted(result[key])
    result['opaque'] = list({json.dumps(item, sort_keys=True): item for item in result['opaque']}.values())
    result['serializers'] = list({json.dumps(item, sort_keys=True): item for item in result['serializers']}.values())
    return result


def _unwrap_view(callback, method):
    view = inspect.unwrap(callback)
    cls = getattr(callback, 'cls', None) or getattr(view, 'cls', None)
    if cls:
        handler = getattr(cls, method.lower())
        original = inspect.getclosurevars(handler).nonlocals.get('func')
        if not inspect.isfunction(original):
            raise ValueError('DRF method does not expose its original FBV')
        return inspect.unwrap(original)
    return view


def _bridge_definitions():
    """Locate literal registrations, including imported native tool builders."""
    definitions = {}
    for name, module in sorted(sys.modules.copy().items()):
        if not name.startswith('content.mcp.') or module is None:
            continue
        try:
            tree = ast.parse(inspect.getsource(module))
        except (OSError, TypeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ('_op', 'panel_operation', '_tool') and node.args):
                tool_name = _literal(node.args[0], {})
                if isinstance(tool_name, str):
                    definitions[tool_name] = name
    return definitions


def _native_origin(handler):
    origin = handler
    seen = set()
    while inspect.isfunction(origin) and origin not in seen:
        seen.add(origin)
        native = inspect.getclosurevars(origin).nonlocals.get('native')
        if not inspect.isfunction(native):
            break
        origin = native
    return origin.__module__


def inventory_tool(connector, tool, *, definitions=None):
    """Inventory one normalized published tool without invoking its handler."""
    operation = tool.get('_panel_operation')
    handler_module = tool['handler'].__module__
    definitions = _bridge_definitions() if definitions is None else definitions
    module = definitions.get(tool['name'], handler_module) if operation else handler_module
    schema_module = definitions.get(tool['name'], _native_origin(tool['handler'])) if not operation else module
    if tool['name'] in {'describe_capabilities', 'confirm_action', 'cancel_action'}:
        schema_module = 'content.mcp.common_tools'
    root = tool['input_schema']
    properties = root.get('properties', {})
    problems = schema_problems(tool)
    state = ('generic' if root.get('additionalProperties') is not False
             else 'aliases' if {'data', 'query'} & properties.keys()
             else 'partially typed' if problems else 'explicit')
    row = {
        'connector': connector, 'name': tool['name'], 'module': module,
        'schema_module': schema_module,
        'family': f'{connector}-bridge' if operation else 'natives',
        'excluded': schema_module in {'content.mcp.entity_history_tools', 'content.mcp.common_tools'},
        'method': operation['method'] if operation else None,
        'route_name': operation['route_name'] if operation else None,
        'path': None, 'view': None, 'input_schema': deepcopy(root),
        'schema_state': state, 'schema_problems': problems,
        'aliases': sorted({'data', 'query'} & tool.get('accepted_arguments_schema', {}).get('properties', {}).keys()),
        'has_accepted_arguments_schema': 'accepted_arguments_schema' in tool,
        'requires_confirmation': bool(tool.get('requires_confirmation')),
        'asset_fields': deepcopy(operation.get('asset_fields', {})) if operation else {},
        'explicit_bridge': bool(operation and (operation.get('payload_schema') is not None or operation.get('query_schema') is not None)),
        'query_reads': [], 'data_reads': [], 'files_reads': [],
        'serializers': [], 'helpers': [], 'opaque': [],
        'panel_only_fields': deepcopy(PANEL_ONLY_FIELDS.get(tool['name'], {}))
        if connector == 'projects' and operation else {},
    }
    if operation:
        try:
            params = {name: 'project' if name == 'entity_type' else 1 for name in operation['path_params']}
            row['path'] = reverse(operation['route_name'], kwargs=params)
            view = _unwrap_view(resolve(row['path']).func, operation['method'])
            row['view'] = f'{view.__module__}.{view.__name__}'
            source, start = inspect.getsourcelines(view)
            row.update(collect_view_reads(''.join(source), function_name=view.__name__, namespace=view.__globals__,
                                          method=operation['method'], line_offset=start - 1))
        except (OSError, TypeError, ValueError, LookupError, AttributeError, NoReverseMatch, Resolver404) as exc:
            row['opaque'].append({'function': row['view'], 'line': None,
                                  'reason': f'View resolution/source unavailable: {type(exc).__name__}: {exc}'})
    declared = set(properties)
    uploaded_fields = {config['field'] for config in row['asset_fields'].values()}
    row['undeclared_query'] = sorted(set(row['query_reads']) - declared)
    row['undeclared_data'] = sorted(set(row['data_reads']) - declared - uploaded_fields)
    return row


def build_inventory(tools_by_slug=None):
    if tools_by_slug is None:
        from content.views.mcp_blog import TOOLS_BY_SLUG
        tools_by_slug = TOOLS_BY_SLUG
    definitions = _bridge_definitions()
    return [inventory_tool(slug, tool, definitions=definitions)
            for slug in CONNECTORS for tool in tools_by_slug[slug]]


def schema_drift(inventory):
    """Compare known explicit reads, retaining documented Panel-only exclusions."""
    return {
        (row['connector'], row['name'], channel, name)
        for row in inventory if row['explicit_bridge'] and not row['opaque'] and not row['excluded']
        for channel in ('query', 'data') for name in row[f'undeclared_{channel}']
        if not row.get('panel_only_fields', {}).get(name, '').strip()
    }


def _cell(value):
    if value in (None, [], {}):
        return '—'
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text.replace('|', '\\|').replace('\n', ' ')


def render_inventory(inventory):
    """Generate the measured portion of the Spanish audit deterministically."""
    lines = ['## Inventario generado', '',
             ('Fuente: `content.views.mcp_blog.TOOLS_BY_SLUG`; rutas resueltas con IDs de ejemplo. '
              'No se ejecutan vistas, validaciones, servicios ni consultas de relaciones.'), '',
             '| Conector | Total | Raíz abierta | Fallan política completa | Excluidas (#503) | Aliases internos |',
             '|---|---:|---:|---:|---:|---:|']
    for connector in CONNECTORS:
        rows = [row for row in inventory if row['connector'] == connector]
        lines.append(f'| {connector} | {len(rows)} | '
                     f'{sum(row["input_schema"].get("additionalProperties") is not False for row in rows)} | '
                     f'{sum(bool(row["schema_problems"]) for row in rows)} | '
                     f'{sum(row["excluded"] for row in rows)} | '
                     f'{sum(row["has_accepted_arguments_schema"] for row in rows)} |')
    failures = [row for row in inventory if row['schema_problems'] and not row['excluded']]
    families = Counter(row['family'] for row in failures)
    lines += ['', '| Familia de ola 2 | Pendientes de política completa |', '|---|---:|']
    lines += [f'| {family} | {families[family]} |' for family in ('documents-bridge', 'projects-bridge', 'natives')]
    lines += ['', ('«generic» = raíz abierta; «aliases» = raíz cerrada con `data`/`query` publicado; '
                   '«partially typed» = raíz plana y cerrada que aún falla otra regla. '
                   'Los aliases de aceptación internos se cuentan aparte.'), '',
              ('Las lecturas incluyen campos **escribibles** del serializer; la columna de campos conserva '
               'también los de sólo lectura. `opaque` evita certificar un conjunto de lecturas incompleto. '
               'Una ausencia de declaración plana en un adaptador genérico puede estar admitida por su envelope.'), '']
    for family in ('documents-bridge', 'projects-bridge', 'natives'):
        lines += [f'### {family}', '',
                  '| Conector · herramienta | Módulo / origen del esquema | Método · ruta · vista | Query | Data | Serializer y campos | Estado · aliases | Especiales / límites |',
                  '|---|---|---|---|---|---|---|---|']
        for row in sorted((item for item in failures if item['family'] == family), key=lambda item: (item['connector'], item['name'])):
            special = []
            if row['requires_confirmation']:
                special.append('confirm_action')
            if row['asset_fields'] or row['files_reads']:
                special.append({'archivos': row['asset_fields'] or row['files_reads']})
            if row['undeclared_query'] or row['undeclared_data']:
                special.append({'sin_declaración_plana': {'query': row['undeclared_query'], 'data': row['undeclared_data']}})
            if row['opaque']:
                special.append({'opaque': row['opaque']})
            special.append({'problemas': row['schema_problems']})
            module = row['module'] if row['module'] == row['schema_module'] else f'{row["module"]} / {row["schema_module"]}'
            route = f'{row["method"]} {row["path"]} → {row["view"]}' if row['method'] else 'Nativa; sin puente Panel'
            cells = [f'{row["connector"]} · `{row["name"]}`', module, route,
                     row['query_reads'], row['data_reads'], row['serializers'],
                     {'estado': row['schema_state'], 'aliases_internos': row['aliases'],
                      'campos_publicados': sorted(row['input_schema'].get('properties', {})),
                      'requeridos': row['input_schema'].get('required', [])}, special]
            lines.append('| ' + ' | '.join(_cell(value) for value in cells) + ' |')
    lines += ['', '### Exclusiones de propiedad', '',
              '| Conector · herramienta | Módulo | Método · ruta · vista | Query | Data | Serializer | Estado | Motivo |',
              '|---|---|---|---|---|---|---|---|']
    for row in inventory:
        if row['excluded']:
            cells = [f'{row["connector"]} · `{row["name"]}`', row['module'],
                     f'{row["method"]} {row["path"]} → {row["view"]}', row['query_reads'],
                     row['data_reads'], row['serializers'], row['schema_state'], 'owned by PR #503']
            lines.append('| ' + ' | '.join(_cell(value) for value in cells) + ' |')
    lines += ['', '### Deriva medible actual', '', '| Conector | Herramienta | Canal | Campo ausente |', '|---|---|---|---|']
    lines += [f'| {slug} | `{name}` | {channel} | `{key}` |' for slug, name, channel, key in sorted(schema_drift(inventory))]
    lines += ['', ('Los adaptadores opacos quedan visibles arriba; no se cuentan como deriva certificada. '
                   'Resolverlos o ampliar el análisis puede revelar campos adicionales.'), '']
    return '\n'.join(lines)


if __name__ == '__main__':
    # Run only with explicitly selected isolated settings, never manage.py/.env.
    from django.conf import settings
    if not settings.configured:
        raise SystemExit('Initialize Django with projectapp.settings_test before running the inventory.')
    if settings.SETTINGS_MODULE != 'projectapp.settings_test':
        raise SystemExit('The inventory requires projectapp.settings_test.')
    print(render_inventory(build_inventory()))
