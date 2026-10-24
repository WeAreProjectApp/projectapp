"""Editorial metadata survives template copies and atomic diagnostic writes."""

from copy import deepcopy

import pytest
from django.urls import reverse

from content.models import (
    BusinessProposal,
    DiagnosticDefaultConfig,
    DiagnosticSection,
    ProposalDefaultConfig,
    ProposalSection,
    WebAppDiagnostic,
)
from content.serializers.proposal import ProposalFromJSONSerializer
from content.services import diagnostic_service
from content.services.proposal_service import (
    apply_proposal_json_update,
    build_proposal_from_json,
    create_section_for_proposal,
    duplicate_proposal,
)


pytestmark = pytest.mark.django_db
FORMAT = 'markdown_html_v1'
SOURCE = '<p><strong>Alcance aprobado</strong></p>'
UNSAFE = '<p style="position:fixed">Contenido prohibido</p>'


@pytest.fixture
def proposal_defaults():
    return ProposalDefaultConfig.objects.create(
        language='es',
        sections_json=[
            {'section_type': 'greeting', 'title': 'Saludo', 'order': 0,
             'content_json': {'clientName': 'Cliente'}},
            {'section_type': 'executive_summary', 'title': 'Resumen', 'order': 1,
             'content_json': {'paragraphs': [SOURCE]}},
        ],
        text_formats={'/sections_json/1/content_json/paragraphs/0': FORMAT},
    )


@pytest.fixture
def proposal():
    return BusinessProposal.objects.create(title='Propuesta editorial', client_name='Cliente')


@pytest.fixture
def diagnostic(diag_client_profile):
    return WebAppDiagnostic.objects.create(
        client=diag_client_profile, language='es', title='Diagnóstico editorial',
    )


@pytest.fixture
def diagnostic_spec():
    return {
        'section_type': 'purpose', 'title': 'Propósito', 'order': 0,
        'content_json': {'body': SOURCE},
        'text_formats': {'/content_json/body': FORMAT},
    }


@pytest.fixture
def diagnostic_sections(diagnostic):
    first = DiagnosticSection.objects.create(
        diagnostic=diagnostic, section_type='purpose', title='Primera', order=0,
        content_json={'body': 'Primer contenido inicial'},
    )
    last = DiagnosticSection.objects.create(
        diagnostic=diagnostic, section_type='scope', title='Última', order=1,
        content_json={'body': 'Último contenido inicial'},
    )
    return first, last


def test_new_proposal_section_inherits_indexed_default_formats(proposal, proposal_defaults):
    """Falla si añadir una sección pierde los formatos de la raíz del template."""
    section = create_section_for_proposal(proposal, 'executive_summary')
    section.refresh_from_db()
    proposal_defaults.refresh_from_db()

    assert section.content_json == {'paragraphs': [SOURCE]}
    assert section.text_formats == {'/content_json/paragraphs/0': FORMAT}
    assert proposal_defaults.text_formats == {
        '/sections_json/1/content_json/paragraphs/0': FORMAT,
    }
    assert proposal_defaults.sections_json[1] == {
        'section_type': 'executive_summary', 'title': 'Resumen', 'order': 1,
        'content_json': {'paragraphs': [SOURCE]},
    }


def test_from_json_creation_inherits_formats_for_default_sections(proposal_defaults):
    """Falla si crear por la ruta compartida con MCP descarta el formato de una sección omitida."""
    serializer = ProposalFromJSONSerializer(data={
        'title': 'Desde JSON', 'client_name': 'Cliente JSON',
        'sections': {'general': {'clientName': 'Cliente JSON'}},
    })

    assert serializer.is_valid(), serializer.errors
    created, unmapped = build_proposal_from_json(serializer.validated_data)
    section = created.sections.get(section_type='executive_summary')

    assert section.content_json == {'paragraphs': [SOURCE]}
    assert section.text_formats == {'/content_json/paragraphs/0': FORMAT}
    assert unmapped == []


def test_duplicate_proposal_preserves_source_format_maps(proposal):
    """Falla si duplicar copia la fuente sin los perfiles necesarios para interpretarla."""
    proposal.email_intro = SOURCE
    proposal.text_formats = {'/email_intro': FORMAT}
    proposal.save(update_fields=['email_intro', 'text_formats'])
    ProposalSection.objects.create(
        proposal=proposal, section_type='executive_summary', title='Resumen',
        content_json={'paragraphs': [SOURCE]},
        text_formats={'/content_json/paragraphs/0': FORMAT},
    )

    duplicate = duplicate_proposal(proposal, via_mcp=True)
    section = duplicate.sections.get(section_type='executive_summary')

    assert duplicate.email_intro == SOURCE
    assert duplicate.text_formats == {'/email_intro': FORMAT}
    assert section.content_json == {'paragraphs': [SOURCE]}
    assert section.text_formats == {'/content_json/paragraphs/0': FORMAT}


def test_from_json_update_respects_new_local_format_ownership(proposal):
    """Falla si un formato antiguo del modelo compite con la anotación local nueva de MCP."""
    section = ProposalSection.objects.create(
        proposal=proposal, section_type='executive_summary', title='Resumen',
        content_json={'paragraphs': ['Texto inicial'], 'subtitle': SOURCE},
        text_formats={'/content_json/paragraphs/0': 'plain', '/content_json/subtitle': FORMAT},
    )
    serializer = ProposalFromJSONSerializer(data={
        'title': proposal.title, 'client_name': proposal.client_name,
        'sections': {
            'general': {'clientName': proposal.client_name},
            'executiveSummary': {
                'paragraphs': [SOURCE], 'subtitle': SOURCE,
                'text_formats': {'/paragraphs/0': FORMAT},
            },
        },
    }, context={'proposal': proposal})

    assert serializer.is_valid(), serializer.errors
    apply_proposal_json_update(proposal, serializer.validated_data)
    section.refresh_from_db()

    assert section.content_json == {
        'paragraphs': [SOURCE], 'subtitle': SOURCE,
        'text_formats': {'/paragraphs/0': FORMAT},
    }
    assert section.text_formats == {'/content_json/subtitle': FORMAT}


def test_diagnostic_seed_inherits_section_format_map(diagnostic, diagnostic_spec):
    """Falla si el diagnóstico recién creado pierde los perfiles declarados en sus defaults."""
    config = DiagnosticDefaultConfig.objects.create(language='es', sections_json=[diagnostic_spec])

    diagnostic_service.seed_sections(diagnostic, config)
    section = diagnostic.sections.get(section_type='purpose')

    assert section.content_json == {'body': SOURCE}
    assert section.text_formats == {'/content_json/body': FORMAT}


@pytest.mark.parametrize('default_formats', [{'/content_json/body': FORMAT}, {}], ids=['restores', 'clears'])
def test_diagnostic_reset_replaces_previous_format_map(diagnostic, diagnostic_spec, default_formats):
    """Falla si restaurar conserva perfiles viejos o ignora los perfiles del default actual."""
    diagnostic_spec['text_formats'] = default_formats
    DiagnosticDefaultConfig.objects.create(language='es', sections_json=[diagnostic_spec])
    section = DiagnosticSection.objects.create(
        diagnostic=diagnostic, section_type='purpose', title='Propósito anterior',
        content_json={'body': 'Texto anterior'}, text_formats={'/content_json/body': 'plain'},
    )

    diagnostic_service.reset_section(section)
    section.refresh_from_db()

    assert section.content_json == {'body': SOURCE}
    assert section.text_formats == default_formats


def test_diagnostic_defaults_reject_unsafe_formatted_source(admin_client, diagnostic_spec):
    """Falla si guardar los defaults permite HTML prohibido dentro de una anotación local."""
    config = DiagnosticDefaultConfig.objects.create(language='es', sections_json=[diagnostic_spec])
    previous = deepcopy(config.sections_json)
    diagnostic_spec['content_json']['body'] = UNSAFE

    response = admin_client.put(reverse('diagnostic-defaults'), {
        'language': 'es', 'sections_json': [diagnostic_spec],
    }, format='json')
    config.refresh_from_db()

    assert response.status_code == 400
    assert 'sections_json' in response.json()
    assert config.sections_json == previous


def test_diagnostic_bulk_rejects_last_invalid_section_without_partial_writes(admin_client, diagnostic, diagnostic_sections):
    """Falla si la última sección inválida deja guardada una sección anterior o devuelve éxito."""
    first, last = diagnostic_sections

    response = admin_client.post(f'/api/diagnostics/{diagnostic.id}/sections/bulk-update/', {
        'sections': [
            {'id': first.id, 'content_json': {'body': SOURCE}, 'text_formats': {'/content_json/body': FORMAT}},
            {'id': last.id, 'content_json': {'body': UNSAFE}, 'text_formats': {'/content_json/body': FORMAT}},
        ],
    }, format='json')
    first.refresh_from_db()
    last.refresh_from_db()

    assert response.status_code == 400
    assert response.json()['code'] == 'validation_error'
    assert first.content_json == {'body': 'Primer contenido inicial'}
    assert last.content_json == {'body': 'Último contenido inicial'}
    assert first.text_formats == {}
    assert last.text_formats == {}
    assert diagnostic.change_logs.count() == 0


def test_diagnostic_bulk_persists_valid_format_maps(admin_client, diagnostic, diagnostic_sections):
    """Falla si validar el lote completo impide guardar fuentes y perfiles seguros."""
    first, last = diagnostic_sections

    response = admin_client.post(f'/api/diagnostics/{diagnostic.id}/sections/bulk-update/', {
        'sections': [
            {'id': first.id, 'content_json': {'body': SOURCE}, 'text_formats': {'/content_json/body': FORMAT}},
            {'id': last.id, 'content_json': {'body': 'Texto plano'}, 'text_formats': {'/content_json/body': 'plain'}},
        ],
    }, format='json')
    first.refresh_from_db()
    last.refresh_from_db()

    assert response.status_code == 200
    assert first.content_json == {'body': SOURCE}
    assert first.text_formats == {'/content_json/body': FORMAT}
    assert last.content_json == {'body': 'Texto plano'}
    assert last.text_formats == {'/content_json/body': 'plain'}
