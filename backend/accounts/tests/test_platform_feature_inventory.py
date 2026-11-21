"""The delivery gate must detect a real missing mapping."""
from copy import deepcopy
import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('feature_inventory', ROOT / 'scripts/check_platform_features.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def test_current_capabilities_have_an_explicit_policy():
    catalog = json.loads((ROOT / 'contracts/platform-features.json').read_text())

    assert inventory.audit(catalog, *inventory.inventory(ROOT)) == []


def test_new_unmapped_route_is_reported():
    catalog = json.loads((ROOT / 'contracts/platform-features.json').read_text())
    pages, apis, capabilities = inventory.inventory(ROOT)

    result = inventory.audit(catalog, [*pages, '/platform/new-feature'], apis, capabilities)

    assert 'Vista sin flag ni exclusión: /platform/new-feature' in result


def test_duplicate_control_is_reported():
    catalog = json.loads((ROOT / 'contracts/platform-features.json').read_text())
    candidate = deepcopy(catalog)
    candidate['features'][0]['routes'].append('/platform/documents')

    result = inventory.audit(candidate, *inventory.inventory(ROOT))

    assert 'Ruta controlada dos veces: /platform/documents' in result


def test_new_endpoint_requires_a_policy():
    catalog = json.loads((ROOT / 'contracts/platform-features.json').read_text())
    pages, apis, capabilities = inventory.inventory(ROOT)

    result = inventory.audit(catalog, pages, apis | {'platform-new-operation'}, capabilities)

    assert 'API sin clasificación: platform-new-operation' in result


def test_generated_endpoint_names_are_inventoried():
    source = "for kind in ('contracts', 'scopes'):\n    urlpatterns += [path('node/', view, name=f'delivery-{kind}-detail')]"

    names = inventory.path_names(ast.parse(source).body)

    assert names == {'delivery-contracts-detail', 'delivery-scopes-detail'}


@pytest.mark.parametrize('key', ['platform.example', 'platform.ai_example'])
def test_new_mapped_feature_requires_enabled_default(key):
    feature = {'key': key, 'routes': ['/platform/example'], 'api_routes': ['example'],
               'targets': ['example'], 'capabilities': ['example'], 'default_enabled': True}
    catalog = {'features': [feature], 'route_exemptions': [], 'api_exemptions': [],
               'api_dynamic': {}, 'capability_exemptions': []}
    surfaces = (['/platform/example'], {'example'}, ['example'])

    assert inventory.audit(catalog, *surfaces) == []
    feature['default_enabled'] = False
    assert inventory.audit(catalog, *surfaces) == [f'Valor inicial incompatible con PA-263: {key}']


def test_route_in_new_nested_urlconf_is_discovered(tmp_path):
    (tmp_path / 'projectapp').mkdir()
    (tmp_path / 'projectapp/urls.py').write_text("urlpatterns = [path('api/platform/v2/', include('v2'))]")
    (tmp_path / 'v2.py').write_text("urlpatterns = [path('extras/', include('extras'))]")
    (tmp_path / 'extras.py').write_text("urlpatterns = [path('draft/', view, name='draft')]")

    assert inventory.mounted_api_names(tmp_path) == {'draft'}


@pytest.mark.parametrize(('field', 'label'), [('capabilities', 'Capacidad'), ('targets', 'Destino')])
def test_duplicate_feature_binding_is_identified(field, label):
    catalog = json.loads((ROOT / 'contracts/platform-features.json').read_text())
    name = catalog['features'][0][field][0]
    catalog['features'][1][field].append(name)

    assert inventory.audit(catalog, *inventory.inventory(ROOT)) == [f'{label} con control duplicado: {name}']
