"""MCP parent changes preserve the captured provenance of delivery guides."""
import pytest
from accounts.models import DeliveryPhase, DeliveryScope, Requirement
from accounts.tests.delivery_authoring_helpers import (
    build_authoring_context,
    citation,
    other_contract,
    signed_amendment,
)

from content.tests.views.test_mcp_delivery import (
    call_projects as call_projects,  # noqa: PLC0414 - pytest discovers this shared fixture.
)
from content.tests.views.test_mcp_delivery import (
    confirm,
    current_version,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def traced(call_projects):
    """Capture signed sources through MCP before attaching a cited draft guide."""
    context = build_authoring_context()
    prepared = call_projects('create_delivery_guide_prompt', {
        'project_id': context.project.pk, 'contract_id': context.contract.pk,
        'scope_id': context.scope.pk, 'request_id': 'parent-integrity-context',
        'expected_version': current_version(call_projects, context.project),
    })
    call_projects('update_delivery_requirement', {
        'project_id': context.project.pk, 'node_id': context.first.pk,
        'expected_version': current_version(call_projects, context.project),
        'context_id': prepared['id'], 'source_references': [citation(prepared)],
        'guide': {**context.first.guide, 'role': ''},
    })
    context.first.refresh_from_db()
    return context, prepared


def test_mcp_phase_move_cannot_change_a_descendant_guide_contract(call_projects, traced):
    """Fails if a conversational parent update bypasses retained guide ancestry."""
    context, _ = traced
    destination = DeliveryScope.objects.create(contract=other_contract(context), key='destination', title='Destination')
    expected = current_version(call_projects, context.project)

    error = call_projects('update_delivery_phase', {
        'project_id': context.project.pk, 'node_id': context.phase.pk,
        'expected_version': expected, 'scope_id': destination.pk,
    }, expect_error=True)

    context.phase.refresh_from_db()
    assert error['code'] == 'CONTEXT_SCOPE'
    assert context.phase.scope_id == context.scope.pk
    assert current_version(call_projects, context.project) == expected


def test_mcp_stage_move_preserves_a_compatible_draft_context(call_projects, traced):
    """Fails if MCP freezes a valid move between draft phases of the same scope."""
    context, prepared = traced
    destination = DeliveryPhase.objects.create(scope=context.scope, key='destination', title='Destination')

    call_projects('update_delivery_stage', {
        'project_id': context.project.pk, 'node_id': context.stage.pk,
        'expected_version': current_version(call_projects, context.project),
        'phase_id': destination.pk,
    })

    context.stage.refresh_from_db()
    context.first.refresh_from_db()
    assert context.stage.phase_id == destination.pk
    assert str(context.first.context_id) == prepared['id']
    assert context.first.source_references == [citation(prepared)]


def _preview_import(call, arguments):
    return call('preview_delivery_import', arguments, expect_error=True)


def _apply_import(call, arguments):
    return confirm(call, 'apply_delivery_import', {**arguments, 'request_id': 'retained-descendants'}, expect_error=True)


@pytest.mark.parametrize('execute', [_preview_import, _apply_import])
def test_mcp_manual_import_cannot_hide_incompatible_retained_descendants(call_projects, traced, execute):
    """Fails if preview or confirmation silently rebinds omitted traced guides."""
    context, _ = traced
    amendment = signed_amendment(context)
    expected = current_version(call_projects, context.project)
    payload = {'schema_version': 1, 'scopes': [{
        'key': context.scope.key, 'title': context.scope.title,
        'contract_id': context.contract.pk, 'amendment_id': amendment.pk, 'phases': [],
    }]}

    error = execute(call_projects, {'project_id': context.project.pk, 'expected_version': expected, 'payload': payload})

    context.scope.refresh_from_db()
    assert error['code'] == 'CONTEXT_SCOPE'
    assert context.scope.amendment_id is None
    assert current_version(call_projects, context.project) == expected


def test_mcp_publication_rejects_an_invalid_retained_quote(call_projects, traced):
    """Fails if confirmation publishes a historically corrupted guide citation."""
    context, prepared = traced
    forged = {**citation(prepared), 'quote': 'This quote does not occur in the signed contract.'}
    Requirement.objects.filter(pk=context.first.pk).update(source_references=[forged])
    expected = current_version(call_projects, context.project)

    error = confirm(call_projects, 'publish_delivery_stage', {
        'project_id': context.project.pk, 'stage_id': context.stage.pk,
        'expected_version': expected, 'request_id': 'invalid-citation-publication',
    }, expect_error=True)

    assert error['code'] == 'CITATION_QUOTE'
    assert not context.stage.publications.exists()
    assert current_version(call_projects, context.project) == expected
