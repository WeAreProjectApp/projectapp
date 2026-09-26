"""Readers and PDFs expose the revised contract from the migrated default."""

import io
import re
from types import SimpleNamespace

import pytest
from django.urls import reverse
from pypdf import PdfReader

from content.services.contract_pdf_service import generate_contract_pdf
from content.services.contract_terms_service import build_contract_terms_payload

pytestmark = pytest.mark.django_db


def clause_content(number):
    return build_contract_terms_payload()['clauses'][number - 1]['content_markdown']


def test_public_reader_requires_full_price_for_source_delivery(api_client, proposal):
    url = reverse('retrieve-public-contract-terms', kwargs={'proposal_uuid': proposal.uuid})

    response = api_client.get(url)

    text = response.data['clauses'][8]['content_markdown']
    assert response.status_code == 200
    assert 'no satisface por sí solo la condición suspensiva' in text
    assert 'completar el pago del cien por ciento (100%) del valor total del contrato' in text
    assert 'se suma al precio contractual y no constituye abono a este' in text
    assert 'haber satisfecho la penalidad' in text


def test_full_payment_after_termination_only_releases_existing_work():
    text = clause_content(9)

    assert 'trabajo efectivamente desarrollado hasta la fecha de terminación' in text
    assert 'no reactivará el contrato ni obligará a EL CONTRATISTA a ejecutar o completar las fases pendientes' in text
    assert 'dentro de los cinco (5) días hábiles' in text
    assert 'Para los demás supuestos de terminación anticipada' in text


def test_unilateral_termination_uses_three_letters():
    text = clause_content(16).split('### Parágrafo Segundo')[1].split('### Parágrafo Tercero')[0]

    assert re.findall(r'^\*\*([a-z])\)\*\*', text, re.MULTILINE) == ['a', 'b', 'c']
    assert 'treinta por ciento (30%) del valor de las fases restantes' in text
    assert 'reservando capacidad de trabajo, asignando personal' in text
    assert 'EL CONTRATISTA entregará a EL CONTRATANTE el código fuente' not in text


def test_ownership_preserves_reusable_assets_without_claiming_third_party_code():
    text = clause_content(10)

    assert 'fragmentos de código (snippets)' in text
    assert 'conocimiento técnico (know-how), la experiencia acumulada' in text
    assert 'respetando la confidencialidad' in text
    assert 'cuya titularidad permanecerá en cabeza de sus respectivos titulares' in text
    assert 'ni permite imponer restricciones contrarias a dichas licencias' in text
    assert 'licencia de uso perpetua, irrevocable, no exclusiva y sin costo adicional' in text


def test_ownership_keeps_client_logic_but_not_generic_components():
    text = clause_content(10)

    assert 'los desarrollos originales realizados específicamente para su proyecto' in text
    assert 'Hacen parte del DESARROLLO ESPECÍFICO la lógica, las reglas de negocio' in text
    assert 'o que se desarrollen, adapten o perfeccionen durante su ejecución' in text
    assert 'no excluye de la cesión las implementaciones originales' not in text
    assert 'no confiere exclusividad sobre ideas, métodos, funcionalidades' in text
    assert 'incluidas las aplicables a la terminación unilateral por EL CONTRATANTE' in text


def test_hosting_cross_references_are_renumbered():
    hosting = clause_content(2).split('### Parágrafo Séptimo')[1].split('### Parágrafo Octavo')[0]
    execution = clause_content(9).split('### Parágrafo Cuarto')[1].split('### Parágrafo Quinto')[0]

    letters = re.compile(r'^\*\*([a-z]+)\)\*\*', re.MULTILINE)
    # f) carries the two external-hosting conditions as roman sub-items.
    assert letters.findall(hosting) == ['a', 'b', 'c', 'd', 'e', 'f', 'i', 'ii', 'g', 'h']
    assert '**h)** Cuando EL CONTRATANTE contrate' in hosting
    assert letters.findall(execution) == ['a', 'b', 'c', 'd']
    assert 'solo lectura' not in hosting + execution


def test_contract_pdf_contains_the_revised_exit_terms():
    """The real PDF renderer must preserve the amounts and delivery condition."""
    pdf = generate_contract_pdf(SimpleNamespace(contract_params={}), draft=True)

    reader = PdfReader(io.BytesIO(pdf))
    text = ' '.join(' '.join(page.extract_text() for page in reader.pages).split())
    assert 'treinta por ciento (30%) del valor de las fases restantes' in text
    assert 'se suma al precio contractual y no constituye abono' in text
    assert 'no reactivará el contrato' in text
    assert 'licencia de uso perpetua, irrevocable, no exclusiva' in text
    assert 'EL CONTRATANTE y el personal que este designe tendrán acceso al servidor' not in text
