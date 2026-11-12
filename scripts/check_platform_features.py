#!/usr/bin/env python3
"""Static inventory gate: no Django, runtime, credentials or database required."""
import argparse
import ast
import json
from pathlib import Path
import re


API_FILES = (
    'accounts/urls.py', 'accounts/project_collaboration_urls.py', 'accounts/delivery_urls.py',
    'accounts/billing_urls.py', 'accounts/issue_report_urls.py', 'secure_links/platform_urls.py',
    'accounts/ai_urls.py', 'accounts/appi_urls.py', 'accounts/platform_help_urls.py',
    'accounts/feature_flags_urls.py',
)


def normalized(route):
    return re.sub(r':[^/]+', ':param', route)


def audit(catalog, pages, api_names, capabilities):
    problems = []
    keys, routes, apis, mapped_capabilities = set(), {}, {}, set()
    for feature in catalog['features']:
        key = feature['key']
        if key in keys:
            problems.append(f'Clave duplicada: {key}')
        keys.add(key)
        if feature['default_enabled'] is key.startswith('platform.ai_'):
            problems.append(f'Valor inicial incompatible con PA-263: {key}')
        for route in feature['routes']:
            route = normalized(route)
            if route in routes:
                problems.append(f'Ruta controlada dos veces: {route}')
            routes[route] = key
        for name in feature['api_routes']:
            if name in apis:
                problems.append(f'API controlada dos veces: {name}')
            apis[name] = key
        mapped_capabilities.update(feature['capabilities'])
        if not feature['routes'] and not feature.get('surfaces'):
            problems.append(f'Falta superficie visible: {key}')
    route_exemptions = {normalized(route) for route in catalog['route_exemptions']}
    problems.extend(f'Vista sin flag ni exclusión: {route}' for route in sorted(set(pages) - routes.keys() - route_exemptions))
    problems.extend(f'Ruta sin página real: {route}' for route in sorted(routes.keys() - set(pages)))
    classified = set(apis) | set(catalog['api_exemptions']) | set(catalog['api_dynamic'])
    problems.extend(f'API sin clasificación: {name}' for name in sorted(set(api_names) - classified))
    problems.extend(f'API declarada inexistente: {name}' for name in sorted(set(apis) - set(api_names)))
    problems.extend(f'Capacidad sin flag ni exclusión: {name}' for name in sorted(
        set(capabilities) - mapped_capabilities - set(catalog['capability_exemptions'])))
    problems.extend(f'Capacidad declarada inexistente: {name}' for name in sorted(mapped_capabilities - set(capabilities)))
    return problems


def inventory(root):
    pages = []
    for path in (root / 'frontend/pages/platform').rglob('*.vue'):
        name = '/platform/' + str(path.relative_to(root / 'frontend/pages/platform').with_suffix(''))
        name = re.sub(r'\[([^\]]+)\]', r':\1', name).removesuffix('/index')
        pages.append(normalized(name))
    names = {'platform-help-videos'}
    for filename in API_FILES:
        tree = ast.parse((root / 'backend' / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'path':
                names.update(kw.value.value for kw in node.keywords if kw.arg == 'name' and isinstance(kw.value, ast.Constant))
    source = (root / 'frontend/config/viewCapabilityCatalog.js').read_text().split('const platformCapabilities = [', 1)[1].split('const public', 1)[0]
    capabilities = re.findall(r"feature\('([^']+)'", source)
    return pages, names, capabilities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    catalog = json.loads((args.root / 'contracts/platform-features.json').read_text())
    problems = audit(catalog, *inventory(args.root))
    print(json.dumps({'ok': not problems, 'problems': problems}, ensure_ascii=False, indent=2))
    return bool(problems)


if __name__ == '__main__':
    raise SystemExit(main())

