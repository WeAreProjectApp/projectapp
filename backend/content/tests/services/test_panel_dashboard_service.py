"""Tests for content/services/panel_dashboard_service.py — global panel dashboard."""
from datetime import timedelta
from decimal import Decimal

import pytest
from accounts.services import proposal_client_service
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    AdditionalModule,
    AdditionalModuleShareLink,
    BusinessProposal,
    Document,
    DocumentType,
    EmailLog,
    HourPackage,
    RecurringPayment,
    Task,
    WebAppDiagnostic,
)
from content.services.panel_dashboard_service import build_panel_dashboard
from content.services.proposal_analytics_service import (
    build_dashboard,
    build_dashboard_core,
)
from content.utils import today_bogota

pytestmark = pytest.mark.django_db


# ── Fixtures ──

@pytest.fixture
def collection_doc_type(db):
    obj, _ = DocumentType.objects.get_or_create(
        code='collection_account',
        defaults={'name': 'Collection Account', 'label': 'Cuenta de cobro'},
    )
    return obj


def _make_collection_account(doc_type, *, due_date, total):
    return Document.objects.create(
        title=f'CC {due_date}',
        document_type=doc_type,
        client_name='ACME Corp',
        language='es',
        commercial_status=Document.CommercialStatus.ISSUED,
        due_date=due_date,
        total=total,
    )


# ── build_panel_dashboard: shape ──

class TestPayloadShape:
    def test_empty_db_skips_finance_and_attention(self):
        payload = build_panel_dashboard(include_finance=False)
        assert payload['finance'] is None
        assert payload['attention'] == []

    def test_empty_db_zeroes_the_proposals_block(self):
        payload = build_panel_dashboard(include_finance=False)
        assert payload['proposals']['total_proposals'] == 0
        assert payload['proposals']['pipeline_count'] == 0
        assert payload['proposals']['recent'] == []

    def test_empty_db_zeroes_the_operations_block(self):
        ops = build_panel_dashboard(include_finance=False)['operations']
        assert ops['tasks']['open'] == 0
        assert ops['tasks']['overdue'] == 0
        assert ops['documents']['collection_accounts']['issued_count'] == 0
        assert ops['diagnostics']['active_pipeline'] == 0
        assert ops['emails']['total_30d'] == 0
        assert ops['emails']['success_rate'] is None
        # Hour packages are seeded by migration; mirror the live count.
        assert ops['hour_packages']['active_count'] == (
            HourPackage.objects.filter(is_active=True).count()
        )

    def test_finance_block_present_when_included(self):
        payload = build_panel_dashboard(include_finance=True)

        finance = payload['finance']
        assert finance['year'] == today_bogota().year
        assert finance['liquid_total'] == Decimal('0')
        assert finance['pocket_balance'] == Decimal('0')
        assert 'total' in finance['card_debt']
        assert len(finance['monthly']) == 12

    def test_additional_modules_matches_the_active_catalog(self):
        payload = build_panel_dashboard(include_finance=False)

        assert payload['additional_modules']['active_module_count'] == (
            AdditionalModule.objects.filter(
                is_active=True,
                category__is_active=True,
            ).count()
        )


class TestAdditionalModulesSummary:
    @freeze_time('2026-08-31 12:00:00')
    def test_reports_usable_links_and_the_latest_historical_open(self):
        module = AdditionalModule.objects.filter(
            is_active=True,
            category__is_active=True,
        ).first()
        active_link = AdditionalModuleShareLink.objects.create(
            recipient_label='Conversación activa',
        )
        active_link.selected_modules.add(module)
        orphan_link = AdditionalModuleShareLink.objects.create(
            recipient_label='Sin selección disponible',
        )
        viewed_at = timezone.now()
        revoked_link = AdditionalModuleShareLink.objects.create(
            recipient_label='Histórico abierto',
            is_active=False,
            revoked_at=viewed_at,
            view_count=1,
            first_viewed_at=viewed_at,
            last_viewed_at=viewed_at,
        )
        revoked_link.selected_modules.add(module)

        summary = build_panel_dashboard(
            include_finance=False,
        )['additional_modules']

        assert summary['active_share_count'] == 1
        assert summary['unopened_active_share_count'] == 1
        assert summary['last_viewed_at'] == viewed_at
        assert orphan_link.first_viewed_at is None


# ── operations: tasks ──

class TestTasksSummary:
    def test_overdue_excludes_done_and_archived(self):
        yesterday = today_bogota() - timedelta(days=1)
        Task.objects.create(title='Late', due_date=yesterday, position=0)
        Task.objects.create(
            title='Done late', due_date=yesterday,
            status=Task.Status.DONE, position=1,
        )
        Task.objects.create(
            title='Archived late', due_date=yesterday,
            is_archived=True, position=2,
        )

        tasks = build_panel_dashboard(include_finance=False)['operations']['tasks']

        assert tasks['overdue'] == 1
        assert tasks['open'] == 1

    def test_overdue_high_priority_marks_attention_danger(self):
        yesterday = today_bogota() - timedelta(days=1)
        Task.objects.create(
            title='Urgent late', due_date=yesterday,
            priority=Task.Priority.HIGH, position=0,
        )

        attention = build_panel_dashboard(include_finance=False)['attention']

        item = next(i for i in attention if i['type'] == 'tasks_overdue')
        assert item['severity'] == 'danger'
        assert item['count'] == 1


# ── operations: documents + attention ──

class TestDocumentsSummary:
    def test_overdue_collection_account_counts_and_alerts(self, collection_doc_type):
        today = today_bogota()
        _make_collection_account(
            collection_doc_type,
            due_date=today - timedelta(days=3), total=Decimal('500000'),
        )
        _make_collection_account(
            collection_doc_type,
            due_date=today + timedelta(days=10), total=Decimal('300000'),
        )

        payload = build_panel_dashboard(include_finance=False)

        accounts = payload['operations']['documents']['collection_accounts']
        assert accounts['issued_count'] == 2
        assert accounts['overdue_issued'] == 1
        assert accounts['outstanding_total'] == Decimal('800000')
        item = next(
            i for i in payload['attention'] if i['type'] == 'documents_overdue'
        )
        assert item['severity'] == 'danger'
        assert item['count'] == 1


# ── operations: emails ──

class TestEmailsSummary:
    def test_success_rate_and_failed_attention(self):
        for _ in range(3):
            EmailLog.objects.create(
                template_key='proposal_send', recipient='a@b.co', status='sent',
            )
        EmailLog.objects.create(
            template_key='proposal_send', recipient='a@b.co', status='failed',
        )

        payload = build_panel_dashboard(include_finance=False)

        emails = payload['operations']['emails']
        assert emails['total_30d'] == 4
        assert emails['failed_count'] == 1
        assert emails['success_rate'] == 75.0
        item = next(
            i for i in payload['attention'] if i['type'] == 'emails_failed'
        )
        assert item['count'] == 1


# ── operations: diagnostics ──

class TestDiagnosticsSummary:
    def test_pipeline_and_accepted_value(self):
        profile = proposal_client_service.get_or_create_client_for_proposal(
            name='Cliente Diag', email='diag@example.com',
        )
        WebAppDiagnostic.objects.create(client=profile, status='sent')
        WebAppDiagnostic.objects.create(client=profile, status='negotiating')
        WebAppDiagnostic.objects.create(
            client=profile, status='accepted',
            investment_amount=Decimal('2000000'),
        )

        diagnostics = build_panel_dashboard(
            include_finance=False,
        )['operations']['diagnostics']

        assert diagnostics['active_pipeline'] == 2
        assert diagnostics['accepted_value'] == Decimal('2000000')


# ── attention: stale proposals ──

class TestStaleProposals:
    @freeze_time('2026-01-15 12:00:00')
    def test_sent_unviewed_over_seven_days_alerts(self):
        stale = BusinessProposal.objects.create(
            title='Olvidada', client_name='Cliente', status='sent',
        )
        BusinessProposal.objects.filter(pk=stale.pk).update(
            sent_at=timezone.now() - timedelta(days=8),
        )
        fresh = BusinessProposal.objects.create(
            title='Reciente', client_name='Cliente', status='sent',
        )
        BusinessProposal.objects.filter(pk=fresh.pk).update(
            sent_at=timezone.now() - timedelta(days=2),
        )

        attention = build_panel_dashboard(include_finance=False)['attention']

        item = next(i for i in attention if i['type'] == 'proposals_stale')
        assert item['count'] == 1
        assert item['severity'] == 'warning'


# ── attention: recurring due (finance-gated) ──

class TestRecurringDue:
    def test_due_soon_only_reported_with_finance(self):
        RecurringPayment.objects.create(
            name='Hosting', price=Decimal('50000.00'),
            cop_equivalent=Decimal('50000.00'), frequency='monthly',
            billing_day=today_bogota().day,
        )

        with_finance = build_panel_dashboard(include_finance=True)['attention']
        without_finance = build_panel_dashboard(include_finance=False)['attention']

        item = next(i for i in with_finance if i['type'] == 'recurring_due')
        assert item['count'] == 1
        assert item['meta']['next_days'] == 0
        assert all(i['type'] != 'recurring_due' for i in without_finance)

    def test_due_soon_excludes_non_notifiable_payments(self):
        billing_day = today_bogota().day
        RecurringPayment.objects.create(
            name='Vigente', price=Decimal('50000.00'),
            cop_equivalent=Decimal('50000.00'), frequency='monthly',
            billing_day=billing_day,
        )
        RecurringPayment.objects.create(
            name='Archivado', price=Decimal('50000.00'),
            cop_equivalent=Decimal('50000.00'), frequency='monthly',
            billing_day=billing_day, is_archived=True,
        )
        RecurringPayment.objects.create(
            name='Silenciado', price=Decimal('50000.00'),
            cop_equivalent=Decimal('50000.00'), frequency='monthly',
            billing_day=billing_day, reminders_muted=True,
        )

        attention = build_panel_dashboard(include_finance=True)['attention']

        item = next(i for i in attention if i['type'] == 'recurring_due')
        assert item['count'] == 1

    @freeze_time('2026-02-25 12:00:00')
    def test_anchor_without_billing_day_appears_in_finance_radar(self):
        """Falla si el radar omite cobros mensuales con un ancla válida."""
        RecurringPayment.objects.create(
            name='Cobro anclado', price=Decimal('50000.00'),
            cop_equivalent=Decimal('50000.00'),
            frequency=RecurringPayment.Frequency.MONTHLY,
            cycle_anchor_date=today_bogota(),
        )

        attention = build_panel_dashboard(include_finance=True)['attention']

        item = next(i for i in attention if i['type'] == 'recurring_due')
        assert item['count'] == 1
        assert item['meta']['next_days'] == 0

    @freeze_time('2026-02-25 12:00:00')
    def test_anchor_wins_over_conflicting_billing_day_at_short_month_end(self):
        """Falla si el radar usa billing_day y adelanta un ciclo anclado al 31."""
        RecurringPayment.objects.create(
            name='Cierre de mes', price=Decimal('50000.00'),
            cop_equivalent=Decimal('50000.00'),
            frequency=RecurringPayment.Frequency.MONTHLY,
            cycle_anchor_date='2026-01-31', billing_day=25,
        )

        attention = build_panel_dashboard(include_finance=True)['attention']

        item = next(i for i in attention if i['type'] == 'recurring_due')
        assert item['count'] == 1
        assert item['meta']['next_days'] == 3

    @freeze_time('2026-02-25 12:00:00')
    def test_monthly_payment_without_schedule_does_not_alert(self):
        """Falla si el radar inventa una fecha para un cobro sin calendario."""
        RecurringPayment.objects.create(
            name='Sin calendario', price=Decimal('50000.00'),
            cop_equivalent=Decimal('50000.00'),
            frequency=RecurringPayment.Frequency.MONTHLY,
        )

        attention = build_panel_dashboard(include_finance=True)['attention']

        assert all(item['type'] != 'recurring_due' for item in attention)

    @freeze_time('2026-02-25 12:00:00')
    def test_anchor_outside_due_window_does_not_alert(self):
        """Falla si billing_day adelanta un aviso fuera de la ventana de siete días."""
        RecurringPayment.objects.create(
            name='Fuera de ventana', price=Decimal('50000.00'),
            cop_equivalent=Decimal('50000.00'),
            frequency=RecurringPayment.Frequency.MONTHLY,
            cycle_anchor_date='2026-03-05', billing_day=25,
        )

        attention = build_panel_dashboard(include_finance=True)['attention']

        assert all(item['type'] != 'recurring_due' for item in attention)


# ── build_dashboard core parity (refactor lock) ──

class TestDashboardCoreParity:
    def test_full_dashboard_contains_core_values(self):
        BusinessProposal.objects.create(
            title='Uno', client_name='Cliente', status='accepted',
            total_investment=Decimal('1000000'),
        )
        BusinessProposal.objects.create(
            title='Dos', client_name='Cliente', status='sent',
            total_investment=Decimal('2000000'),
        )

        core = build_dashboard_core(include_recent=False)
        full = build_dashboard()

        for key, value in core.items():
            assert full[key] == value
        assert 'recent' not in full

    def test_core_recent_lists_latest_proposals(self):
        for idx in range(6):
            BusinessProposal.objects.create(
                title=f'P{idx}', client_name='Cliente',
            )

        recent = build_dashboard_core()['recent']

        assert len(recent) == 5
        assert recent[0]['title'] == 'P5'
        assert set(recent[0]) == {'id', 'title', 'client_name', 'status'}
