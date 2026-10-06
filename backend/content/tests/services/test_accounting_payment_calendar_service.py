"""Tests for the daily payment calendar digest."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from django.core import mail

from content.models import (
    AccountingSettings,
    EmailLog,
    EmailLogTarget,
    ExpenseRecord,
    HostingRecord,
    IncomeRecord,
    NotificationRecipient,
    ProjectRetentionContext,
    RecurringPayment,
)
from content.services.accounting_payment_calendar_service import (
    TEMPLATE_KEY,
    run_payment_calendar,
)
from content.services.email_delivery_service import EmailDeliveryGateway

pytestmark = pytest.mark.django_db

TODAY = date(2026, 7, 10)
User = get_user_model()


@pytest.fixture(autouse=True)
def _recipients(settings):
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }
    # Migration 0191 seeds two production inboxes into every test database.
    NotificationRecipient.objects.all().delete()
    for email in ('team@projectapp.co', 'carlos@projectapp.co'):
        NotificationRecipient.objects.create(email=email)
    config = AccountingSettings.load()
    config.save()
    return config


def make_expected(days_left=15, **overrides):
    fields = {
        'concept': 'Kore - Hosting julio',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': TODAY + timedelta(days=days_left),
        'total_amount': Decimal('1000000.00'),
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def pay(expected, amount):
    """Register a liquid child against an expected income."""
    return IncomeRecord.objects.create(
        concept=f'{expected.concept} (pago)',
        kind=IncomeRecord.Kind.LIQUID,
        period_date=TODAY,
        total_amount=Decimal(amount),
        expected_income=expected,
    )


def make_recurring(**overrides):
    fields = {
        'name': 'Figma',
        'price': Decimal('60000.00'),
        'frequency': RecurringPayment.Frequency.MONTHLY,
        'is_active': True,
    }
    fields.update(overrides)
    return RecurringPayment.objects.create(**fields)


def make_hosting(days_left=7, **overrides):
    fields = {
        'client_name': 'German - Kore',
        'domain_url': 'https://korehealths.com/',
        'monthly_value': Decimal('91667.00'),
        'payment_modality': 'semiannual',
        'payment_per_cycle': Decimal('550002.00'),
        'valid_from': TODAY - timedelta(days=180),
        'valid_to': TODAY + timedelta(days=days_left),
        'is_active': True,
    }
    fields.update(overrides)
    return HostingRecord.objects.create(**fields)


def sent_logs():
    return EmailLog.objects.filter(
        template_key=TEMPLATE_KEY, status=EmailLog.Status.SENT,
    )


class TestIncomeCadence:
    def test_announces_at_15_days(self):
        record = make_expected(days_left=15)
        assert run_payment_calendar(TODAY) == 1
        record.refresh_from_db()
        assert record.reminder_count == 1
        assert record.reminder_last_sent_at == TODAY
        assert record.reminder_target_date == record.period_date

    def test_silent_before_the_window(self):
        make_expected(days_left=16)
        assert run_payment_calendar(TODAY) == 0

    def test_unclassified_legacy_project_is_silent(self):
        client = User.objects.create_user(
            username='legacy-project@example.com',
            email='legacy-project@example.com',
        )
        project = Project.objects.create(
            name='Legacy archive',
            client=client,
            status=Project.STATUS_ARCHIVED,
        )
        record = make_expected(days_left=7, project=project)

        assert run_payment_calendar(TODAY) == 0
        record.refresh_from_db()
        assert record.reminder_count == 0

    def test_retained_expected_income_is_absent_while_operational_income_is_announced(self):
        """Fails if a retained income continues to create payment-calendar reminders."""
        client = User.objects.create_user(
            username='retained-income@example.com',
            email='retained-income@example.com',
        )
        context = ProjectRetentionContext.objects.create(
            client=client,
            original_project_id=101,
            project_name='Deleted income project',
            retained_records={},
            created_by=client,
        )
        retained = make_expected(days_left=15, retention_context=context)
        operational = make_expected(days_left=15, concept='Operational income')

        sent = run_payment_calendar(TODAY)

        retained.refresh_from_db()
        operational.refresh_from_db()
        assert sent == 1
        assert retained.reminder_count == 0
        assert operational.reminder_count == 1

    def test_announces_again_when_crossing_7_days(self):
        make_expected(days_left=15)
        run_payment_calendar(TODAY)
        assert run_payment_calendar(TODAY + timedelta(days=8)) == 1

    def test_announces_on_the_due_day(self):
        make_expected(days_left=7)
        run_payment_calendar(TODAY)
        assert run_payment_calendar(TODAY + timedelta(days=7)) == 1

    def test_a_late_record_announces_itself_immediately(self):
        make_expected(days_left=-40)
        assert run_payment_calendar(TODAY) == 1

    def test_moving_the_expected_date_restarts_the_cadence(self):
        record = make_expected(days_left=7)
        run_payment_calendar(TODAY)
        IncomeRecord.objects.filter(pk=record.pk).update(
            period_date=TODAY + timedelta(days=70),
        )
        # Far from the new date: silent, and the old cadence state is cleared.
        assert run_payment_calendar(TODAY + timedelta(days=1)) == 0
        record.refresh_from_db()
        assert record.reminder_count == 0
        assert record.reminder_last_sent_at is None


class TestOverdueReminders:
    def test_repeats_every_fortnight_by_default(self):
        make_expected(days_left=0)
        run_payment_calendar(TODAY)
        assert run_payment_calendar(TODAY + timedelta(days=13)) == 0
        assert run_payment_calendar(TODAY + timedelta(days=14)) == 1

    def test_weekly_setting_repeats_every_week(self, _recipients):
        _recipients.overdue_reminder_frequency = 'weekly'
        _recipients.save()
        make_expected(days_left=0)
        run_payment_calendar(TODAY)
        assert run_payment_calendar(TODAY + timedelta(days=7)) == 1

    def test_the_overdue_line_says_how_late_it_is(self):
        make_expected(days_left=-3)
        run_payment_calendar(TODAY)
        assert 'Vencido hace 3 días' in mail.outbox[0].body


class TestStopsWhenCollected:
    def test_a_fully_paid_income_stops_announcing(self):
        expected = make_expected(days_left=7)
        pay(expected, '1000000.00')
        assert run_payment_calendar(TODAY) == 0

    def test_a_partial_payment_keeps_announcing_the_balance(self):
        expected = make_expected(days_left=7)
        pay(expected, '400000.00')
        assert run_payment_calendar(TODAY) == 1
        body = mail.outbox[0].body
        # Balance first, gross second: the pending figure is the one to chase.
        # Millions carry the apostrophe the email money format uses, and the
        # plain-text part must not HTML-escape it into $1&#x27;000.000.
        assert '$600.000' in body
        assert "de $1'000.000" in body

    def test_a_deduction_can_close_the_income(self):
        expected = make_expected(days_left=7)
        pay(expected, '992000.00')
        deduction = ExpenseRecord.objects.create(
            concept='Comisión Wompi',
            period_date=TODAY,
            total_amount=Decimal('8000.00'),
            deduction_type=ExpenseRecord.DeductionType.GATEWAY_FEE,
        )
        ExpenseRecord.objects.filter(pk=deduction.pk).update(source_income=expected)
        assert run_payment_calendar(TODAY) == 0

    def test_a_lost_child_does_not_count_as_payment(self):
        expected = make_expected(days_left=7)
        IncomeRecord.objects.create(
            concept='Perdido',
            kind=IncomeRecord.Kind.LOST,
            period_date=TODAY,
            total_amount=Decimal('1000000.00'),
            expected_income=expected,
        )
        assert run_payment_calendar(TODAY) == 1

    def test_writing_the_income_off_stops_it(self):
        record = make_expected(days_left=7)
        IncomeRecord.objects.filter(pk=record.pk).update(kind=IncomeRecord.Kind.LOST)
        assert run_payment_calendar(TODAY) == 0


class TestMuting:
    def test_an_indefinitely_muted_income_is_silent(self):
        record = make_expected(days_left=7)
        IncomeRecord.objects.filter(pk=record.pk).update(reminders_muted=True)
        assert run_payment_calendar(TODAY) == 0

    def test_a_mute_with_a_future_date_is_silent(self):
        record = make_expected(days_left=7)
        IncomeRecord.objects.filter(pk=record.pk).update(
            reminders_muted=True,
            reminders_muted_until=TODAY + timedelta(days=30),
        )
        assert run_payment_calendar(TODAY) == 0

    def test_a_mute_resumes_by_itself_on_its_date(self):
        record = make_expected(days_left=7)
        IncomeRecord.objects.filter(pk=record.pk).update(
            reminders_muted=True, reminders_muted_until=TODAY,
        )
        assert run_payment_calendar(TODAY) == 1
        record.refresh_from_db()
        assert record.reminders_muted is False
        assert record.reminders_muted_until is None


class TestRecurring:
    def test_announces_the_next_charge_at_15_days(self):
        make_recurring(cycle_anchor_date=TODAY + timedelta(days=15))
        assert run_payment_calendar(TODAY) == 1

    def test_announces_the_next_charge_at_7_days(self):
        make_recurring(cycle_anchor_date=TODAY + timedelta(days=7))
        assert run_payment_calendar(TODAY) == 1

    def test_announces_the_next_charge_on_its_due_day(self):
        make_recurring(cycle_anchor_date=TODAY)
        assert run_payment_calendar(TODAY) == 1

    def test_goes_quiet_after_the_charge_day(self):
        payment = make_recurring(cycle_anchor_date=TODAY)
        assert run_payment_calendar(TODAY) == 1
        # The next day the projection rolls to the following cycle, which is a
        # month away: an unpaid cycle does not nag.
        assert run_payment_calendar(TODAY + timedelta(days=1)) == 0
        payment.refresh_from_db()
        assert payment.reminder_last_sent_at is None

    def test_an_inactive_payment_is_skipped(self):
        make_recurring(cycle_anchor_date=TODAY + timedelta(days=7), is_active=False)
        assert run_payment_calendar(TODAY) == 0

    def test_an_archived_payment_is_skipped(self):
        make_recurring(
            cycle_anchor_date=TODAY + timedelta(days=7),
            is_archived=True,
        )
        assert run_payment_calendar(TODAY) == 0

    def test_an_indefinitely_muted_payment_is_skipped(self):
        make_recurring(
            cycle_anchor_date=TODAY + timedelta(days=7),
            reminders_muted=True,
        )
        assert run_payment_calendar(TODAY) == 0

    def test_a_future_recurring_mute_is_skipped(self):
        make_recurring(
            cycle_anchor_date=TODAY + timedelta(days=7),
            reminders_muted=True,
            reminders_muted_until=TODAY + timedelta(days=30),
        )
        assert run_payment_calendar(TODAY) == 0

    def test_an_expired_recurring_mute_reactivates(self):
        payment = make_recurring(
            cycle_anchor_date=TODAY + timedelta(days=7),
            reminders_muted=True,
            reminders_muted_until=TODAY,
        )

        assert run_payment_calendar(TODAY) == 1
        payment.refresh_from_db()
        assert payment.reminders_muted is False
        assert payment.reminders_muted_until is None

    def test_a_non_monthly_payment_without_an_anchor_is_skipped(self):
        make_recurring(frequency=RecurringPayment.Frequency.ANNUAL, billing_day=10)
        assert run_payment_calendar(TODAY) == 0

    def test_a_monthly_payment_falls_back_to_its_billing_day(self):
        make_recurring(billing_day=(TODAY + timedelta(days=7)).day)
        assert run_payment_calendar(TODAY) == 1


class TestDelivery:
    def test_an_empty_day_sends_nothing(self):
        assert run_payment_calendar(TODAY) == 0
        assert mail.outbox == []
        assert EmailLog.objects.count() == 0

    def test_everything_due_travels_in_one_email(self):
        make_expected(days_left=7)
        make_expected(days_left=0, concept='Vastago - Desarrollo')
        make_recurring(cycle_anchor_date=TODAY + timedelta(days=15))
        assert run_payment_calendar(TODAY) == 3
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert 'INGRESOS ESPERADOS' in body
        assert 'GASTOS RECURRENTES' in body

    def test_income_line_renders_complete_details(self):
        user = User.objects.create_user(
            username='ana@example.com', email='ana@example.com',
            first_name='Ana', last_name='Perez',
        )
        client = UserProfile.objects.create(user=user, company_name='Acme')
        make_expected(days_left=7, client=client)

        run_payment_calendar(TODAY)

        body = mail.outbox[0].body
        assert 'Ana Perez' in body
        assert "$1'000.000" in body
        assert 'Vie, 17 jul 2026' in body

    def test_client_address_is_not_a_calendar_recipient(self):
        user = User.objects.create_user(
            username='cliente@example.com', email='cliente@example.com',
        )
        client = UserProfile.objects.create(user=user, company_name='Acme')
        make_expected(days_left=7, client=client)

        run_payment_calendar(TODAY)

        assert set(mail.outbox[0].to) == {
            'team@projectapp.co', 'carlos@projectapp.co',
        }
        assert user.email not in mail.outbox[0].to

    def test_one_log_row_per_recipient_naming_every_record(self):
        record = make_expected(days_left=7)
        run_payment_calendar(TODAY)
        assert sent_logs().count() == 2
        metadata = sent_logs().first().metadata
        assert metadata['counts']['incomes'] == 1
        assert metadata['overdue_every_days'] == 14
        assert metadata['incomes'][0]['id'] == record.pk

    def test_log_targets_link_every_record_in_the_digest(self):
        """Fails if a sent digest leaves any internal recipient without a target."""
        income = make_expected(days_left=7)
        recurring = make_recurring(cycle_anchor_date=TODAY + timedelta(days=15))
        hosting = make_hosting(days_left=7)

        assert run_payment_calendar(TODAY) == 3

        logs = sent_logs()
        assert logs.count() == 2
        assert logs.filter(
            targets__entity_type='income', targets__object_id=income.pk,
        ).distinct().count() == 2
        assert logs.filter(
            targets__entity_type='recurring', targets__object_id=recurring.pk,
        ).distinct().count() == 2
        assert logs.filter(
            targets__entity_type='hosting', targets__object_id=hosting.pk,
        ).distinct().count() == 2
        assert EmailLogTarget.objects.filter(email_log__in=logs).count() == 6

    def test_failed_delivery_does_not_advance_income_cadence(self, monkeypatch):
        def fail_send(*args, **kwargs):
            raise RuntimeError('SMTP unavailable')

        monkeypatch.setattr(EmailDeliveryGateway, 'send', fail_send)
        record = make_expected(days_left=7)

        assert run_payment_calendar(TODAY) == 0

        record.refresh_from_db()
        assert record.reminder_last_sent_at is None
        assert record.reminder_count == 0

    def test_failed_delivery_is_diagnosable_from_the_log(self, monkeypatch):
        """Fails if a failed digest omits targets from any internal recipient log."""
        def fail_send(*args, **kwargs):
            raise RuntimeError('SMTP unavailable')

        monkeypatch.setattr(EmailDeliveryGateway, 'send', fail_send)
        income = make_expected(days_left=7)
        recurring = make_recurring(cycle_anchor_date=TODAY + timedelta(days=15))
        hosting = make_hosting(days_left=7)

        run_payment_calendar(TODAY)

        logs = EmailLog.objects.filter(
            template_key=TEMPLATE_KEY, status=EmailLog.Status.FAILED,
        )
        assert logs.count() == 2
        assert set(logs.values_list('recipient', flat=True)) == {
            'team@projectapp.co', 'carlos@projectapp.co',
        }
        assert 'SMTP unavailable' in logs.first().error_message
        assert logs.filter(
            targets__entity_type='income', targets__object_id=income.pk,
        ).distinct().count() == 2
        assert logs.filter(
            targets__entity_type='recurring', targets__object_id=recurring.pk,
        ).distinct().count() == 2
        assert logs.filter(
            targets__entity_type='hosting', targets__object_id=hosting.pk,
        ).distinct().count() == 2
        assert EmailLogTarget.objects.filter(email_log__in=logs).count() == 6

    def test_without_recipients_nothing_is_sent_and_no_state_advances(self, _recipients):
        NotificationRecipient.objects.all().delete()
        record = make_expected(days_left=7)
        assert run_payment_calendar(TODAY) == 0
        assert mail.outbox == []
        record.refresh_from_db()
        assert record.reminder_last_sent_at is None
        assert record.reminder_count == 0

    def test_the_master_switch_silences_the_calendar(self, _recipients):
        _recipients.payment_calendar_enabled = False
        _recipients.save()
        make_expected(days_left=7)
        assert run_payment_calendar(TODAY) == 0

    def test_notifications_off_silences_everything(self, _recipients):
        _recipients.notifications_enabled = False
        _recipients.save()
        make_expected(days_left=7)
        assert run_payment_calendar(TODAY) == 0

    def test_the_subject_summarises_the_day(self):
        make_expected(days_left=-2)
        make_expected(days_left=0, concept='Vastago')
        make_expected(days_left=7, concept='Otro')
        run_payment_calendar(TODAY)
        assert mail.outbox[0].subject == (
            '[Contabilidad] Calendario de cobros y pagos: '
            '1 vencido, 1 vence hoy, 1 próximo'
        )

    def test_the_most_overdue_income_leads_the_section(self):
        make_expected(days_left=7, concept='El que viene')
        make_expected(days_left=-20, concept='El mas atrasado')
        run_payment_calendar(TODAY)
        body = mail.outbox[0].body
        assert body.index('El mas atrasado') < body.index('El que viene')
