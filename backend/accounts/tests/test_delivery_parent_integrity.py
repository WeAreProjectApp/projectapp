"""Prospective ancestry and publication preserve the provenance of retained guides."""
import copy

import pytest
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError

from accounts.models import (
    ContractAmendment,
    DeliveryPhase,
    DeliveryScope,
    DeliveryStage,
    ProjectContract,
    Requirement,
)
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_authoring_helpers import (
    build_authoring_context,
    citation,
    other_contract,
    pdf_bytes,
    signed_amendment,
    source_document,
)
from accounts.tests.delivery_helpers import (
    RECORDED_AT,
    decisions,
    prepare_prompt,
    publish,
    version,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    """Provide real signed source bytes and an unpublished guide hierarchy."""
    return build_authoring_context()


def _trace(context, *, selected_scope=True, **selection):
    if selected_scope:
        selection['scope_id'] = context.scope.pk
    prepared = prepare_prompt(context, **selection)
    delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
        'expected_version': version(context), 'context_id': prepared['id'],
        'source_references': [citation(prepared)], 'guide': {**context.first.guide, 'role': ''},
    }, context.first.pk)
    context.first.refresh_from_db()
    return prepared


def _scope(context, contract=None, *, key='destination'):
    return DeliveryScope.objects.create(contract=contract or context.contract, key=key, title='Destination scope')


def _phase(scope, key='destination-phase'):
    return DeliveryPhase.objects.create(scope=scope, key=key, title='Destination phase')


def _signed_other_scope(context):
    document = source_document(context, 'Signed alternative contractual scope.', requires_signature=True,
                               signed_by=context.client, signed_at=RECORDED_AT, signature_name='Client')
    document.generated_file.save('other.pdf', ContentFile(pdf_bytes('Signed alternative contractual scope.')), save=True)
    contract = ProjectContract.objects.create(project=context.project, key='signed-other', title='Other contract',
                                               document=document, client_visible=True)
    return _scope(context, contract)


def test_existing_stage_cannot_reopen_an_approved_phase(context):
    """Fails if PATCH can bypass the closed phase rule that CREATE already enforces."""
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'approved')))
    origin = _phase(context.scope, 'draft-origin')
    stage = DeliveryStage.objects.create(phase=origin, key='draft-stage', title='Draft stage')
    expected = version(context)

    with pytest.raises(ValidationError, match='fase aprobada'):
        delivery.mutate_node(context.project.pk, context.admin, 'stages',
                             {'expected_version': expected, 'phase_id': context.phase.pk}, stage.pk)

    stage.refresh_from_db()
    assert stage.phase_id == origin.pk
    assert version(context) == expected


def test_amendment_cannot_leave_its_dependent_scope_contract(context):
    """Fails if an unsigned amendment moves while an existing scope still uses it."""
    amendment = ContractAmendment.objects.create(contract=context.contract, key='unsigned', title='Unsigned change',
                                                  document=source_document(context))
    context.scope.amendment = amendment
    context.scope.save(update_fields=['amendment'])
    destination = other_contract(context)

    with pytest.raises(ValidationError, match='contrato de los alcances'):
        delivery.mutate_node(context.project.pk, context.admin, 'amendments', {
            'expected_version': version(context), 'contract_id': destination.pk,
        }, amendment.pk)

    amendment.refresh_from_db()
    assert amendment.contract_id == context.contract.pk


def test_unused_unsigned_amendment_can_move_within_the_project(context):
    """Fails if the integrity guard freezes an unused editable amendment."""
    amendment = ContractAmendment.objects.create(contract=context.contract, key='unused', title='Unused change',
                                                  document=source_document(context))
    destination = other_contract(context)

    delivery.mutate_node(context.project.pk, context.admin, 'amendments', {
        'expected_version': version(context), 'contract_id': destination.pk,
    }, amendment.pk)

    amendment.refresh_from_db()
    assert amendment.contract_id == destination.pk


@pytest.mark.parametrize(('kind', 'node_name', 'parent_field'), [
    ('phases', 'phase', 'scope_id'),
    ('stages', 'stage', 'phase_id'),
])
def test_ancestor_move_cannot_change_a_traced_guide_contract(context, kind, node_name, parent_field):
    """Fails if moving an ancestor retains citations captured for another contract."""
    _trace(context)
    destination = _scope(context, other_contract(context))
    destination_phase = _phase(destination)
    node = getattr(context, node_name)
    original_parent = getattr(node, parent_field)
    data = {parent_field: {'scope_id': destination.pk, 'phase_id': destination_phase.pk}[parent_field]}
    expected = version(context)

    with pytest.raises(ValidationError, match='contrato y alcance'):
        delivery.mutate_node(context.project.pk, context.admin, kind, {'expected_version': expected, **data}, node.pk)

    node.refresh_from_db()
    assert getattr(node, parent_field) == original_parent
    assert context.first.context_id is not None
    assert version(context) == expected


def test_scope_contract_cannot_change_under_a_traced_guide(context):
    """Fails if a scope PATCH silently rebinds its retained guide evidence."""
    _trace(context)
    destination = other_contract(context)

    with pytest.raises(ValidationError, match='contrato y alcance'):
        delivery.mutate_node(context.project.pk, context.admin, 'scopes', {
            'expected_version': version(context), 'contract_id': destination.pk,
        }, context.scope.pk)

    context.scope.refresh_from_db()
    assert context.scope.contract_id == context.contract.pk


def test_scope_amendment_cannot_replace_the_captured_identity(context):
    """Fails if a traced scope swaps between amendments selected in the same prompt."""
    original = signed_amendment(context, key='original-change')
    replacement = signed_amendment(context, key='other-change')
    context.scope.amendment = original
    context.scope.save(update_fields=['amendment'])
    _trace(context, amendment_ids=[original.pk, replacement.pk])

    with pytest.raises(ValidationError, match='otrosí o identidad'):
        delivery.mutate_node(context.project.pk, context.admin, 'scopes', {
            'expected_version': version(context), 'amendment_id': replacement.pk,
        }, context.scope.pk)

    context.scope.refresh_from_db()
    assert context.scope.amendment_id == original.pk


def test_scope_key_cannot_invalidate_its_captured_identity(context):
    """Fails if changing the scope key detaches descendants from their captured scope."""
    _trace(context)

    with pytest.raises(ValidationError, match='otrosí o identidad'):
        delivery.mutate_node(context.project.pk, context.admin, 'scopes', {
            'expected_version': version(context), 'key': 'different-identity',
        }, context.scope.pk)

    context.scope.refresh_from_db()
    assert context.scope.key == 'alcance'


def test_traced_stage_can_move_between_draft_phases_of_the_same_scope(context):
    """Fails if a compatible draft move unnecessarily freezes its guide citations."""
    _trace(context)
    destination = _phase(context.scope)
    references = copy.deepcopy(context.first.source_references)

    delivery.mutate_node(context.project.pk, context.admin, 'stages', {
        'expected_version': version(context), 'phase_id': destination.pk,
    }, context.stage.pk)

    context.stage.refresh_from_db()
    context.first.refresh_from_db()
    assert context.stage.phase_id == destination.pk
    assert context.first.source_references == references


def test_contract_level_context_allows_another_draft_scope_of_the_same_contract(context):
    """Fails if a context without a selected scope is treated as bound to one scope."""
    _trace(context, selected_scope=False)
    destination = _scope(context)

    delivery.mutate_node(context.project.pk, context.admin, 'phases', {
        'expected_version': version(context), 'scope_id': destination.pk,
    }, context.phase.pk)

    context.phase.refresh_from_db()
    assert context.phase.scope_id == destination.pk


def test_manual_unpublished_guides_remain_movable(context):
    """Fails if untraced editable guides acquire a new artificial source restriction."""
    destination = _scope(context, other_contract(context))

    delivery.mutate_node(context.project.pk, context.admin, 'phases', {
        'expected_version': version(context), 'scope_id': destination.pk,
    }, context.phase.pk)

    context.phase.refresh_from_db()
    assert context.phase.scope_id == destination.pk
    assert Requirement.objects.get(pk=context.first.pk).context_id is None


@pytest.mark.parametrize('apply', [False, True])
def test_manual_import_cannot_hide_incompatible_retained_descendants(context, apply):
    """Fails if an omitted guide lets JSON v1 rewrite its captured scope identity."""
    _trace(context)
    amendment = signed_amendment(context)
    payload = {'schema_version': 1, 'scopes': [{
        'key': context.scope.key, 'title': context.scope.title, 'contract_id': context.contract.pk,
        'amendment_id': amendment.pk,
    }]}
    expected = version(context)

    with pytest.raises(ValidationError, match='otrosí o identidad'):
        delivery.import_payload(context.project.pk, context.admin, payload, expected,
                                apply=apply, request_id='omitted-traced-guides')

    context.scope.refresh_from_db()
    assert context.scope.amendment_id is None
    assert version(context) == expected


def test_publication_rejects_contract_drift_in_historical_guide_ancestry(context):
    """Fails if publication accepts an existing guide bound to another contract."""
    _trace(context)
    destination = _signed_other_scope(context)
    DeliveryPhase.objects.filter(pk=context.phase.pk).update(scope=destination)
    expected = version(context)

    with pytest.raises(ValidationError, match='contrato y alcance'):
        publish(context)

    assert not context.stage.publications.exists()
    assert version(context) == expected


def test_publication_rejects_an_invalid_retained_quote(context):
    """Fails if a forged quote is accepted after a guide was initially validated."""
    prepared = _trace(context)
    reference = {**citation(prepared), 'quote': 'This quotation does not exist in the signed source.'}
    Requirement.objects.filter(pk=context.first.pk).update(source_references=[reference])

    with pytest.raises(ValidationError, match='localizador o la cita'):
        publish(context)

    assert not context.stage.publications.exists()


def test_publication_rejects_an_amendment_under_another_contract(context):
    """Fails if a pre-existing scope can publish with another contract's amendment."""
    destination = other_contract(context)
    amendment = signed_amendment(context, contract=destination)
    DeliveryScope.objects.filter(pk=context.scope.pk).update(amendment=amendment)

    with pytest.raises(ValidationError, match='contrato de este alcance'):
        publish(context)

    assert not context.stage.publications.exists()


def test_publication_accepts_the_original_verified_guide_context(context):
    """Fails if the defense rejects intact scope identity and verified citations."""
    prepared = _trace(context)

    publish(context)

    context.first.refresh_from_db()
    assert context.first.review_status == 'in_review'
    assert str(context.first.context_id) == prepared['id']
    assert context.stage.publications.count() == 1
