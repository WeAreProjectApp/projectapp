"""Tests for manual TaskAlert CRUD endpoints and Huey notification task."""
from unittest.mock import patch

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from content.models import Task, TaskAlert

User = get_user_model()


@pytest.fixture
def admin_client(db):
    user = User.objects.create_superuser(
        username='admin', password='pass', email='admin@test.com',
    )
    UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': UserProfile.ROLE_ADMIN},
    )
    client = Client()
    client.login(username='admin', password='pass')
    return client, user


@pytest.fixture
def task(db, admin_client):
    _, user = admin_client
    return Task.objects.create(
        title='Test task',
        status=Task.Status.TODO,
        priority=Task.Priority.MEDIUM,
    )


class TestListTaskAlerts(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin2', password='pass', email='admin2@test.com',
        )
        UserProfile.objects.get_or_create(
            user=self.user,
            defaults={'role': UserProfile.ROLE_ADMIN},
        )
        self.client.login(username='admin2', password='pass')
        self.task = Task.objects.create(title='My task', status=Task.Status.TODO)

    def test_empty_list(self):
        url = reverse('list-task-alerts', kwargs={'task_id': self.task.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_returns_alerts_ordered(self):
        today = timezone.localdate()
        a1 = TaskAlert.objects.create(task=self.task, notify_at=today, note='First')
        a2 = TaskAlert.objects.create(task=self.task, notify_at=today, note='Second')
        url = reverse('list-task-alerts', kwargs={'task_id': self.task.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        ids = [a['id'] for a in response.json()]
        self.assertEqual(ids, [a1.pk, a2.pk])

    def test_404_for_missing_task(self):
        url = reverse('list-task-alerts', kwargs={'task_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class TestCreateTaskAlert(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin3', password='pass', email='admin3@test.com',
        )
        UserProfile.objects.get_or_create(
            user=self.user,
            defaults={'role': UserProfile.ROLE_ADMIN},
        )
        self.client.login(username='admin3', password='pass')
        self.task = Task.objects.create(title='Task B', status=Task.Status.TODO)

    def test_create_alert(self):
        url = reverse('create-task-alert', kwargs={'task_id': self.task.pk})
        payload = {'notify_at': '2030-06-15', 'note': 'Check in with client'}
        response = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['notify_at'], '2030-06-15')
        self.assertEqual(data['note'], 'Check in with client')
        self.assertFalse(data['sent'])
        self.assertEqual(TaskAlert.objects.filter(task=self.task).count(), 1)

    def test_create_alert_without_note(self):
        url = reverse('create-task-alert', kwargs={'task_id': self.task.pk})
        response = self.client.post(url, data={'notify_at': '2030-07-01'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['note'], '')

    def test_create_alert_missing_date(self):
        url = reverse('create-task-alert', kwargs={'task_id': self.task.pk})
        response = self.client.post(url, data={'note': 'No date'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('notify_at', response.json())


class TestDeleteTaskAlert(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin4', password='pass', email='admin4@test.com',
        )
        UserProfile.objects.get_or_create(
            user=self.user,
            defaults={'role': UserProfile.ROLE_ADMIN},
        )
        self.client.login(username='admin4', password='pass')
        self.task = Task.objects.create(title='Task C', status=Task.Status.TODO)

    def test_delete_alert(self):
        alert = TaskAlert.objects.create(task=self.task, notify_at='2030-08-01')
        url = reverse('delete-task-alert', kwargs={'task_id': self.task.pk, 'alert_id': alert.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(TaskAlert.objects.filter(pk=alert.pk).exists())

    def test_cannot_delete_other_tasks_alert(self):
        other_task = Task.objects.create(title='Other task', status=Task.Status.TODO)
        alert = TaskAlert.objects.create(task=other_task, notify_at='2030-08-01')
        url = reverse('delete-task-alert', kwargs={'task_id': self.task.pk, 'alert_id': alert.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)


class TestCheckTaskAlertNotifications(TestCase):
    def setUp(self):
        self.task = Task.objects.create(title='Huey task', status=Task.Status.TODO)

    def test_sends_email_for_due_alerts_and_marks_sent(self):
        today = timezone.localdate()
        alert = TaskAlert.objects.create(task=self.task, notify_at=today, note='Now!')

        with patch('content.tasks._send_task_alert_email') as mock_send:
            from content.tasks import check_task_alert_notifications
            check_task_alert_notifications.call_local()

        mock_send.assert_called_once_with(alert)
        alert.refresh_from_db()
        self.assertTrue(alert.sent)

    def test_skips_already_sent_alerts(self):
        today = timezone.localdate()
        alert = TaskAlert.objects.create(task=self.task, notify_at=today, sent=True)

        with patch('content.tasks._send_task_alert_email') as mock_send:
            from content.tasks import check_task_alert_notifications
            check_task_alert_notifications.call_local()

        mock_send.assert_not_called()
        self.assertEqual(mock_send.call_count, 0)
        alert.refresh_from_db()
        self.assertTrue(alert.sent)

    def test_skips_future_alerts(self):
        from datetime import date, timedelta
        future = date.today() + timedelta(days=10)
        alert = TaskAlert.objects.create(task=self.task, notify_at=future)

        with patch('content.tasks._send_task_alert_email') as mock_send:
            from content.tasks import check_task_alert_notifications
            check_task_alert_notifications.call_local()

        mock_send.assert_not_called()
        alert.refresh_from_db()
        self.assertFalse(alert.sent)
