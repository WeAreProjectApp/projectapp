"""Tests for the Tasks (Kanban) MCP connector HTTP endpoint."""
import json

import pytest

from content.models import McpConnector, Task, TaskAlert, TaskComment
from content.tests.mcp_confirmation_helpers import call_confirmed, confirmed_payload


@pytest.fixture
def tasks_connector(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='tasks', defaults={'name': 'Gestor de Tareas'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector, connector.generate_token()


@pytest.fixture
def mcp_superuser(db, django_user_model):
    """A superuser so mcp_actor() (comment author) can resolve."""
    return django_user_model.objects.create_user(
        username='mcp_tasks_actor', password='x', is_staff=True, is_superuser=True,
    )


def _url(token):
    return f'/api/mcp/tasks/{token}/'


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, token, name, arguments):
    return api_client.post(
        _url(token), _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


def _call_confirmed(api_client, token, name, arguments):
    return call_confirmed(api_client, _url(token), _rpc, name, arguments)


@pytest.mark.django_db
class TestTasksMcpBoard:
    def test_tool_list_includes_core_tools(self, api_client, tasks_connector):
        _, token = tasks_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        names = [t['name'] for t in response.data['result']['tools']]
        for expected in ('list_tasks', 'create_task', 'reorder_task', 'create_task_comment'):
            assert expected in names

    def test_create_and_list(self, api_client, tasks_connector):
        _, token = tasks_connector
        created = _call(api_client, token, 'create_task', {'title': 'Escribir README'})
        assert created.data['result']['isError'] is False
        listed = _call(api_client, token, 'list_tasks', {'board': 'standard'})
        text = listed.data['result']['content'][0]['text']
        assert 'Escribir README' in text

    def test_list_filters_by_q(self, api_client, tasks_connector):
        _, token = tasks_connector
        _call(api_client, token, 'create_task', {'title': 'Alpha task'})
        _call(api_client, token, 'create_task', {'title': 'Beta task'})
        response = _call(api_client, token, 'list_tasks', {'q': 'Alpha'})
        text = response.data['result']['content'][0]['text']
        assert 'Alpha task' in text
        assert 'Beta task' not in text

    def test_invalid_board_errors(self, api_client, tasks_connector):
        _, token = tasks_connector
        response = _call(api_client, token, 'list_tasks', {'board': 'nope'})
        assert response.data['result']['isError'] is True


@pytest.mark.django_db
class TestTasksMcpMutations:
    def test_update_moves_status(self, api_client, tasks_connector):
        task = Task.objects.create(title='Mover', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'update_task', {'task_id': task.id, 'status': 'done'})
        assert response.data['result']['isError'] is False
        task.refresh_from_db()
        assert task.status == 'done'

    def test_reorder_renumbers_column(self, api_client, tasks_connector):
        a = Task.objects.create(title='A', status='todo', position=0)
        b = Task.objects.create(title='B', status='todo', position=1)
        _, token = tasks_connector
        response = _call(api_client, token, 'reorder_task', {
            'task_id': b.id, 'status': 'todo', 'position': 0,
        })
        assert response.data['result']['isError'] is False
        b.refresh_from_db()
        a.refresh_from_db()
        assert b.position == 0 and a.position == 1

    def test_duplicate_task(self, api_client, tasks_connector):
        task = Task.objects.create(title='Original', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'duplicate_task', {'task_id': task.id})
        assert response.data['result']['isError'] is False
        assert Task.objects.filter(title='Original (copia)').exists()

    def test_delete_task(self, api_client, tasks_connector):
        task = Task.objects.create(title='Borrar', status='todo')
        _, token = tasks_connector
        response = _call_confirmed(
            api_client, token, 'delete_task', {'task_id': task.id},
        )
        assert response.data['result']['isError'] is False
        assert not Task.objects.filter(pk=task.id).exists()


@pytest.mark.django_db
class TestTasksMcpComments:
    def test_create_comment_uses_connector_service_actor(
        self, api_client, tasks_connector,
    ):
        task = Task.objects.create(title='Con comentario', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'create_task_comment', {
            'task_id': task.id, 'text': 'Hola',
        })
        assert response.data['result']['isError'] is False
        comment = TaskComment.objects.get(task=task)
        assert comment.author.username == 'mcp_tasks'
        assert comment.author.has_usable_password() is False

    def test_create_comment_bootstraps_actor_without_panel_superuser(
        self, api_client, tasks_connector,
    ):
        task = Task.objects.create(title='Sin actor', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'create_task_comment', {
            'task_id': task.id, 'text': 'Hola',
        })
        assert response.data['result']['isError'] is False
        assert TaskComment.objects.get(task=task).author.username == 'mcp_tasks'


def _payload(response):
    return confirmed_payload(response)


@pytest.mark.django_db
class TestTasksMcpHandlerBranches:
    def test_get_task_returns_payload(self, api_client, tasks_connector):
        task = Task.objects.create(title='Visible', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'get_task', {'task_id': task.id})
        assert _payload(response)['title'] == 'Visible'

    def test_get_unknown_task_errors(self, api_client, tasks_connector):
        _, token = tasks_connector
        response = _call(api_client, token, 'get_task', {'task_id': 999999})
        assert response.data['result']['isError'] is True

    def test_create_task_invalid_payload_errors(self, api_client, tasks_connector):
        _, token = tasks_connector
        response = _call(api_client, token, 'create_task', {'title': ''})
        result = response.data['result']
        assert result['isError'] is True
        assert 'Datos inválidos' in result['content'][0]['text']

    def test_update_without_fields_errors(self, api_client, tasks_connector):
        task = Task.objects.create(title='Quieta', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'update_task', {'task_id': task.id})
        assert response.data['result']['isError'] is True

    def test_update_invalid_payload_errors(self, api_client, tasks_connector):
        task = Task.objects.create(title='Quieta', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'update_task', {
            'task_id': task.id, 'status': 'limbo',
        })
        assert response.data['result']['isError'] is True

    def test_list_macro_board_returns_flat_filtered_items(
        self, api_client, tasks_connector,
    ):
        Task.objects.create(title='Roadmap Q3', status='todo', board_type='macro')
        Task.objects.create(title='Otra macro', status='todo', board_type='macro')
        _, token = tasks_connector
        response = _call(api_client, token, 'list_tasks', {
            'board': 'macro', 'q': 'Roadmap',
        })
        items = _payload(response)['columns']['items']
        assert len(items) == 1
        assert items[0]['title'] == 'Roadmap Q3'

    def test_list_archived_returns_only_archived(self, api_client, tasks_connector):
        Task.objects.create(title='Activa', status='todo')
        Task.objects.create(title='Guardada', status='done', is_archived=True)
        _, token = tasks_connector
        response = _call(api_client, token, 'list_archived_tasks', {})
        results = _payload(response)['results']
        assert len(results) == 1
        assert results[0]['title'] == 'Guardada'

    def test_list_assignees_returns_active_staff(
        self, api_client, tasks_connector, mcp_superuser,
    ):
        _, token = tasks_connector
        response = _call(api_client, token, 'list_task_assignees', {})
        names = [row['name'] for row in _payload(response)['results']]
        assert 'mcp_tasks_actor' in names

    def test_reorder_invalid_status_errors(self, api_client, tasks_connector):
        task = Task.objects.create(title='Mover', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'reorder_task', {
            'task_id': task.id, 'status': 'limbo', 'position': 0,
        })
        assert response.data['result']['isError'] is True

    def test_reorder_invalid_position_errors(self, api_client, tasks_connector):
        task = Task.objects.create(title='Mover', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'reorder_task', {
            'task_id': task.id, 'status': 'todo', 'position': 'xx',
        })
        assert response.data['result']['isError'] is True

    def test_reorder_clamps_negative_position_to_top(
        self, api_client, tasks_connector,
    ):
        Task.objects.create(title='Primera', status='todo', position=0)
        task = Task.objects.create(title='Sube', status='todo', position=1)
        _, token = tasks_connector
        response = _call(api_client, token, 'reorder_task', {
            'task_id': task.id, 'status': 'todo', 'position': -5,
        })
        assert response.data['result']['isError'] is False
        task.refresh_from_db()
        assert task.position == 0

    def test_archive_task_sets_flag_and_reason(self, api_client, tasks_connector):
        task = Task.objects.create(title='Cerrada', status='done')
        _, token = tasks_connector
        response = _call(api_client, token, 'archive_task', {
            'task_id': task.id, 'archive_reason': 'Entregada al cliente',
        })
        assert response.data['result']['isError'] is False
        task.refresh_from_db()
        assert task.is_archived is True
        assert task.archive_reason == 'Entregada al cliente'

    def test_unarchive_task_clears_flag(self, api_client, tasks_connector):
        task = Task.objects.create(
            title='Vuelve', status='todo', is_archived=True,
            archive_reason='vieja',
        )
        _, token = tasks_connector
        response = _call(api_client, token, 'unarchive_task', {'task_id': task.id})
        assert response.data['result']['isError'] is False
        task.refresh_from_db()
        assert task.is_archived is False
        assert task.archive_reason == ''

    def test_list_comments_returns_task_comments(
        self, api_client, tasks_connector, mcp_superuser,
    ):
        task = Task.objects.create(title='Comentada', status='todo')
        TaskComment.objects.create(task=task, author=mcp_superuser, text='Nota 1')
        _, token = tasks_connector
        response = _call(api_client, token, 'list_task_comments', {'task_id': task.id})
        results = _payload(response)['results']
        assert len(results) == 1
        assert results[0]['text'] == 'Nota 1'

    def test_create_comment_invalid_payload_errors(
        self, api_client, tasks_connector, mcp_superuser,
    ):
        task = Task.objects.create(title='Sin texto', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'create_task_comment', {
            'task_id': task.id, 'text': '',
        })
        assert response.data['result']['isError'] is True

    def test_delete_comment_removes_row(
        self, api_client, tasks_connector, mcp_superuser,
    ):
        task = Task.objects.create(title='Comentada', status='todo')
        comment = TaskComment.objects.create(task=task, author=mcp_superuser, text='X')
        _, token = tasks_connector
        response = _call_confirmed(api_client, token, 'delete_task_comment', {
            'task_id': task.id, 'comment_id': comment.id,
        })
        assert _payload(response)['deleted'] is True
        assert not TaskComment.objects.filter(pk=comment.pk).exists()

    def test_delete_unknown_comment_errors(self, api_client, tasks_connector):
        task = Task.objects.create(title='Sin comentarios', status='todo')
        _, token = tasks_connector
        response = _call_confirmed(api_client, token, 'delete_task_comment', {
            'task_id': task.id, 'comment_id': 999999,
        })
        assert response.data['result']['isError'] is True

    def test_create_alert_persists_notify_at(self, api_client, tasks_connector):
        task = Task.objects.create(title='Con alerta', status='todo')
        _, token = tasks_connector
        response = _call(api_client, token, 'create_task_alert', {
            'task_id': task.id,
            'notify_at': '2026-08-01',
            'note': 'Revisar entrega',
        })
        assert response.data['result']['isError'] is False
        assert TaskAlert.objects.filter(task=task, note='Revisar entrega').exists()

    def test_list_alerts_returns_task_alerts(self, api_client, tasks_connector):
        task = Task.objects.create(title='Con alerta', status='todo')
        TaskAlert.objects.create(task=task, notify_at='2026-08-01', note='N1')
        _, token = tasks_connector
        response = _call(api_client, token, 'list_task_alerts', {'task_id': task.id})
        assert len(_payload(response)['results']) == 1

    def test_delete_alert_removes_row(self, api_client, tasks_connector):
        task = Task.objects.create(title='Con alerta', status='todo')
        alert = TaskAlert.objects.create(
            task=task, notify_at='2026-08-01', note='N1',
        )
        _, token = tasks_connector
        response = _call_confirmed(api_client, token, 'delete_task_alert', {
            'task_id': task.id, 'alert_id': alert.id,
        })
        assert _payload(response)['deleted'] is True
        assert not TaskAlert.objects.filter(pk=alert.pk).exists()
