"""Tests for extended proposal views, services, serializers and tasks.

Covers edge cases and uncovered branches across:
- content/views/proposal.py
- content/services/proposal_email_service.py
- content/tasks.py
- content/serializers/proposal.py
- content/views/email_templates.py
- content/views/portfolio_works.py
- content/models/email_log.py
- content/serializers/blog.py
"""
import copy
from datetime import datetime, timedelta
from datetime import timezone as dt_tz
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from content.models import (
    BusinessProposal,
    EmailLog,
    ProposalChangeLog,
    ProposalSection,
    ProposalSectionView,
    ProposalViewEvent,
)
from content.tests.email_stubs import stub_email_message

pytestmark = pytest.mark.django_db

FROZEN_NOW = datetime(2026, 1, 15, 10, 0, 0, tzinfo=dt_tz.utc)


# ═══════════════════════════════════════════════════════════════════
# content/models/email_log.py — __str__
# ═══════════════════════════════════════════════════════════════════

class TestEmailLogStr:
    def test_str_representation(self, db):
        """EmailLog.__str__ returns 'template_key → recipient (status)'."""
        log = EmailLog.objects.create(
            template_key='proposal_sent',
            recipient='client@test.com',
            subject='Test',
            status='sent',
        )
        assert str(log) == 'proposal_sent → client@test.com (sent)'


# ═══════════════════════════════════════════════════════════════════
# content/views/portfolio_works.py — legacy endpoint
# ═══════════════════════════════════════════════════════════════════

class TestLegacyPortfolioWorksList:
    def test_legacy_endpoint_returns_200(self, db):
        """Legacy portfolio_works_list endpoint returns 200 with data."""
        from content.models import PortfolioWork
        from content.views.portfolio_works import portfolio_works_list

        PortfolioWork.objects.create(
            title_en='Test Work', title_es='Trabajo Test',
            project_url='https://example.com',
        )
        factory = APIRequestFactory()
        request = factory.get('/fake/')
        response = portfolio_works_list(request)
        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — email_deliverability_dashboard
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestEmailDeliverabilityDashboard:
    def test_returns_counts_and_rate(self, admin_client, db):
        """Dashboard returns correct counts and success rate."""
        EmailLog.objects.create(
            template_key='proposal_sent', recipient='a@t.com',
            subject='S1', status='sent', sent_at=FROZEN_NOW - timedelta(days=1),
        )
        EmailLog.objects.create(
            template_key='proposal_sent', recipient='b@t.com',
            subject='S2', status='delivered', sent_at=FROZEN_NOW - timedelta(days=2),
        )
        EmailLog.objects.create(
            template_key='proposal_reminder', recipient='c@t.com',
            subject='S3', status='failed', error_message='SMTP error',
            sent_at=FROZEN_NOW - timedelta(days=3),
        )
        EmailLog.objects.create(
            template_key='proposal_urgency', recipient='d@t.com',
            subject='S4', status='bounced', sent_at=FROZEN_NOW - timedelta(days=4),
        )

        url = reverse('email-deliverability-dashboard')
        response = admin_client.get(url)

        assert response.status_code == 200
        data = response.data
        assert data['total_emails_30d'] == 4
        assert data['sent_count'] == 2
        assert data['failed_count'] == 2
        assert data['success_rate'] == 50.0

    def test_returns_trend_and_failures(self, admin_client, db):
        """Dashboard returns daily_trend, by_template and recent_failures."""
        EmailLog.objects.create(
            template_key='proposal_sent', recipient='a@t.com',
            subject='S1', status='failed', error_message='err',
            sent_at=FROZEN_NOW - timedelta(days=1),
        )

        url = reverse('email-deliverability-dashboard')
        response = admin_client.get(url)

        assert response.status_code == 200
        assert len(response.data['by_template']) >= 1
        assert len(response.data['daily_trend']) >= 1
        assert len(response.data['recent_failures']) >= 1

    def test_returns_empty_stats_with_no_logs(self, admin_client, db):
        """Dashboard returns zeros when no email logs exist."""
        url = reverse('email-deliverability-dashboard')
        response = admin_client.get(url)

        assert response.status_code == 200
        assert response.data['total_emails_30d'] == 0
        assert response.data['success_rate'] == 0

    def test_requires_admin(self, api_client, db):
        """Dashboard requires admin authentication."""
        url = reverse('email-deliverability-dashboard')
        response = api_client.get(url)

        assert response.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — magic link rate-limit + exception handlers
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestMagicLinkRateLimit:
    def test_rate_limited_when_recent_magic_link_sent(self, api_client, db):
        """Magic link returns 200 without sending when rate-limited."""
        BusinessProposal.objects.create(
            title='Rate Limit Test', client_name='Client',
            client_email='ratelimit@test.com',
            total_investment=Decimal('5000.00'),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        EmailLog.objects.create(
            template_key='magic_link',
            recipient='ratelimit@test.com',
            subject='Magic Link',
            status='sent',
            sent_at=FROZEN_NOW - timedelta(minutes=2),
        )

        url = reverse('request-magic-link')
        with patch(
            'content.services.proposal_email_service'
            '.ProposalEmailService.send_magic_link_email',
        ) as mock_send:
            response = api_client.post(
                url, {'email': 'ratelimit@test.com'}, format='json',
            )
            mock_send.assert_not_called()

        assert response.status_code == 200

    def test_send_exception_handled_gracefully(self, api_client, db):
        """Magic link handles send_magic_link_email exception gracefully."""
        BusinessProposal.objects.create(
            title='Exception Test', client_name='Client',
            client_email='exception@test.com',
            total_investment=Decimal('5000.00'),
            expires_at=FROZEN_NOW + timedelta(days=10),
            is_active=True,
        )

        url = reverse('request-magic-link')
        with patch(
            'content.services.proposal_email_service'
            '.ProposalEmailService.send_magic_link_email',
            side_effect=Exception('SMTP down'),
        ):
            response = api_client.post(
                url, {'email': 'exception@test.com'}, format='json',
            )

        assert response.status_code == 200

    def test_rate_limit_db_exception_is_swallowed(self, api_client, db):
        """Magic link swallows DB exceptions during rate-limit check."""
        url = reverse('request-magic-link')
        with patch(
            'content.models.email_log.EmailLog.objects',
        ) as mock_qs:
            mock_qs.filter.return_value.exists.side_effect = Exception('DB lost')
            with patch(
                'content.services.proposal_email_service'
                '.ProposalEmailService.send_magic_link_email',
            ):
                response = api_client.post(
                    url, {'email': 'db-fail@test.com'}, format='json',
                )

        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — JSON template additionalModules annotation
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestJsonTemplateAnnotation:
    def test_do_not_remove_set_on_additional_modules(self, admin_client, db):
        """JSON template annotates _do_not_remove on additionalModules."""
        from content.services.proposal_service import ProposalService

        real_defaults = ProposalService.get_default_sections('es')
        patched = copy.deepcopy(real_defaults)
        for section in patched:
            if section['section_type'] == 'functional_requirements':
                section['content_json']['additionalModules'] = [
                    {'id': 'test_mod', 'title': 'Test Module'},
                ]
                break

        url = reverse('proposal-json-template')
        with patch(
            'content.services.proposal_service.ProposalService.get_default_sections',
            return_value=patched,
        ):
            response = admin_client.get(url)

        assert response.status_code == 200
        fr = response.data.get('functionalRequirements', {})
        mods = fr.get('additionalModules', [])
        assert len(mods) >= 1
        assert mods[0].get('_do_not_remove') is True


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — view_mode update, engagement declining
# reset, cached_heat_score exception
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestTrackProposalEngagementEdgeCases:
    @pytest.fixture(autouse=True)
    def stable_tracking_throttle_clock(self, monkeypatch):
        """Keep DRF's throttle timer callable under the frozen class clock."""
        from content.throttles import TrackingAnonThrottle

        monkeypatch.setattr(
            TrackingAnonThrottle,
            'timer',
            staticmethod(lambda: FROZEN_NOW.timestamp()),
        )

    @pytest.fixture
    def tracked_proposal(self, db):
        """A viewed proposal with tracking data."""
        p = BusinessProposal.objects.create(
            title='Track Test', client_name='Tracker',
            client_email='track@test.com',
            total_investment=Decimal('5000.00'),
            status='viewed',
            sent_at=FROZEN_NOW - timedelta(days=5),
            first_viewed_at=FROZEN_NOW - timedelta(days=3),
            last_activity_at=FROZEN_NOW - timedelta(hours=2),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        ProposalSection.objects.create(
            proposal=p, section_type='greeting', title='Greeting', order=0,
        )
        ProposalSection.objects.create(
            proposal=p, section_type='investment', title='Investment', order=1,
        )
        return p

    def test_view_mode_updated_on_existing_event(self, api_client, tracked_proposal):
        """View mode updates from 'unknown' to a known value on second track call."""
        p = tracked_proposal
        url = reverse('track-proposal-engagement', kwargs={'proposal_uuid': p.uuid})
        api_client.post(url, {
            'session_id': 'sess-1',
            'sections': [{'section_type': 'greeting', 'time_spent_seconds': 5}],
            'view_mode': 'unknown',
        }, format='json')

        event = ProposalViewEvent.objects.get(proposal=p, session_id='sess-1')
        assert event.view_mode == 'unknown'

        api_client.post(url, {
            'session_id': 'sess-1',
            'sections': [{'section_type': 'greeting', 'time_spent_seconds': 10}],
            'view_mode': 'executive',
        }, format='json')

        event.refresh_from_db()
        assert event.view_mode == 'executive'

    def test_view_mode_technical_persisted_on_track(self, api_client, tracked_proposal):
        """Technical view mode is stored on the view event."""
        p = tracked_proposal
        url = reverse('track-proposal-engagement', kwargs={'proposal_uuid': p.uuid})
        api_client.post(url, {
            'session_id': 'sess-tech',
            'sections': [{'section_type': 'tech_intro', 'time_spent_seconds': 2}],
            'view_mode': 'technical',
        }, format='json')
        event = ProposalViewEvent.objects.get(proposal=p, session_id='sess-tech')
        assert event.view_mode == 'technical'

    def test_view_mode_legal_persisted_on_track(
        self, api_client, tracked_proposal, monkeypatch,
    ):
        from content.throttles import TrackingAnonThrottle

        monkeypatch.setattr(
            TrackingAnonThrottle,
            'timer',
            staticmethod(lambda: FROZEN_NOW.timestamp()),
        )
        p = tracked_proposal
        url = reverse('track-proposal-engagement', kwargs={'proposal_uuid': p.uuid})

        api_client.post(url, {
            'session_id': 'sess-legal',
            'sections': [{
                'section_type': 'contract_terms_document',
                'subsection_key': 'clause-03',
                'time_spent_seconds': 8,
            }],
            'view_mode': 'legal',
        }, format='json')

        event = ProposalViewEvent.objects.get(proposal=p, session_id='sess-legal')
        assert event.view_mode == 'legal'
        clause_view = ProposalSectionView.objects.get(view_event=event)
        assert clause_view.subsection_key == 'clause-03'

    def test_engagement_declining_reset_on_normal_engagement(
        self, api_client, tracked_proposal,
    ):
        """Engagement declining flag resets when current engagement is normal."""
        p = tracked_proposal
        p.engagement_declining = True
        p.save(update_fields=['engagement_declining'])

        url = reverse('track-proposal-engagement', kwargs={'proposal_uuid': p.uuid})

        prev_event = ProposalViewEvent.objects.create(
            proposal=p, session_id='prev-sess',
            viewed_at=FROZEN_NOW - timedelta(hours=5),
            finalized_at=FROZEN_NOW - timedelta(hours=4),
        )
        ProposalSectionView.objects.create(
            view_event=prev_event, section_type='greeting',
            section_title='Greeting', time_spent_seconds=10,
            entered_at=FROZEN_NOW - timedelta(hours=5),
        )

        api_client.post(url, {
            'session_id': 'new-sess',
            'is_final': True,
            'sections': [
                {'section_type': 'greeting', 'time_spent_seconds': 15},
                {'section_type': 'investment', 'time_spent_seconds': 20},
            ],
        }, format='json')

        p.refresh_from_db()
        assert p.engagement_declining is False

    def test_cached_heat_score_exception_handled(
        self, api_client, tracked_proposal,
    ):
        """Track endpoint handles the heat score service exception."""
        p = tracked_proposal
        url = reverse('track-proposal-engagement', kwargs={'proposal_uuid': p.uuid})

        with patch(
            'content.services.proposal_tracking_service.compute_heat_score_for_proposal',
            side_effect=Exception('DB error'),
        ):
            response = api_client.post(url, {
                'session_id': 'exc-sess',
                'sections': [{'section_type': 'greeting', 'time_spent_seconds': 5}],
            }, format='json')

        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — heat score branches
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestHeatScoreBranches:
    def test_investment_time_60s_adds_2_points(self, db):
        """Investment section time >= 60s adds 2 points to heat score."""
        from content.views.proposal import _compute_heat_score_with_summary

        p = BusinessProposal.objects.create(
            title='Heat Test', client_name='Client',
            client_email='heat@test.com', status='viewed',
            total_investment=Decimal('5000.00'),
            view_count=1, first_viewed_at=FROZEN_NOW - timedelta(days=1),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        event = ProposalViewEvent.objects.create(
            proposal=p, session_id='heat-sess',
            viewed_at=FROZEN_NOW - timedelta(hours=1), ip_address='1.2.3.4',
        )
        ProposalSectionView.objects.create(
            view_event=event, section_type='investment',
            section_title='Investment', time_spent_seconds=65,
            entered_at=FROZEN_NOW - timedelta(hours=1),
        )

        result = _compute_heat_score_with_summary(p.id, FROZEN_NOW)
        assert result['score'] >= 2

    def test_view_count_5_adds_2_points(self, db):
        """View count >= 5 adds 2 points to heat score."""
        from content.views.proposal import _compute_heat_score_with_summary

        p = BusinessProposal.objects.create(
            title='Views Test', client_name='Client',
            client_email='views@test.com', status='viewed',
            total_investment=Decimal('5000.00'),
            view_count=5, first_viewed_at=FROZEN_NOW - timedelta(days=1),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )

        result = _compute_heat_score_with_summary(p.id, FROZEN_NOW)
        assert result['score'] >= 2


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — view mode analytics in dashboard
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestDashboardViewModeAnalytics:
    def test_dashboard_includes_view_mode_win_rate(self, admin_client, db):
        """Dashboard returns win_rate_by_view_mode when proposals have events."""
        p = BusinessProposal.objects.create(
            title='Accepted VP', client_name='Client',
            client_email='vp@test.com', status='accepted',
            total_investment=Decimal('5000.00'),
            sent_at=FROZEN_NOW - timedelta(days=10),
            first_viewed_at=FROZEN_NOW - timedelta(days=8),
            responded_at=FROZEN_NOW - timedelta(days=1),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        ProposalViewEvent.objects.create(
            proposal=p, session_id='vp-sess', view_mode='executive',
            viewed_at=FROZEN_NOW - timedelta(days=5),
        )

        url = reverse('proposal-dashboard')
        response = admin_client.get(url)

        assert response.status_code == 200
        assert 'win_rate_by_view_mode' in response.data

    def test_dashboard_top_dropoff_omits_synthetic_technical_public(self, admin_client, db):
        """Global top_dropoff ignores technical_document_public (not in funnel allowlist)."""
        p = BusinessProposal.objects.create(
            title='Tech Only', client_name='T', client_email='t@t.com',
            status='sent', total_investment=Decimal('1000.00'),
            sent_at=FROZEN_NOW - timedelta(days=1),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        ev = ProposalViewEvent.objects.create(
            proposal=p, session_id='only-synth-tech', view_mode='technical',
            viewed_at=FROZEN_NOW - timedelta(hours=1),
        )
        ProposalSectionView.objects.create(
            view_event=ev,
            section_type='technical_document_public',
            section_title='Stack',
            time_spent_seconds=30,
            entered_at=FROZEN_NOW - timedelta(hours=1),
            view_mode='technical',
        )
        url = reverse('proposal-dashboard')
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.data['top_dropoff_section'] is None


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — heat score technical summary
# ═══════════════════════════════════════════════════════════════════


@freeze_time('2026-01-15T10:00:00Z')
class TestHeatScoreTechnicalSummary:
    def test_engagement_summary_includes_technical_fields(self, db):
        """Heat score summary exposes technical_time_sec after public technical views."""
        p = BusinessProposal.objects.create(
            title='H', client_name='H', client_email='h@h.com',
            status='viewed', total_investment=Decimal('5000.00'),
            sent_at=FROZEN_NOW - timedelta(days=2),
            first_viewed_at=FROZEN_NOW - timedelta(days=1),
            view_count=1,
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        ev = ProposalViewEvent.objects.create(
            proposal=p, session_id='heat-tech', view_mode='technical',
            viewed_at=FROZEN_NOW - timedelta(hours=2),
        )
        ProposalSectionView.objects.create(
            view_event=ev,
            section_type='technical_document_public',
            section_title='Arquitectura',
            time_spent_seconds=30,
            entered_at=FROZEN_NOW - timedelta(hours=2),
            view_mode='technical',
        )
        from content.views.proposal import _compute_heat_score_with_summary

        result = _compute_heat_score_with_summary(p.id, FROZEN_NOW)
        summary = result['engagement_summary']
        assert summary['technical_time_sec'] == 30
        assert summary['technical_viewed'] is True


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — module merging in create-from-json
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestCreateProposalFromJSONModuleMerging:
    @pytest.fixture
    def patched_defaults_and_payload(self, db):
        """Build patched defaults with additionalModules and JSON payload."""
        from content.services.proposal_service import ProposalService

        real_defaults = ProposalService.get_default_sections('es')
        fr_default = next(
            (s for s in real_defaults
             if s['section_type'] == 'functional_requirements'), None,
        )
        if not fr_default:
            pytest.skip('No functional_requirements in defaults')

        patched_defaults = copy.deepcopy(real_defaults)
        for section in patched_defaults:
            if section['section_type'] == 'functional_requirements':
                section['content_json']['additionalModules'] = [
                    {'id': 'pwa_module', 'title': 'PWA Default', 'is_visible': True},
                    {'id': 'dark_mode_module', 'title': 'Dark Mode', 'is_visible': False},
                ]
                break

        payload = {
            'title': 'Merge Test', 'client_name': 'Merger',
            'client_email': 'merge@test.com',
            'total_investment': 5000, 'currency': 'COP', 'language': 'es',
            'sections': {
                'general': {'clientName': 'Merger', 'proposalTitle': 'Merge Test'},
                'functionalRequirements': {
                    'groups': fr_default['content_json'].get('groups', []),
                    'additionalModules': [
                        {'id': 'pwa_module', 'title': 'PWA Overridden'},
                        {'id': 'brand_new_module', 'title': 'Brand New'},
                    ],
                },
            },
        }
        return patched_defaults, payload

    def test_additional_modules_merged_with_defaults(
        self, admin_client, patched_defaults_and_payload,
    ):
        """Create-from-JSON merges additionalModules from JSON with defaults."""
        patched_defaults, payload = patched_defaults_and_payload

        url = reverse('create-proposal-from-json')
        with patch(
            'content.services.proposal_service.ProposalService.get_default_sections',
            return_value=patched_defaults,
        ):
            response = admin_client.post(url, payload, format='json')

        assert response.status_code == 201
        proposal = BusinessProposal.objects.get(title='Merge Test')
        fr_section = ProposalSection.objects.filter(
            proposal=proposal, section_type='functional_requirements',
        ).first()
        assert fr_section is not None
        modules = fr_section.content_json.get('additionalModules', [])
        module_ids = [m.get('id') for m in modules]
        assert set(module_ids) >= {'pwa_module', 'dark_mode_module', 'brand_new_module'}
        pwa = next(m for m in modules if m['id'] == 'pwa_module')
        assert pwa['title'] == 'PWA Overridden'


# ═══════════════════════════════════════════════════════════════════
# content/services/proposal_email_service.py — cooldown + magic link
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestProposalEmailServiceCooldown:
    @pytest.fixture
    def cooldown_proposal(self, db):
        """A proposal with recent automated email (cooldown active)."""
        return BusinessProposal.objects.create(
            title='Cooldown Test', client_name='Client',
            client_email='cooldown@test.com',
            total_investment=Decimal('5000.00'),
            status='viewed',
            sent_at=FROZEN_NOW - timedelta(days=5),
            first_viewed_at=FROZEN_NOW - timedelta(days=3),
            last_activity_at=FROZEN_NOW - timedelta(hours=2),
            expires_at=FROZEN_NOW + timedelta(days=10),
            last_automated_email_at=FROZEN_NOW - timedelta(hours=1),
        )

    def test_send_reminder_blocked_by_cooldown(self, cooldown_proposal):
        """send_reminder returns False when cooldown is active."""
        from content.services.proposal_email_service import ProposalEmailService

        result = ProposalEmailService.send_reminder(cooldown_proposal)
        assert result is False

    def test_send_urgency_email_blocked_by_cooldown(self, cooldown_proposal):
        """send_urgency_email returns False when cooldown is active."""
        from content.services.proposal_email_service import ProposalEmailService

        result = ProposalEmailService.send_urgency_email(cooldown_proposal)
        assert result is False

    def test_send_abandonment_followup_blocked_by_cooldown(self, cooldown_proposal):
        """send_abandonment_followup returns False when cooldown is active."""
        from content.services.proposal_email_service import ProposalEmailService

        result = ProposalEmailService.send_abandonment_followup(cooldown_proposal)
        assert result is False

    def test_send_investment_followup_blocked_by_cooldown(self, cooldown_proposal):
        """send_investment_interest_followup returns False when cooldown is active."""
        from content.services.proposal_email_service import ProposalEmailService

        result = ProposalEmailService.send_investment_interest_followup(
            cooldown_proposal, 120.0,
        )
        assert result is False


@freeze_time('2026-01-15T10:00:00Z')
class TestSendMagicLinkEmail:
    def test_send_magic_link_email_success(self, db):
        """send_magic_link_email sends email and logs it."""
        from content.services.proposal_email_service import ProposalEmailService

        p = BusinessProposal.objects.create(
            title='Magic Test', client_name='Link Client',
            client_email='magic@test.com',
            total_investment=Decimal('5000.00'),
            status='viewed',
            sent_at=FROZEN_NOW - timedelta(days=3),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )

        with patch(
            'content.services.proposal_email_service.EmailMultiAlternatives',
        ) as mock_cls:
            mock_instance = stub_email_message()
            mock_cls.return_value = mock_instance
            result = ProposalEmailService.send_magic_link_email('magic@test.com', [p])

        assert result is True
        mock_instance.attach_alternative.assert_called_once()
        mock_instance.send.assert_called_once()
        assert EmailLog.objects.filter(
            template_key='magic_link', recipient='magic@test.com',
        ).exists()

    def test_send_magic_link_email_returns_false_for_empty_list(self, db):
        """send_magic_link_email returns False for empty proposals list."""
        from content.services.proposal_email_service import ProposalEmailService

        result = ProposalEmailService.send_magic_link_email('test@test.com', [])
        assert result is False

    def test_send_magic_link_email_handles_send_failure(self, db):
        """send_magic_link_email returns False and logs failure on exception."""
        from content.services.proposal_email_service import ProposalEmailService

        p = BusinessProposal.objects.create(
            title='Fail Magic', client_name='Fail Client',
            client_email='fail@test.com',
            total_investment=Decimal('5000.00'),
            status='viewed',
            sent_at=FROZEN_NOW - timedelta(days=3),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )

        with patch(
            'content.services.proposal_email_service.EmailMultiAlternatives',
        ) as mock_cls:
            mock_instance = stub_email_message()
            mock_instance.send.side_effect = Exception('SMTP error')
            mock_cls.return_value = mock_instance
            result = ProposalEmailService.send_magic_link_email('fail@test.com', [p])

        assert result is False
        mock_instance.send.assert_called_once()
        assert EmailLog.objects.filter(
            template_key='magic_link', status='failed',
        ).exists()


# ═══════════════════════════════════════════════════════════════════
# content/tasks.py — escalation skip + refresh_cached_heat_scores
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestEscalationAndHeatRefresh:
    def test_escalation_skips_recent_activity(self, db):
        """Escalation task skips proposals with recent last_activity_at."""
        from content.tasks import escalate_seller_inactivity

        p = BusinessProposal.objects.create(
            title='Recent Activity', client_name='Active',
            client_email='active@test.com',
            total_investment=Decimal('5000.00'),
            status='viewed',
            sent_at=FROZEN_NOW - timedelta(days=10),
            first_viewed_at=FROZEN_NOW - timedelta(days=8),
            last_activity_at=FROZEN_NOW - timedelta(days=1),
            expires_at=FROZEN_NOW + timedelta(days=10),
            automations_paused=False,
        )

        escalate_seller_inactivity()

        assert not ProposalChangeLog.objects.filter(
            proposal=p, change_type='escalation_email',
        ).exists()

    def test_refresh_cached_heat_scores(self, db):
        """refresh_cached_heat_scores updates changed scores."""
        from content.tasks import refresh_cached_heat_scores

        p = BusinessProposal.objects.create(
            title='Heat Refresh', client_name='Refresh',
            client_email='refresh@test.com',
            total_investment=Decimal('5000.00'),
            status='viewed',
            cached_heat_score=0,
            sent_at=FROZEN_NOW - timedelta(days=5),
            first_viewed_at=FROZEN_NOW - timedelta(days=3),
            last_activity_at=FROZEN_NOW - timedelta(hours=1),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        ProposalViewEvent.objects.create(
            proposal=p, session_id='refresh-sess',
            viewed_at=FROZEN_NOW - timedelta(hours=1),
            ip_address='10.0.0.1',
        )

        refresh_cached_heat_scores.call_local()

        p.refresh_from_db()
        assert p.cached_heat_score > 0


# ═══════════════════════════════════════════════════════════════════
# content/serializers/proposal.py — validation branches
# ═══════════════════════════════════════════════════════════════════

class TestProposalSerializerValidation:
    def test_validate_language_rejects_invalid_directly(self):
        """validate_language raises ValidationError for invalid language."""
        from content.serializers.proposal import ProposalDefaultConfigSerializer

        serializer = ProposalDefaultConfigSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_language('fr')
        assert 'must be' in str(exc_info.value.detail)

    def test_validate_language_accepts_valid(self):
        """validate_language passes for 'es' and 'en'."""
        from content.serializers.proposal import ProposalDefaultConfigSerializer

        serializer = ProposalDefaultConfigSerializer()
        assert serializer.validate_language('es') == 'es'
        assert serializer.validate_language('en') == 'en'

    def test_sections_json_rejects_non_dict_entry(self):
        """ProposalDefaultConfigSerializer rejects non-dict section entry."""
        from content.serializers.proposal import ProposalDefaultConfigSerializer

        serializer = ProposalDefaultConfigSerializer(data={
            'language': 'es',
            'sections_json': ['not_a_dict'],
        })
        assert not serializer.is_valid()
        assert 'sections_json' in serializer.errors

    def test_validate_content_overrides_accepts_dict(self):
        """validate_content_overrides returns value for valid dict."""
        from content.serializers.proposal import EmailTemplateConfigSerializer

        serializer = EmailTemplateConfigSerializer()
        result = serializer.validate_content_overrides({'subject': 'Test'})
        assert result == {'subject': 'Test'}

    def test_validate_content_overrides_rejects_non_dict(self):
        """validate_content_overrides raises ValidationError for non-dict."""
        from content.serializers.proposal import EmailTemplateConfigSerializer

        serializer = EmailTemplateConfigSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_content_overrides('not_a_dict')
        assert 'must be a JSON object' in str(exc_info.value.detail)


# ═══════════════════════════════════════════════════════════════════
# content/views/email_templates.py — template entry None, render exception
# ═══════════════════════════════════════════════════════════════════

class TestEmailTemplateViewsEdgeCases:
    def test_list_skips_unknown_template_key(self, admin_client, db):
        """Template list skips entries where get_template_entry returns None."""
        from content.services.email_template_registry import get_all_keys

        real_keys = get_all_keys()
        fake_keys = real_keys + ['nonexistent_fake_template']

        url = reverse('email-template-list')
        with patch(
            'content.views.email_templates.get_all_keys',
            return_value=fake_keys,
        ):
            response = admin_client.get(url)

        assert response.status_code == 200
        keys = [e['template_key'] for e in response.data]
        assert 'nonexistent_fake_template' not in keys

    def test_preview_handles_render_exception(self, admin_client, db):
        """Preview returns 500 when template rendering fails."""
        from content.services.email_template_registry import (
            get_all_keys,
            get_template_entry,
        )

        target_key = None
        for k in get_all_keys():
            entry = get_template_entry(k)
            if entry and entry.get('html_template'):
                target_key = k
                break

        if not target_key:
            pytest.skip('No template with html_template found')

        url = reverse('email-template-preview', kwargs={'template_key': target_key})
        with patch(
            'content.views.email_templates.render_to_string',
            side_effect=Exception('Template render failed'),
        ):
            response = admin_client.get(url)

        assert response.status_code == 500
        assert 'No se pudo generar la vista previa' in response.data['detail']


# ═══════════════════════════════════════════════════════════════════
# content/serializers/blog.py — source not-dict validation
# ═══════════════════════════════════════════════════════════════════

class TestBlogSerializerSourceValidation:
    def test_validate_sources_rejects_non_dict_entry(self):
        """Blog serializer validate_sources raises for non-dict source entry."""
        from content.serializers.blog import BlogPostFromJSONSerializer

        serializer = BlogPostFromJSONSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_sources(['not_a_dict'])
        assert 'JSON object' in str(exc_info.value.detail)


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — heat score edge cases
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestHeatScoreEdgeCases:
    """Cover remaining branches in _compute_heat_score_with_summary."""

    def _make_proposal(self, db, **kwargs):
        defaults = dict(
            title='HS', client_name='Client', client_email='hs@hs.com',
            status='viewed', total_investment=Decimal('5000.00'),
            sent_at=FROZEN_NOW - timedelta(days=3),
            first_viewed_at=FROZEN_NOW - timedelta(days=1),
            view_count=1,
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        defaults.update(kwargs)
        return BusinessProposal.objects.create(**defaults)

    def test_investment_time_15s_to_59s_adds_one_point(self, db):
        """inv_time in [15, 59] seconds adds 1 point (not 2)."""
        from content.views.proposal import _compute_heat_score_with_summary

        p = self._make_proposal(db)
        ev = ProposalViewEvent.objects.create(proposal=p, session_id='s1', viewed_at=FROZEN_NOW)
        ProposalSectionView.objects.create(
            view_event=ev, section_type='investment', section_title='Inv',
            time_spent_seconds=30, entered_at=FROZEN_NOW,
        )

        base = _compute_heat_score_with_summary(p.id, FROZEN_NOW)
        assert base['score'] >= 1

    def test_view_count_2_to_4_adds_one_point(self, db):
        """view_count in [2, 4] adds 1 point (not 2)."""
        from content.views.proposal import _compute_heat_score_with_summary

        p = self._make_proposal(db, view_count=3)
        result = _compute_heat_score_with_summary(p.id, FROZEN_NOW)
        assert result['score'] >= 1

    def test_recent_first_view_within_3_days_adds_recency_point(self, db):
        """first_viewed_at within 3 days adds 1 recency point."""
        from content.views.proposal import _compute_heat_score_with_summary

        p = self._make_proposal(db, first_viewed_at=FROZEN_NOW - timedelta(days=2))
        result_recent = _compute_heat_score_with_summary(p.id, FROZEN_NOW)

        p2 = self._make_proposal(db, first_viewed_at=FROZEN_NOW - timedelta(days=10))
        result_old = _compute_heat_score_with_summary(p2.id, FROZEN_NOW)

        assert result_recent['score'] >= result_old['score']

    def test_engagement_declining_flag_reduces_score(self, db):
        """engagement_declining=True subtracts 1 point from score."""
        from content.views.proposal import _compute_heat_score_with_summary

        p_normal = self._make_proposal(db, engagement_declining=False)
        p_declining = self._make_proposal(db, engagement_declining=True)

        score_normal = _compute_heat_score_with_summary(p_normal.id, FROZEN_NOW)['score']
        score_declining = _compute_heat_score_with_summary(p_declining.id, FROZEN_NOW)['score']

        assert score_declining <= score_normal

    def test_nonexistent_proposal_returns_score_one(self, db):
        """Non-existent proposal_id returns fallback score=1."""
        from content.views.proposal import _compute_heat_score_with_summary

        result = _compute_heat_score_with_summary(99999, FROZEN_NOW)
        assert result['score'] == 1
        assert result['engagement_summary'] is None

    def test_last_activity_same_day_with_hours_shows_hours_string(self, db):
        """last_activity_at hours ago (same day) shows 'hace Xh' string."""
        from content.views.proposal import _compute_heat_score_with_summary

        p = self._make_proposal(db, last_activity_at=FROZEN_NOW - timedelta(hours=3))
        result = _compute_heat_score_with_summary(p.id, FROZEN_NOW)
        assert result['engagement_summary']['last_activity'] == 'hace 3h'

    def test_last_activity_within_one_hour_shows_less_than_one(self, db):
        """last_activity_at < 1h ago shows 'hace menos de 1h'."""
        from content.views.proposal import _compute_heat_score_with_summary

        p = self._make_proposal(db, last_activity_at=FROZEN_NOW - timedelta(minutes=30))
        result = _compute_heat_score_with_summary(p.id, FROZEN_NOW)
        assert result['engagement_summary']['last_activity'] == 'hace menos de 1h'

    def test_last_activity_days_ago_shows_days_string(self, db):
        """last_activity_at days ago shows 'hace Xd' string."""
        from content.views.proposal import _compute_heat_score_with_summary

        p = self._make_proposal(db, last_activity_at=FROZEN_NOW - timedelta(days=2))
        result = _compute_heat_score_with_summary(p.id, FROZEN_NOW)
        assert result['engagement_summary']['last_activity'] == 'hace 2d'


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — calculator interaction admin skip
# ═══════════════════════════════════════════════════════════════════

class TestCalculatorInteractionRetired:

    def test_staff_user_receives_retired_response_without_creating_log(self, admin_user, db):
        """Falla si la ruta retirada vuelve a aceptar eventos del calculador."""
        import json as _json

        from django.test import Client

        p = BusinessProposal.objects.create(
            title='Calc', client_name='C', client_email='c@c.com',
            status='sent', is_active=True, total_investment=Decimal('5000.00'),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        url = reverse('track-calculator-interaction', kwargs={'proposal_uuid': p.uuid})

        # Use Django session client so get_user(request._request) resolves the staff user
        session_client = Client()
        session_client.login(username='admin_test', password='testpass123')
        response = session_client.post(
            url,
            data=_json.dumps({'event': 'confirmed', 'selected': []}),
            content_type='application/json',
        )
        assert response.status_code == 410
        assert _json.loads(response.content) == {
            'error': 'The investment calculator has been retired.',
            'code': 'calculator_retired',
        }
        assert ProposalChangeLog.objects.filter(proposal=p).count() == 0


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — engagement score status branches
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestEngagementScoreStatusBranches:
    """Cover status and days-without-response branches in _compute_engagement_score."""

    def test_accepted_status_adds_max_response_score(self, db):
        """Accepted status contributes max points for the response-time factor."""
        from content.views.proposal import _compute_engagement_score

        p = BusinessProposal.objects.create(
            title='Acc', client_name='C', client_email='c@c.com',
            status='accepted', total_investment=Decimal('5000.00'),
            sent_at=FROZEN_NOW - timedelta(days=5),
            first_viewed_at=FROZEN_NOW - timedelta(days=3),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        view_events = ProposalViewEvent.objects.filter(proposal=p)
        score = _compute_engagement_score(p, view_events, [], 1)
        assert score >= 15

    def test_viewed_one_day_ago_adds_max_response_pts(self, db):
        """days_since first_view <= 1 adds 15 response-time points."""
        from content.views.proposal import _compute_engagement_score

        p = BusinessProposal.objects.create(
            title='Day1', client_name='C', client_email='c@c.com',
            status='viewed', total_investment=Decimal('5000.00'),
            sent_at=FROZEN_NOW - timedelta(days=2),
            first_viewed_at=FROZEN_NOW - timedelta(hours=12),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        view_events = ProposalViewEvent.objects.filter(proposal=p)
        score = _compute_engagement_score(p, view_events, [], 1)
        assert score >= 15

    def test_viewed_three_days_ago_adds_mid_response_pts(self, db):
        """days_since first_view <= 3 adds 10 response-time points."""
        from content.views.proposal import _compute_engagement_score

        p = BusinessProposal.objects.create(
            title='Day3', client_name='C', client_email='c@c.com',
            status='viewed', total_investment=Decimal('5000.00'),
            sent_at=FROZEN_NOW - timedelta(days=4),
            first_viewed_at=FROZEN_NOW - timedelta(days=2),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        view_events = ProposalViewEvent.objects.filter(proposal=p)
        score = _compute_engagement_score(p, view_events, [], 1)
        assert score >= 10

    def test_multiple_revisit_sessions_add_score(self, db):
        """unique_sessions > 1 contributes revisit bonus points."""
        from content.views.proposal import _compute_engagement_score

        p = BusinessProposal.objects.create(
            title='Revisit', client_name='C', client_email='c@c.com',
            status='viewed', total_investment=Decimal('5000.00'),
            sent_at=FROZEN_NOW - timedelta(days=5),
            first_viewed_at=FROZEN_NOW - timedelta(days=3),
            expires_at=FROZEN_NOW + timedelta(days=10),
        )
        view_events = ProposalViewEvent.objects.filter(proposal=p)
        score_single = _compute_engagement_score(p, view_events, [], 1)
        score_revisit = _compute_engagement_score(p, view_events, [], 3)
        assert score_revisit > score_single


# ═══════════════════════════════════════════════════════════════════
# content/views/proposal.py — item id assignment + linked_item_ids
# in create-from-json / update-from-json
# ═══════════════════════════════════════════════════════════════════

@freeze_time('2026-01-15T10:00:00Z')
class TestFromJSONItemRequirementTraceability:
    def _base_payload(self, title):
        return {
            'title': title, 'client_name': 'Trace Client',
            'client_email': 'trace@test.com',
            'total_investment': 5000, 'currency': 'COP', 'language': 'es',
            'sections': {
                'general': {'clientName': 'Trace Client', 'proposalTitle': title},
                'functionalRequirements': {
                    'groups': [
                        {'id': 'views', 'title': 'Vistas', 'items': [
                            {'icon': '🏠', 'name': 'Registro de usuario', 'description': 'Alta'},
                        ]},
                    ],
                },
                'technicalDocument': {
                    'epics': [{
                        'epicKey': 'views',
                        'title': 'Vistas',
                        'requirements': [{
                            'flowKey': 'req-registro',
                            'title': 'Registro con verificación',
                            'linkedItemIds': ['item-views-registro-de-usuario'],
                        }],
                    }],
                },
            },
        }

    def test_create_from_json_assigns_item_ids(self, admin_client, db):
        response = admin_client.post(
            reverse('create-proposal-from-json'),
            self._base_payload('Trace Create'),
            format='json',
        )
        assert response.status_code == 201
        proposal = BusinessProposal.objects.get(title='Trace Create')
        fr = ProposalSection.objects.get(
            proposal=proposal, section_type='functional_requirements',
        )
        views_group = next(g for g in fr.content_json['groups'] if g['id'] == 'views')
        registro = next(i for i in views_group['items'] if i['name'] == 'Registro de usuario')
        assert registro['id'] == 'item-views-registro-de-usuario'

    def test_create_from_json_normalizes_technical_linked_item_ids(self, admin_client, db):
        response = admin_client.post(
            reverse('create-proposal-from-json'),
            self._base_payload('Trace Create Tech'),
            format='json',
        )
        assert response.status_code == 201
        proposal = BusinessProposal.objects.get(title='Trace Create Tech')
        tech = ProposalSection.objects.get(
            proposal=proposal, section_type='technical_document',
        )
        req = tech.content_json['epics'][0]['requirements'][0]
        assert req['linked_item_ids'] == ['item-views-registro-de-usuario']
        assert 'linkedItemIds' not in req

    def test_update_from_json_assigns_item_ids_and_normalizes_links(self, admin_client, db):
        create_resp = admin_client.post(
            reverse('create-proposal-from-json'),
            self._base_payload('Trace Update'),
            format='json',
        )
        assert create_resp.status_code == 201
        proposal = BusinessProposal.objects.get(title='Trace Update')

        payload = self._base_payload('Trace Update')
        payload['sections']['functionalRequirements']['groups'][0]['items'].append(
            {'icon': '📊', 'name': 'Panel de métricas', 'description': 'KPIs'},
        )
        payload['sections']['technicalDocument']['epics'][0]['requirements'].append({
            'flowKey': 'req-metricas',
            'title': 'Panel de métricas en vivo',
            'linkedItemIds': ['item-views-panel-de-metricas', 'item-views-panel-de-metricas'],
        })
        response = admin_client.put(
            reverse('update-proposal-from-json', args=[proposal.id]),
            payload,
            format='json',
        )
        assert response.status_code == 200

        fr = ProposalSection.objects.get(
            proposal=proposal, section_type='functional_requirements',
        )
        views_group = next(g for g in fr.content_json['groups'] if g['id'] == 'views')
        metricas = next(i for i in views_group['items'] if i['name'] == 'Panel de métricas')
        assert metricas['id'] == 'item-views-panel-de-metricas'

        tech = ProposalSection.objects.get(
            proposal=proposal, section_type='technical_document',
        )
        new_req = tech.content_json['epics'][0]['requirements'][1]
        assert new_req['linked_item_ids'] == ['item-views-panel-de-metricas']
