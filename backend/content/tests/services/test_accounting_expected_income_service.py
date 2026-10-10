"""Expected-income plans retain the panel's financial and billing rules."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError

from content.models import Document, IncomeRecord
from content.serializers.accounting import split_half
from content.services import accounting_expected_income_service as service

pytestmark = pytest.mark.django_db


def create_fields(**overrides):
    return {'concept': 'Servicio esperado', 'origin': 'development', 'vat_rate': None,
            'period_date': '2026-11-01', 'total_amount': '1000.00', **overrides}


def test_company_create_uses_panel_split():
    plan = service.build_change_plan(create_fields())
    gustavo, carlos = split_half(Decimal('1000.00'))
    assert plan['split'] == {
        'rule': 'panel_auto', 'gustavo': str(gustavo), 'carlos': str(carlos), 'company': '0.00',
        'message': f'Reparto calculado con la regla del Panel: Gustavo {gustavo}, Carlos {carlos}, empresa 0.00.',
    }
    assert plan['needs_confirmation'] is True
    assert plan['notices'][0]['code'] == 'panel_auto'


@pytest.mark.parametrize(('ledger', 'expected'), [
    ('gustavo', {'gustavo_amount': '1000.00', 'carlos_amount': '0.00', 'company_amount': '0.00'}),
    ('carlos', {'gustavo_amount': '0.00', 'carlos_amount': '1000.00', 'company_amount': '0.00'}),
])
def test_personal_ledger_belongs_to_owner(ledger, expected):
    plan = service.build_change_plan(create_fields(ledger=ledger))
    assert {key: plan['after'][key] for key in expected} == expected


def test_payment_changes_etag_without_touching_parent(make_income):
    income = make_income()
    before = service.income_etag(income)
    updated_at = income.updated_at
    make_income(kind='liquid', expected_income=income, total_amount=Decimal('100.00'),
                gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'))
    income.refresh_from_db()
    assert income.updated_at == updated_at
    assert service.income_etag(income) != before


def test_issued_collection_account_changes_etag(make_income):
    income = make_income()
    account = Document.objects.create(title='Cuenta', income_record=income, commercial_status='draft', total=1000)
    before = service.income_etag(income)
    account.commercial_status = 'issued'
    account.save(update_fields=['commercial_status'])
    assert service.income_etag(income) != before


def test_total_recalculates_automatic_split(make_income):
    income = make_income()
    plan = service.build_change_plan({'total_amount': '4200000.00'}, income=income)
    gustavo, carlos = split_half(Decimal('4200000.00'))
    assert {key: plan['split'][key] for key in ('rule', 'gustavo', 'carlos', 'company')} == {
        'rule': 'panel_auto', 'gustavo': str(gustavo), 'carlos': str(carlos), 'company': '0.00',
    }
    assert plan['needs_confirmation'] is True


def test_automatic_split_reports_company_remainder(make_income):
    """A total-only automatic plan reports the company's residual peso."""
    income = make_income()
    with patch.object(service, 'split_half', return_value=(Decimal('500000.00'), Decimal('500000.00'))):
        plan = service.build_change_plan({'total_amount': '1000001.00'}, income=income)
    message = ('Reparto recalculado con la regla del Panel: Gustavo 500000.00, '
               'Carlos 500000.00, empresa 1.00.')
    assert plan['split'] == {
        'rule': 'panel_auto', 'gustavo': '500000.00', 'carlos': '500000.00', 'company': '1.00',
        'message': message,
    }
    assert plan['notices'] == [{'code': 'panel_auto', 'message': message}]
    assert plan['after']['company_amount'] == '1.00'
    assert plan['needs_confirmation'] is True


def test_personal_ledger_to_company_recalculates_panel_split(make_income):
    """Returning a personal income to company reapplies the automatic rule."""
    income = make_income(ledger='gustavo', gustavo_amount=Decimal('1000000.00'), carlos_amount=Decimal('0'))
    plan = service.build_change_plan({'ledger': 'company'}, income=income)
    gustavo, carlos = split_half(income.total_amount)
    message = (f'Reparto recalculado con la regla del Panel: Gustavo {gustavo}, '
               f'Carlos {carlos}, empresa 0.00.')
    assert plan['split'] == {
        'rule': 'panel_auto', 'gustavo': str(gustavo), 'carlos': str(carlos), 'company': '0.00',
        'message': message,
    }
    assert (plan['after']['ledger'], plan['after']['gustavo_amount'], plan['after']['carlos_amount']) == (
        'company', str(gustavo), str(carlos),
    )
    assert plan['notices'] == [{'code': 'panel_auto', 'message': message}]
    assert plan['needs_confirmation'] is True


def test_custom_split_is_kept_with_residual_warning(make_income):
    income = make_income(gustavo_amount=Decimal('300000.00'), carlos_amount=Decimal('200000.00'))
    plan = service.build_change_plan({'total_amount': '4200000.00'}, income=income)
    assert plan['split'] == {
        'rule': 'kept_custom', 'gustavo': '300000.00', 'carlos': '200000.00', 'company': '3700000.00',
        'message': 'Se conserva el reparto personalizado del Panel.',
    }
    assert plan['warnings'] == [{
        'code': 'custom_split_kept', 'message': 'Se conserva el reparto personalizado del Panel.',
        'company_amount': '3700000.00',
    }]


def test_explicit_split_must_sum_to_total():
    with pytest.raises(service.ExpectedIncomeError) as error:
        service.build_change_plan(create_fields(gustavo_amount='400', carlos_amount='400', company_amount='100'))
    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'reason': 'split_mismatch', 'total': '1000.00', 'sum': '900.00'}


def test_vat_amount_must_match_computed_breakdown():
    with pytest.raises(service.ExpectedIncomeError) as error:
        service.build_change_plan(create_fields(total_amount='119.00', vat_rate='19', base_amount='100', vat_amount='18'))
    assert error.value.details == {
        'reason': 'vat_mismatch', 'expected': {
            'vat_rate': '19.00', 'base_amount': '100.00', 'vat_amount': '19.00', 'total_amount': '119.00',
        },
    }


def test_base_and_rate_determine_total():
    fields = create_fields(base_amount='1000.00', vat_rate='19')
    fields.pop('total_amount')
    plan = service.build_change_plan(fields)
    assert plan['vat'] == {
        'vat_rate': '19.00', 'base_amount': '1000.00', 'vat_amount': '190.00', 'total_amount': '1190.00',
    }
    assert set(plan['serializer'].validated_data) & {'amount', 'amount_mode', 'base_amount', 'vat_amount'} == set()


def test_descriptive_update_needs_no_confirmation(make_income):
    income = make_income()
    plan = service.build_change_plan({'notes': 'Referencia documental'}, income=income)
    assert plan['changes'] == [{'field': 'notes', 'label': 'Notas', 'before': '', 'after': 'Referencia documental'}]
    assert plan['needs_confirmation'] is False
    assert set(plan['serializer'].validated_data) & {'gustavo_amount', 'carlos_amount', 'total_amount'} == set()


def test_payments_lock_financial_changes(make_income):
    income = make_income()
    make_income(kind='liquid', expected_income=income, total_amount=Decimal('100.00'),
                gustavo_amount=Decimal('50.00'), carlos_amount=Decimal('50.00'))
    with pytest.raises(service.ExpectedIncomeError) as error:
        service.build_change_plan({'total_amount': '2000000'}, income=income)
    assert error.value.code == 'INCOME_LOCKED'
    assert error.value.details['blocked_fields'] == ['carlos_amount', 'gustavo_amount', 'total_amount']


def test_paid_income_accepts_notes_with_warning(make_income):
    income = make_income()
    make_income(kind='liquid', expected_income=income)
    plan = service.build_change_plan({'notes': 'Seguimiento'}, income=income)
    assert plan['after']['notes'] == 'Seguimiento'
    assert plan['warnings'][0]['code'] == 'financial_fields_locked'
    assert plan['needs_confirmation'] is False


def test_duplicate_preserves_expected_payment_offset(make_income):
    income = make_income(origin='hosting', period_date=date(2026, 11, 1), period_start=date(2026, 10, 1),
                         period_end=date(2027, 3, 31), period_cadence='semiannual', vat_rate=None)
    fields = service.build_duplicate_fields(income, {'period_start': '2027-04-01', 'total_amount': '4200000'})
    assert {key: fields[key] for key in ('period_date', 'period_start', 'period_end', 'period_cadence')} == {
        'period_date': '2027-05-01', 'period_start': '2027-04-01',
        'period_end': '2027-09-30', 'period_cadence': 'semiannual',
    }
    assert set(fields) & service.SPLIT_FIELDS == set()


@pytest.mark.parametrize(('fields', 'expected'), [
    ({'gustavo_amount': '200', 'company_amount': '100'}, ('200.00', '700.00', '100.00')),
    ({'carlos_amount': '200', 'company_amount': '100'}, ('700.00', '200.00', '100.00')),
])
def test_company_share_derives_missing_partner(fields, expected):
    plan = service.build_change_plan(create_fields(**fields))
    assert tuple(plan['split'][key] for key in ('gustavo', 'carlos', 'company')) == expected


def test_custom_split_over_new_total_suggests_panel_split(make_income):
    """An invalid custom split suggests the automatic split with its residual peso."""
    income = make_income(gustavo_amount=Decimal('700000.00'), carlos_amount=Decimal('200000.00'))
    with patch.object(service, 'split_half', return_value=(Decimal('400000.00'), Decimal('400000.00'))):
        with pytest.raises(service.ExpectedIncomeError) as error:
            service.build_change_plan({'total_amount': '800001.00'}, income=income)
    assert error.value.details == {
        'reason': 'split_exceeds_total', 'total': '800001.00', 'sum': '900000.00',
        'suggestion': {'gustavo_amount': '400000.00', 'carlos_amount': '400000.00', 'company_amount': '1.00'},
    }


def test_client_change_preview_includes_cleared_project(make_income, make_client_profile):
    """The validated preview must include the panel's automatic project clearing."""
    from accounts.models import Project

    original, target = make_client_profile(), make_client_profile(company='Otro')
    project = Project.objects.create(name='Anterior', client=original.user)
    income = make_income(client=original, project=project)
    plan = service.build_change_plan({'client': target.pk}, income=income)
    assert {row['field']: row['after'] for row in plan['changes']} == {'client': target.pk, 'project': None}
    assert plan['after']['project_id'] is None


def test_switching_origin_preview_clears_hosting_window(make_income):
    income = make_income(origin='hosting', period_start=date(2026, 10, 1), period_end=date(2027, 3, 31),
                         period_cadence='semiannual', period_date=date(2026, 11, 1))
    plan = service.build_change_plan({'origin': 'development'}, income=income)
    assert {key: plan['after'][key] for key in ('period_start', 'period_end', 'period_cadence', 'period_date')} == {
        'period_start': None, 'period_end': None, 'period_cadence': '', 'period_date': '2026-11-01',
    }
    assert plan['needs_confirmation'] is False


def test_fully_paid_income_keeps_panel_confidence_guard(make_income):
    income = make_income()
    make_income(kind='liquid', expected_income=income)
    with pytest.raises(ValidationError) as error:
        service.build_change_plan({'collection_confidence': 'medium'}, income=income)
    assert error.value.get_codes() == {'is_receivable_candidate': ['invalid']}
