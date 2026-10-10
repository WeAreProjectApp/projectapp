"""API tests for the duplicate-draft endpoint of an income.

The endpoint persists nothing: it returns the prefill the panel form opens
with, so the operator can adjust the date or the amount before confirming.
The two rules with teeth are that the draft is always born expected and that
it never carries the links of the occurrence it was copied from.
"""
from datetime import date
from decimal import Decimal

import pytest

from accounts.models import Project
from content.models import HostingRecord, IncomeRecord
from content.serializers.accounting import IncomeRecordSerializer

pytestmark = pytest.mark.django_db


def url(record):
    return f'/api/accounting/incomes/{record.pk}/duplicate-draft/'


def make_hosting(**overrides):
    fields = {
        'client_name': 'Acme SAS',
        'monthly_value': Decimal('90000.00'),
        'payment_modality': HostingRecord.LEGACY_ANNUAL,
    }
    fields.update(overrides)
    return HostingRecord.objects.create(**fields)


class TestAuth:
    def test_staff_without_superuser_is_rejected(self, admin_client, make_income):
        response = admin_client.get(url(make_income()))
        assert response.status_code == 403

    def test_unknown_income_returns_404(self, super_client):
        response = super_client.get('/api/accounting/incomes/999999/duplicate-draft/')
        assert response.status_code == 404


class TestCopiedFields:
    def test_copies_the_fields_the_form_edits(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile(company='Acme SAS')
        project = Project.objects.create(
            name='Kore', client=profile.user, status=Project.STATUS_ACTIVE,
        )
        income = make_income(
            concept='Kore - Hosting anual',
            client=profile,
            project=project,
            origin=IncomeRecord.Origin.DEVELOPMENT,
            ledger='gustavo',
            total_amount=Decimal('1200000.00'),
            gustavo_amount=Decimal('1200000.00'),
            carlos_amount=Decimal('0.00'),
            notes='Renovar antes del corte',
        )

        response = super_client.get(url(income))

        assert response.status_code == 200
        assert response.data['concept'] == 'Kore - Hosting anual'
        assert response.data['client'] == profile.pk
        # Same label the list rows carry: the form shows it in the client
        # picker, and a different shape there would read as another client.
        assert (
            response.data['client_name']
            == IncomeRecordSerializer(income).data['client_name']
        )
        assert response.data['project'] == project.pk
        assert response.data['project_name'] == 'Kore'
        assert response.data['origin'] == IncomeRecord.Origin.DEVELOPMENT
        assert response.data['ledger'] == 'gustavo'
        assert response.data['total_amount'] == '1200000.00'
        assert response.data['gustavo_amount'] == '1200000.00'
        assert response.data['carlos_amount'] == '0.00'
        assert response.data['notes'] == 'Renovar antes del corte'

    @pytest.mark.parametrize('origin', [
        IncomeRecord.Origin.DEVELOPMENT,
        IncomeRecord.Origin.HOSTING,
        IncomeRecord.Origin.DIAGNOSTIC,
        IncomeRecord.Origin.OTHER,
    ])
    def test_every_business_line_travels(self, super_client, make_income, origin):
        """The origin is not one more copied field.

        It decides which date block the form opens with — single date or
        covered window — so a duplicate that loses it opens configured as a
        different kind of income than the one it copies.
        """
        response = super_client.get(url(make_income(origin=origin)))

        assert response.data['origin'] == origin

    def test_an_unclassified_original_copies_its_blank(
        self, super_client, make_income,
    ):
        """Faithful, not helpful: guessing the line of business would be worse.

        Most of the book predates the field. The draft says what the original
        says, and the form is what tells the operator the original carried no
        origin — a blank that explains itself instead of one that reads as a
        copy that failed.
        """
        response = super_client.get(url(make_income(origin='')))

        assert response.data['origin'] == ''

    def test_concept_is_copied_verbatim_without_a_copy_suffix(
        self, super_client, make_income,
    ):
        """The concept is printed on the cuenta de cobro: no "(copia)" here."""
        income = make_income(concept='Kore - Hosting anual')

        response = super_client.get(url(income))

        assert response.data['concept'] == 'Kore - Hosting anual'

    def test_draft_creates_nothing(self, super_client, make_income):
        income = make_income()

        super_client.get(url(income))

        assert IncomeRecord.objects.count() == 1


class TestAlwaysExpected:
    def test_a_liquid_original_yields_an_expected_draft(
        self, super_client, make_income,
    ):
        income = make_income(
            kind=IncomeRecord.Kind.LIQUID,
            destination=IncomeRecord.Destination.POCKET,
        )

        response = super_client.get(url(income))

        assert response.data['kind'] == IncomeRecord.Kind.EXPECTED
        assert response.data['destination'] == IncomeRecord.Destination.PARTNERS

    def test_a_lost_original_yields_an_expected_draft(
        self, super_client, make_income,
    ):
        income = make_income(kind=IncomeRecord.Kind.LOST)

        response = super_client.get(url(income))

        assert response.data['kind'] == IncomeRecord.Kind.EXPECTED


class TestOccurrenceLinksAreDropped:
    def test_draft_omits_the_links_and_identity_of_the_original(
        self, super_client, make_income,
    ):
        expected = make_income()
        liquid = make_income(
            kind=IncomeRecord.Kind.LIQUID,
            expected_income=expected,
            source_ref='income:1:settlement',
        )

        response = super_client.get(url(liquid))

        assert 'id' not in response.data
        assert 'expected_income' not in response.data
        assert 'pocket_movement' not in response.data
        assert 'source_ref' not in response.data

    def test_draft_does_not_inherit_a_silenced_calendar(
        self, super_client, make_income,
    ):
        """Requirement 8: the duplicate enters the notice calendar clean."""
        income = make_income(
            reminders_muted=True,
            reminders_muted_until=date(2026, 12, 31),
            reminder_count=3,
        )

        response = super_client.get(url(income))

        assert 'reminders_muted' not in response.data
        assert 'reminders_muted_until' not in response.data
        assert 'reminder_count' not in response.data


class TestProposedDate:
    def test_hosting_origin_proposes_the_next_cycle(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_ANNUAL)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 3, 1),
        )

        response = super_client.get(url(income))

        assert response.data['period_date'] == '2027-03-01'
        assert response.data['period_date_source'] == 'hosting_cycle'

    def test_quarterly_hosting_advances_three_months(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.Modality.QUARTERLY)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 3, 1),
        )

        response = super_client.get(url(income))

        assert response.data['period_date'] == '2026-06-01'

    def test_the_day_is_clamped_when_the_cycle_overflows(
        self, super_client, make_income, make_client_profile,
    ):
        """Jan 31 + one month is Feb 28, not March 3."""
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_MONTHLY)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 1, 31),
        )

        response = super_client.get(url(income))

        assert response.data['period_date'] == '2026-02-28'

    def test_the_project_narrows_the_hosting_match(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile()
        billed = Project.objects.create(
            name='Kore', client=profile.user, status=Project.STATUS_ACTIVE,
        )
        other = Project.objects.create(
            name='Otro', client=profile.user, status=Project.STATUS_ACTIVE,
        )
        make_hosting(
            client=profile, project=billed,
            payment_modality=HostingRecord.LEGACY_MONTHLY,
        )
        make_hosting(
            client=profile, project=other,
            payment_modality=HostingRecord.LEGACY_ANNUAL,
        )
        income = make_income(
            client=profile,
            project=billed,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 3, 1),
        )

        response = super_client.get(url(income))

        assert response.data['period_date'] == '2026-04-01'

    def test_a_non_hosting_origin_leaves_the_date_empty(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_ANNUAL)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.DEVELOPMENT,
            period_date=date(2026, 3, 1),
        )

        response = super_client.get(url(income))

        assert response.data['period_date'] is None
        assert response.data['period_date_source'] is None

    def test_hosting_origin_without_a_matching_hosting_leaves_it_empty(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile()
        income = make_income(client=profile, origin=IncomeRecord.Origin.HOSTING)

        response = super_client.get(url(income))

        assert response.data['period_date'] is None

    def test_conflicting_modalities_leave_the_date_empty(
        self, super_client, make_income, make_client_profile,
    ):
        """Two hostings on the same client disagreeing: guessing is worse."""
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_MONTHLY)
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_ANNUAL)
        income = make_income(client=profile, origin=IncomeRecord.Origin.HOSTING)

        response = super_client.get(url(income))

        assert response.data['period_date'] is None
        assert response.data['period_date_source'] is None

    def test_an_inactive_hosting_is_ignored(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile()
        make_hosting(
            client=profile, is_active=False,
            payment_modality=HostingRecord.LEGACY_ANNUAL,
        )
        income = make_income(client=profile, origin=IncomeRecord.Origin.HOSTING)

        response = super_client.get(url(income))

        assert response.data['period_date'] is None


class TestCycleOptions:
    """The candidate dates the form offers so the next period is one click.

    They matter most exactly where the hosting lookup gives up, which is the
    normal case: an income with no origin and no client resolves to nothing.
    """

    def test_offers_the_four_cadences_counted_from_the_original(
        self, super_client, make_income,
    ):
        income = make_income(period_date=date(2026, 3, 15))

        response = super_client.get(url(income))

        assert response.data['cycle_options'] == [
            {'months': 1, 'date': '2026-04-15'},
            {'months': 3, 'date': '2026-06-15'},
            {'months': 6, 'date': '2026-09-15'},
            {'months': 12, 'date': '2027-03-15'},
        ]

    def test_the_options_are_offered_when_no_date_could_be_proposed(
        self, super_client, make_income,
    ):
        """An income with no origin and no client: the everyday case."""
        income = make_income(period_date=date(2026, 3, 1))

        response = super_client.get(url(income))

        assert response.data['period_date'] is None
        assert [o['date'] for o in response.data['cycle_options']] == [
            '2026-04-01', '2026-06-01', '2026-09-01', '2027-03-01',
        ]

    def test_the_day_is_clamped_in_the_options_too(self, super_client, make_income):
        """Jan 31 + one month is Feb 28 here as well, not March 3."""
        income = make_income(period_date=date(2026, 1, 31))

        response = super_client.get(url(income))

        assert response.data['cycle_options'][0] == {
            'months': 1, 'date': '2026-02-28',
        }

    def test_the_options_count_from_the_original_not_from_the_proposal(
        self, super_client, make_income, make_client_profile,
    ):
        """A quarterly hosting proposes June; +1 month is still April."""
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.Modality.QUARTERLY)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 3, 1),
        )

        response = super_client.get(url(income))

        assert response.data['period_date'] == '2026-06-01'
        assert response.data['cycle_options'][0]['date'] == '2026-04-01'


class TestRecordedPeriod:
    """A hosting income with a recorded window proposes the following one.

    First-hand data beats the hosting lookup: the window says what this very
    charge covered, while the lookup infers a modality from the catalog.
    `period_end` is inclusive, so the next window starts the day after it.
    """

    def test_proposes_the_window_right_after_the_recorded_one(
        self, super_client, make_income,
    ):
        income = make_income(
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 8, 15),
            period_start=date(2026, 8, 15),
            period_end=date(2027, 8, 14),
            period_cadence='annual',
        )

        response = super_client.get(url(income))

        assert response.data['period_start'] == '2027-08-15'
        assert response.data['period_end'] == '2028-08-14'
        assert response.data['period_cadence'] == 'annual'
        assert response.data['period_date'] == '2027-08-15'
        assert response.data['period_date_source'] == 'income_period'

    @pytest.mark.parametrize('start, end, billing, cadence, next_start, next_end, next_billing', [
        ('2026-10-01', '2027-03-31', '2026-11-01', 'semiannual',
         '2027-04-01', '2027-09-30', '2027-05-01'),
        ('2026-01-01', '2026-01-31', '2026-01-31', 'monthly',
         '2026-02-01', '2026-02-28', '2026-02-28'),
        ('2026-03-01', '2026-03-15', '2026-03-10', 'custom',
         '2026-03-16', '2026-03-30', '2026-03-25'),
    ], ids=['semester_offset', 'month_end_clamp', 'day_offset'])
    def test_the_expected_payment_date_keeps_its_window_offset(
        self, super_client, make_income, start, end, billing, cadence,
        next_start, next_end, next_billing,
    ):
        """The next charge shifts its expected-payment date with its covered window."""
        income = make_income(
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date.fromisoformat(billing),
            period_start=date.fromisoformat(start),
            period_end=date.fromisoformat(end),
            period_cadence=cadence,
        )

        response = super_client.get(url(income))

        assert response.status_code == 200, response.data
        assert response.data['period_start'] == next_start
        assert response.data['period_end'] == next_end
        assert response.data['period_date'] == next_billing

    def test_the_recorded_window_beats_the_hosting_lookup(
        self, super_client, make_income, make_client_profile,
    ):
        """The catalog says quarterly, the record says monthly: record wins."""
        profile = make_client_profile()
        make_hosting(
            client=profile, payment_modality=HostingRecord.Modality.QUARTERLY,
        )
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 3, 1),
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            period_cadence='monthly',
        )

        response = super_client.get(url(income))

        assert response.data['period_start'] == '2026-04-01'
        assert response.data['period_end'] == '2026-04-30'
        assert response.data['period_date_source'] == 'income_period'

    def test_the_day_is_clamped_across_the_inclusive_arithmetic(
        self, super_client, make_income,
    ):
        """A window ending Jan 31: the next one is Feb 1 through Feb 28."""
        income = make_income(
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 1, 1),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            period_cadence='monthly',
        )

        response = super_client.get(url(income))

        assert response.data['period_start'] == '2026-02-01'
        assert response.data['period_end'] == '2026-02-28'

    def test_a_custom_cadence_repeats_the_recorded_duration(
        self, super_client, make_income,
    ):
        income = make_income(
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 3, 1),
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 15),
            period_cadence='custom',
        )

        response = super_client.get(url(income))

        assert response.data['period_start'] == '2026-03-16'
        assert response.data['period_end'] == '2026-03-30'

    def test_a_legacy_hosting_without_a_window_falls_back_to_the_lookup(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_ANNUAL)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 3, 1),
        )

        response = super_client.get(url(income))

        assert response.data['period_start'] is None
        assert response.data['period_end'] is None
        assert response.data['period_date'] == '2027-03-01'
        assert response.data['period_date_source'] == 'hosting_cycle'

    def test_a_non_hosting_income_never_proposes_a_window(
        self, super_client, make_income,
    ):
        """A stray recorded window on another origin must not leak through."""
        income = make_income(
            origin=IncomeRecord.Origin.DEVELOPMENT,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            period_cadence='monthly',
        )

        response = super_client.get(url(income))

        assert response.data['period_start'] is None
        assert response.data['period_date_source'] is None


class TestPeriodAnchor:
    """What the duplicate's window is counted from, and off what.

    Duplicating opens the period that follows, so the count starts at the
    original. The draft cannot always prefill a window, but it can always say
    what to count from — which is what keeps the form off today, a date that
    continues nothing.
    """

    def test_a_recorded_window_anchors_the_day_after_it_closes(
        self, super_client, make_income,
    ):
        income = make_income(
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 2, 1),
            period_start=date(2026, 2, 1),
            period_end=date(2026, 7, 31),
            period_cadence='semiannual',
        )

        response = super_client.get(url(income))

        assert response.data['period_anchor'] == {
            'source': 'income_period',
            'start': '2026-08-01',
            'origin_start': '2026-02-01',
            'origin_end': '2026-07-31',
            'origin_date': '2026-02-01',
        }

    def test_the_hosting_cycle_anchors_on_the_original_date_plus_the_cycle(
        self, super_client, make_income, make_client_profile,
    ):
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.Modality.QUARTERLY)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 3, 1),
        )

        response = super_client.get(url(income))

        anchor = response.data['period_anchor']
        assert anchor['source'] == 'hosting_cycle'
        assert anchor['start'] == '2026-06-01'
        assert anchor['origin_date'] == '2026-03-01'
        assert anchor['origin_start'] is None

    def test_the_day_is_clamped_on_the_hosting_cycle_anchor(
        self, super_client, make_income, make_client_profile,
    ):
        """Jan 31 plus a month lands on Feb 28, not on March 3."""
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_MONTHLY)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 1, 31),
        )

        response = super_client.get(url(income))

        assert response.data['period_anchor']['start'] == '2026-02-28'

    def test_without_a_window_or_a_resolvable_hosting_the_date_is_the_ground(
        self, super_client, make_income, make_client_profile,
    ):
        """Two active hostings and no project: the catalog cannot decide.

        This is the case the whole anchor exists for — the majority of the book
        until every hosting income carries its window. Nothing is prefilled,
        because only the cadence the operator picks can say how long the
        original's period lasted, but the date it is counted from travels.
        """
        profile = make_client_profile()
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_MONTHLY)
        make_hosting(client=profile, payment_modality=HostingRecord.LEGACY_ANNUAL)
        income = make_income(
            client=profile,
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 2, 1),
        )

        response = super_client.get(url(income))

        assert response.data['period_date'] is None
        assert response.data['period_anchor'] == {
            'source': 'original_date',
            'start': None,
            'origin_start': None,
            'origin_end': None,
            'origin_date': '2026-02-01',
        }

    def test_a_non_hosting_original_still_carries_its_date(
        self, super_client, make_income,
    ):
        """The operator may switch the origin to Hosting inside the modal.

        The window then has to chain with the record being duplicated just the
        same, so the anchor is built for every origin — not only for hosting.
        """
        income = make_income(
            origin=IncomeRecord.Origin.DEVELOPMENT,
            period_date=date(2026, 5, 20),
        )

        response = super_client.get(url(income))

        assert response.data['period_anchor']['source'] == 'original_date'
        assert response.data['period_anchor']['origin_date'] == '2026-05-20'

    def test_the_anchor_agrees_with_what_the_draft_prefills(
        self, super_client, make_income,
    ):
        """One resolution, so the dates and the explanation cannot disagree."""
        income = make_income(
            origin=IncomeRecord.Origin.HOSTING,
            period_date=date(2026, 2, 1),
            period_start=date(2026, 2, 1),
            period_end=date(2026, 7, 31),
            period_cadence='semiannual',
        )

        response = super_client.get(url(income))

        assert (
            response.data['period_anchor']['start']
            == response.data['period_start']
            == response.data['period_date']
        )
