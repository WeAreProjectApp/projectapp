"""Reproducible surface/tool matrix and fail-closed functional-evidence checks.

No handler is executed and no business data is read. Static mappings remain
unverified until an independent functional run fills the evidence columns.
"""
import hashlib
import inspect
import json
import re
import subprocess
from functools import partial
from pathlib import Path

from django.conf import settings
from django.urls import get_resolver, resolve, reverse

from content.mcp.connectors import CONNECTORS, TOOLS_BY_SLUG
from content.mcp.contract_report import fingerprint
from content.mcp.module_catalog import INFRASTRUCTURE_TOOLS
from content.mcp.presentation import connector_name
from content.mcp.surface_catalog import assignment, feature_tools
from content.services.data_integrity.hashing import digest

ROOT = Path(settings.BASE_DIR).parent
MANIFEST = ROOT / 'docs/audits/PA-221/surfaces.json'
HEX40 = re.compile(r'^[0-9a-f]{40}$')


class CoverageError(ValueError):
    pass


def revision():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        raise CoverageError('No se pudo identificar la revisión de código.') from None


def tracked_tree_clean():
    result = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=ROOT, check=False)
    return result.returncode == 0


def surface_manifest():
    manifest = json.loads(MANIFEST.read_text())
    for path, expected in manifest['sources'].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise CoverageError('El inventario de superficies está desactualizado; regenera surfaces.json.')
    return [{**surface, **assignment(surface)} for surface in manifest['surfaces']]


def _source(tool):
    operation = tool.get('_panel_operation')
    if operation:
        definitions = get_resolver().reverse_dict.getlist(operation['route_name'])
        converters = definitions[0][3] if definitions else {}
        examples = {'UUIDConverter': '00000000-0000-4000-8000-000000000001', 'IntConverter': 1}
        values = {key: examples.get(type(converters.get(key)).__name__, 'sample') for key in operation['path_params']}
        callback = resolve(reverse(operation['route_name'], kwargs=values)).func
        permissions = [permission.__name__ for permission in callback.cls.permission_classes]
        return {'route': operation['route_name'], 'method': operation['method'],
                'permissions': permissions, 'source': 'backend/' + callback.__module__.replace('.', '/') + '.py'}
    handler = inspect.unwrap(tool['handler'])
    while isinstance(handler, partial):
        handler = inspect.unwrap(handler.func)
    source = inspect.getsourcefile(handler)
    path = Path(source) if source else None
    return {'route': None, 'method': None, 'permissions': ['Actor técnico, alcance de la credencial y guardas del dominio'],
            'source': str(path.relative_to(ROOT)) if path and path.is_relative_to(ROOT) else handler.__module__}


def build_matrix():
    surfaces = surface_manifest()
    for surface in surfaces:
        if surface['result'] != 'exempt':
            actions = surface['features'] or [{'id': surface['id'], 'summary': surface.get('description', '')}]
            names = [tool['name'] for tool in TOOLS_BY_SLUG.get(surface.get('connector'), [])
                     if tool['name'] not in INFRASTRUCTURE_TOOLS]
            surface['feature_checks'] = [
                {'id': feature['id'], 'action': feature['summary'], 'result': 'mapped_unverified',
                 'candidate_tools': [f"{surface['connector']}:{name}" for name in feature_tools(feature['id'], names)],
                 'checks': [], 'evidence': []} for feature in actions
            ]
            if any(not feature['candidate_tools'] for feature in surface['feature_checks']):
                surface['result'] = 'gap'
    rows = []
    contracts = {}
    for slug, spec in sorted(CONNECTORS.items()):
        if spec.compatibility:
            continue
        contracts[slug] = fingerprint(slug)
        views = [row['id'] for row in surfaces if row.get('connector') == slug]
        for tool in TOOLS_BY_SLUG[slug]:
            if tool['name'] in INFRASTRUCTURE_TOOLS or tool.get('_hidden'):
                continue
            rows.append({
                'id': f"{slug}:{tool['name']}", 'connector': slug, 'manager': connector_name(slug),
                'tool': tool['name'], 'action': tool['description'], 'candidate_view_ids': views, 'view_ids': [],
                'surface': sorted({row['surface'] for row in surfaces if row['id'] in views}),
                'risk': tool['risk'], 'requires_confirmation': bool(tool.get('requires_confirmation')),
                **_source(tool), 'result': 'mapped_unverified', 'tested_role': '',
                'evidence': [], 'permission_evidence': [], 'confirmation_evidence': [],
            })
    basis = {'surfaces': surfaces, 'rows': rows, 'contracts': contracts}
    return {'schema': 1, 'revision': revision(), 'tracked_tree_clean': tracked_tree_clean(),
            'matrix_fingerprint': digest(basis), **basis}


def _references(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and bool(item.strip()) and len(item) <= 1000
        and (re.fullmatch(r'https://github\.com/WeAreProjectApp/projectapp/actions/runs/[0-9]+(?:/artifacts/[0-9]+)?/?', item)
             or (re.fullmatch(r'docs/audits/[A-Za-z0-9_./-]+\.(?:json|md|csv|xml|png|jpg)', item)
                 and '..' not in Path(item).parts and (ROOT / item).is_file()
                 and not (ROOT / item).is_symlink()
                 and (ROOT / item).resolve().is_relative_to(ROOT / 'docs/audits')))
        for item in value)


def validate_report(report):
    """Validate exact current metadata; a static inventory cannot authorize retirement."""
    current = build_matrix()
    if (not isinstance(report, dict) or report.get('schema') != 1
            or not HEX40.fullmatch(str(report.get('revision', '')))
            or report['revision'] != current['revision']
            or report.get('tracked_tree_clean') is not True or not current['tracked_tree_clean']
            or report.get('matrix_fingerprint') != current['matrix_fingerprint']
            or report.get('contracts') != current['contracts']):
        raise CoverageError('La evidencia no corresponde a la revisión y al catálogo actuales.')
    rows = report.get('rows', [])
    if not isinstance(rows, list) or len(rows) != len(current['rows']):
        raise CoverageError('La matriz no contiene todas las operaciones actuales.')
    by_id = {row.get('id'): row for row in rows if isinstance(row, dict)}
    if len(by_id) != len(rows):
        raise CoverageError('La matriz contiene operaciones duplicadas o inválidas.')
    for expected in current['rows']:
        row = by_id.get(expected['id'], {})
        metadata = {key: value for key, value in expected.items() if key not in {
            'result', 'tested_role', 'evidence', 'permission_evidence', 'confirmation_evidence', 'view_ids',
        }}
        if (any(row.get(key) != value for key, value in metadata.items())
                or row.get('result') != 'mapped_verified'
                or not isinstance(row.get('tested_role'), str) or not row['tested_role'].strip()
                or not isinstance(row.get('view_ids'), list) or not row['view_ids']
                or any(view not in expected['candidate_view_ids'] for view in row['view_ids'])
                or not _references(row.get('evidence')) or not _references(row.get('permission_evidence'))
                or (expected['requires_confirmation'] and not _references(row.get('confirmation_evidence')))):
            raise CoverageError('Hay operaciones sin comprobación funcional, permisos o confirmación vigente.')
    surfaces = report.get('surfaces', [])
    if not isinstance(surfaces, list) or len(surfaces) != len(current['surfaces']):
        raise CoverageError('La matriz no contiene todas las superficies actuales.')
    by_surface = {row.get('id'): row for row in surfaces if isinstance(row, dict)}
    if len(by_surface) != len(surfaces):
        raise CoverageError('La matriz contiene superficies duplicadas o inválidas.')
    for expected in current['surfaces']:
        surface = by_surface.get(expected['id'], {})
        if any(surface.get(key) != value for key, value in expected.items() if key not in {'result', 'feature_checks'}):
            raise CoverageError('El inventario de funciones o sus excepciones fue alterado.')
        if expected['result'] == 'exempt':
            if surface.get('result') != 'exempt':
                raise CoverageError('Las excepciones de identidad deben permanecer explícitas.')
        elif (expected['result'] == 'gap' or surface.get('result') != 'mapped_verified'
              or not _references(surface.get('evidence'))
              or not surface.get('checks') or any(
                  check not in by_id or surface['id'] not in by_id[check]['view_ids']
                  for check in surface.get('checks', []))):
            raise CoverageError('Hay vistas o funcionalidades sin cotejo funcional en su gestor.')
        else:
            features = surface.get('feature_checks', [])
            if not isinstance(features, list) or len(features) != len(expected.get('feature_checks', [])):
                raise CoverageError('Falta el cotejo de funcionalidades de una vista.')
            by_feature = {feature.get('id'): feature for feature in features if isinstance(feature, dict)}
            if len(by_feature) != len(features):
                raise CoverageError('Hay funcionalidades duplicadas o inválidas.')
            for baseline in expected.get('feature_checks', []):
                feature = by_feature.get(baseline['id'], {})
                if (feature.get('action') != baseline['action'] or feature.get('result') != 'mapped_verified'
                        or feature.get('candidate_tools') != baseline['candidate_tools']
                        or not _references(feature.get('evidence')) or not feature.get('checks')
                        or any(check not in baseline['candidate_tools'] or check not in by_id
                               or surface['id'] not in by_id[check]['view_ids']
                               for check in feature.get('checks', []))):
                    raise CoverageError('Hay funcionalidades sin acciones comprobadas en su vista.')
    return current


def load_verified_report(path):
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 16 * 1024 * 1024:
        raise CoverageError('Indica un archivo JSON regular de evidencia de hasta 16 MiB.')
    if any(part.startswith('.env') or part == 'credentials' for part in source.resolve().parts):
        raise CoverageError('La evidencia no se lee desde archivos de credenciales.')
    try:
        raw = source.read_bytes()
        report = json.loads(raw)
        validate_report(report)
    except (OSError, ValueError, KeyError, TypeError):
        raise CoverageError('La evidencia está incompleta, desactualizada o no acredita las comprobaciones requeridas.') from None
    return {'schema': 1, 'report_sha256': hashlib.sha256(raw).hexdigest(),
            'report_path': str(source.resolve()),
            'revision': report['revision'], 'matrix_fingerprint': report['matrix_fingerprint'],
            'contracts': report['contracts'], 'operations': len(report['rows']), 'surfaces': len(report['surfaces'])}


def coverage_current(connector, catalog):
    if not isinstance(connector.retirement_evidence, dict):
        return False
    entries = connector.retirement_evidence.get(catalog, [])
    if not isinstance(entries, list) or not entries or not isinstance(entries[-1], dict):
        return False
    current = build_matrix()
    latest = entries[-1]
    return (latest.get('schema') == 1 and latest.get('revision') == current['revision']
            and current['tracked_tree_clean']
            and isinstance(latest.get('report_sha256'), str)
            and re.fullmatch(r'[0-9a-f]{64}', latest['report_sha256']) is not None
            and latest.get('matrix_fingerprint') == current['matrix_fingerprint']
            and latest.get('contracts') == current['contracts'])
