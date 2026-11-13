"""Versioned capability inventory shared with the Nuxt route/navigation policy."""
import json
from pathlib import Path


CATALOG = json.loads((Path(__file__).resolve().parents[2] / 'contracts/platform-features.json').read_text())
FEATURES = {item['key']: item for item in CATALOG['features']}
API_FEATURES = {name: item['key'] for item in FEATURES.values() for name in item['api_routes']}
TARGET_FEATURES = {name: item['key'] for item in FEATURES.values() for name in item['targets']}

