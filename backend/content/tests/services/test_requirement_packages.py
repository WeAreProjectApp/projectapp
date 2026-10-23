"""Behavior tests for the size-based requirement package catalog."""
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

import pytest
from django.urls import reverse
from pypdf import PdfReader
from rest_framework.exceptions import ValidationError

from content.models import (
    AccountingSettings,
    HourPackage,
    HourPackageSettings,
    ProposalDocument,
    ProposalSection,
)
from content.serializers.hour_packages import (
    HourPackageCreateUpdateSerializer,
    HourPackageSettingsSerializer,
)
from content.serializers.proposal import (
    ProposalDetailSerializer,
    ProposalSectionUpdateSerializer,
)
from content.services.proposal_snapshot_service import (
    ProposalSnapshotError,
    prepare_proposal_snapshots,
)
from content.services.requirement_package_service import (
    freeze_proposal_packages,
    priced_package,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def price_settings():
    settings = HourPackageSettings.load()
    settings.xs_price_cop = Decimal('50000')
    settings.s_price_cop = Decimal('125000')
    settings.m_price_cop = Decimal('360000')
    settings.foreign_multiplier = Decimal('1.4')
    settings.usa_multiplier = Decimal('1.8')
    settings.save()
    accounting = AccountingSettings.load()
    accounting.usd_exchange_rate = Decimal('4000')
    accounting.save()
    return settings


def _package(nationality, *, xs, small, medium, discount, name='Package'):
    return HourPackage.objects.create(
        nationality=nationality,
        pricing_model='requirements',
        name_es=name,
        name_en=name,
        xs_count=xs,
        s_count=small,
        m_count=medium,
        discount_percent=discount,
        validity_months=12,
    )


@pytest.mark.parametrize(
    ('nationality', 'xs', 'small', 'medium', 'discount', 'reference', 'total', 'savings'),
    [
        ('COL', 30, 0, 0, 10, '1500000', '1350000', '150000'),
        ('COL', 30, 20, 0, 15, '4000000', '3400000', '600000'),
        ('COL', 30, 20, 10, 25, '7600000', '5700000', '1900000'),
        ('EXT', 30, 0, 0, 10, '525.00', '472.50', '52.50'),
        ('EXT', 30, 20, 0, 15, '1400.00', '1190.00', '210.00'),
        ('EXT', 30, 20, 10, 25, '2660.00', '1995.00', '665.00'),
        ('USA', 30, 0, 0, 10, '675.00', '607.50', '67.50'),
        ('USA', 30, 20, 0, 15, '1800.00', '1530.00', '270.00'),
        ('USA', 30, 20, 10, 25, '3420.00', '2565.00', '855.00'),
    ],
)
def test_priced_package_uses_size_prices_market_factor_and_discount(
    price_settings, nationality, xs, small, medium, discount, reference, total, savings,
):
    """Fails if a package stops applying its size mix, market factor, or discount."""
    package = _package(nationality, xs=xs, small=small, medium=medium, discount=discount)

    result = priced_package(package, settings=price_settings)

    assert result == {'reference_price': reference, 'total_price': total, 'savings': savings}


def test_priced_package_rounds_the_final_usd_total_from_unrounded_reference(price_settings):
    """Fails if fractional USD totals are rounded from an already rounded reference price."""
    AccountingSettings.objects.update(usd_exchange_rate=Decimal('3900'))
    package = _package('EXT', xs=30, small=0, medium=0, discount=10)

    result = priced_package(package, settings=price_settings)

    assert result == {'reference_price': '538.46', 'total_price': '484.62', 'savings': '53.84'}


@pytest.mark.parametrize(
    ('payload', 'error_key'),
    [
        ({'xs_count': -1, 's_count': 1, 'm_count': 0}, 'xs_count'),
        ({'xs_count': '1.5', 's_count': 0, 'm_count': 0}, 'xs_count'),
        ({'xs_count': 0, 's_count': 0, 'm_count': 0}, 'non_field_errors'),
        ({'xs_count': 1, 's_count': 0, 'm_count': 0, 'validity_months': 0}, 'validity_months'),
        ({'xs_count': 1, 's_count': 0, 'm_count': 0, 'discount_percent': 100}, 'discount_percent'),
        ({'xs_count': 1, 's_count': 0, 'm_count': 0, 'discount_percent': -1}, 'discount_percent'),
    ],
)
def test_package_serializer_rejects_invalid_requirement_commitments(payload, error_key):
    """Fails if a catalog package can promise impossible sizes, validity, or discount."""
    serializer = HourPackageCreateUpdateSerializer(data={
        'nationality': 'COL', 'name_es': 'Paquete', 'name_en': 'Package', **payload,
    })

    assert not serializer.is_valid()
    assert error_key in serializer.errors
    assert HourPackage.objects.filter(name_es='Paquete').count() == 0


@pytest.mark.parametrize(
    ('payload', 'error_key'),
    [
        ({'xs_price_cop': '0'}, 'xs_price_cop'),
        ({'foreign_multiplier': '0'}, 'foreign_multiplier'),
        ({'alliance_xs_count': 0, 'alliance_s_count': 0, 'alliance_m_count': 0}, 'non_field_errors'),
    ],
)
def test_settings_serializer_rejects_zero_prices_factors_and_empty_alliance(payload, error_key):
    """Fails if internal pricing or the alliance can be saved without usable capacity."""
    serializer = HourPackageSettingsSerializer(HourPackageSettings.load(), data=payload, partial=True)

    assert not serializer.is_valid()
    assert error_key in serializer.errors


def test_usd_quote_requires_positive_exchange_rate_while_colombia_still_prices(price_settings):
    """Fails if a missing exchange rate silently creates a zero-dollar offer or blocks COP offers."""
    AccountingSettings.objects.update(usd_exchange_rate=Decimal('0'))
    colombia = _package('COL', xs=30, small=0, medium=0, discount=10)
    foreign = _package('EXT', xs=30, small=0, medium=0, discount=10)

    assert priced_package(colombia, settings=price_settings)['total_price'] == '1350000'
    with pytest.raises(ValidationError) as exc_info:
        priced_package(foreign, settings=price_settings)
    assert 'exchange_rate' in exc_info.value.detail


def _requirements_content():
    return {
        'pricingModel': 'requirements',
        'hourPackagesMode': 'manual',
        'hourPackagesEnabled': True,
        'currency': 'COP',
        'packagesTitle': 'Paquetes de requerimientos',
        'packagesIntro': 'Selecciona el paquete que aplica.',
        'effortBadge': 'Las tallas se validan antes de programar.',
        'scopeTitle': 'Alcance',
        'scopeParagraphs': ['L y XL se cotizan aparte.'],
        'packages': [{
            'id': 999,
            'name': 'Paquete Premium',
            'xsCount': 30,
            'sCount': 20,
            'mCount': 10,
            'validityMonths': 12,
            'referencePrice': '7600000',
            'discountPercent': 25,
            'totalPrice': '5700000',
            'terms': 'Compra única, con 12 meses desde el pago.',
        }],
    }


def test_legacy_section_stays_hour_based_until_a_draft_explicitly_adopts(proposal):
    """Fails if editing a legacy commercial section silently converts its committed hours."""
    section = ProposalSection.objects.create(
        proposal=proposal,
        section_type='commercial_conditions',
        title='Condiciones',
        order=1,
        content_json={'pricingModel': 'hours', 'hourlyRate': 90000, 'packages': [{'hours': 20}]},
    )
    serializer = ProposalSectionUpdateSerializer(
        section, data={'content_json': section.content_json}, partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    serializer.save()
    section.refresh_from_db()
    assert section.content_json == {'pricingModel': 'hours', 'hourlyRate': 90000, 'packages': [{'hours': 20}]}


def test_sent_section_rejects_requirement_adoption_without_mutating_saved_hours(sent_proposal):
    """Fails if an already sent offer can change from hours to size-based commitments."""
    section = ProposalSection.objects.create(
        proposal=sent_proposal,
        section_type='commercial_conditions',
        title='Condiciones',
        order=1,
        content_json={'pricingModel': 'hours', 'hourlyRate': 90000, 'packages': [{'hours': 20}]},
    )
    serializer = ProposalSectionUpdateSerializer(
        section, data={'content_json': _requirements_content()}, partial=True,
    )

    assert not serializer.is_valid()
    assert 'Sólo un borrador' in str(serializer.errors)
    section.refresh_from_db()
    assert section.content_json['pricingModel'] == 'hours'
    assert section.content_json['packages'][0]['hours'] == 20


def test_sent_manual_requirement_revision_unfreezes_next_offer_without_mutating_history(sent_proposal):
    """Fails if revising a sent manual package changes history or leaves the next offer frozen."""
    content = _requirements_content() | {'packagesFrozen': True}
    section = ProposalSection.objects.create(
        proposal=sent_proposal,
        section_type='commercial_conditions',
        title='Condiciones',
        order=1,
        content_json=content,
    )
    history = ProposalDocument.objects.create(
        proposal=sent_proposal,
        document_type=ProposalDocument.DOC_TYPE_OTHER,
        title='Oferta enviada',
        content_markdown='Total histórico 5.700.000 COP',
    )
    revised = _requirements_content()
    revised['packages'][0]['referencePrice'] = '8000000'
    revised['packages'][0]['totalPrice'] = '6000000'
    serializer = ProposalSectionUpdateSerializer(
        section, data={'content_json': revised}, partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    serializer.save()
    section.refresh_from_db()
    history.refresh_from_db()
    assert section.content_json['packagesFrozen'] is False
    assert section.content_json['packages'][0]['totalPrice'] == '6000000'
    assert history.content_markdown == 'Total histórico 5.700.000 COP'


def test_freeze_keeps_auto_foreign_package_after_catalog_and_fx_changes(proposal, price_settings):
    """Fails if later catalog or FX changes reprice an issued foreign requirement package."""
    proposal.nationality = 'EXT'
    proposal.save(update_fields=['nationality'])
    AccountingSettings.objects.update(usd_exchange_rate=Decimal('3900'))
    _package('EXT', xs=30, small=0, medium=0, discount=10, name='Paquete Ágil')
    section = ProposalSection.objects.create(
        proposal=proposal,
        section_type='commercial_conditions',
        title='Condiciones',
        order=1,
        content_json={
            'pricingModel': 'requirements', 'hourPackagesMode': 'auto',
            'hourPackagesEnabled': True, 'packagesTitle': 'Paquetes',
            'packagesIntro': 'Elige uno.', 'scopeTitle': 'Alcance',
            'scopeParagraphs': ['L y XL se cotizan aparte.'],
        },
    )

    freeze_proposal_packages(proposal)
    section.refresh_from_db()
    proposal.refresh_from_db()
    settings = HourPackageSettings.load()
    settings.xs_price_cop = Decimal('60000')
    settings.save()
    AccountingSettings.objects.update(usd_exchange_rate=Decimal('5000'))

    from content.services.proposal_pdf_service import ProposalPdfService
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(ProposalPdfService.generate(proposal))).pages)

    assert section.content_json['packagesFrozen'] is True
    assert section.content_json['packages'][0]['xsCount'] == 30
    assert section.content_json['packages'][0]['totalPrice'] == '484.62'
    assert proposal.package_pricing_context == {'exchange_rate': '3900', 'factor': '1.4'}
    assert '30 XS / 0 S / 0 M' in text
    assert '484.62' in text


def test_public_serializer_hides_private_requirement_pricing_context(proposal):
    """Fails if public proposal data leaks the frozen exchange rate or internal size prices."""
    proposal.package_pricing_context = {'exchange_rate': '3900', 'factor': '1.4'}
    proposal.save(update_fields=['package_pricing_context'])

    public = ProposalDetailSerializer(proposal, context={'is_admin': False}).data

    assert 'package_pricing_context' not in public
    assert 'xs_price_cop' not in str(public)


def test_contract_parameter_update_preserves_frozen_fx_context(proposal, admin_client):
    """Fails if a legal-detail edit drops the frozen requirement pricing context."""
    frozen = {'exchange_rate': '3900', 'factor': '1.4'}
    proposal.contract_params = {
        'client_cedula': '1234567890',
        'client_full_name': 'Cliente',
    }
    proposal.package_pricing_context = frozen
    proposal.save(update_fields=['contract_params', 'package_pricing_context'])

    response = admin_client.patch(
        reverse('update-contract-params', kwargs={'proposal_id': proposal.pk}),
        {'contract_params': {
            'client_cedula': '1234567890',
            'client_full_name': 'Nombre actualizado',
            'contract_source': 'custom',
            'custom_contract_markdown': '# Contrato actualizado',
        }},
        format='json',
    )

    assert response.status_code == 200
    proposal.refresh_from_db()
    assert proposal.contract_params['client_full_name'] == 'Nombre actualizado'
    assert proposal.package_pricing_context == frozen


def test_contract_parameter_update_rejects_client_override_of_frozen_fx_context(proposal, admin_client):
    """Fails if request data can overwrite the exchange rate frozen at offer issuance."""
    frozen = {'exchange_rate': '3900', 'factor': '1.4'}
    proposal.contract_params = {'client_cedula': '1234567890', 'client_full_name': 'Cliente'}
    proposal.package_pricing_context = frozen
    proposal.save(update_fields=['contract_params', 'package_pricing_context'])

    response = admin_client.patch(
        reverse('update-contract-params', kwargs={'proposal_id': proposal.pk}),
        {'contract_params': {
            'client_cedula': '1234567890',
            'client_full_name': 'Nombre actualizado',
            'requirement_package_pricing': {'exchange_rate': '1', 'factor': '99'},
            'contract_source': 'custom',
            'custom_contract_markdown': '# Contrato actualizado',
        }},
        format='json',
    )

    assert response.status_code == 200
    proposal.refresh_from_db()
    assert proposal.package_pricing_context == frozen


def test_snapshot_failure_rolls_back_frozen_requirement_data(proposal, price_settings):
    """Fails if a PDF error leaves a proposal partially frozen without a delivered snapshot."""
    section = ProposalSection.objects.create(
        proposal=proposal,
        section_type='commercial_conditions',
        title='Condiciones',
        order=1,
        content_json=_requirements_content(),
    )

    with patch('content.services.proposal_pdf_service.ProposalPdfService.generate', side_effect=RuntimeError('PDF error')):
        with pytest.raises(ProposalSnapshotError):
            prepare_proposal_snapshots([proposal])

    section.refresh_from_db()
    proposal.refresh_from_db()
    assert 'packagesFrozen' not in section.content_json
    assert proposal.package_pricing_context == {}


def test_requirement_pdf_shows_mix_term_total_and_savings_without_unit_prices(proposal):
    """Fails if the customer PDF omits the agreed composition, validity, or saving."""
    ProposalSection.objects.create(
        proposal=proposal,
        section_type='commercial_conditions',
        title='Condiciones',
        order=1,
        content_json=_requirements_content(),
    )

    from content.services.proposal_pdf_service import ProposalPdfService
    pdf = ProposalPdfService.generate(proposal)
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(pdf)).pages)

    assert '30 XS / 20 S / 10 M' in text
    assert '5.700.000' in text
    assert '1.900.000' in text
    assert '12 meses' in text
    assert '50.000' not in text
