"""The optional Appi writer can only add evidence-grounded plain text."""
import json
from unittest.mock import Mock

import pytest

from accounts.services import appi_answers, appi_jev

from .appi_test_support import project_status_data
from .test_appi_jev import ProviderReply

pytest_plugins = ('accounts.tests.appi_test_support',)
pytestmark = pytest.mark.django_db


def grounded_payload(choice):
    """Return the closed Jev grounding decision for one writer draft."""
    return {'answers': {'grounded': {
        'type': 'choice', 'choice': choice, 'confidence': 0.99,
        'probabilities': {'supported': int(choice == 'supported'), 'unsupported': int(choice == 'unsupported')},
    }}, 'usage': {'input_tokens': 5}}


@pytest.mark.parametrize('raw', [
    json.dumps({'summary': 'Estado inventado.', 'fact_ids': ['missing']}),
    json.dumps({'summary': 'El avance es 99.', 'fact_ids': ['f1']}),
    json.dumps({'summary': 'Consulta https://example.test.', 'fact_ids': ['f1']}),
    '{respuesta rota',
])
def test_invalid_writer_output_falls_back_to_the_template(appi_context, monkeypatch, raw):
    """Fails if a writer can invent a citation, number, URL, or malformed JSON in a client answer."""
    query, data = project_status_data(appi_context)
    writer = Mock(return_value=(raw, 'usage-id'))
    grounding = Mock(return_value=ProviderReply(grounded_payload('supported')))
    monkeypatch.setattr(appi_answers, 'generate_text', writer)
    monkeypatch.setattr(appi_jev.requests, 'post', grounding)

    result = appi_answers.answer(appi_context.actor, appi_context.project, 'Explícame el estado', query, data, 'es', config=appi_context.config)

    assert result['provenance'] == 'template'
    assert result['text'] == 'Appi project\n\n' + '\n'.join(item['text'] for item in data['facts'])
    writer.assert_called_once()
    grounding.assert_not_called()


def test_unsupported_jev_grounding_falls_back_to_the_template(appi_context, monkeypatch):
    """Fails if a polished but unsupported explanation is shown as a project fact."""
    query, data = project_status_data(appi_context)
    raw = json.dumps({'summary': 'El proyecto tiene avance registrado.', 'fact_ids': ['f1']})
    writer = Mock(return_value=(raw, 'usage-id'))
    grounding = Mock(return_value=ProviderReply(grounded_payload('unsupported')))
    monkeypatch.setattr(appi_answers, 'generate_text', writer)
    monkeypatch.setattr(appi_jev.requests, 'post', grounding)

    result = appi_answers.answer(appi_context.actor, appi_context.project, 'Explícame el estado', query, data, 'es', config=appi_context.config)

    assert result['provenance'] == 'template'
    assert result['text'].startswith('Appi project\n\nAppi project:')
    writer.assert_called_once()
    grounding.assert_called_once()


def test_grounded_writer_summary_is_marked_as_writer_provenance(appi_context, monkeypatch):
    """Fails if an evidence-backed explanatory response is discarded or mislabelled as a template."""
    query, data = project_status_data(appi_context)
    raw = json.dumps({'summary': 'El proyecto tiene avance registrado.', 'fact_ids': ['f1']})
    writer = Mock(return_value=(raw, 'usage-id'))
    grounding = Mock(return_value=ProviderReply(grounded_payload('supported')))
    monkeypatch.setattr(appi_answers, 'generate_text', writer)
    monkeypatch.setattr(appi_jev.requests, 'post', grounding)

    result = appi_answers.answer(appi_context.actor, appi_context.project, 'Explícame el estado', query, data, 'es', config=appi_context.config)

    assert result['provenance'] == 'writer'
    assert result['text'] == (
        'El proyecto tiene avance registrado.\n\nAppi project\n\n'
        + '\n'.join(item['text'] for item in data['facts'])
    )
    writer.assert_called_once()
    grounding.assert_called_once()
