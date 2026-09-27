"""Public proposal serializer tests for welcome-video visibility."""

import pytest

from content.models import (
    BusinessProposal,
    ExplainerVideoSettings,
    ProposalSection,
)
from content.serializers.proposal import ProposalDetailSerializer


pytestmark = pytest.mark.django_db


@pytest.fixture
def proposal_with_video_prerequisites(request):
    proposal_values, technical_enabled, global_visible = request.param
    values = {
        'title': 'Propuesta con video de bienvenida',
        'client_name': 'Cliente de propuesta',
        'language': 'es',
        'is_active': True,
        'show_contract_terms': True,
        'show_explainer_video': True,
    }
    values.update(proposal_values)
    proposal = BusinessProposal.objects.create(**values)
    if technical_enabled is not None:
        ProposalSection.objects.create(
            proposal=proposal,
            section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
            title='Detalle técnico',
            is_enabled=technical_enabled,
        )
    ExplainerVideoSettings.objects.create(show_proposal_video=global_visible)
    return proposal


@pytest.mark.parametrize(
    ('proposal_with_video_prerequisites', 'expected'),
    [
        (({}, True, True), True),
        (({'is_active': False}, True, True), False),
        (({'language': 'en'}, True, True), False),
        (({'show_explainer_video': False}, True, True), False),
        (({'show_contract_terms': False}, True, True), False),
        (({}, True, False), False),
        (({}, None, True), False),
        (({}, False, True), False),
    ],
    indirect=['proposal_with_video_prerequisites'],
)
def test_public_serializer_requires_every_welcome_video_prerequisite(
    proposal_with_video_prerequisites, expected,
):
    """Fails if a public proposal exposes the video after any required condition is false."""
    payload = ProposalDetailSerializer(
        proposal_with_video_prerequisites, context={'is_admin': False},
    ).data

    assert payload['show_explainer_video'] is expected
