"""Visibility rule for the explainer videos shown in the client-facing views."""

from content.models import ExplainerVideoSettings

# Explainer ids match frontend/composables/useExplainerVideos.js.
MODULE_SWITCHES = {
    'additional-modules': 'show_additional_modules_video',
    'financing': 'show_financing_video',
    'proposal': 'show_proposal_video',
}


def explainer_video_visible(module, *, share_link=None):
    """Return whether the public view of ``module`` may show its explainer.

    The panel switch of the module governs. A shared catalog link can only hide
    the video for its recipient: it shows when both switches are on. Whether a
    render exists for the visitor's language is decided by the frontend.
    """

    if module not in MODULE_SWITCHES:
        raise ValueError(f'Unknown explainer module: {module}')
    visible = getattr(ExplainerVideoSettings.load(), MODULE_SWITCHES[module])
    if share_link is not None:
        visible = visible and share_link.show_explainer_video
    return visible


def proposal_explainer_video_visible(proposal, sections):
    """Public welcome video: both switches and all four options are required.

    Reuse the serialized public sections, avoiding another query or diverging
    from the enabled-section filter. The flag is evaluated on every GET.
    """
    if not (proposal.is_active and proposal.language == 'es'
            and proposal.show_explainer_video and proposal.show_contract_terms):
        return False
    has_technical = any(
        section['section_type'] == 'technical_document' and section['is_enabled']
        for section in sections
    )
    return has_technical and explainer_video_visible('proposal')
