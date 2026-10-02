"""Seed plausible fake data for the accounting module (dev/staging).

Usage:
    python manage.py create_fake_accounting [--count N]

Every row is tagged source_ref='fake:accounting' so delete_fake_data can
remove exactly these rows. Written with the plain ORM: no change logs,
no email notifications.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Project, UserProfile

from content.models import (
    CreditCardStatement,
    CreditCardTransaction,
    MerchantAlias,
    AdsSpendRecord,
    CardBalanceSnapshot,
    CreditCard,
    ExpenseRecord,
    HostingCycle,
    HostingRecord,
    IncomeRecord,
    Ledger,
    NotificationRecipient,
    PocketMovement,
    RecurringCategory,
    RecurringPayment,
)
from content.serializers.accounting import split_half
from content.fake_data import add_seed_arguments, ensure_fake_data_allowed, seed_context

FAKE_REF = 'fake:accounting'
_ANCHOR_DATE = None

INCOME_CONCEPTS = [
    'Acme SAS - Inicio 40%', 'Acme SAS - Diseño 30%', 'Acme SAS - Entrega 30%',
    'Globex - Inicio 40%', 'Globex - Hosting', 'Initech - Entrega 30%',
    'Umbrella - Diseño 30%', 'Hooli - Inicio 40%',
]
EXPENSE_CONCEPTS = [
    ('Claude Code 20x', 'business'), ('Google Ads - Campaña', 'business'),
    ('Figma mensual', 'business'), ('Anuncios FB', 'business'),
    ('Almuerzo equipo', 'personal'), ('Gasolina carro', 'personal'),
    ('Aporte casa EPM', 'personal'), ('Windsurf', 'business'),
]
def _month_start(months_ago):
    anchor = (_ANCHOR_DATE or date.today()).replace(day=1)
    absolute_month = anchor.year * 12 + anchor.month - 1 - months_ago
    year, zero_based_month = divmod(absolute_month, 12)
    return date(year, zero_based_month + 1, 1)


class Command(BaseCommand):
    help = 'Create fake accounting data (tagged fake:accounting).'

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=10)

    def handle(self, *args, **options):
        ensure_fake_data_allowed('create_fake_accounting')
        context = seed_context(options, 'accounting')
        global _ANCHOR_DATE
        _ANCHOR_DATE = context.anchor_date
        count = options['count']
        rng = context.rng

        created = 0
        # Client profiles may not exist at all: this command also runs
        # standalone in tests. Without them every income stays unassigned,
        # which is a legitimate (and useful) seed state.
        client_profiles = list(UserProfile.objects.clients()[:max(count, 8)])
        if not client_profiles:
            call_command(
                'create_fake_clients_projects',
                '--count', str(max(8, min(count, 60))),
                '--seed', str(context.seed),
                '--anchor-date', context.anchor_date.isoformat(),
                verbosity=0,
            )
            client_profiles = list(UserProfile.objects.clients()[:max(count, 8)])
        # Seed a small project catalog before resolving projects per client:
        # the Projects module needs clients WITH projects (counts, scopes,
        # the fly-create picker) and clients WITHOUT any (the indicator's
        # bucket). The first two profiles get one — plus one archived row to
        # exercise the Archivados scope — and the rest stay uncovered on
        # purpose. delete_fake_data removes Project wholesale, so these need
        # no source tag.
        for offset, profile in enumerate(client_profiles[:2]):
            if Project.objects.filter(client_id=profile.user_id).exists():
                # Never widen an existing catalog: callers (and tests) that
                # pre-created a project rely on every linked row using it.
                continue
            base = (profile.company_name or 'Proyecto demo').strip()
            Project.objects.get_or_create(
                client_id=profile.user_id, name=f'{base} Web',
                defaults={'status': 'active'},
            )
            if offset == 0:
                Project.objects.get_or_create(
                    client_id=profile.user_id, name=f'{base} Legacy',
                    defaults={'status': 'archived'},
                )
        # A record's project must belong to its own client (the write
        # serializers enforce it), so the seed resolves projects per client
        # rather than picking from a global pool. Clients with no project
        # simply seed rows without one — a legitimate state, and the one a
        # cobro por diagnóstico is in.
        projects_by_client = {
            profile.pk: list(Project.objects.filter(client_id=profile.user_id))
            for profile in client_profiles
        }
        project_clients = [
            profile for profile in client_profiles
            if projects_by_client.get(profile.pk)
        ]

        def project_for(profile, index):
            """One of the client's own projects, or None.

            Every sixth linked row is left without a project on purpose:
            'Sin proyecto' is a real state the filters have a bucket for.
            """
            if profile is None or index % 6 == 1:
                return None
            options = projects_by_client.get(profile.pk) or []
            return options[index % len(options)] if options else None

        for index in range(count):
            period = _month_start(rng.choice([-3, -1, 0, 1, 3, 6, 12]))
            total = (
                Decimal('999999999999.99') if index == 0
                else Decimal(rng.randrange(400_000, 4_000_000, 10_000))
            )
            gustavo, carlos = split_half(total)
            concept = rng.choice(INCOME_CONCEPTS)
            # Cobro por diagnóstico: what the "Con diagnóstico facturado"
            # subfilter of /panel/clients reads. Chosen by index rather than by
            # concept so the cut always has data, and so `rng.choice` above is
            # still consumed every iteration — the seeded stream, and every
            # assertion that depends on it, stays exactly as it was. Index 3 is
            # also the written-off row, which seeds the case the filter must
            # exclude.
            is_diagnostic = index % 4 == 0 or index % 8 == 3
            if is_diagnostic:
                concept = 'Diagnóstico técnico - Cobro único'
            origin = (
                IncomeRecord.Origin.DIAGNOSTIC if is_diagnostic
                else IncomeRecord.Origin.HOSTING if 'Hosting' in concept
                else IncomeRecord.Origin.DEVELOPMENT
            )
            client_pool = project_clients or client_profiles
            client = client_pool[index % len(client_pool)]
            # Written off: money we already know will never arrive. It stays
            # out of the expected projection, so it never gets a liquid row.
            is_lost = index % 8 == 3
            # The rows intentionally cover every manual forecast state: three
            # partials cycle green/amber/red, a pending row remains selected
            # without a colour, and a paid row keeps a historical colour while
            # its independent switch is off. Paid and lost rows never enter
            # the active shortlist.
            confidence = (
                IncomeRecord.CollectionConfidence.HIGH if index == 2 else ''
            )
            is_receivable_candidate = False
            if not is_lost and index % 4 == 1:
                confidence = (
                    IncomeRecord.CollectionConfidence.HIGH,
                    IncomeRecord.CollectionConfidence.MEDIUM,
                    IncomeRecord.CollectionConfidence.LOW,
                )[(index // 4) % 3]
                is_receivable_candidate = True
            elif not is_lost and index % 8 == 7:
                is_receivable_candidate = True
            income = IncomeRecord.objects.create(
                vat_rate=Decimal('19') if index % 3 == 0 else Decimal('0') if index % 3 == 1 else None,
                concept=concept,
                kind=(
                    IncomeRecord.Kind.LOST if is_lost
                    else IncomeRecord.Kind.EXPECTED
                ),
                period_date=period,
                total_amount=total,
                gustavo_amount=gustavo,
                carlos_amount=carlos,
                client=client,
                project=project_for(client, index),
                origin=origin,
                is_receivable_candidate=is_receivable_candidate,
                collection_confidence=confidence,
                source_ref=FAKE_REF,
            )
            created += 1
            if is_lost:
                continue
            # Fulfilment mix covering the three states the Ingresos tab
            # renders: a 40% partial for a quarter of the rows, a full
            # payment for the (remaining) even rows — a third of those into
            # the company pocket — and nothing for the rest.
            if index % 4 == 1:
                paid_fraction = Decimal('0.4')
            elif index % 2 == 0:
                paid_fraction = Decimal('1')
            else:
                continue
            paid = (total * paid_fraction).quantize(Decimal('0.01'))
            paid_gustavo, paid_carlos = split_half(paid)
            # index % 6 == 0 is always even, so a partial row never lands
            # in the pocket branch.
            to_pocket = index % 6 == 0
            movement = None
            if to_pocket:
                movement = PocketMovement.objects.create(
                    concept=f'Ingreso: {concept}',
                    movement_date=period + timedelta(days=14),
                    direction=PocketMovement.Direction.IN,
                    amount=paid,
                    source_ref=FAKE_REF,
                )
                created += 1
            IncomeRecord.objects.create(
                concept=concept,
                kind=IncomeRecord.Kind.LIQUID,
                # Pocket liquidations record the exact payment day, the
                # liquidate modal's optional toggle; the rest stay monthly.
                period_date=(
                    period + timedelta(days=14) if to_pocket else period
                ),
                destination=(
                    IncomeRecord.Destination.POCKET
                    if to_pocket else IncomeRecord.Destination.PARTNERS
                ),
                total_amount=paid,
                gustavo_amount=Decimal('0') if to_pocket else paid_gustavo,
                carlos_amount=Decimal('0') if to_pocket else paid_carlos,
                expected_income=income,
                vat_rate=income.vat_rate,
                pocket_movement=movement,
                client=client,
                origin=origin,
                source_ref=FAKE_REF,
            )
            created += 1

        # One abono: a single pocket movement covering three expected
        # incomes (two in full, the third partially), the state the bulk
        # settle flow produces. Appended AFTER the loop on purpose — the
        # loop's rng stream and index arithmetic are load-bearing for
        # existing assertions. Amounts are fixed for the same reason.
        abono_client = client_profiles[0] if client_profiles else None
        abono_day = _month_start(0) + timedelta(days=5)
        abono_movement = PocketMovement.objects.create(
            concept=(
                f'Abono {abono_client.company_name}'.strip()
                if abono_client else 'Abono 3 ingresos'
            ),
            movement_date=abono_day,
            direction=PocketMovement.Direction.IN,
            amount=Decimal('1000000'),
            source_ref=FAKE_REF,
        )
        created += 1
        abono_slices = [
            (Decimal('500000'), Decimal('500000'), _month_start(3)),
            (Decimal('300000'), Decimal('300000'), _month_start(2)),
            (Decimal('400000'), Decimal('200000'), _month_start(1)),
        ]
        for offset, (expected_total, paid_slice, period) in enumerate(
            abono_slices,
        ):
            slice_concept = f'Abono demo - Fase {offset + 1}'
            gustavo, carlos = split_half(expected_total)
            parent = IncomeRecord.objects.create(
                concept=slice_concept,
                kind=IncomeRecord.Kind.EXPECTED,
                period_date=period,
                total_amount=expected_total,
                gustavo_amount=gustavo,
                carlos_amount=carlos,
                client=abono_client,
                origin=IncomeRecord.Origin.DEVELOPMENT,
                source_ref=FAKE_REF,
            )
            paid_gustavo, paid_carlos = split_half(paid_slice)
            IncomeRecord.objects.create(
                concept=slice_concept,
                kind=IncomeRecord.Kind.LIQUID,
                period_date=abono_day,
                destination=IncomeRecord.Destination.POCKET,
                total_amount=paid_slice,
                gustavo_amount=paid_gustavo,
                carlos_amount=paid_carlos,
                expected_income=parent,
                pocket_movement=abono_movement,
                client=abono_client,
                origin=IncomeRecord.Origin.DEVELOPMENT,
                source_ref=FAKE_REF,
            )
            created += 2

        for index in range(count):
            concept, category = EXPENSE_CONCEPTS[index % len(EXPENSE_CONCEPTS)]
            total = Decimal(rng.randrange(20_000, 1_200_000, 1_000))
            half = (total / 2).quantize(Decimal('0.01'))
            custom_split = index % 3 == 0
            ExpenseRecord.objects.create(
                concept=concept,
                period_date=_month_start(rng.choice([-2, 0, 1, 4, 8, 12])),
                category=category,
                total_amount=total,
                gustavo_amount=total if custom_split else half,
                carlos_amount=Decimal('0') if custom_split else total - half,
                source_ref=FAKE_REF,
            )
            created += 1

        hosting_target = max(1, min(count, 45))
        for index in range(hosting_target):
            hosting_client = client_profiles[index % len(client_profiles)]
            client_name = (
                hosting_client.company_name
                or hosting_client.user.get_full_name()
                or f'Cliente hosting {index + 1}'
            )
            domain = f'https://hosting-{index + 1}.example.test/'
            monthly = Decimal(rng.randrange(20_000, 100_000, 1_000))
            cycles = index % 5
            modality = rng.choice(list(HostingRecord.Modality))
            modality_months = HostingRecord.MODALITY_MONTHS[modality]
            payment_per_cycle = monthly * modality_months
            hosting = HostingRecord.objects.create(
                vat_rate=Decimal('19') if index % 2 == 0 else Decimal('0'),
                client=hosting_client,
                project=project_for(hosting_client, index),
                client_name=client_name,
                client_email=f'facturacion@{domain.split("//")[-1].strip("/")}',
                domain_url=domain,
                monthly_value=monthly,
                payment_modality=modality,
                valid_from=_month_start((12, 6, 1)[index % 3]),
                valid_to=(
                    _month_start(0) - timedelta(days=1)
                    if index % 3 == 0
                    else _month_start((-2, -8)[index % 2])
                ),
                cycles_count=cycles,
                payment_per_cycle=payment_per_cycle,
                total_paid=payment_per_cycle * cycles,
                source_ref=FAKE_REF,
            )
            # Cycle history is the source of truth for total_paid.
            for cycle_index in range(cycles):
                HostingCycle.objects.create(
                    hosting_record=hosting,
                    modality=hosting.payment_modality,
                    amount=payment_per_cycle,
                    paid_at=_month_start(
                        modality_months * (cycles - cycle_index),
                    ),
                    source_ref=FAKE_REF,
                )
                created += 1
            created += 1

        # Pocket egresos follow the operating model: every draw is a
        # company-ledger expense (a partner attribution assigns it 100%
        # to that partner, category personal), mirroring _sync_from_pocket.
        # A third of the rows stay unlinked to represent historical
        # movements created before the linkage existed (no backfill).
        for index in range(count):
            movement_date = _month_start(rng.randrange(0, 6)) + timedelta(
                days=rng.randrange(0, 28),
            )
            amount = Decimal(rng.randrange(50_000, 900_000, 1_000))
            shape = index % 3
            if shape == 2:
                PocketMovement.objects.create(
                    concept=rng.choice(['Trans. histórica', 'Ajuste inicial']),
                    movement_date=movement_date,
                    direction=rng.choice(list(PocketMovement.Direction)),
                    amount=amount,
                    source_ref=FAKE_REF,
                )
                created += 1
                continue
            if shape == 0:
                attribution = rng.choice([Ledger.GUSTAVO, Ledger.CARLOS])
                concept = f'Retiro {attribution.label}'
                category = ExpenseRecord.Category.PERSONAL
            else:
                attribution = Ledger.COMPANY
                concept = 'Pago T.C'
                category = ExpenseRecord.Category.BUSINESS
            if attribution == Ledger.GUSTAVO:
                gustavo, carlos = amount, Decimal('0')
            elif attribution == Ledger.CARLOS:
                gustavo, carlos = Decimal('0'), amount
            else:
                gustavo, carlos = split_half(amount)
            movement = PocketMovement.objects.create(
                concept=concept,
                movement_date=movement_date,
                direction=PocketMovement.Direction.OUT,
                amount=amount,
                source_ref=FAKE_REF,
            )
            ExpenseRecord.objects.create(
                vat_rate=Decimal('19') if shape == 1 and index % 2 == 0 else Decimal('0'),
                concept=concept,
                period_date=movement_date.replace(day=1),
                ledger=Ledger.COMPANY,
                category=category,
                total_amount=amount,
                gustavo_amount=gustavo,
                carlos_amount=carlos,
                pocket_movement=movement,
                source_ref=FAKE_REF,
            )
            created += 2

        frequencies = RecurringPayment.Frequency
        # The frequency mix is deliberate: it spans a catalog entry per order of
        # magnitude plus a custom cycle, so the monthly-equivalent column and the
        # percentage weights get exercised by the fake dataset.
        for (
            name, price, currency, category_name, frequency, months,
            is_active, is_archived, reminders_muted,
        ) in [
            (
                'Claude Code 20x', '200.00', 'USD',
                'Suscripciones de IA', frequencies.MONTHLY, None,
                True, False, False,
            ),
            (
                'Netflix', '39800.00', 'COP',
                'Extras / otros', frequencies.MONTHLY, None,
                False, False, False,
            ),
            (
                'NameCheap', '10.98', 'USD',
                'Arquitectura e infraestructura', frequencies.ANNUAL, None,
                True, False, True,
            ),
            (
                'Plan Figma equipo', '270000.00', 'COP',
                'Extras / otros', frequencies.QUARTERLY, None,
                True, False, False,
            ),
            (
                'Mantenimiento servidor', '500000.00', 'COP',
                'Arquitectura e infraestructura', frequencies.CUSTOM, 5,
                True, False, False,
            ),
            (
                'Herramienta de pruebas cancelada', '85000.00', 'COP',
                'Extras / otros', frequencies.MONTHLY, None,
                False, True, False,
            ),
        ]:
            recurring_category = RecurringCategory.objects.filter(
                name=category_name,
            ).first()
            RecurringPayment.objects.create(
                name=name,
                price=Decimal(price),
                currency=currency,
                frequency=frequency,
                custom_months=months,
                billing_day=rng.randrange(1, 29),
                category=recurring_category,
                is_active=is_active,
                is_archived=is_archived,
                archived_at=timezone.now() if is_archived else None,
                reminders_muted=reminders_muted,
                source_ref=FAKE_REF,
            )
            created += 1

        for index in range(count):
            AdsSpendRecord.objects.create(
                spend_date=_month_start(rng.randrange(0, 6)) + timedelta(
                    days=rng.randrange(0, 28),
                ),
                origin_card=rng.choice(['T.C 0655', 'T.C 0656']),
                amount=Decimal(rng.randrange(30_000, 200_000, 1_000)),
                source_ref=FAKE_REF,
            )
            created += 1

        # Card catalog: 'T.C 0064' may already exist as the real seeded
        # card (source_ref='') — get_or_create leaves it intact and only
        # tags cards this command actually creates.
        catalog_specs = [
            ('T.C 0064', Decimal('8000000.00'), _month_start(5)),
            ('T.C 0655', Decimal('5000000.00'), _month_start(2)),
        ]
        for name, credit_limit, statements_since in catalog_specs:
            _, was_created = CreditCard.objects.get_or_create(
                name=name,
                defaults={
                    'credit_limit': credit_limit,
                    'statements_since': statements_since,
                    'source_ref': FAKE_REF,
                },
            )
            if was_created:
                created += 1

        main_card = CreditCard.objects.get(name='T.C 0064')
        for months_ago in range(3):
            debt = Decimal(rng.randrange(1_000_000, 8_000_000, 1_000))
            CardBalanceSnapshot.objects.create(
                snapshot_date=_month_start(months_ago),
                card_name=main_card.name,
                available_amount=main_card.credit_limit - debt,
                debt_amount=debt,
                source_ref=FAKE_REF,
            )
            created += 1

        # Credit-card statements: two cards, mixed draft/processed, with
        # installments, a USD purchase, a refund and an unidentified line.
        aliases = [
            ('PAYU*NETFLIX', 'Netflix', 'software'),
            ('PRIMAX MEDELLIN', 'Primax', 'fuel'),
            ('FACEBK ADS', 'Meta Ads', 'advertising'),
        ]
        for match_text, merchant, category in aliases:
            MerchantAlias.objects.get_or_create(
                match_text=match_text,
                defaults={
                    'merchant_name': merchant,
                    'default_category': category,
                    'source_ref': FAKE_REF,
                },
            )
            created += 1

        statement_specs = [
            ('T.C 0064', 2, CreditCardStatement.Status.PROCESSED),
            ('T.C 0064', 1, CreditCardStatement.Status.PROCESSED),
            ('T.C 0064', 0, CreditCardStatement.Status.DRAFT),
            ('T.C 0655', 1, CreditCardStatement.Status.PROCESSED),
        ]
        for card_name, months_ago, statement_status in statement_specs:
            period = _month_start(months_ago)
            transactions = [
                {
                    'raw_description': 'PAYU*NETFLIX 990011',
                    'merchant_name': 'Netflix', 'category': 'software',
                    'amount': Decimal('44900.00'), 'is_identified': True,
                },
                {
                    'raw_description': 'PRIMAX MEDELLIN 8811',
                    'merchant_name': 'Primax', 'category': 'fuel',
                    'amount': Decimal(rng.randrange(120_000, 260_000, 5_000)),
                    'is_identified': True,
                },
                {
                    'raw_description': 'ANTHROP*CLAUDE.AI SF',
                    'merchant_name': 'Anthropic', 'category': 'software',
                    'amount': Decimal('88000.00'), 'is_identified': True,
                    'original_amount': Decimal('20.00'),
                    'original_currency': 'USD',
                },
                {
                    'raw_description': 'EXITO POBLADO POS 4451',
                    'merchant_name': 'Éxito', 'category': 'groceries',
                    'amount': Decimal(rng.randrange(150_000, 500_000, 10_000)),
                    'is_identified': True,
                    'installment_number': 1 + months_ago,
                    'installments_total': 12,
                },
                {
                    'raw_description': 'COMERCIALIZADORA XYZ SAS',
                    'amount': Decimal('99900.00'),
                },
                {
                    'raw_description': 'REVERSION PAYU*NETFLIX',
                    'merchant_name': 'Netflix', 'category': 'software',
                    'amount': Decimal('-44900.00'), 'is_identified': True,
                },
            ]
            purchases_total = sum(tx['amount'] for tx in transactions)
            statement, was_created = CreditCardStatement.objects.get_or_create(
                card_name=card_name,
                period_date=period,
                defaults={
                    'status': statement_status,
                    'purchases_total': purchases_total,
                    'previous_balance': Decimal(
                        rng.randrange(1_000_000, 5_000_000, 10_000),
                    ),
                    'payments_total': Decimal(
                        rng.randrange(500_000, 2_000_000, 10_000),
                    ),
                    'interest_and_fees': Decimal(
                        rng.randrange(30_000, 120_000, 1_000),
                    ),
                    'minimum_payment': Decimal(
                        rng.randrange(200_000, 600_000, 10_000),
                    ),
                    'due_date': period + timedelta(days=45),
                    'source_ref': FAKE_REF,
                },
            )
            if was_created:
                CreditCardTransaction.objects.bulk_create(
                    CreditCardTransaction(
                        statement=statement,
                        transaction_date=period + timedelta(
                            days=rng.randrange(1, 27),
                        ),
                        source_ref=FAKE_REF,
                        **tx,
                    )
                    for tx in transactions
                )
                created += 1 + len(transactions)

        # One paused recipient on purpose: the panel's per-recipient toggle
        # is only exercised when the seeded list has both states.
        if not NotificationRecipient.objects.exists():
            NotificationRecipient.objects.bulk_create([
                NotificationRecipient(
                    email='gustavo@example.com',
                    is_active=True,
                    source_ref=FAKE_REF,
                ),
                NotificationRecipient(
                    email='carlos@example.com',
                    is_active=False,
                    source_ref=FAKE_REF,
                ),
            ])
            created += 2

        self.stdout.write(self.style.SUCCESS(
            f'Created {created} fake accounting rows (source_ref={FAKE_REF}, '
            f'seed={context.seed}, anchor={context.anchor_date}).',
        ))
