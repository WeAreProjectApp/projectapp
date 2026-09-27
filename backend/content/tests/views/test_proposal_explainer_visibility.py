"""Public proposal welcome-video visibility tests."""

import pytest
from django.urls import reverse

from content.models import (
    BusinessProposal,
    ExplainerVideoSettings,
    ProposalSection,
    ProposalShareLink,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def eligible_proposal_with_hidden_global_video():
    proposal = BusinessProposal.objects.create(
        title='Propuesta pública coherente',
        client_name='Cliente público',
        language='es',
        is_active=True,
        show_contract_terms=True,
        show_explainer_video=True,
    )
    ProposalSection.objects.create(
        proposal=proposal,
        section_type=ProposalSection.SectionType.TECHNICAL_DOCUMENT,
        title='Detalle técnico',
        is_enabled=True,
    )
    share_link = ProposalShareLink.objects.create(
        proposal=proposal,
        shared_by_name='Remitente',
    )
    settings = ExplainerVideoSettings.objects.create(show_proposal_video=False)
    return proposal, share_link, settings


@pytest.mark.parametrize(
    ('route_name', 'route_kwarg'),
    [
        ('retrieve-public-proposal', 'proposal_uuid'),
        ('retrieve-public-proposal-by-slug', 'proposal_slug'),
        ('retrieve-shared-proposal', 'share_uuid'),
    ],
)
def test_global_switch_hides_welcome_video_from_each_public_route(
    api_client, eligible_proposal_with_hidden_global_video, route_name, route_kwarg,
):
    """Fails if a public proposal route bypasses the global welcome-video switch."""
    proposal, share_link, _settings = eligible_proposal_with_hidden_global_video
    route_value = {
        'proposal_uuid': proposal.uuid,
        'proposal_slug': proposal.slug,
        'share_uuid': share_link.uuid,
    }[route_kwarg]

    response = api_client.get(reverse(route_name, kwargs={route_kwarg: route_value}))

    assert response.status_code == 200
    assert response.data['show_explainer_video'] is False


def test_reenabling_global_switch_restores_public_welcome_video(
    api_client, eligible_proposal_with_hidden_global_video,
):
    """Fails if restoring the global switch cannot reveal an eligible proposal's video."""
    proposal, _share_link, settings = eligible_proposal_with_hidden_global_video
    settings.show_proposal_video = True
    settings.save(update_fields=['show_proposal_video'])
    response = api_client.get(reverse(
        'retrieve-public-proposal', kwargs={'proposal_uuid': proposal.uuid},
    ))

    assert response.status_code == 200
    assert response.data['show_explainer_video'] is True


def test_admin_payload_keeps_individual_welcome_video_preference(
    admin_client, eligible_proposal_with_hidden_global_video,
):
    """Fails if the global public switch overwrites the panel's stored preference."""
    proposal, _share_link, _settings = eligible_proposal_with_hidden_global_video

    response = admin_client.get(reverse(
        'retrieve-proposal', kwargs={'proposal_id': proposal.id},
    ))

    assert response.status_code == 200
    assert response.data['show_explainer_video'] is True
