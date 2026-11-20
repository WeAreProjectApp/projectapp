"""Tests for content/views/task.py — Kanban task CRUD + reorder."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from content.models import Task

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def non_admin_client(api_client, db):
    user = User.objects.create_user(
        username='regular', email='regular@test.com',
        password='pw', is_staff=False,
    )
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def todo_task(db):
    return Task.objects.create(title='T1', status=Task.Status.TODO, position=0)


@pytest.fixture
def in_progress_task(db):
    return Task.objects.create(
        title='T2', status=Task.Status.IN_PROGRESS, position=0,
    )


class TestListTasks:
    def test_groups_by_status(self, admin_client, todo_task, in_progress_task):
        url = reverse('list-tasks')
        response = admin_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {'todo', 'in_progress', 'blocked', 'done'}
        assert [t['title'] for t in data['todo']] == ['T1']
        assert [t['title'] for t in data['in_progress']] == ['T2']
        assert data['blocked'] == []
        assert data['done'] == []

    def test_requires_admin(self, non_admin_client):
        url = reverse('list-tasks')
        response = non_admin_client.get(url)
        assert response.status_code == 403


class TestCreateTask:
    def test_defaults_to_todo_and_appends_position(self, admin_client, todo_task):
        url = reverse('create-task')
        response = admin_client.post(
            url, {'title': 'Second'}, format='json',
        )

        assert response.status_code == 201
        data = response.json()
        assert data['status'] == 'todo'
        assert data['priority'] == 'medium'
        assert data['position'] == todo_task.position + 1

    def test_honors_provided_status_and_priority(self, admin_client):
        url = reverse('create-task')
        response = admin_client.post(
            url,
            {'title': 'Urgent', 'status': 'blocked', 'priority': 'high'},
            format='json',
        )

        assert response.status_code == 201
        data = response.json()
        assert data['status'] == 'blocked'
        assert data['priority'] == 'high'

    def test_rejects_missing_title(self, admin_client):
        url = reverse('create-task')
        response = admin_client.post(url, {}, format='json')
        assert response.status_code == 400


class TestUpdateTask:
    def test_changes_status_and_repositions(self, admin_client, todo_task, in_progress_task):
        url = reverse('update-task', kwargs={'task_id': todo_task.id})
        response = admin_client.patch(
            url, {'status': 'in_progress'}, format='json',
        )

        assert response.status_code == 200
        todo_task.refresh_from_db()
        assert todo_task.status == 'in_progress'
        # Appended after in_progress_task
        assert todo_task.position == in_progress_task.position + 1

    def test_updates_title(self, admin_client, todo_task):
        url = reverse('update-task', kwargs={'task_id': todo_task.id})
        response = admin_client.patch(
            url, {'title': 'Renamed'}, format='json',
        )
        assert response.status_code == 200
        todo_task.refresh_from_db()
        assert todo_task.title == 'Renamed'


class TestReorderTask:
    def test_reassigns_positions_within_column(self, admin_client):
        a = Task.objects.create(title='A', status=Task.Status.TODO, position=0)
        b = Task.objects.create(title='B', status=Task.Status.TODO, position=1)
        c = Task.objects.create(title='C', status=Task.Status.TODO, position=2)

        url = reverse('reorder-task', kwargs={'task_id': c.id})
        response = admin_client.patch(
            url, {'status': 'todo', 'position': 0}, format='json',
        )

        assert response.status_code == 200
        titles = [t['title'] for t in response.json()['todo']]
        assert titles == ['C', 'A', 'B']
        for obj in (a, b, c):
            obj.refresh_from_db()
        assert (c.position, a.position, b.position) == (0, 1, 2)

    def test_moves_between_columns(self, admin_client, todo_task):
        url = reverse('reorder-task', kwargs={'task_id': todo_task.id})
        response = admin_client.patch(
            url, {'status': 'done', 'position': 0}, format='json',
        )
        assert response.status_code == 200
        todo_task.refresh_from_db()
        assert todo_task.status == 'done'
        assert todo_task.position == 0

    def test_persists_drop_before_the_second_destination_task(self, admin_client):
        source_ids = [1, 2, 9, 33]
        destination_ids = [3, 21, 25, 45, 49]
        Task.objects.bulk_create([
            Task(pk=pk, title=f'Tarea {pk}', status=status, position=position)
            for status, ids in [('todo', source_ids), ('in_progress', destination_ids)]
            for position, pk in enumerate(ids)
        ])

        response = admin_client.patch(
            reverse('reorder-task', kwargs={'task_id': 9}),
            {'status': 'in_progress', 'position': 1}, format='json',
        )

        assert response.status_code == 200
        assert list(Task.objects.filter(status='todo').order_by('position').values_list('pk', flat=True)) == [1, 2, 33]
        assert list(Task.objects.filter(status='in_progress').order_by('position').values_list('pk', flat=True)) == [3, 9, 21, 25, 45, 49]
        assert Task.objects.get(pk=9).position == 1

    def test_rejects_invalid_status(self, admin_client, todo_task):
        url = reverse('reorder-task', kwargs={'task_id': todo_task.id})
        response = admin_client.patch(
            url, {'status': 'not_a_status', 'position': 0}, format='json',
        )
        assert response.status_code == 400


class TestDeleteTask:
    def test_removes_task(self, admin_client, todo_task):
        url = reverse('delete-task', kwargs={'task_id': todo_task.id})
        response = admin_client.delete(url)
        assert response.status_code == 204
        assert not Task.objects.filter(pk=todo_task.id).exists()

    def test_nonexistent_task_returns_404(self, admin_client):
        url = reverse('delete-task', kwargs={'task_id': 999999})
        response = admin_client.delete(url)
        assert response.status_code == 404


class TestDuplicateTask:
    def _create_duplicate_scenario(self, db):
        original = Task.objects.create(title='Plan release', description='Q3 launch', status=Task.Status.IN_PROGRESS, priority=Task.Priority.HIGH, board_type=Task.BoardType.WEEKLY, position=4)
        Task.objects.create(title='Other', status=Task.Status.IN_PROGRESS, board_type=Task.BoardType.WEEKLY, position=5)
        return original

    def test_duplicates_title_description_and_status(self, admin_client, db):
        """Duplicate inherits title with (copia) suffix, description, and status."""
        original = self._create_duplicate_scenario(db)
        response = admin_client.post(reverse('duplicate-task', kwargs={'task_id': original.id}), {}, format='json')
        assert response.status_code == 201
        data = response.json()
        assert data['title'] == 'Plan release (copia)'
        assert data['description'] == 'Q3 launch'
        assert data['status'] == 'in_progress'

    def test_duplicates_basic_fields_with_copia_suffix(self, admin_client, db):
        """Duplicate inherits priority, board, position, and does not archive; original is preserved."""
        original = self._create_duplicate_scenario(db)
        response = admin_client.post(reverse('duplicate-task', kwargs={'task_id': original.id}), {}, format='json')
        data = response.json()
        assert data['priority'] == 'high'
        assert data['board_type'] == 'weekly'
        assert data['position'] == 6
        assert data['is_archived'] is False
        assert Task.objects.filter(pk=original.id).exists()

    def test_does_not_copy_comments_alerts_or_archive_state(self, admin_client, admin_user, db):
        from datetime import date

        from content.models import TaskAlert, TaskComment

        original = Task.objects.create(
            title='Source',
            status=Task.Status.TODO,
            is_archived=True,
            archive_reason='reason here',
        )
        TaskComment.objects.create(task=original, author=admin_user, text='note')
        TaskAlert.objects.create(task=original, notify_at=date(2030, 1, 1))

        response = admin_client.post(
            reverse('duplicate-task', kwargs={'task_id': original.id}), {}, format='json',
        )

        assert response.status_code == 201
        copy_id = response.json()['id']
        copy = Task.objects.get(pk=copy_id)
        assert copy.is_archived is False
        assert copy.archive_reason == ''
        assert copy.comments.count() == 0
        assert copy.alerts.count() == 0

    def test_nonexistent_task_returns_404(self, admin_client):
        response = admin_client.post(
            reverse('duplicate-task', kwargs={'task_id': 999999}), {}, format='json',
        )
        assert response.status_code == 404


class TestListTasksMacroBoard:
    def test_returns_macro_board_tasks_only(self, admin_client):
        Task.objects.create(title='Standard', board_type=Task.BoardType.STANDARD, status=Task.Status.TODO)
        Task.objects.create(title='Macro', board_type=Task.BoardType.MACRO, status=Task.Status.TODO)

        response = admin_client.get(reverse('list-tasks'), {'board': 'macro'})

        assert response.status_code == 200
        data = response.json()
        # MACRO board returns {'items': [...]} instead of status-grouped dict
        assert 'items' in data
        titles = [t['title'] for t in data['items']]
        assert 'Macro' in titles
        assert 'Standard' not in titles

    def test_invalid_board_type_returns_400(self, admin_client):
        response = admin_client.get(reverse('list-tasks'), {'board': 'does_not_exist'})
        assert response.status_code == 400


class TestArchiveTask:
    def test_archive_sets_is_archived_true(self, admin_client, todo_task):
        response = admin_client.patch(
            reverse('archive-task', kwargs={'task_id': todo_task.id}),
            {'archive_reason': 'No longer needed'},
            format='json',
        )
        assert response.status_code == 200
        todo_task.refresh_from_db()
        assert todo_task.is_archived is True
        assert todo_task.archive_reason == 'No longer needed'

    def test_unarchive_clears_archived_flag_and_reason(self, admin_client, todo_task):
        todo_task.is_archived = True
        todo_task.archive_reason = 'Old reason'
        todo_task.save(update_fields=['is_archived', 'archive_reason'])

        response = admin_client.patch(
            reverse('unarchive-task', kwargs={'task_id': todo_task.id}),
            {},
            format='json',
        )
        assert response.status_code == 200
        todo_task.refresh_from_db()
        assert todo_task.is_archived is False
        assert todo_task.archive_reason == ''

    def test_list_archived_returns_only_archived_tasks(self, admin_client, todo_task):
        Task.objects.create(title='Active', status=Task.Status.TODO)
        Task.objects.create(
            title='Archived', status=Task.Status.TODO, is_archived=True,
        )
        response = admin_client.get(reverse('list-archived-tasks'))
        assert response.status_code == 200
        titles = [t['title'] for t in response.json()]
        assert 'Archived' in titles
        assert 'Active' not in titles
        assert todo_task.title not in titles


class TestTaskComments:
    def test_create_comment_returns_201(self, admin_client, todo_task):
        response = admin_client.post(
            reverse('create-task-comment', kwargs={'task_id': todo_task.id}),
            {'text': 'This needs review.'},
            format='json',
        )
        assert response.status_code == 201
        assert response.json()['text'] == 'This needs review.'

    def test_list_comments_returns_all_comments(self, admin_client, todo_task):
        admin_client.post(
            reverse('create-task-comment', kwargs={'task_id': todo_task.id}),
            {'text': 'First comment'},
            format='json',
        )
        admin_client.post(
            reverse('create-task-comment', kwargs={'task_id': todo_task.id}),
            {'text': 'Second comment'},
            format='json',
        )
        response = admin_client.get(
            reverse('list-task-comments', kwargs={'task_id': todo_task.id}),
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_delete_comment_returns_204(self, admin_client, todo_task):
        create = admin_client.post(
            reverse('create-task-comment', kwargs={'task_id': todo_task.id}),
            {'text': 'To be deleted'},
            format='json',
        )
        comment_id = create.json()['id']
        response = admin_client.delete(
            reverse('delete-task-comment', kwargs={'task_id': todo_task.id, 'comment_id': comment_id}),
        )
        assert response.status_code == 204

    def test_delete_comment_wrong_task_returns_404(self, admin_client, todo_task):
        other_task = Task.objects.create(title='Other', status=Task.Status.TODO)
        create = admin_client.post(
            reverse('create-task-comment', kwargs={'task_id': todo_task.id}),
            {'text': 'Orphan'},
            format='json',
        )
        comment_id = create.json()['id']
        response = admin_client.delete(
            reverse('delete-task-comment', kwargs={'task_id': other_task.id, 'comment_id': comment_id}),
        )
        assert response.status_code == 404


class TestTaskAlerts:
    def test_create_alert_returns_201(self, admin_client, todo_task):
        response = admin_client.post(
            reverse('create-task-alert', kwargs={'task_id': todo_task.id}),
            {'notify_at': '2026-05-01', 'note': 'Check progress'},
            format='json',
        )
        assert response.status_code == 201
        assert response.json()['notify_at'] == '2026-05-01'

    def test_list_alerts_returns_all_alerts(self, admin_client, todo_task):
        admin_client.post(
            reverse('create-task-alert', kwargs={'task_id': todo_task.id}),
            {'notify_at': '2026-05-01'},
            format='json',
        )
        admin_client.post(
            reverse('create-task-alert', kwargs={'task_id': todo_task.id}),
            {'notify_at': '2026-05-15'},
            format='json',
        )
        response = admin_client.get(
            reverse('list-task-alerts', kwargs={'task_id': todo_task.id}),
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_delete_alert_returns_204(self, admin_client, todo_task):
        create = admin_client.post(
            reverse('create-task-alert', kwargs={'task_id': todo_task.id}),
            {'notify_at': '2026-05-01'},
            format='json',
        )
        alert_id = create.json()['id']
        response = admin_client.delete(
            reverse('delete-task-alert', kwargs={'task_id': todo_task.id, 'alert_id': alert_id}),
        )
        assert response.status_code == 204
