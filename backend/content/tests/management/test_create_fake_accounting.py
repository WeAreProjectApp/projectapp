"""Tests for create_fake_accounting and its delete_fake_data integration."""
from decimal import Decimal

import pytest
from django.core import mail
from django.core.management import call_command
from django.db.models import F

from content.models import (
    AccountingSettings,
    NotificationRecipient,
    AdsSpendRecord,
    ExpenseRecord,
    HostingRecord,
    IncomeRecord,
    Ledger,
    PocketMovement,
    RecurringPayment,
)


@pytest.mark.django_db
class TestCreateFakeAccounting:
    def test_recurring_equivalents_use_the_configured_rate(self):
        settings = AccountingSettings.load()
        settings.usd_exchange_rate = Decimal('4350.50')
        settings.save()

        call_command('create_fake_accounting', '--count', '6')

        payment = RecurringPayment.objects.get(name='Claude Code 20x')
        assert payment.cop_equivalent == Decimal('870100.00')

    def test_recurring_fake_rows_cover_lifecycle_states(self):
        call_command('create_fake_accounting', '--count', '6')

        rows = RecurringPayment.objects.filter(source_ref='fake:accounting')
        assert rows.filter(is_active=True, is_archived=False).exists()
        assert rows.filter(is_active=False, is_archived=False).exists()
        assert rows.filter(is_archived=True, archived_at__isnull=False).exists()
        assert rows.filter(reminders_muted=True).exists()

    def test_creates_tagged_rows_for_every_entity(self):
        call_command('create_fake_accounting', '--count', '6')
        for model in (
            IncomeRecord, ExpenseRecord, HostingRecord,
            PocketMovement, RecurringPayment, AdsSpendRecord,
        ):
            assert model.objects.filter(source_ref='fake:accounting').exists()
        assert not IncomeRecord.objects.exclude(
            source_ref='fake:accounting',
        ).exists()

    def test_seeds_a_billed_diagnostic_and_the_lost_one_it_must_exclude(
        self, make_client_profile,
    ):
        """The Diagnóstico module of /panel/clients renders (0) without this.

        Both halves matter: a billable row with a client so the cut has data,
        and a written-off one so the exclusion is exercised rather than
        assumed. The profile is seeded first because the command only links
        incomes to clients that already exist.
        """
        make_client_profile(company='Diag SAS')
        call_command('create_fake_accounting', '--count', '40')

        diagnostic = IncomeRecord.objects.filter(
            origin=IncomeRecord.Origin.DIAGNOSTIC,
        )
        assert diagnostic.filter(
            client__isnull=False,
        ).exclude(kind=IncomeRecord.Kind.LOST).exists()
        assert diagnostic.filter(kind=IncomeRecord.Kind.LOST).exists()

    def test_covers_every_income_kind_and_fulfilment_state(self):
        """The Ingresos tab renders Pagado/Parcial/Pendiente plus Perdido.

        Without a row in each, those UI paths ship unexercised by hand.
        """
        call_command('create_fake_accounting', '--count', '12')
        kinds = set(
            IncomeRecord.objects.values_list('kind', flat=True).distinct(),
        )
        assert kinds == {'expected', 'liquid', 'lost'}

        states = set()
        for expected in IncomeRecord.objects.filter(kind='expected'):
            paid = sum(
                child.total_amount
                for child in expected.liquid_records.filter(kind='liquid')
            )
            if not paid:
                states.add('pending')
            elif paid < expected.total_amount:
                states.add('partial')
            else:
                states.add('paid')
        assert states == {'pending', 'partial', 'paid'}

    def test_seeds_every_manual_receivable_forecast_state(self):
        call_command('create_fake_accounting', '--count', '12')

        selected = IncomeRecord.objects.filter(is_receivable_candidate=True)
        assert set(selected.values_list('collection_confidence', flat=True)) == {
            '',
            IncomeRecord.CollectionConfidence.HIGH,
            IncomeRecord.CollectionConfidence.MEDIUM,
            IncomeRecord.CollectionConfidence.LOW,
        }
        assert not selected.exclude(
            kind=IncomeRecord.Kind.EXPECTED,
            ledger=Ledger.COMPANY,
        ).exists()
        assert IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.EXPECTED,
            is_receivable_candidate=False,
            collection_confidence=IncomeRecord.CollectionConfidence.HIGH,
        ).exists()

    def test_written_off_income_never_has_payments(self):
        call_command('create_fake_accounting', '--count', '12')
        for lost in IncomeRecord.objects.filter(kind='lost'):
            assert not lost.liquid_records.exists()

    def test_seeds_notification_recipients_when_empty(self):
        NotificationRecipient.objects.all().delete()

        call_command('create_fake_accounting', '--count', '2')

        rows = NotificationRecipient.objects.order_by('email')
        assert [r.email for r in rows] == [
            'carlos@example.com', 'gustavo@example.com',
        ]
        # One paused on purpose, so the panel's toggle has something to show.
        assert [r.is_active for r in rows] == [False, True]

    def test_sends_no_emails(self, accounting_settings):
        mail.outbox = []
        call_command('create_fake_accounting', '--count', '3')
        assert mail.outbox == []

    def test_partner_draws_mirror_company_expenses_fully_assigned(self):
        """A pocket draw attributed to a partner is a company-ledger
        expense 100% the partner's, category personal (#114)."""
        call_command('create_fake_accounting', '--count', '6')
        draws = ExpenseRecord.objects.filter(
            source_ref='fake:accounting',
            category=ExpenseRecord.Category.PERSONAL,
            pocket_movement__isnull=False,
        )
        assert draws.count() > 0
        assert draws.exclude(ledger=Ledger.COMPANY).count() == 0
        assert draws.exclude(
            pocket_movement__direction=PocketMovement.Direction.OUT,
        ).count() == 0
        assert draws.exclude(
            total_amount=F('pocket_movement__amount'),
        ).count() == 0
        assert draws.exclude(gustavo_amount=0).exclude(
            carlos_amount=0,
        ).count() == 0

    def test_pocket_outs_mix_linked_business_and_historical_rows(self):
        """Company pocket payments carry a linked business expense while
        some rows stay unlinked as pre-linkage history."""
        call_command('create_fake_accounting', '--count', '6')
        linked_business = ExpenseRecord.objects.filter(
            source_ref='fake:accounting',
            category=ExpenseRecord.Category.BUSINESS,
            pocket_movement__isnull=False,
        )
        assert linked_business.count() > 0
        historical = PocketMovement.objects.filter(
            source_ref='fake:accounting',
            income_records__isnull=True,
            expense_record__isnull=True,
        )
        assert historical.count() > 0

    def test_pocket_liquidations_record_exact_payment_day(self):
        """Liquid incomes into the pocket keep a full payment date, the
        liquidate modal's exact-day option (#114)."""
        call_command('create_fake_accounting', '--count', '12')
        exact = IncomeRecord.objects.filter(
            source_ref='fake:accounting',
            kind=IncomeRecord.Kind.LIQUID,
            destination=IncomeRecord.Destination.POCKET,
        ).exclude(period_date__day=1)
        assert exact.count() > 0

    def test_seeds_a_shared_abono_movement(self):
        """One movement covering three expected incomes (two paid, one
        partial) — the state the bulk settle flow produces, so the pocket's
        reparto UI and the Cobro column have a demo row."""
        call_command('create_fake_accounting', '--count', '6')
        movement = PocketMovement.objects.get(
            source_ref='fake:accounting', concept__startswith='Abono',
        )
        children = list(movement.income_records.order_by('pk'))
        assert len(children) == 3
        assert movement.amount == sum(
            child.total_amount for child in children
        )
        states = []
        for child in children:
            parent = child.expected_income
            paid = sum(
                sibling.total_amount
                for sibling in parent.liquid_records.filter(kind='liquid')
            )
            states.append(
                'paid' if paid >= parent.total_amount else 'partial',
            )
        assert states == ['paid', 'paid', 'partial']

    def test_delete_fake_data_removes_only_fake_rows(self, make_income):
        real_income = make_income(concept='Ingreso real')
        call_command('create_fake_accounting', '--count', '4')
        call_command('delete_fake_data', '--confirm')
        assert not IncomeRecord.objects.filter(
            source_ref='fake:accounting',
        ).exists()
        assert not PocketMovement.objects.filter(
            source_ref='fake:accounting',
        ).exists()
        assert IncomeRecord.objects.filter(pk=real_income.pk).exists()

    def test_seeded_rows_link_to_their_own_clients_project(self):
        """Seeding the project link is what makes the Proyecto column, its
        filter and the cuenta's inheritance visible without hand-editing."""
        from accounts.models import Project, UserProfile
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username='cliente@example.com', email='cliente@example.com',
            password='pass12345', first_name='Ana', last_name='Pérez',
        )
        profile = UserProfile.objects.create(user=user, role='client')
        project = Project.objects.create(name='MIMITTOS', client=user)

        call_command('create_fake_accounting', '--count', '8')

        linked = IncomeRecord.objects.filter(project=project)
        assert linked.exists()
        # A project always belongs to the row's own client — the rule the
        # write serializers enforce.
        for income in linked:
            assert income.client_id == profile.pk
        # And some rows stay without one: "Sin proyecto" is a real state.
        assert IncomeRecord.objects.filter(
            client=profile, project__isnull=True,
        ).exists()

    def test_fake_accounting_is_cleared_before_protected_project_deletion(self):
        """The reset removes fictitious money before its protected project."""
        from accounts.models import Project, UserProfile
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username='cliente@example.com', email='cliente@example.com',
            password='pass12345', first_name='Ana', last_name='Pérez',
        )
        UserProfile.objects.create(user=user, role='client')
        project = Project.objects.create(name='MIMITTOS', client=user)

        call_command('create_fake_accounting', '--count', '8')
        call_command('delete_fake_data', '--confirm')

        assert not Project.objects.filter(pk=project.pk).exists()
        assert not IncomeRecord.objects.filter(
            source_ref='fake:accounting',
        ).exists()
        assert not HostingRecord.objects.filter(
            source_ref='fake:accounting',
        ).exists()

    def test_project_reset_preserves_manual_accounting(self, admin_user, make_income):
        from accounts.models import Project

        project = Project.objects.create(name='Manual accounting', client=admin_user)
        income = make_income(
            project=project, concept='Imported receivable',
            total_amount=Decimal('125.00'), gustavo_amount=Decimal('75.00'),
            carlos_amount=Decimal('50.00'),
        )
        hosting = HostingRecord.objects.create(
            project=project, client_name='Manual operator', monthly_value=Decimal('77.00'),
        )

        call_command('delete_fake_data', '--confirm')

        income.refresh_from_db()
        hosting.refresh_from_db()
        assert income.project_id is None
        assert income.total_amount == Decimal('125.00')
        assert hosting.project_id is None
        assert hosting.monthly_value == Decimal('77.00')

    def test_fake_reset_requires_explicit_capability(self, settings, admin_user):
        from accounts.models import Project
        from django.core.management.base import CommandError

        project = Project.objects.create(name='Protected reset', client=admin_user)
        settings.FAKE_DATA_ALLOWED = False

        with pytest.raises(CommandError, match='FAKE_DATA_ALLOWED=True'):
            call_command('delete_fake_data', '--confirm')

        assert Project.objects.filter(pk=project.pk).exists()
