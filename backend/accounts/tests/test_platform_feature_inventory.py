"""The delivery gate must detect a real missing mapping."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

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
