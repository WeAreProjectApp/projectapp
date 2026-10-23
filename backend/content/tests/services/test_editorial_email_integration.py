"""Integration coverage for editorial content in composed email alternatives."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from content.models import BusinessProposal
from content.services.email_markdown import normalize_sections
from content.services.proposal_email_service import ProposalEmailService
from content.tests.email_stubs import stub_email_message


pytestmark = pytest.mark.django_db

ANNOTATED_SECTION = (
    '<p style="text-align:justify"><span style="color:#ff0000">'
    '<strong>Oferta</strong></span></p>\n\n'
    '- Alcance\n- Entrega\n\n'
    '| Fase | Estado |\n| --- | --- |\n| Diseño | Listo |'
)


def render_annotated_section():
    return ProposalEmailService.render_composed_email(
        'branded_email', None, 'Entrega', 'Hola', [ANNOTATED_SECTION], '', [],
        text_formats={'/sections/0': 'markdown_html_v1'},
    )


@pytest.fixture
def editorial_email_proposal(db):
    """Proposal whose client email can render the real sent-client templates."""
    return BusinessProposal.objects.create(
        title='Propuesta editorial',
        client_name='Cliente Editorial',
        client_email='editorial@example.com',
        language='es',
        total_investment=Decimal('1200000'),
        currency='COP',
        status='sent',
        expires_at=timezone.now() + timezone.timedelta(days=10),
    )


def test_composed_email_renders_annotated_section_as_inline_html():
    """Falla si un cuerpo editorial anotado se escapa antes de llegar a la alternativa HTML."""
    html, _ = render_annotated_section()

    assert '<strong>Oferta</strong>' in html
    assert '<ul' in html
    assert '<table' in html
    assert '&lt;p' not in html


def test_composed_email_uses_plain_text_alternative_for_annotated_section():
    """Falla si la alternativa de texto de un cuerpo editorial conserva etiquetas o sintaxis."""
    _, text = render_annotated_section()

    assert '<table' not in text
    assert '<strong' not in text
    assert 'Oferta' in text
    assert 'Diseño' in text


def test_composed_email_uses_plain_text_alternative_for_annotated_greeting():
    """Falla si el texto alternativo de un saludo editorial conserva sintaxis Markdown o HTML."""
    html, text = ProposalEmailService.render_composed_email(
        'branded_email', None, 'Entrega', '**Hola equipo**', ['Mensaje'], '', [],
        text_formats={'/greeting': 'markdown'},
    )

    assert '<strong>Hola equipo</strong>' in html
    assert 'Hola equipo' in text
    assert '**Hola equipo**' not in text


def test_composed_email_keeps_unannotated_legacy_section_escaped():
    """Falla si contenido histórico sin perfil cambia de texto literal a HTML ejecutable."""
    legacy = '<strong>Literal histórico</strong>'

    html, text = ProposalEmailService.render_composed_email(
        'branded_email', None, 'Entrega', 'Hola', [legacy], '', [],
    )

    assert '&lt;strong&gt;Literal histórico&lt;/strong&gt;' in html
    assert legacy in text


def test_normalize_sections_marks_valid_new_editorial_markdown():
    """Falla si una sección nueva del editor pierde el marcador que activa su salida editorial."""
    sections = normalize_sections(
        [{'text': '<p><strong>Entrega</strong></p>', 'markdown': True}],
        strict_editorial=True,
    )

    assert sections == [{
        'text': '<p><strong>Entrega</strong></p>',
        'markdown': True,
        'format': 'markdown_html_v1',
    }]


def test_normalize_sections_rejects_invalid_editorial_css_for_new_submission():
    """Falla si una entrada nueva puede guardar color sobre una etiqueta fuera del contrato editorial."""
    with pytest.raises(ValidationError, match='style'):
        normalize_sections(
            [{'text': '<p style="color:red">Entrega</p>', 'markdown': True}],
            strict_editorial=True,
        )


def test_normalize_sections_keeps_legacy_markdown_shape_without_editorial_flag():
    """Falla si una sección Markdown histórica cambia de formato interno sin metadatos nuevos."""
    sections = normalize_sections([{'text': '**Entrega**', 'markdown': True}])

    assert sections == [{'text': '**Entrega**', 'markdown': True}]


def test_composed_email_uses_marker_from_new_editorial_submission():
    """Falla si el marcador validado por una vista nueva se pierde antes de generar la previsualización."""
    sections = normalize_sections(
        [{'text': '<p><strong>Entrega</strong></p>', 'markdown': True}],
        strict_editorial=True,
    )

    html, text = ProposalEmailService.render_composed_email(
        'branded_email', None, 'Entrega', 'Hola', sections, '', [],
    )

    assert '<strong>Entrega</strong>' in html
    assert '<strong' not in text


@patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
@patch('content.services.proposal_email_service.EmailMultiAlternatives')
def test_sent_email_projects_annotated_feature_to_html_and_plain_text(
    mock_email_cls, mock_pdf, editorial_email_proposal,
):
    """Falla si una prestación anotada se escapa en HTML o conserva Markdown en el texto alternativo."""
    editorial_email_proposal.email_features = ['**Alcance prioritario**']
    editorial_email_proposal.text_formats = {'/email_features/0': 'markdown'}
    editorial_email_proposal.save(update_fields=['email_features', 'text_formats'])
    email = stub_email_message()
    mock_email_cls.return_value = email

    result = ProposalEmailService.send_proposal_to_client(editorial_email_proposal)

    html = email.attach_alternative.call_args.args[0]
    text = mock_email_cls.call_args.kwargs['body']
    assert result['ok'] is True
    assert '<strong>Alcance prioritario</strong>' in html
    assert '01. Alcance prioritario' in text
    assert '**Alcance prioritario**' not in text


@patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
@patch('content.services.proposal_email_service.EmailMultiAlternatives')
def test_sent_email_projects_annotated_phase_to_html_and_plain_text(
    mock_email_cls, mock_pdf, editorial_email_proposal,
):
    """Falla si una descripción de fase anotada pierde estilo HTML o expone etiquetas en el texto alternativo."""
    editorial_email_proposal.email_method_phases = [{
        'number': '01',
        'title': 'Diseño',
        'duration': '1 semana',
        'description': (
            '<p><span style="color:#ff0000"><strong>Diseño verificado</strong>'
            '</span></p>'
        ),
    }]
    editorial_email_proposal.text_formats = {
        '/email_method_phases/0/description': 'markdown_html_v1',
    }
    editorial_email_proposal.save(update_fields=['email_method_phases', 'text_formats'])
    email = stub_email_message()
    mock_email_cls.return_value = email

    result = ProposalEmailService.send_proposal_to_client(editorial_email_proposal)

    html = email.attach_alternative.call_args.args[0]
    text = mock_email_cls.call_args.kwargs['body']
    assert result['ok'] is True
    assert '<strong>Diseño verificado</strong>' in html
    assert 'color: rgb(255, 0, 0)' in html
    assert 'Diseño verificado' in text
    assert '<strong>Diseño verificado</strong>' not in text


@patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
@patch('content.services.proposal_email_service.EmailMultiAlternatives')
def test_sent_email_escapes_unannotated_legacy_feature(
    mock_email_cls, mock_pdf, editorial_email_proposal,
):
    """Falla si una prestación histórica sin metadato deja de escaparse sólo en la alternativa HTML."""
    legacy_feature = '<strong>Literal legado</strong>'
    editorial_email_proposal.email_features = [legacy_feature]
    editorial_email_proposal.save(update_fields=['email_features'])
    email = stub_email_message()
    mock_email_cls.return_value = email

    ProposalEmailService.send_proposal_to_client(editorial_email_proposal)

    html = email.attach_alternative.call_args.args[0]
    text = mock_email_cls.call_args.kwargs['body']
    assert '&lt;strong&gt;Literal legado&lt;/strong&gt;' in html
    assert '&lt;strong&gt;Literal legado&lt;/strong&gt;' in text


@patch('content.services.proposal_pdf_service.ProposalPdfService.generate', return_value=b'pdf')
@patch('content.services.proposal_email_service.EmailMultiAlternatives')
def test_multi_email_projects_each_annotated_intro_with_its_own_format(
    mock_email_cls, mock_pdf, editorial_email_proposal,
):
    """Falla si el envío múltiple aplica el formato de una propuesta al texto introductorio de otra."""
    editorial_email_proposal.email_intro = '**Primer alcance**'
    editorial_email_proposal.text_formats = {'/email_intro': 'markdown'}
    editorial_email_proposal.save(update_fields=['email_intro', 'text_formats'])
    second_proposal = BusinessProposal.objects.create(
        title='Segunda propuesta editorial',
        client_name='Cliente Editorial',
        client_email='editorial@example.com',
        language='es',
        total_investment=Decimal('1800000'),
        currency='COP',
        status='sent',
        expires_at=editorial_email_proposal.expires_at,
        email_intro=(
            '<p><span style="color:#ff0000"><strong>Segundo alcance</strong>'
            '</span></p>'
        ),
        text_formats={'/email_intro': 'markdown_html_v1'},
    )
    email = stub_email_message()
    mock_email_cls.return_value = email

    result = ProposalEmailService.send_multi_proposal_to_client(
        [editorial_email_proposal, second_proposal],
    )

    html = email.attach_alternative.call_args.args[0]
    text = mock_email_cls.call_args.kwargs['body']
    assert result['ok'] is True
    assert '<strong>Primer alcance</strong>' in html
    assert '<strong>Segundo alcance</strong>' in html
    assert 'color: rgb(255, 0, 0)' in html
    assert 'Primer alcance' in text
    assert 'Segundo alcance' in text
    assert '<strong>Segundo alcance</strong>' not in text
