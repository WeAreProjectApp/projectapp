"""Tests for contact API views.

Covers: POST /api/new-contact/ (happy path, validation errors) and that the
contact inbox is not exposed at GET /api/contacts/.
"""
from unittest.mock import patch

import pytest
from django.urls import resolve, reverse

from content.models import Contact

pytestmark = pytest.mark.django_db


class TestContactInboxIsNotExposed:
    def test_contacts_path_is_not_routed_to_a_data_view(self, api_client, contact):
        """Fails if a view that lists Contact messages is mounted at /api/contacts/ again."""
        match = resolve('/api/contacts/')
        response = api_client.get('/api/contacts/')

        assert match.url_name == 'nuxt-page'
        assert contact.email.encode() not in response.content


class TestNewContactView:
    @patch('content.views.contact.send_email_notification')
    def test_creates_contact_returns_201(self, mock_email, api_client):
        payload = {
            'email': 'new@example.com',
            'phone_number': '+573009999999',
            'subject': 'New project',
            'message': 'I want a website.',
            'budget': '10-20K',
        }
        response = api_client.post(reverse('new-contact'), payload, format='json')
        assert response.status_code == 201
        assert Contact.objects.count() == 1
        assert Contact.objects.first().email == 'new@example.com'
        mock_email.assert_called_once()

    @patch('content.views.contact.send_email_notification')
    def test_creates_contact_without_optional_fields(self, mock_email, api_client):
        payload = {
            'email': 'min@example.com',
            'phone_number': '123',
            'subject': 'Quick question',
        }
        response = api_client.post(reverse('new-contact'), payload, format='json')
        assert response.status_code == 201

    def test_returns_400_with_missing_email(self, api_client):
        payload = {
            'phone_number': '123',
            'subject': 'Test',
        }
        response = api_client.post(reverse('new-contact'), payload, format='json')
        assert response.status_code == 400
        assert 'email' in response.data

    def test_returns_400_with_invalid_email(self, api_client):
        payload = {
            'email': 'not-an-email',
            'phone_number': '123',
            'subject': 'Test',
        }
        response = api_client.post(reverse('new-contact'), payload, format='json')
        assert response.status_code == 400

    @patch('content.views.contact.send_email_notification')
    def test_email_notification_contains_subject(self, mock_email, api_client):
        payload = {
            'email': 'test@test.com',
            'phone_number': '123',
            'subject': 'Important Project',
            'message': 'Details here.',
        }
        api_client.post(reverse('new-contact'), payload, format='json')
        call_args = mock_email.call_args
        assert 'Important Project' in call_args[0][0]
