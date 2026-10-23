"""Public Consulting brochure, PDF and protected administration endpoints."""
from io import BytesIO
from urllib.parse import unquote

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from content.models import ConsultingProgramRevision
from content.tests.consulting_fixtures import changed_consulting_program, consulting_program

pytestmark = pytest.mark.django_db
PUBLIC_PATHS = ['/api/consulting/public/', '/api/consulting/public/pdf/']
PANEL_PATHS = ['/api/consulting/admin/', '/api/consulting/admin/program/versions/']


@pytest.mark.parametrize(('lang', 'title', 'canonical_path'), [
    ('es', 'Una empresa más saludable. Tiempo y dinero mejor aprovechados.', '/es-co/consulting'),
    ('en', 'A healthier business. Better use of time and money.', '/en-us/consulting'),
])
def test_public_program_returns_the_localized_business_health_message(lang, title, canonical_path):
    """Fails if a public locale loses its health message or routes to the other language's brochure."""
    response = APIClient().get('/api/consulting/public/', {'lang': lang})

    assert response.status_code == 200
    assert response.data['hero']['title'] == title
    assert response.data['canonical_path'] == canonical_path
    assert response.data['pdf_path'] == f'/api/consulting/public/pdf/?lang={lang}'


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_public_program_exposes_only_the_customer_projection(consulting_program, lang):
    """Fails if public copy loses its core offer, conversion URL, or leaks editorial provenance."""
    response = APIClient().get('/api/consulting/public/', {'lang': lang})

    assert response.status_code == 200
    assert (len(response.data['areas']['items']), len(response.data['impact']['items'])) == (5, 6)
    assert unquote(response.data['cta']['whatsapp_url']).endswith(
        consulting_program.current_revision.content[lang]['cta']['whatsapp_message']
    )
    assert {'content', 'author', 'change_note', 'etag'}.isdisjoint(response.data)
    assert response['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('path', PUBLIC_PATHS)
def test_public_endpoints_reject_unsupported_languages(path):
    """Fails if a typo in the locale silently serves a different brochure or PDF."""
    response = APIClient().get(path, {'lang': 'fr'})

    assert response.status_code == 400
    assert response.data == {'lang': ['Usa es o en.']}


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_public_pdf_contains_the_current_localized_hero(consulting_program, lang):
    """Fails if the download is not the current localized Consulting presentation."""
    response = APIClient().get('/api/consulting/public/pdf/', {'lang': lang})
    text = ' '.join(' '.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages).split())

    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')
    assert consulting_program.current_revision.content[lang]['hero']['title'] in text
    assert response['Content-Disposition'] == f'attachment; filename="consulting-{lang}.pdf"'
    assert response['Cache-Control'] == 'private, no-store'


@pytest.mark.parametrize('path', PANEL_PATHS)
def test_panel_endpoints_require_an_administrator(path, django_user_model):
    """Fails if ordinary users can inspect private editorial provenance or connector status."""
    client = APIClient()
    client.force_authenticate(user=django_user_model.objects.create_user(username='consulting-reader'))

    response = client.get(path)

    assert response.status_code == 403


@pytest.mark.parametrize('path', PANEL_PATHS)
def test_anonymous_visitors_cannot_read_private_panel_metadata(path, api_client):
    """Fails if anonymous visitors can read Consulting provenance through a Panel route."""
    response = api_client.get(path)

    assert response.status_code == 403


def test_admin_overview_returns_seed_provenance_and_commercial_connector(consulting_program, admin_client):
    """Fails if the Panel cannot identify the seeded program or its Commercial publishing path."""
    response = admin_client.get('/api/consulting/admin/')

    assert response.status_code == 200
    assert response.data['program']['version'] == 1
    assert response.data['program']['author'] == 'Sistema'
    assert response.data['connector']['slug'] == 'commercial'
    assert response.data['public_paths'] == {'es': '/es-co/consulting', 'en': '/en-us/consulting'}


def test_admin_history_pages_metadata_without_exposing_full_content(changed_consulting_program, admin_client):
    """Fails if history pagination returns the wrong revision or leaks editable bilingual copy by default."""
    seed = ConsultingProgramRevision.objects.get(pk=changed_consulting_program['version_id'])
    response = admin_client.get('/api/consulting/admin/program/versions/', {'limit': 1, 'offset': 1})

    assert response.status_code == 200
    assert response.data['total'] == 2
    assert response.data['versions'] == [{
        'version_id': seed.pk, 'version': 1, 'author': 'Sistema',
        'created_at': seed.created_at.isoformat(),
        'change_note': 'Presentación inicial de Consultoría y asesoría.',
        'restored_from_version_id': None, 'restored_from_version': None,
    }]


@pytest.mark.parametrize('query', [{'limit': 'invalid'}, {'offset': 'invalid'}, {'limit': 0}, {'offset': -1}])
def test_admin_history_rejects_invalid_pagination(admin_client, query):
    """Fails if malformed history paging turns into a server error or an unbounded history read."""
    response = admin_client.get('/api/consulting/admin/program/versions/', query)

    assert response.status_code == 400
