from datetime import datetime, timezone as datetime_timezone
from io import BytesIO
from unittest.mock import patch

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from pypdf import PdfReader
from rest_framework.test import APIClient

from content.models import (
    AdditionalModule,
    AdditionalModuleCategory,
    AdditionalModuleShareLink,
    AdditionalModuleShareView,
    ExplainerVideoSettings,
)


pytestmark = pytest.mark.django_db
FIXED_REVOKED_AT = datetime(2026, 8, 20, 12, tzinfo=datetime_timezone.utc)
ADMIN_ENDPOINTS = (
    pytest.param('get', '/api/additional-modules/admin/', id='catalog'),
    pytest.param(
        'post', '/api/additional-modules/admin/categories/', id='create-category',
    ),
    pytest.param(
        'patch', '/api/additional-modules/admin/categories/999999/',
        id='update-category',
    ),
    pytest.param(
        'post', '/api/additional-modules/admin/categories/999999/retire/',
        id='category-status',
    ),
    pytest.param(
        'post', '/api/additional-modules/admin/modules/', id='create-module',
    ),
    pytest.param(
        'patch', '/api/additional-modules/admin/modules/999999/',
        id='update-module',
    ),
    pytest.param(
        'post', '/api/additional-modules/admin/modules/999999/retire/',
        id='module-status',
    ),
    pytest.param(
        'post', '/api/additional-modules/admin/reorder/', id='reorder',
    ),
    pytest.param('get', '/api/additional-modules/admin/shares/', id='shares'),
    pytest.param(
        'post',
        '/api/additional-modules/admin/shares/'
        '00000000-0000-4000-8000-000000000099/revoke/',
        id='share-status',
    ),
    pytest.param(
        'patch',
        '/api/additional-modules/admin/shares/'
        '00000000-0000-4000-8000-000000000099/',
        id='share-update',
    ),
    pytest.param('post', '/api/additional-modules/admin/pdf/', id='pdf'),
)


def module_data(category, slug='landing-page', order=0):
    return {
        'category': category,
        'slug': slug,
        'icon': '🚀',
        'order': order,
        'name_es': f'Módulo {slug}',
        'name_en': f'{slug} module',
        'summary_es': 'Resuelve una necesidad comercial concreta.',
        'summary_en': 'Solves one concrete commercial need.',
        'what_is_es': 'Una capacidad integrada a la plataforma.',
        'what_is_en': 'A capability integrated into the platform.',
        'purpose_es': 'Ayudar al cliente a completar una tarea.',
        'purpose_en': 'Help the customer complete a task.',
        'problems_solved_es': ['Evita trabajo manual.'],
        'problems_solved_en': ['Avoids manual work.'],
        'integrations_es': ['Se integra con el flujo principal.'],
        'integrations_en': ['Integrates with the core flow.'],
        'implementation_requirements_es': ['Definir reglas del negocio.'],
        'implementation_requirements_en': ['Define the business rules.'],
    }


@pytest.fixture
def catalog():
    AdditionalModuleShareView.objects.all().delete()
    AdditionalModuleShareLink.objects.all().delete()
    AdditionalModule.objects.all().delete()
    AdditionalModuleCategory.objects.all().delete()
    commerce = AdditionalModuleCategory.objects.create(
        slug='commerce',
        name_es='Comercio',
        name_en='Commerce',
        order=0,
    )
    experience = AdditionalModuleCategory.objects.create(
        slug='experience',
        name_es='Experiencia',
        name_en='Experience',
        order=1,
    )
    landing = AdditionalModule.objects.create(**module_data(commerce))
    pwa = AdditionalModule.objects.create(
        **module_data(experience, slug='pwa', order=0),
    )
    return commerce, experience, landing, pwa


@pytest.fixture
def staff_client():
    user = get_user_model().objects.create_user(
        username='catalog-admin',
        password='catalog-pass',
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    client.user = user
    return client


@pytest.fixture
def non_staff_client():
    user = get_user_model().objects.create_user(
        username='catalog-user',
        password='catalog-pass',
        is_staff=False,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_share(user, modules, **overrides):
    share = AdditionalModuleShareLink.objects.create(
        recipient_label=overrides.get('recipient_label', 'Cliente demo'),
        language=overrides.get('language', 'es'),
        show_explainer_video=overrides.get('show_explainer_video', True),
        created_by=user,
    )
    share.selected_modules.set(modules)
    return share


def set_catalog_video(visible):
    settings = ExplainerVideoSettings.load()
    settings.show_additional_modules_video = visible
    settings.save()


def test_public_catalog_localizes_content_without_price_fields(catalog):
    response = APIClient().get('/api/additional-modules/public/?lang=en')

    assert response.status_code == 200
    assert response.data['total_modules'] == 2
    assert response.data['categories'][0]['name'] == 'Commerce'
    assert response.data['categories'][0]['modules'][0]['name'] == 'landing-page module'
    assert 'price' not in str(response.data).lower()


def test_public_catalog_rejects_unknown_language(catalog):
    response = APIClient().get('/api/additional-modules/public/?lang=fr')

    assert response.status_code == 400
    assert response.data['lang'] == ['Usa es o en.']


def test_admin_module_create_rejects_empty_detail_lists(catalog, staff_client):
    commerce, _experience, _landing, _pwa = catalog
    payload = module_data(commerce, slug='empty-details', order=3)
    payload['category'] = commerce.id
    payload['problems_solved_es'] = []

    response = staff_client.post(
        '/api/additional-modules/admin/modules/',
        payload,
        format='json',
    )

    assert response.status_code == 400
    assert response.data['problems_solved_es'] == ['Incluye al menos un elemento.']


def test_category_retire_conflicts_while_active_modules_remain(catalog, staff_client):
    commerce, _experience, _landing, _pwa = catalog

    response = staff_client.post(
        f'/api/additional-modules/admin/categories/{commerce.id}/retire/',
        {},
        format='json',
    )

    assert response.status_code == 409
    assert response.data['active_module_count'] == 1


def test_retiring_module_removes_it_from_public_catalog(catalog, staff_client):
    """Falla si un módulo retirado sigue visible en el índice público."""
    _commerce, _experience, landing, _pwa = catalog

    retire_response = staff_client.post(
        f'/api/additional-modules/admin/modules/{landing.id}/retire/',
        {},
        format='json',
    )
    catalog_response = APIClient().get('/api/additional-modules/public/?lang=es')

    public_slugs = [
        module['slug']
        for category in catalog_response.data['categories']
        for module in category['modules']
    ]
    assert retire_response.status_code == 200
    assert retire_response.data['is_active'] is False
    assert catalog_response.status_code == 200
    assert catalog_response.data['total_modules'] == 1
    assert landing.slug not in public_slugs


def test_share_create_persists_fixed_selection(catalog, staff_client):
    _commerce, _experience, landing, pwa = catalog

    response = staff_client.post(
        '/api/additional-modules/admin/shares/',
        {
            'recipient_label': 'Campaña agosto',
            'language': 'en',
            'selected_module_ids': [pwa.id],
        },
        format='json',
    )

    assert response.status_code == 201
    share = AdditionalModuleShareLink.objects.get(uuid=response.data['uuid'])
    assert list(share.selected_modules.values_list('id', flat=True)) == [pwa.id]
    assert landing.id not in list(share.selected_modules.values_list('id', flat=True))


def test_share_create_defaults_to_spanish(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog

    response = staff_client.post(
        '/api/additional-modules/admin/shares/',
        {
            'recipient_label': 'Campaña en español',
            'selected_module_ids': [landing.id],
        },
        format='json',
    )

    assert response.status_code == 201
    assert response.data['language'] == 'es'
    assert response.data['public_path'].startswith('/es-co/additional-modules/')


def test_share_create_keeps_explainer_video_by_default(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog

    response = staff_client.post(
        '/api/additional-modules/admin/shares/',
        {'recipient_label': 'Cliente con video', 'selected_module_ids': [landing.id]},
        format='json',
    )

    assert response.status_code == 201
    assert response.data['show_explainer_video'] is True


def test_share_create_can_hide_explainer_video(catalog, staff_client):
    """Fails if a link created without the video still shows it to that client."""
    _commerce, _experience, landing, _pwa = catalog

    response = staff_client.post(
        '/api/additional-modules/admin/shares/',
        {
            'recipient_label': 'Tres módulos puntuales',
            'selected_module_ids': [landing.id],
            'show_explainer_video': False,
        },
        format='json',
    )

    share = AdditionalModuleShareLink.objects.get(uuid=response.data['uuid'])
    assert response.status_code == 201
    assert response.data['show_explainer_video'] is False
    assert share.show_explainer_video is False


def test_public_catalog_follows_catalog_video_switch(catalog):
    """Fails if hiding the catalog video in the panel still shows it to clients."""
    visible = APIClient().get('/api/additional-modules/public/?lang=es')
    set_catalog_video(False)
    hidden = APIClient().get('/api/additional-modules/public/?lang=es')

    assert visible.data['show_explainer_video'] is True
    assert hidden.data['show_explainer_video'] is False


@pytest.mark.parametrize(
    ('catalog_on', 'link_on', 'expected'),
    [(True, True, True), (True, False, False), (False, True, False)],
)
def test_public_share_shows_video_only_with_both_switches_on(
    catalog, staff_client, catalog_on, link_on, expected,
):
    """Fails if a shared selection shows the video while the catalog or the link hides it."""
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing], show_explainer_video=link_on)
    set_catalog_video(catalog_on)

    response = APIClient().get(
        f'/api/additional-modules/public/shares/{share.uuid}/',
    )

    assert response.status_code == 200
    assert response.data['show_explainer_video'] is expected


def test_public_share_hides_internal_recipient_and_metrics(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing], recipient_label='Cuenta privada')

    response = APIClient().get(
        f'/api/additional-modules/public/shares/{share.uuid}/',
    )

    assert response.status_code == 200
    body = str(response.data)
    assert 'Cuenta privada' not in body
    assert 'view_count' not in response.data
    assert response.data['total_modules'] == 1


def test_public_share_reads_updated_live_content(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing])
    landing.name_es = 'Landing actualizada'
    landing.save(update_fields=['name_es', 'updated_at'])

    response = APIClient().get(
        f'/api/additional-modules/public/shares/{share.uuid}/',
    )

    assert response.data['categories'][0]['modules'][0]['name'] == 'Landing actualizada'


def test_revoked_share_returns_gone(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing])
    share.is_active = False
    share.revoked_at = FIXED_REVOKED_AT
    share.save(update_fields=['is_active', 'revoked_at'])

    response = APIClient().get(
        f'/api/additional-modules/public/shares/{share.uuid}/',
    )

    assert response.status_code == 410


def test_share_without_active_modules_returns_gone(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing])
    landing.is_active = False
    landing.save(update_fields=['is_active', 'updated_at'])

    response = APIClient().get(
        f'/api/additional-modules/public/shares/{share.uuid}/',
    )

    assert response.status_code == 410


def test_tracking_counts_one_open_per_session(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing])
    client = APIClient()
    url = f'/api/additional-modules/public/shares/{share.uuid}/track/'
    payload = {'session_id': 'session_12345678'}

    first = client.post(url, payload, format='json')
    second = client.post(url, payload, format='json')

    share.refresh_from_db()
    assert first.data['status'] == 'recorded'
    assert second.data['status'] == 'existing'
    assert share.view_count == 1
    assert AdditionalModuleShareView.objects.filter(share_link=share).count() == 1


def test_staff_session_preview_is_not_tracked(catalog):
    """Falla si el endpoint omite el evento pero modifica las métricas del enlace."""
    _commerce, _experience, landing, _pwa = catalog
    user = get_user_model().objects.create_user(
        username='preview-admin', password='preview-pass', is_staff=True,
    )
    UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': UserProfile.ROLE_ADMIN},
    )
    share = create_share(user, [landing])
    client = APIClient()
    assert client.login(username='preview-admin', password='preview-pass')

    response = client.post(
        f'/api/additional-modules/public/shares/{share.uuid}/track/',
        {'session_id': 'preview_12345678'},
        format='json',
    )

    share.refresh_from_db()
    assert response.data['status'] == 'skipped'
    assert not AdditionalModuleShareView.objects.filter(share_link=share).exists()
    assert share.view_count == 0
    assert share.first_viewed_at is None
    assert share.last_viewed_at is None


def test_reorder_applies_category_and_module_positions(catalog, staff_client):
    commerce, experience, landing, pwa = catalog
    current = staff_client.get('/api/additional-modules/admin/').data

    response = staff_client.post(
        '/api/additional-modules/admin/reorder/',
        {
            'revision': current['revision'],
            'category_ids': [experience.id, commerce.id],
            'module_groups': [
                {'category_id': experience.id, 'module_ids': [pwa.id, landing.id]},
                {'category_id': commerce.id, 'module_ids': []},
            ],
        },
        format='json',
    )

    landing.refresh_from_db()
    experience.refresh_from_db()
    assert response.status_code == 200
    assert experience.order == 0
    assert landing.category_id == experience.id
    assert landing.order == 1


def test_reorder_rejects_stale_revision(catalog, staff_client):
    commerce, experience, landing, pwa = catalog

    response = staff_client.post(
        '/api/additional-modules/admin/reorder/',
        {
            'revision': 'stale',
            'category_ids': [commerce.id, experience.id],
            'module_groups': [
                {'category_id': commerce.id, 'module_ids': [landing.id]},
                {'category_id': experience.id, 'module_ids': [pwa.id]},
            ],
        },
        format='json',
    )

    assert response.status_code == 409
    assert response.data['code'] == 'stale_catalog_revision'


def test_admin_pdf_respects_selected_modules(catalog, staff_client):
    """The generated document contains only the selection and no currency."""
    _commerce, _experience, landing, pwa = catalog

    response = staff_client.post(
        '/api/additional-modules/admin/pdf/',
        {'language': 'es', 'module_ids': [landing.id]},
        format='json',
    )

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'

    text = '\n'.join(
        page.extract_text() or ''
        for page in PdfReader(BytesIO(response.content)).pages
    )
    assert landing.name_es in text
    assert pwa.name_es not in text
    assert all(currency not in text for currency in ('$', 'COP', 'USD'))


def test_admin_pdf_defaults_to_spanish(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog

    with patch(
        'content.views.additional_modules.AdditionalModulePdfService.build',
        return_value=b'%PDF-spanish-default',
    ) as build_pdf:
        response = staff_client.post(
            '/api/additional-modules/admin/pdf/',
            {'module_ids': [landing.id]},
            format='json',
        )

    assert response.status_code == 200
    assert response['Content-Disposition'] == (
        'attachment; filename="catalogo-modulos-adicionales.pdf"'
    )
    build_pdf.assert_called_once_with(
        language='es',
        module_ids=[landing.id],
        recipient_label='',
    )


def test_admin_pdf_prints_optional_recipient(catalog, staff_client):
    """Render the optional client label on the PDF cover."""
    _commerce, _experience, landing, _pwa = catalog

    response = staff_client.post(
        '/api/additional-modules/admin/pdf/',
        {
            'language': 'es',
            'module_ids': [landing.id],
            'recipient_label': 'Acme & Asociados',
        },
        format='json',
    )

    text = '\n'.join(
        page.extract_text() or ''
        for page in PdfReader(BytesIO(response.content)).pages
    )
    assert 'PREPARADO PARA' in text
    assert 'Acme & Asociados' in text


def test_public_share_catalog_accepts_viewer_language(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing], language='es')

    response = APIClient().get(
        f'/api/additional-modules/public/shares/{share.uuid}/?lang=en',
    )

    assert response.status_code == 200
    assert response.data['language'] == 'en'
    assert response.data['categories'][0]['modules'][0]['name'] == landing.name_en
    assert response.data['canonical_path'] == '/en-us/additional-modules'


def test_public_share_pdf_uses_the_fixed_module_selection(catalog, staff_client):
    """Falla si el PDF público ignora la selección fija del enlace."""
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing])

    with patch(
        'content.views.additional_modules.AdditionalModulePdfService.build',
        return_value=b'%PDF-public-share',
    ) as build_pdf:
        response = APIClient().get(
            f'/api/additional-modules/public/shares/{share.uuid}/pdf/',
        )

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert response.content == b'%PDF-public-share'
    build_pdf.assert_called_once_with(
        language='es',
        module_ids=[landing.id],
        recipient_label='Cliente demo',
    )


def test_public_share_pdf_accepts_viewer_language(catalog, staff_client):
    """Use the viewer-selected language for a shared PDF response."""
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(
        staff_client.user,
        [landing],
        language='es',
        recipient_label='Acme',
    )

    with patch(
        'content.views.additional_modules.AdditionalModulePdfService.build',
        return_value=b'%PDF-public-share',
    ) as build_pdf:
        response = APIClient().get(
            f'/api/additional-modules/public/shares/{share.uuid}/pdf/?lang=en',
        )

    assert response.status_code == 200
    assert response['Content-Disposition'] == (
        'attachment; filename="additional-modules-catalog.pdf"'
    )
    build_pdf.assert_called_once_with(
        language='en',
        module_ids=[landing.id],
        recipient_label='Acme',
    )


def test_share_update_hides_video_on_that_link_only(catalog, staff_client):
    """Fails if turning off one link's video is not persisted or leaks to other links."""
    _commerce, _experience, landing, pwa = catalog
    share = create_share(staff_client.user, [landing])
    other = create_share(staff_client.user, [pwa], recipient_label='Otro cliente')

    response = staff_client.patch(
        f'/api/additional-modules/admin/shares/{share.uuid}/',
        {'show_explainer_video': False},
        format='json',
    )

    share.refresh_from_db()
    other.refresh_from_db()
    assert response.status_code == 200
    assert response.data['show_explainer_video'] is False
    assert share.show_explainer_video is False
    assert other.show_explainer_video is True


def test_share_update_requires_the_video_flag(catalog, staff_client):
    _commerce, _experience, landing, _pwa = catalog
    share = create_share(staff_client.user, [landing])

    response = staff_client.patch(
        f'/api/additional-modules/admin/shares/{share.uuid}/',
        {},
        format='json',
    )

    assert response.status_code == 400
    assert 'show_explainer_video' in response.data


def test_share_update_keeps_language_and_selection_immutable(catalog, staff_client):
    """Fails if the video endpoint lets a sent link change its language or modules."""
    _commerce, _experience, landing, pwa = catalog
    share = create_share(staff_client.user, [landing])

    response = staff_client.patch(
        f'/api/additional-modules/admin/shares/{share.uuid}/',
        {
            'show_explainer_video': False,
            'language': 'en',
            'selected_module_ids': [pwa.id],
        },
        format='json',
    )

    share.refresh_from_db()
    assert response.status_code == 200
    assert share.language == 'es'
    assert list(share.selected_modules.values_list('id', flat=True)) == [landing.id]


def test_share_update_unknown_link_returns_not_found(catalog, staff_client):
    response = staff_client.patch(
        '/api/additional-modules/admin/shares/00000000-0000-4000-8000-000000000099/',
        {'show_explainer_video': False},
        format='json',
    )

    assert response.status_code == 404


def test_unknown_share_returns_not_found(catalog):
    response = APIClient().get(
        '/api/additional-modules/public/shares/'
        '00000000-0000-4000-8000-000000000099/',
    )

    assert response.status_code == 404


class TestAdditionalModuleCatalogAdministration:
    def test_category_creation_uses_next_catalog_position(self, catalog, staff_client):
        """Falla si una categoría nueva reutiliza una posición ya ocupada."""
        response = staff_client.post(
            '/api/additional-modules/admin/categories/',
            {
                'slug': 'security',
                'name_es': 'Seguridad',
                'name_en': 'Security',
            },
            format='json',
        )

        category = AdditionalModuleCategory.objects.get(slug='security')
        assert response.status_code == 201
        assert response.data['order'] == 2
        assert category.order == 2
        assert category.is_active is True

    def test_category_update_cannot_bypass_status_action(self, catalog, staff_client):
        """Falla si editar contenido permite retirar una categoría por accidente."""
        commerce, _experience, _landing, _pwa = catalog

        response = staff_client.patch(
            f'/api/additional-modules/admin/categories/{commerce.id}/',
            {'name_es': 'Comercio actualizado', 'is_active': False},
            format='json',
        )

        commerce.refresh_from_db()
        assert response.status_code == 200
        assert response.data['name_es'] == 'Comercio actualizado'
        assert commerce.name_es == 'Comercio actualizado'
        assert commerce.is_active is True

    def test_category_restore_reactivates_retired_category(
        self,
        catalog,
        staff_client,
    ):
        """Falla si restaurar una categoría retirada no la vuelve publicable."""
        commerce, _experience, landing, _pwa = catalog
        landing.is_active = False
        landing.save(update_fields=['is_active', 'updated_at'])
        commerce.is_active = False
        commerce.save(update_fields=['is_active', 'updated_at'])

        response = staff_client.post(
            f'/api/additional-modules/admin/categories/{commerce.id}/restore/',
            {},
            format='json',
        )

        commerce.refresh_from_db()
        assert response.status_code == 200
        assert response.data['is_active'] is True
        assert commerce.is_active is True

    def test_module_creation_uses_next_category_position(self, catalog, staff_client):
        """Falla si un módulo nuevo pisa el orden de otro módulo de su categoría."""
        commerce, _experience, _landing, _pwa = catalog
        payload = module_data(commerce, slug='regional-payments', order=99)
        payload['category'] = commerce.id

        response = staff_client.post(
            '/api/additional-modules/admin/modules/',
            payload,
            format='json',
        )

        module = AdditionalModule.objects.get(slug='regional-payments')
        assert response.status_code == 201
        assert response.data['order'] == 1
        assert module.order == 1
        assert module.is_active is True

    def test_module_update_moves_to_destination_end(self, catalog, staff_client):
        """Falla si mover un módulo crea una posición duplicada en el destino."""
        _commerce, experience, landing, _pwa = catalog

        response = staff_client.patch(
            f'/api/additional-modules/admin/modules/{landing.id}/',
            {'category': experience.id},
            format='json',
        )

        landing.refresh_from_db()
        assert response.status_code == 200
        assert response.data['category'] == experience.id
        assert landing.category_id == experience.id
        assert landing.order == 1

    def test_module_restore_requires_active_category(self, catalog, staff_client):
        """Falla si un módulo vuelve a publicarse dentro de una categoría retirada."""
        commerce, _experience, landing, _pwa = catalog
        landing.is_active = False
        landing.save(update_fields=['is_active', 'updated_at'])
        commerce.is_active = False
        commerce.save(update_fields=['is_active', 'updated_at'])

        response = staff_client.post(
            f'/api/additional-modules/admin/modules/{landing.id}/restore/',
            {},
            format='json',
        )

        landing.refresh_from_db()
        assert response.status_code == 409
        assert response.data['detail'] == 'Restaura primero la categoría del módulo.'
        assert landing.is_active is False

    def test_reorder_rejects_incomplete_category_set(self, catalog, staff_client):
        """Falla si un reordenamiento puede omitir una categoría del catálogo."""
        commerce, experience, landing, pwa = catalog
        current = staff_client.get('/api/additional-modules/admin/').data

        response = staff_client.post(
            '/api/additional-modules/admin/reorder/',
            {
                'revision': current['revision'],
                'category_ids': [commerce.id],
                'module_groups': [
                    {'category_id': commerce.id, 'module_ids': [landing.id]},
                    {'category_id': experience.id, 'module_ids': [pwa.id]},
                ],
            },
            format='json',
        )

        commerce.refresh_from_db()
        experience.refresh_from_db()
        assert response.status_code == 400
        assert response.data['code'] == 'invalid_catalog_order'
        assert response.data['detail'] == (
            'La lista de categorías debe incluir el catálogo completo.'
        )
        assert (commerce.order, experience.order) == (0, 1)

    def test_share_list_returns_fixed_selection(self, catalog, staff_client):
        """Falla si el historial administrativo pierde la selección compartida."""
        _commerce, _experience, landing, _pwa = catalog
        share = create_share(staff_client.user, [landing], language='en')

        response = staff_client.get('/api/additional-modules/admin/shares/')

        assert response.status_code == 200
        assert response.data[0]['uuid'] == str(share.uuid)
        assert response.data[0]['selected_modules'][0]['slug'] == 'landing-page'
        assert response.data[0]['public_path'] == (
            f'/en-us/additional-modules/share/{share.uuid}'
        )

    def test_share_creation_rejects_empty_selection(self, catalog, staff_client):
        """Falla si se publica un enlace que no contiene ningún módulo."""
        response = staff_client.post(
            '/api/additional-modules/admin/shares/',
            {
                'recipient_label': 'Selección vacía',
                'language': 'es',
                'selected_module_ids': [],
            },
            format='json',
        )

        assert response.status_code == 400
        assert response.data['selected_module_ids'] == [
            'Selecciona al menos un módulo.',
        ]

    def test_share_creation_rejects_duplicate_selection(self, catalog, staff_client):
        """Falla si un enlace guarda el mismo módulo más de una vez."""
        _commerce, _experience, landing, _pwa = catalog

        response = staff_client.post(
            '/api/additional-modules/admin/shares/',
            {
                'recipient_label': 'Selección repetida',
                'language': 'es',
                'selected_module_ids': [landing.id, landing.id],
            },
            format='json',
        )

        assert response.status_code == 400
        assert response.data['selected_module_ids'] == [
            'La selección contiene módulos repetidos.',
        ]

    @freeze_time('2026-08-20 12:00:00')
    def test_share_revocation_disables_public_access(self, catalog, staff_client):
        """Falla si revocar un enlace no bloquea su catálogo público."""
        _commerce, _experience, landing, _pwa = catalog
        share = create_share(staff_client.user, [landing])

        revoke_response = staff_client.post(
            f'/api/additional-modules/admin/shares/{share.uuid}/revoke/',
            {},
            format='json',
        )
        public_response = APIClient().get(
            f'/api/additional-modules/public/shares/{share.uuid}/',
        )

        share.refresh_from_db()
        assert revoke_response.status_code == 200
        assert revoke_response.data['is_active'] is False
        assert share.revoked_at == FIXED_REVOKED_AT
        assert public_response.status_code == 410
        assert public_response.data['code'] == 'catalog_link_unavailable'

    def test_share_restoration_reopens_public_access(self, catalog, staff_client):
        """Falla si restaurar un enlace no recupera su selección pública."""
        _commerce, _experience, landing, _pwa = catalog
        share = create_share(staff_client.user, [landing])
        share.is_active = False
        share.revoked_at = FIXED_REVOKED_AT
        share.save(update_fields=['is_active', 'revoked_at'])

        restore_response = staff_client.post(
            f'/api/additional-modules/admin/shares/{share.uuid}/restore/',
            {},
            format='json',
        )
        public_response = APIClient().get(
            f'/api/additional-modules/public/shares/{share.uuid}/',
        )

        share.refresh_from_db()
        assert restore_response.status_code == 200
        assert restore_response.data['is_active'] is True
        assert share.revoked_at is None
        assert public_response.status_code == 200
        assert public_response.data['total_modules'] == 1

    def test_admin_pdf_rejects_empty_selection(self, catalog, staff_client):
        """Falla si el panel genera un PDF sin módulos seleccionados."""
        response = staff_client.post(
            '/api/additional-modules/admin/pdf/',
            {'language': 'es', 'module_ids': []},
            format='json',
        )

        assert response.status_code == 400
        assert response.data['module_ids'] == ['Selecciona al menos un módulo.']

    def test_admin_pdf_rejects_duplicate_selection(self, catalog, staff_client):
        """Falla si el PDF procesa dos veces el mismo módulo."""
        _commerce, _experience, landing, _pwa = catalog

        response = staff_client.post(
            '/api/additional-modules/admin/pdf/',
            {'language': 'es', 'module_ids': [landing.id, landing.id]},
            format='json',
        )

        assert response.status_code == 400
        assert response.data['module_ids'] == [
            'La selección contiene módulos repetidos.',
        ]


class TestAdditionalModuleCatalogPublicErrors:
    def test_public_catalog_pdf_rejects_unknown_language(self, catalog):
        """Falla si el PDF público acepta un idioma sin contenido definido."""
        response = APIClient().get('/api/additional-modules/public/pdf/?lang=fr')

        assert response.status_code == 400
        assert response.data['lang'] == ['Usa es o en.']

    def test_public_catalog_pdf_reports_empty_catalog(self, catalog):
        """Falla si un catálogo vacío descarga un documento engañoso."""
        AdditionalModule.objects.update(is_active=False)

        response = APIClient().get('/api/additional-modules/public/pdf/?lang=es')

        assert response.status_code == 410
        assert response.data['code'] == 'catalog_link_unavailable'
        assert response.data['detail'] == 'No hay módulos activos para generar el PDF.'

    def test_public_share_rejects_unknown_language(self, catalog, staff_client):
        _commerce, _experience, landing, _pwa = catalog
        share = create_share(staff_client.user, [landing])

        response = APIClient().get(
            f'/api/additional-modules/public/shares/{share.uuid}/?lang=fr',
        )

        assert response.status_code == 400
        assert response.data['lang'] == ['Usa es o en.']

    def test_tracking_rejects_invalid_session_identifier(self, catalog, staff_client):
        """Falla si el seguimiento acepta una sesión con formato inválido."""
        _commerce, _experience, landing, _pwa = catalog
        share = create_share(staff_client.user, [landing])

        response = APIClient().post(
            f'/api/additional-modules/public/shares/{share.uuid}/track/',
            {'session_id': 'short'},
            format='json',
        )

        assert response.status_code == 400
        assert response.data['session_id'] == [
            'Usa un identificador de sesión válido.',
        ]
        assert AdditionalModuleShareView.objects.filter(share_link=share).count() == 0

    def test_tracking_rejects_revoked_share(self, catalog, staff_client):
        """Falla si un enlace revocado todavía registra aperturas."""
        _commerce, _experience, landing, _pwa = catalog
        share = create_share(staff_client.user, [landing])
        share.is_active = False
        share.revoked_at = FIXED_REVOKED_AT
        share.save(update_fields=['is_active', 'revoked_at'])

        response = APIClient().post(
            f'/api/additional-modules/public/shares/{share.uuid}/track/',
            {'session_id': 'revoked_12345678'},
            format='json',
        )

        assert response.status_code == 410
        assert response.data['code'] == 'catalog_link_unavailable'
        assert AdditionalModuleShareView.objects.filter(share_link=share).count() == 0

    def test_public_share_pdf_rejects_revoked_share(self, catalog, staff_client):
        """Falla si un enlace revocado conserva una descarga PDF pública."""
        _commerce, _experience, landing, _pwa = catalog
        share = create_share(staff_client.user, [landing])
        share.is_active = False
        share.revoked_at = FIXED_REVOKED_AT
        share.save(update_fields=['is_active', 'revoked_at'])

        response = APIClient().get(
            f'/api/additional-modules/public/shares/{share.uuid}/pdf/',
        )

        assert response.status_code == 410
        assert response.data['code'] == 'catalog_link_unavailable'


class TestAdditionalModuleCatalogPermissions:
    @pytest.mark.parametrize(('method', 'path'), ADMIN_ENDPOINTS)
    def test_admin_endpoint_requires_authentication(self, method, path):
        """Falla si una vista administrativa queda accesible sin iniciar sesión."""
        response = getattr(APIClient(), method)(path, {}, format='json')

        assert response.status_code == 401

    @pytest.mark.parametrize(('method', 'path'), ADMIN_ENDPOINTS)
    def test_admin_endpoint_rejects_non_staff_user(
        self,
        non_staff_client,
        method,
        path,
    ):
        """Falla si un usuario común puede administrar el catálogo comercial."""
        response = getattr(non_staff_client, method)(path, {}, format='json')

        assert response.status_code == 403
