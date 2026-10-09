"""Public bilingual payload, downloadable booklet and read-only administration."""
import json
import re
from copy import deepcopy
from io import BytesIO
from urllib.parse import unquote

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from content.services.building_with_us_content import FIGURES_PATTERN, SECTION_KEYS

pytestmark = pytest.mark.django_db
PANEL_PATHS = ['/api/building-with-us/admin/', '/api/building-with-us/admin/program/versions/']


@pytest.mark.parametrize(('lang', 'title', 'canonical_path'), [
    ('es', 'Construye con nosotros. Construimos para ti.', '/es-co/building-with-us'),
    ('en', 'Build with us. We build for you.', '/en-us/building-with-us'),
])
def test_public_payload_is_localized(building_with_us_program, lang, title, canonical_path):
    """Fails if public content drifts from the canonical order or leaks restricted fields."""
    response = APIClient().get('/api/building-with-us/public/', {'lang': lang})
    payload = deepcopy(response.data)
    whatsapp_url = payload['cta'].pop('whatsapp_url')

    assert response.status_code == 200
    assert list(payload)[:len(SECTION_KEYS)] == list(SECTION_KEYS)
    assert payload['hero']['title'] == title
    assert payload['canonical_path'] == canonical_path
    assert unquote(whatsapp_url).endswith(building_with_us_program.current_revision.content[lang]['cta']['whatsapp_message'])
    assert 'video' not in json.dumps(payload).lower()
    assert re.search(FIGURES_PATTERN, json.dumps(payload, ensure_ascii=False), re.IGNORECASE) is None


def test_public_payload_rejects_an_invalid_language():
    """Fails if an unsupported locale silently returns a different language."""
    response = APIClient().get('/api/building-with-us/public/', {'lang': 'fr'})

    assert response.status_code == 400
    assert response.data == {'lang': ['Usa es o en.']}


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_public_pdf_contains_the_current_hero(building_with_us_program, lang):
    """Fails if the download is not a PDF of the localized current presentation."""
    response = APIClient().get('/api/building-with-us/public/pdf/', {'lang': lang})
    text = ' '.join(' '.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages).split())

    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')
    assert building_with_us_program.current_revision.content[lang]['hero']['title'] in text
    assert response['Content-Disposition'] == f'attachment; filename="building-with-us-{lang}.pdf"'
    assert response['Cache-Control'] == 'private, no-store'


def test_sitemap_exposes_both_presentation_locales():
    """Fails if the public alliance page cannot be discovered in either language."""
    response = APIClient().get('/sitemap.xml')
    xml = response.content.decode()

    assert response.status_code == 200
    assert '<loc>https://projectapp.co/es-co/building-with-us</loc>' in xml
    assert '<loc>https://projectapp.co/en-us/building-with-us</loc>' in xml


@pytest.mark.parametrize('path', PANEL_PATHS)
def test_panel_rejects_non_admin_users(path, django_user_model):
    """Fails if ordinary users can read private presentation history."""
    client = APIClient()
    client.force_authenticate(user=django_user_model.objects.create_user(username='bwu-reader'))

    response = client.get(path)

    assert response.status_code == 403


@pytest.mark.parametrize('path', PANEL_PATHS)
@pytest.mark.parametrize('method', ['post', 'patch', 'delete'])
def test_panel_rejects_mutations(admin_client, path, method):
    """Fails if the read-only Panel becomes an alternate presentation writer."""
    response = getattr(admin_client, method)(path, {}, format='json')

    assert response.status_code == 405


def test_overview_returns_program_metadata(building_with_us_program, admin_client):
    """Fails if administration cannot inspect the seeded program and connector state."""
    response = admin_client.get(PANEL_PATHS[0])

    assert response.status_code == 200
    assert response.data['program']['version'] == 1
    assert response.data['program']['author'] == 'Sistema'
    assert response.data['contract'] is None
    assert response.data['connector'] == {'slug': 'building-with-us', 'is_active': False}
    assert response.data['public_paths'] == {'es': '/es-co/building-with-us', 'en': '/en-us/building-with-us'}


def test_versions_returns_paginated_metadata(changed_building_with_us_program, admin_client):
    """Fails if the read-only history omits provenance or exposes full content by default."""
    from content.models import BuildingWithUsProgramRevision

    initial = BuildingWithUsProgramRevision.objects.get(pk=changed_building_with_us_program['version_id'])
    response = admin_client.get(PANEL_PATHS[1], {'limit': 1, 'offset': 1})

    assert response.status_code == 200
    assert response.data['total'] == 2
    assert response.data['versions'] == [{
        'version_id': changed_building_with_us_program['version_id'], 'version': 1, 'author': 'Sistema',
        'created_at': initial.created_at.isoformat(),
        'change_note': changed_building_with_us_program['change_note'], 'restored_from_version_id': None,
    }]
