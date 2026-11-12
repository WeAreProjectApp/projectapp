"""Panel administration boundaries missed by the initial procurement tests."""

import pytest
from procurement.models import (
    Activity,
    Alert,
    Classification,
    SavedSearch,
    Settings,
    SyncRun,
)

pytestmark = pytest.mark.django_db


def test_list_rejects_malformed_filter_json(staff_client):
    """Falla si unos filtros dañados en la URL provocan un error del servidor."""
    response = staff_client.get('/api/procurement/opportunities/', {'filters': '{bad'})

    assert response.status_code == 400
    assert response.json() == {'filters': 'Filtros JSON inválidos.'}


def test_classified_filter_uses_requesters_state(opportunity, staff_user, other_staff_user, staff_client):
    """Falla si Mis clasificados incluye decisiones ajenas o ignora el estado solicitado."""
    mine = opportunity('OWN-DISCARD')
    foreign = opportunity('FOREIGN-DISCARD')
    Classification.objects.create(opportunity=mine, owner=staff_user, state='discarded', notes='Fuera de perfil')
    Classification.objects.create(opportunity=foreign, owner=other_staff_user, state='discarded', notes='Ajena')
    Classification.objects.create(opportunity=foreign, owner=staff_user, state='interesting')

    response = staff_client.get('/api/procurement/opportunities/', {'classified': 'true', 'state': 'discarded'})

    assert response.status_code == 200
    assert [item['id'] for item in response.json()['results']] == [mine.pk]


def test_restore_rejects_process_without_discard(opportunity, staff_client):
    """Falla si restaurar inventa una clasificación o un historial que no existían."""
    record = opportunity('NEVER-DISCARDED')

    response = staff_client.post(f'/api/procurement/opportunities/{record.pk}/restore/', {}, format='json')

    assert response.status_code == 400
    assert response.json() == ['Sólo se restaura una clasificación descartada.']
    assert Classification.objects.count() == 0
    assert Activity.objects.count() == 0


def test_search_creation_persists_normalized_filters(staff_client, staff_user):
    """Falla si el panel pierde los filtros de una búsqueda guardada válida."""
    response = staff_client.post('/api/procurement/searches/', {
        'name': 'Consultoría', 'filters': {'keywords': ['consultoría']},
    }, format='json')

    assert response.status_code == 201
    saved = SavedSearch.objects.get(pk=response.json()['id'])
    assert saved.owner_id == staff_user.pk
    assert saved.filters['keywords'] == ['consultoría']


def test_search_list_hides_other_staff_preferences(staff_client, staff_user, other_staff_user):
    """Falla si el panel mezcla las búsquedas personales de dos administradores."""
    mine = SavedSearch.objects.create(owner=staff_user, name='Mía')
    SavedSearch.objects.create(owner=other_staff_user, name='Ajena')

    response = staff_client.get('/api/procurement/searches/')

    assert response.status_code == 200
    assert [item['id'] for item in response.json()] == [mine.pk]


def test_search_rename_rejects_duplicate_name_without_losing_original(staff_client, staff_user):
    """Falla si un nombre duplicado produce un 500 o cambia la búsqueda original."""
    first = SavedSearch.objects.create(owner=staff_user, name='Original')
    SavedSearch.objects.create(owner=staff_user, name='Ocupado')

    response = staff_client.patch(f'/api/procurement/searches/{first.pk}/', {'name': 'Ocupado'}, format='json')

    first.refresh_from_db()
    assert response.status_code == 400
    assert response.json() == {'name': 'Ya existe una búsqueda con ese nombre.'}
    assert first.name == 'Original'


def test_search_deletion_preserves_shared_alert(staff_client, staff_user, alert):
    """Falla si borrar una búsqueda también elimina una alerta independiente."""
    search = SavedSearch.objects.create(owner=staff_user, name='Temporal')
    shared = alert(is_active=False)

    response = staff_client.delete(f'/api/procurement/searches/{search.pk}/')

    assert response.status_code == 204
    assert SavedSearch.objects.filter(pk=search.pk).count() == 0
    assert Alert.objects.get(pk=shared.pk).name == 'Alertas jurídicas'


def test_search_creation_requires_name(staff_client):
    """Falla si se puede guardar una búsqueda sin un nombre identificable."""
    response = staff_client.post('/api/procurement/searches/', {'filters': {}}, format='json')

    assert response.status_code == 400
    assert response.json() == {'name': 'Campo obligatorio.'}
    assert SavedSearch.objects.count() == 0


def test_alert_creation_rejects_case_insensitive_duplicate_recipients(staff_client):
    """Falla si un destinatario repetido con otra capitalización recibe dos correos."""
    response = staff_client.post('/api/procurement/alerts/', {
        'name': 'Duplicada', 'filters': {}, 'recipients': ['Carlos@example.com', 'carlos@example.com'],
    }, format='json')

    assert response.status_code == 400
    assert response.json() == {'recipients': ['No repitas destinatarios.']}
    assert Alert.objects.count() == 0


def test_alert_creation_reports_all_missing_required_fields(staff_client):
    """Falla si se guardan alertas incompletas que no pueden evaluarse o enviarse."""
    response = staff_client.post('/api/procurement/alerts/', {}, format='json')

    assert response.status_code == 400
    assert response.json() == {
        'name': ['Campo obligatorio.'], 'recipients': ['Campo obligatorio.'], 'filters': ['Campo obligatorio.'],
    }
    assert Alert.objects.count() == 0


@pytest.mark.parametrize('endpoint', ['alerts', 'searches'])
def test_configuration_rejects_non_object_filters(staff_client, endpoint):
    """Falla si una lista sustituye el objeto de filtros que necesita la evaluación."""
    response = staff_client.post(f'/api/procurement/{endpoint}/', {
        'name': 'Inválida', 'filters': [],
    }, format='json')

    assert response.status_code == 400
    assert response.json()['filters'] == ['Usa un objeto de filtros.']


def test_settings_patch_preserves_other_schedule_defaults(staff_client):
    """Falla si ajustar el horario semanal sobrescribe otros horarios o habilita envíos."""
    response = staff_client.patch('/api/procurement/settings/', {
        'weekly_day': 4, 'weekly_time': '08:15', 'lookback_days': 45,
    }, format='json')
    persisted = staff_client.get('/api/procurement/settings/')

    assert response.status_code == 200
    assert persisted.json()['weekly_day'] == 4
    assert persisted.json()['weekly_time'] == '08:15:00'
    assert persisted.json()['lookback_days'] == 45
    assert persisted.json()['daily_time'] == '07:00:00'
    assert Settings.current().email_enabled is False


def test_filter_catalog_returns_sorted_nonblank_distinct_values(opportunity, staff_client):
    """Falla si los filtros del panel muestran valores vacíos o repetidos de SECOP."""
    opportunity('CATALOG-A', entity_name='Entidad B', department='', unspsc_code='80101500')
    opportunity('CATALOG-B', entity_name='Entidad A', department='Antioquia', unspsc_code='80101500')

    response = staff_client.get('/api/procurement/filters/')

    assert response.status_code == 200
    assert response.json()['entity_names'] == ['Entidad A', 'Entidad B']
    assert response.json()['departments'] == ['Antioquia']
    assert response.json()['unspsc_codes'] == ['80101500']


def test_sync_status_retains_last_success_after_newer_failure(opportunity, staff_client):
    """Falla si el panel presenta una ejecución fallida como última sincronización exitosa."""
    success = SyncRun.objects.create(status='success', processed=3)
    failed = SyncRun.objects.create(status='failed', errors=3)
    opportunity('STATUS-OPEN')
    opportunity('STATUS-CLOSED', source_status='Adjudicado')

    response = staff_client.get('/api/procurement/sync/')

    assert response.status_code == 200
    assert response.json()['last_success']['id'] == success.pk
    assert response.json()['recent'][0]['id'] == failed.pk
    assert response.json()['open_count'] == 1


def test_alert_activation_enqueues_evaluation_after_commit(
        staff_client, alert, monkeypatch, django_capture_on_commit_callbacks):
    """Falla si activar una alerta desde el panel no encola la evaluación de oportunidades."""
    from unittest.mock import Mock

    shared = alert(is_active=False)
    enqueue = Mock(return_value=None)
    monkeypatch.setattr('procurement.tasks.evaluate_alert', enqueue)

    with django_capture_on_commit_callbacks(execute=True):
        response = staff_client.patch(f'/api/procurement/alerts/{shared.pk}/', {'is_active': True}, format='json')

    shared.refresh_from_db()
    assert response.status_code == 200
    assert shared.is_active is True
    assert shared.version == 2
    enqueue.assert_called_once_with(shared.pk)
