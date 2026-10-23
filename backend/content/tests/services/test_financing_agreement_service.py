"""Behavior tests for financing agreements and frozen monthly allowances."""

import hashlib
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader

from content.models import FinancingAgreement, FinancingAgreementTemplate
from content.services.financing_agreement_pdf_service import (
    FinancingAgreementPdfService,
)
from content.services.financing_agreement_service import (
    DEFAULT_FINANCING_TEMPLATE_MARKDOWN,
    FinancingAgreementTransitionError,
    FinancingAgreementValidationError,
    add_years,
    build_installment_schedule,
    calculate_financed_balance,
    create_agreement,
    create_second_cycle,
    mark_ready,
    normalize_installment_schedule,
    resolve_agreement_markdown,
    update_draft,
    validate_template_markdown,
)

pytestmark = pytest.mark.django_db


def _template():
    return FinancingAgreementTemplate.objects.create(
        name='Prueba',
        version=1,
        is_default=True,
        content_markdown=DEFAULT_FINANCING_TEMPLATE_MARKDOWN,
    )


def _agreement_data(client, template, **overrides):
    data = {
        'client': client,
        'original_contract_reference': 'Contrato PA-001',
        'original_contract_date': date(2026, 1, 15),
        'project_name': 'Vástago',
        'financed_scope': 'Desarrollo e implementación de la fase 2.',
        'modality': FinancingAgreement.Modality.FIVE_YEAR,
        'partnership_start_date': date(2026, 2, 1),
        'currency': 'COP',
        'total_value': Decimal('25000000.00'),
        'initial_payment': Decimal('5000000.00'),
        'hosting_value': Decimal('500000.00'),
        'hosting_period': FinancingAgreement.HostingPeriod.MONTHLY,
        'first_installment_date': date(2026, 3, 5),
        'template': template,
    }
    data.update(overrides)
    return data


def _current_policy(actor):
    from content.models import FinancingPolicyRevision
    return FinancingPolicyRevision.get_current() or FinancingPolicyRevision.objects.create(
        version=1, created_by=actor,
    )


def test_schedule_rounding_preserves_exact_financed_balance():
    schedule = build_installment_schedule(Decimal('100.00'), date(2026, 3, 5))

    assert len(schedule) == 12
    assert schedule[0]['amount'] == '8.33'
    assert schedule[-1]['amount'] == '8.37'
    assert sum(Decimal(row['amount']) for row in schedule) == Decimal('100.00')


@pytest.mark.parametrize(
    ('modality', 'includes_exclusivity'),
    [('five_year', True), ('three_year', False)],
)
def test_draft_conceptual_exclusivity_follows_selected_modality(
    make_client_profile, admin_user, company_settings, modality, includes_exclusivity,
):
    """Only a five-year draft includes the contractor's bounded non-compete."""
    agreement = create_agreement(
        _agreement_data(make_client_profile(nit='9001'), _template(), modality=modality),
        actor=admin_user,
    )

    markdown = resolve_agreement_markdown(agreement, draft=True)

    assert ('Exclusividad conceptual y no competencia de EL CONTRATISTA' in markdown) is includes_exclusivity
    assert ('compitan en el mismo sector y nicho' in markdown) is includes_exclusivity
    assert ('Un segundo ciclo no reinicia ni amplía esta restricción' in markdown) is includes_exclusivity


def test_switching_draft_to_three_years_removes_conceptual_exclusivity(
    make_client_profile, admin_user, company_settings,
):
    """Changing modality must remove the previously offered extra commitment."""
    agreement = create_agreement(
        _agreement_data(make_client_profile(nit='9001'), _template()),
        actor=admin_user,
    )
    assert 'Exclusividad conceptual' in resolve_agreement_markdown(agreement, draft=True)

    updated = update_draft(agreement, {'modality': 'three_year'}, actor=admin_user)

    assert 'Exclusividad conceptual' not in resolve_agreement_markdown(updated, draft=True)
    assert updated.partnership_end_date == date(2029, 2, 1)


def test_pdf_keeps_previously_frozen_conceptual_terms(
    make_client_profile, admin_user, company_settings,
):
    """Generating an existing addendum must not insert newly published terms."""
    agreement = create_agreement(
        _agreement_data(make_client_profile(nit='9001'), _template()),
        actor=admin_user,
    )
    ready = mark_ready(agreement, actor=admin_user)
    previous_text = '# Otrosí\n\nCondiciones originales revisadas por las partes.'
    FinancingAgreement.objects.filter(pk=ready.pk).update(
        resolved_contract_markdown=previous_text,
        resolved_contract_sha256=hashlib.sha256(previous_text.encode()).hexdigest(),
    )
    ready.refresh_from_db()

    pdf = FinancingAgreementPdfService.build_draft(ready)
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)

    assert 'Condiciones originales revisadas por las partes.' in text
    assert 'Exclusividad conceptual' not in text
    ready.refresh_from_db()
    assert ready.resolved_contract_markdown == previous_text


def test_schedule_rejects_due_date_after_fifth_day():
    schedule = build_installment_schedule(Decimal('1200.00'), date(2026, 3, 5))
    schedule[4]['due_date'] = '2026-07-06'

    with pytest.raises(FinancingAgreementValidationError) as exc_info:
        normalize_installment_schedule(schedule, Decimal('1200.00'))

    assert 'días 1 y 5' in str(exc_info.value.errors['installment_schedule'])


def test_mark_ready_freezes_numbered_legal_snapshot(
    make_client_profile,
    admin_user,
    company_settings,
):
    client = make_client_profile(nit='901234567-1')
    agreement = create_agreement(
        _agreement_data(client, _template()),
        actor=admin_user,
    )

    ready = mark_ready(agreement, actor=admin_user)

    assert ready.number.startswith('OFIN-')
    assert ready.status == FinancingAgreement.Status.READY
    assert 'Ana Cliente' in ready.resolved_contract_markdown
    assert '20.000.000,00 COP' in ready.resolved_contract_markdown
    assert ready.resolved_contract_sha256 == hashlib.sha256(
        ready.resolved_contract_markdown.encode('utf-8'),
    ).hexdigest()


def test_second_cycle_requires_completed_first_cycle(
    make_client_profile,
    admin_user,
    company_settings,
):
    agreement = create_agreement(
        _agreement_data(make_client_profile(nit='9001'), _template()),
        actor=admin_user,
    )

    with pytest.raises(FinancingAgreementTransitionError):
        create_second_cycle(agreement, actor=admin_user)


def test_second_cycle_update_preserves_original_partnership_end(
    make_client_profile,
    admin_user,
    company_settings,
):
    first = create_agreement(
        _agreement_data(make_client_profile(nit='9002'), _template()),
        actor=admin_user,
    )
    FinancingAgreement.objects.filter(pk=first.pk).update(
        status=FinancingAgreement.Status.COMPLETED,
    )
    first.refresh_from_db()
    second = create_second_cycle(first, actor=admin_user)

    updated = update_draft(
        second,
        {
            'partnership_start_date': first.partnership_start_date,
            'total_value': Decimal('25000000.00'),
            'initial_payment': Decimal('5000000.00'),
            'first_installment_date': date(2028, 3, 5),
            'financed_scope': 'Segunda fase del producto.',
        },
        actor=admin_user,
    )

    assert updated.partnership_end_date == first.partnership_end_date
    assert 'Un segundo ciclo no reinicia ni amplía esta restricción' in resolve_agreement_markdown(updated, draft=True)


def test_five_year_agreement_freezes_the_current_monthly_requirement_allowance(
    make_client_profile, admin_user, company_settings,
):
    """Fails if changing the allowance settings rewrites a signed commercial commitment."""
    from content.models import HourPackageSettings

    settings = HourPackageSettings.load()
    settings.alliance_xs_count = 4
    settings.alliance_s_count = 2
    settings.alliance_m_count = 1
    settings.save()
    _current_policy(admin_user)
    template = _template()
    first = create_agreement(
        _agreement_data(make_client_profile(nit='9011'), template), actor=admin_user,
    )
    settings.alliance_xs_count = 8
    settings.alliance_s_count = 3
    settings.alliance_m_count = 2
    settings.save()
    second = create_agreement(
        _agreement_data(make_client_profile(nit='9012'), template), actor=admin_user,
    )

    assert first.requirement_allowance == {'xs': 4, 's': 2, 'm': 1}
    assert second.requirement_allowance == {'xs': 8, 's': 3, 'm': 2}
    assert '4 XS, 2 S y 1 M cada mes' in resolve_agreement_markdown(first, draft=True)


def test_legacy_empty_allowance_keeps_its_historical_hours_clause(
    make_client_profile, admin_user, company_settings,
):
    """Fails if an old financing agreement is retroactively rewritten as a size package."""
    _current_policy(admin_user)
    agreement = create_agreement(
        _agreement_data(make_client_profile(nit='9013'), _template()), actor=admin_user,
    )
    FinancingAgreement.objects.filter(pk=agreement.pk).update(requirement_allowance={})
    agreement.refresh_from_db()

    assert 'sesenta (60) horas' in resolve_agreement_markdown(agreement, draft=True)


def test_three_year_agreement_does_not_offer_monthly_requirement_allowances(
    make_client_profile, admin_user, company_settings,
):
    """Fails if the shorter agreement starts promising the five-year allowance."""
    _current_policy(admin_user)
    agreement = create_agreement(
        _agreement_data(
            make_client_profile(nit='9014'), _template(), modality=FinancingAgreement.Modality.THREE_YEAR,
        ), actor=admin_user,
    )

    text = resolve_agreement_markdown(agreement, draft=True)

    assert agreement.requirement_allowance == {}
    assert 'no incluye cupos mensuales de requerimientos' in text
    assert 'cada mes desde la salida a producción' not in text

    from content.models import HourPackageSettings
    settings = HourPackageSettings.load()
    settings.alliance_xs_count = 8
    settings.alliance_s_count = 3
    settings.alliance_m_count = 2
    settings.save()
    revised = update_draft(agreement, {'modality': FinancingAgreement.Modality.FIVE_YEAR}, actor=admin_user)

    assert revised.requirement_allowance == {'xs': 8, 's': 3, 'm': 2}


@pytest.mark.parametrize(
    ('total', 'initial', 'field'),
    [
        ('-1.00', '0.00', 'total_value'),
        ('100.00', '-1.00', 'initial_payment'),
        ('100.00', '101.00', 'initial_payment'),
    ],
)
def test_financed_balance_rejects_invalid_values(total, initial, field):
    with pytest.raises(FinancingAgreementValidationError) as exc_info:
        calculate_financed_balance(total, initial)

    assert field in exc_info.value.errors


@pytest.mark.parametrize(
    ('invalid_item', 'message'),
    [
        (None, 'formato inválido'),
        ({'due_date': 'invalid', 'amount': '100.00'}, 'fecha'),
        ({'due_date': '2026-03-05', 'amount': 'invalid'}, 'valor'),
        ({'due_date': '2026-03-05', 'amount': '0.00'}, 'valor positivo'),
    ],
)
def test_installment_schedule_rejects_malformed_item(invalid_item, message):
    schedule = build_installment_schedule(Decimal('1200.00'), date(2026, 3, 5))
    schedule[0] = invalid_item

    with pytest.raises(FinancingAgreementValidationError) as exc_info:
        normalize_installment_schedule(schedule, Decimal('1200.00'))

    assert message in str(exc_info.value.errors['installment_schedule'])


def test_installment_schedule_rejects_duplicate_dates():
    schedule = build_installment_schedule(Decimal('1200.00'), date(2026, 3, 5))
    schedule[1]['due_date'] = schedule[0]['due_date']

    with pytest.raises(FinancingAgreementValidationError) as exc_info:
        normalize_installment_schedule(schedule, Decimal('1200.00'))

    assert 'únicas' in str(exc_info.value.errors['installment_schedule'])


def test_installment_schedule_rejects_inexact_total():
    schedule = build_installment_schedule(Decimal('1200.00'), date(2026, 3, 5))
    schedule[0]['amount'] = '101.00'

    with pytest.raises(FinancingAgreementValidationError) as exc_info:
        normalize_installment_schedule(schedule, Decimal('1200.00'))

    assert 'sumar exactamente' in str(exc_info.value.errors['installment_schedule'])


@pytest.mark.parametrize(
    ('markdown', 'message'),
    [
        ('', 'no puede estar vacío'),
        ('Texto con {unknown_placeholder}', 'no reconocidos'),
        ('Texto con una llave {', 'llaves inválidas'),
        ('Texto sin marcadores', 'marcadores obligatorios'),
    ],
)
def test_contract_template_rejects_invalid_markdown(markdown, message):
    with pytest.raises(FinancingAgreementValidationError) as exc_info:
        validate_template_markdown(markdown)

    assert message in str(exc_info.value.errors['contract_markdown'])


def test_zero_balance_builds_empty_installment_schedule():
    assert build_installment_schedule(Decimal('0.00'), date(2026, 3, 5)) == []


def test_first_installment_rejects_day_after_fifth():
    with pytest.raises(FinancingAgreementValidationError) as exc_info:
        build_installment_schedule(Decimal('1200.00'), date(2026, 3, 6))

    assert 'días 1 y 5' in str(exc_info.value.errors['first_installment_date'])


def test_add_years_clamps_leap_day():
    assert add_years(date(2024, 2, 29), 1) == date(2025, 2, 28)
