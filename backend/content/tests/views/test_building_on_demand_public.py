"""Localized public Building on Demand routes, discovery and bounded reads."""
import json
import re
from copy import deepcopy
from urllib.parse import unquote
from xml.etree import ElementTree

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from content.models import BuildingOnDemandProgramRevision, ExplainerVideoSettings

pytestmark = pytest.mark.django_db
PUBLIC_PATHS = ['/api/building-on-demand/public/', '/api/building-on-demand/public/pdf/']


@pytest.mark.parametrize(('lang', 'canonical', 'alternate'), [
    ('es', '/es-co/building-on-demand', '/en-us/building-on-demand'),
    ('en', '/en-us/building-on-demand', '/es-co/building-on-demand'),
])
def test_public_payload_is_localized(building_on_demand_program, lang, canonical, alternate):
    """Fails if the public sales presentation loses its locale or exposes private costs."""
    response = APIClient().get(PUBLIC_PATHS[0], {'lang': lang})
    payload = response.data
    text = building_on_demand_program.current_revision.content[lang]

    assert response.status_code == 200
    assert payload['hero'] == text['hero']
    assert (payload['language'], payload['canonical_path'], payload['alternate_path']) == (lang, canonical, alternate)
    assert payload['pdf_path'] == f'/api/building-on-demand/public/pdf/?lang={lang}'
    assert unquote(payload['cta']['whatsapp_url']).endswith(text['cta']['whatsapp_message'])
    assert response['Cache-Control'] == 'no-store'
    assert re.search(r'"internal"|55000|Hostinger|KVM', json.dumps(payload)) is None


def test_public_payload_exposes_the_default_explainer(building_on_demand_program):
    """Fails if the visible Scrum explainer lacks its default resource descriptor."""
    response = APIClient().get(PUBLIC_PATHS[0], {'lang': 'es'})

    assert response.status_code == 200
    assert response.data['show_explainer_video'] is True
    assert response.data['explainer_video'] == {'mode': 'default', 'video': None}


def test_public_payload_hides_the_explainer_when_its_switch_is_off(building_on_demand_program):
    """Fails if the public Scrum page exposes an explainer that staff hid."""
    settings = ExplainerVideoSettings.load()
    settings.show_building_on_demand_video = False
    settings.save(update_fields=['show_building_on_demand_video', 'updated_at'])

    response = APIClient().get(PUBLIC_PATHS[0], {'lang': 'es'})

    assert response.status_code == 200
    assert response.data['show_explainer_video'] is False


def test_public_payload_reports_a_removed_spanish_explainer(admin_client, building_on_demand_program):
    """Fails if removing the Scrum explainer silently restores its default video."""
    removed = admin_client.post(
        '/api/video-resources/admin/modules/building-on-demand/es/',
        {'action': 'remove', 'revision': 0},
        format='json',
    )

    response = APIClient().get(PUBLIC_PATHS[0], {'lang': 'es'})

    assert removed.status_code == 200
    assert removed.data['mode'] == 'none'
    assert response.status_code == 200
    assert response.data['explainer_video'] == {'mode': 'none', 'video': None}


def test_public_payload_defaults_to_spanish(building_on_demand_program):
    """Fails if opening the default public URL renders the English program."""
    response = APIClient().get(PUBLIC_PATHS[0])

    assert response.status_code == 200
    assert response.data['language'] == 'es'
    assert response.data['tiers']['items'][0]['bag_hours'] == 96


@pytest.mark.parametrize('path', PUBLIC_PATHS)
def test_public_endpoint_rejects_an_invalid_language(path):
    """Fails if an unsupported language silently falls back in JSON or a download."""
    response = APIClient().get(path, {'lang': 'fr'})

    assert response.status_code == 400
    assert response.data == {'lang': ['Usa es o en.']}


@pytest.mark.parametrize('path', PUBLIC_PATHS)
def test_public_endpoint_ignores_unrelated_credentials(building_on_demand_program, path):
    """Fails if a stale authentication header prevents an anonymous public read."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Bearer invalid-public-token')

    response = client.get(path)

    assert response.status_code == 200
    assert response['Cache-Control'].endswith('no-store')


@pytest.mark.parametrize('path', PUBLIC_PATHS)
def test_public_endpoint_rejects_post(building_on_demand_program, path):
    """Fails if a public presentation endpoint becomes a writer."""
    response = APIClient().post(path, {}, format='json')

    assert response.status_code == 405
    assert BuildingOnDemandProgramRevision.objects.count() == 1


@pytest.mark.parametrize(('locale', 'alternate'), [('es-co', 'en-us'), ('en-us', 'es-co')])
def test_sitemap_exposes_a_localized_program(locale, alternate):
    """Fails if a public program locale is missing its discoverable alternate."""
    response = APIClient().get('/sitemap.xml')
    document = ElementTree.fromstring(response.content)
    namespaces = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'xh': 'http://www.w3.org/1999/xhtml'}
    entry = document.find(f"sm:url[sm:loc='https://projectapp.co/{locale}/building-on-demand']", namespaces)

    assert response.status_code == 200
    assert entry.find('sm:changefreq', namespaces).text == 'monthly'
    assert entry.find('sm:priority', namespaces).text == '0.8'
    assert entry.find(f"xh:link[@hreflang='{alternate}']", namespaces).attrib['href'] == (
        f'https://projectapp.co/{alternate}/building-on-demand'
    )


def test_public_query_count_stays_constant(building_on_demand_program, building_on_demand_content):
    """Fails if a growing revision history causes extra queries for a public read."""
    client = APIClient()
    client.get(PUBLIC_PATHS[0])
    with CaptureQueriesContext(connection) as first_reads:
        first = client.get(PUBLIC_PATHS[0])
    revision = BuildingOnDemandProgramRevision.objects.create(
        version=2, content=deepcopy(building_on_demand_content), change_note='Historial adicional de prueba.',
    )
    building_on_demand_program.current_revision = revision
    building_on_demand_program.save(update_fields=['current_revision', 'updated_at'])

    with CaptureQueriesContext(connection) as later_reads:
        later = client.get(PUBLIC_PATHS[0])

    assert (first.status_code, later.status_code) == (200, 200)
    assert (first.data['version'], later.data['version']) == (1, 2)
    # Program/revision, live visibility, and the localized video resource stay fixed per read.
    assert len(first_reads) == len(later_reads) == 3
