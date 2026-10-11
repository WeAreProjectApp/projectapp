"""Public booklet content, canonical figures and private-data isolation."""
import re
from copy import deepcopy
from io import BytesIO

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from content.models import BuildingOnDemandProgramRevision
from content.services.building_on_demand_pdf_service import BuildingOnDemandPdfService

pytestmark = pytest.mark.django_db


def pdf_text(data):
    """Normalize layout whitespace while exercising a real PDF parser."""
    return ' '.join(' '.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages).split())


def publish_content(program, content):
    """Point the singleton to a test revision without modifying its immutable seed."""
    revision = BuildingOnDemandProgramRevision.objects.create(
        version=2, content=deepcopy(content), change_note='Contenido para probar el PDF.',
    )
    program.current_revision = revision
    program.save(update_fields=['current_revision', 'updated_at'])


@pytest.mark.parametrize('language', ['es', 'en'])
def test_pdf_download_renders_localized_cover(building_on_demand_program, language):
    """Fails if the download is not the localized current public booklet."""
    response = APIClient().get('/api/building-on-demand/public/pdf/', {'lang': language})
    text = pdf_text(response.content)
    copy = building_on_demand_program.current_revision.content[language]

    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')
    assert copy['hero']['positioning'] in text
    assert copy['hero']['title'] in text
    assert copy['legal']['disclaimer'] in text
    assert response['Content-Disposition'] == f'attachment; filename="building-on-demand-{language}.pdf"'
    assert response['Cache-Control'] == 'private, no-store'


@pytest.mark.parametrize('section', ['cell', 'fit', 'tiers', 'bag', 'estimator', 'hosting', 'faq', 'cta'])
def test_pdf_contains_a_public_section(building_on_demand_program, section):
    """Fails if a section of the current public sales page is omitted from the booklet."""
    text = pdf_text(BuildingOnDemandPdfService.build(language='es'))

    assert building_on_demand_program.current_revision.content['es'][section]['title'] in text
    assert re.search(r'55000|55\.000|Hostinger|KVM|hour_cost|internal', text) is None


@pytest.mark.parametrize(('language', 'tier_name', 'bag_label'), [
    ('es', 'Starter', '96 horas al mes'), ('en', 'Business', '192 hours per month'),
    ('es', 'Enterprise', '288 horas al mes'),
])
def test_pdf_renders_tier_hour_bags(building_on_demand_program, language, tier_name, bag_label):
    """Fails if a tier's card omits its canonical monthly capacity."""
    text = pdf_text(BuildingOnDemandPdfService.build(language=language))

    assert tier_name in text
    assert bag_label in text
    assert 'vCPU' in text


@pytest.mark.parametrize(('language', 'monthly', 'total', 'discount', 'vat_label'), [
    ('es', '$1.710.000', '$5.130.000', '5 %', '+ IVA'),
    ('en', '$7.200.000', '$64.800.000', '25 %', '+ VAT'),
])
def test_pdf_renders_discounted_term_prices(building_on_demand_program, language, monthly, total, discount, vat_label):
    """Fails if the booklet changes a derived discounted price or its prepaid total."""
    text = pdf_text(BuildingOnDemandPdfService.build(language=language))

    assert f'{monthly} COP {vat_label}' in text
    assert f'{total} COP {vat_label}' in text
    assert discount in text


@pytest.mark.parametrize(('language', 'vat_label'), [('es', '+ IVA'), ('en', '+ VAT')])
def test_pdf_omits_surcharge_for_vat_included_prices(building_on_demand_program, building_on_demand_content, language, vat_label):
    """Fails if a VAT-inclusive offer is advertised with an additional tax surcharge."""
    building_on_demand_content['offer']['prices_include_vat'] = True
    publish_content(building_on_demand_program, building_on_demand_content)

    text = pdf_text(BuildingOnDemandPdfService.build(language=language))

    assert '$1.800.000 COP' in text
    assert vat_label not in text


def test_pdf_accepts_long_valid_tier_copy(building_on_demand_program, building_on_demand_content):
    """Fails if valid long tier content makes its card too tall to print across pages."""
    building_on_demand_content['es']['tiers']['items'][0]['roles'] = ['Desarrollo con criterio. ' * 6] * 10
    building_on_demand_content['en']['tiers']['items'][0]['roles'] = ['Development with judgment. ' * 5] * 10
    building_on_demand_content['es']['tiers']['items'][0]['highlights'] = ['Prioridades visibles. ' * 7] * 8
    building_on_demand_content['en']['tiers']['items'][0]['highlights'] = ['Visible priorities. ' * 7] * 8
    publish_content(building_on_demand_program, building_on_demand_content)

    data = BuildingOnDemandPdfService.build(language='es')
    text = pdf_text(data)

    assert data.startswith(b'%PDF-')
    assert text.count('Desarrollo con criterio.') == 60
    assert '$13.770.000 COP + IVA' in text
    assert building_on_demand_content['es']['legal']['disclaimer'] in text


def test_pdf_reads_estimator_ranges_from_the_public_offer(building_on_demand_program, building_on_demand_content):
    """Fails if an edited reference range is ignored in favor of a hardcoded estimate."""
    building_on_demand_content['offer']['estimator']['sizes'][0]['hours_max'] = 6
    publish_content(building_on_demand_program, building_on_demand_content)

    text = pdf_text(BuildingOnDemandPdfService.build(language='es'))

    assert '2–6 horas de referencia' in text
    assert building_on_demand_content['es']['estimator']['disclaimer'] in text
    assert building_on_demand_content['es']['estimator']['tasks'][2]['hint'] in text


def test_pdf_explains_monthly_renewal_of_prepaid_hours(building_on_demand_program):
    """Fails if a prepaid-term booklet loses its monthly hour renewal condition."""
    content = building_on_demand_program.current_revision.content['es']
    text = pdf_text(BuildingOnDemandPdfService.build(language='es'))

    assert content['terms']['note'] in text
    assert content['bag']['rules'][0]['summary'] in text
    assert 'https://wa.me/' in text
