"""Tests for preview_sync_section (with-project path) and apply_sync_section."""
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from content.models import ProposalSection

pytestmark = pytest.mark.django_db


@pytest.fixture
def proposal_with_deliverable(proposal, admin_user):
    from accounts.models import Deliverable, Project
    from django.contrib.auth import get_user_model

    User = get_user_model()
    client_user = User.objects.create_user(
        username='deliv_client@test.com',
        email='deliv_client@test.com',
        password='testpass123',
    )
    project = Project.objects.create(name='Sync Test Project', client=client_user)
    deliverable = Deliverable.objects.create(
        project=project,
        title='MVP Deliverable',
        category='OTHER',
        source_epic_key='epic-1',
        source_epic_title='Main Epic',
        uploaded_by=admin_user,
    )
    proposal.deliverable = deliverable
    proposal.platform_onboarding_completed_at = timezone.now()
    proposal.save(update_fields=['deliverable', 'platform_onboarding_completed_at'])
    return proposal


@pytest.fixture
def technical_section(proposal):
    return ProposalSection.objects.create(
        proposal=proposal,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
        content_json={},
        order=14,
    )


@pytest.fixture
def technical_section_with_deliverable(proposal_with_deliverable):
    return ProposalSection.objects.create(
        proposal=proposal_with_deliverable,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
        content_json={},
        order=14,
    )


class TestPreviewSyncSectionWithProject:
    def _url(self, section):
        return reverse('section-sync-preview', kwargs={'section_id': section.id})

    def test_returns_has_project_true_with_deliverable(
        self, admin_client, technical_section_with_deliverable
    ):
        with patch(
            'accounts.services.technical_resources_sync.compute_sync_diff'
        ) as mock_diff:
            mock_diff.return_value = {'added': [], 'removed': [], 'unchanged': []}
            resp = admin_client.post(
                self._url(technical_section_with_deliverable),
                {'content_json': {'epics': []}},
                format='json',
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert data['has_project'] is True
        assert 'diff' in data
        assert 'project' in data
        assert 'deliverable' in data

    def test_calls_compute_sync_diff_once(
        self, admin_client, technical_section_with_deliverable
    ):
        with patch(
            'accounts.services.technical_resources_sync.compute_sync_diff'
        ) as mock_diff:
            mock_diff.return_value = {'added': [], 'removed': [], 'unchanged': []}
            resp = admin_client.post(
                self._url(technical_section_with_deliverable),
                {'content_json': {'epics': []}},
                format='json',
            )

        assert resp.status_code == 200
        mock_diff.assert_called_once()

    def test_returns_401_for_unauthenticated(self, api_client, technical_section_with_deliverable):
        resp = api_client.post(
            self._url(technical_section_with_deliverable),
            {'content_json': {'epics': []}},
            format='json',
        )

        assert resp.status_code == 401


class TestApplySyncSection:
    def _url(self, section):
        return reverse('section-apply-sync', kwargs={'section_id': section.id})

    def test_returns_400_for_non_technical_section(self, admin_client, proposal_section):
        resp = admin_client.post(
            self._url(proposal_section),
            {'content_json': {'epics': []}},
            format='json',
        )

        assert resp.status_code == 400
        assert 'technical_document' in resp.json()['detail']

    def test_returns_400_when_proposal_has_no_deliverable(
        self, admin_client, technical_section
    ):
        resp = admin_client.post(
            self._url(technical_section),
            {'content_json': {'epics': []}},
            format='json',
        )

        assert resp.status_code == 400
        assert 'no tiene proyecto asociado' in resp.json()['detail']

    def test_returns_400_for_non_dict_content_json(
        self, admin_client, technical_section_with_deliverable
    ):
        resp = admin_client.post(
            self._url(technical_section_with_deliverable),
            {'content_json': [1, 2, 3]},
            format='json',
        )

        assert resp.status_code == 400

    def test_returns_200_and_syncs_when_deliverable_present(
        self, admin_client, technical_section_with_deliverable
    ):
        with patch(
            'accounts.services.technical_resources_sync.sync_technical_resources_for_deliverable'
        ) as mock_sync:
            mock_sync.return_value = {'synced': 0, 'created': 0, 'updated': 0, 'deleted': 0}
            resp = admin_client.post(
                self._url(technical_section_with_deliverable),
                {'content_json': {'epics': []}},
                format='json',
            )

        assert resp.status_code == 200
        assert 'section' in resp.json()
        mock_sync.assert_called_once()

    def test_returns_401_for_unauthenticated(self, api_client, technical_section_with_deliverable):
        resp = api_client.post(
            self._url(technical_section_with_deliverable),
            {'content_json': {'epics': []}},
            format='json',
        )

        assert resp.status_code == 401
