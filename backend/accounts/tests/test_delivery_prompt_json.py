"""Cited JSON crosses the same atomic draft boundary as manual authoring."""
import copy

import pytest
from freezegun import freeze_time
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import DeliveryScope, Project, Requirement
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_authoring_helpers import (
    api_for, build_authoring_context, citation, endpoint, existing_tree_payload, guide_leaf,
    guides_payload, malformed_guides, manual_payload, other_contract, reference,
    signed_amendment, source_document, trace_first,
)
from accounts.tests.delivery_helpers import RECORDED_AT, decisions, prepare_prompt, publish, version

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        yield build_authoring_context()


def apply(context, payload, request_id='apply-cited-guides'):
    return delivery.import_payload(context.project.pk, context.admin, payload, version(context),
                                   apply=True, request_id=request_id)


def trace_first_with_complete_role_guide(context, prepared):
    """Prepare the cited v2 version that the client will actually approve."""
    guide = {
        **context.first.guide,
        'access': 'Use the existing client test account.',
        'allowed_actions': 'View the validation screen and save the record.',
        'blocked_actions': 'Cannot change another client record.',
        'blocked_steps': ['Open another client record with the same account.'],
        'blocked_result': 'The other client record remains unavailable.',
    }
    delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
        'expected_version': version(context), 'context_id': prepared['id'],
        'source_references': [citation(prepared)], 'guide': guide,
    }, context.first.pk)
    context.first.refresh_from_db()


def test_cited_preview_writes_no_delivery_rows(context):
    """Fails if previewing cited guides changes requirements or the workspace version."""
    prepared = prepare_prompt(context)

    result = delivery.import_payload(context.project.pk, context.admin, guides_payload(prepared), 0)

    assert result['valid'] is True
    assert Requirement.objects.count() == 2
    assert DeliveryScope.objects.count() == 1
    assert version(context) == 0


def test_cited_apply_retains_server_verified_provenance(context):
    """Fails if applying cited guides loses their captured source identity."""
    prepared = prepare_prompt(context)

    result = apply(context, guides_payload(prepared))

    requirement = Requirement.objects.get(key='validacion-1')
    assert str(requirement.context_id) == prepared['id']
    assert requirement.source_references == [citation(prepared)]
    assert requirement.review_status == 'pending'
    assert requirement.stage.editorial_status == 'draft'
    assert result['version'] == 1


def test_forged_quote_rolls_back_the_import(context):
    """Fails if an invented contractual quotation creates delivery rows."""
    prepared = prepare_prompt(context)
    payload = guides_payload(prepared)
    guide_leaf(payload)['source_references'][0]['quote'] = 'Invented analytics clause.'

    with pytest.raises(ValidationError, match='no existe'):
        apply(context, payload)

    assert Requirement.objects.count() == 2
    assert version(context) == 0


def test_unknown_locator_rejects_an_existing_quote(context):
    """Fails if a real quotation can be attributed to an invented source location."""
    prepared = prepare_prompt(context)
    payload = guides_payload(prepared)
    guide_leaf(payload)['source_references'][0]['locator'] = 'Página 999'

    with pytest.raises(ValidationError, match='localizador'):
        apply(context, payload)

    assert Requirement.objects.count() == 2


def test_annex_alone_cannot_establish_contractual_scope(context):
    """Fails if administrative annex evidence alone authorizes contractual guide content."""
    document = source_document(context, 'Administrative annex allows analytics.')
    prepared = prepare_prompt(context, sources=[reference(document, role='contractual_annex')])
    source = prepared['sources'][1]
    payload = guides_payload(prepared)
    guide_leaf(payload)['source_references'] = [{'source_key': source['source_key'],
                                               'locator': source['fragments'][0]['locator'],
                                               'quote': 'Administrative annex allows analytics.'}]

    with pytest.raises(ValidationError, match='contrato u otrosí'):
        apply(context, payload)

    assert Requirement.objects.count() == 2
    assert DeliveryScope.objects.count() == 1
    assert version(context) == 0


@pytest.mark.parametrize('kind', ['phase', 'stages', 'requirements'])
def test_malformed_cited_tree_returns_400_without_writes(context, kind):
    """Fails if malformed nested JSON causes a server error or partial import."""
    prepared = prepare_prompt(context)
    api = api_for(context.admin)

    response = api.post(endpoint(context, 'import/apply/'), {
        'expected_version': 0, 'request_id': 'invalid-cited-tree',
        'payload': malformed_guides(prepared, kind),
    }, format='json')

    assert response.status_code == 400
    assert Requirement.objects.count() == 2
    assert DeliveryScope.objects.count() == 1
    assert version(context) == 0


def test_invalid_context_uuid_returns_400_without_writes(context):
    """Fails if an invalid context identifier causes a server error or changes delivery rows."""
    prepared = prepare_prompt(context)
    payload = guides_payload(prepared)
    payload['context_id'] = 'not-a-uuid'

    response = api_for(context.admin).post(endpoint(context, 'import/preview/'),
                                           {'expected_version': 0, 'payload': payload}, format='json')

    assert response.status_code == 400
    assert Requirement.objects.count() == 2


def test_cited_context_cannot_cross_projects(context):
    """Fails if cited guides can reuse a context belonging to another project."""
    prepared = prepare_prompt(context)
    other = Project.objects.create(name='Other project', client=context.client)

    with pytest.raises(NotFound):
        delivery.import_payload(other.pk, context.admin, guides_payload(prepared), 0)

    assert DeliveryScope.objects.filter(contract__project=other).count() == 0


def test_manual_v1_cannot_claim_a_context(context):
    """Fails if manual JSON claims captured provenance without version-two validation."""
    prepared = prepare_prompt(context)
    payload = manual_payload(prepared)
    payload['context_id'] = prepared['id']

    with pytest.raises(ValidationError, match='schema_version'):
        apply(context, payload)

    assert Requirement.objects.count() == 2


def test_manual_v1_cannot_claim_verified_citations(context):
    """Fails if manual JSON can forge verified source references."""
    prepared = prepare_prompt(context)
    payload = manual_payload(prepared)
    guide_leaf(payload)['source_references'] = [citation(prepared)]

    with pytest.raises(ValidationError, match='campos no permitidos'):
        apply(context, payload)

    assert Requirement.objects.count() == 2


def test_manual_v1_cannot_rewrite_a_traced_guide(context):
    """Fails if manual JSON bypasses citation review on an already traced guide."""
    prepared = prepare_prompt(context)
    apply(context, guides_payload(prepared))
    payload = manual_payload(prepared)
    guide_leaf(payload)['title'] = 'Unverified replacement title'

    with pytest.raises(ValidationError, match='JSON v2'):
        apply(context, payload, request_id='manual-downgrade')

    requirement = Requirement.objects.get(key='validacion-1')
    assert requirement.title == 'Qué podrá comprobar el cliente'
    assert str(requirement.context_id) == prepared['id']
    assert version(context) == 1


def test_requirement_patch_cannot_remove_captured_provenance(context):
    """Fails if editing a requirement can erase its retained source context."""
    prepared = prepare_prompt(context)
    trace_first(context, prepared)

    response = api_for(context.admin).patch(endpoint(context, f'requirements/{context.first.pk}/'), {
        'expected_version': version(context), 'context_id': None, 'source_references': [],
    }, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 400
    assert str(context.first.context_id) == prepared['id']
    assert version(context) == 1


def test_traced_guide_edit_requires_explicit_references(context):
    """Fails if a traced guide changes without explicitly reviewing its contractual references."""
    prepared = prepare_prompt(context)
    trace_first(context, prepared)

    response = api_for(context.admin).patch(endpoint(context, f'requirements/{context.first.pk}/'),
                                           {'expected_version': 1, 'title': 'Edited without source review'}, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 400
    assert context.first.title == 'Guardar registro'


def test_traced_guide_edit_accepts_verified_references(context):
    """Fails if a valid cited correction cannot update an editable traced guide."""
    prepared = prepare_prompt(context)
    trace_first(context, prepared)

    response = api_for(context.admin).patch(endpoint(context, f'requirements/{context.first.pk}/'), {
        'expected_version': 1, 'title': 'Review record creation',
        'context_id': prepared['id'], 'source_references': [citation(prepared)],
    }, format='json')

    context.first.refresh_from_db()
    assert response.status_code == 200
    assert context.first.title == 'Review record creation'
    assert context.first.source_references == [citation(prepared)]


def test_requirement_context_cannot_change_contractual_ancestry(context):
    """Fails if a requirement can cite a context captured for a different contract."""
    other = other_contract(context)
    prepared = prepare_prompt(context, contract_id=other.pk)

    with pytest.raises(ValidationError, match='contrato y alcance'):
        delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
            'expected_version': 0, 'context_id': prepared['id'],
            'source_references': guide_leaf(guides_payload(prepared))['source_references'],
        }, context.first.pk)

    context.first.refresh_from_db()
    assert context.first.context_id is None


def test_cited_scope_cannot_swap_its_captured_amendment(context):
    """Fails if cited JSON reassigns a captured scope to another selected amendment."""
    selected = signed_amendment(context, key='selected')
    alternative = signed_amendment(context, key='alternative')
    context.scope.amendment = selected
    context.scope.save(update_fields=['amendment'])
    prepared = prepare_prompt(context, scope_id=context.scope.pk, amendment_ids=[selected.pk, alternative.pk])
    payload = guides_payload(prepared)
    payload['scopes'][0]['amendment_id'] = alternative.pk

    with pytest.raises(ValidationError, match='otrosí del alcance capturado'):
        apply(context, payload)

    context.scope.refresh_from_db()
    assert context.scope.amendment_id == selected.pk
    assert Requirement.objects.count() == 2
    assert version(context) == 0


def test_cited_import_preserves_an_approved_guide(context):
    """Fails if new draft guides change an approved requirement or the prior client publication."""
    prepared = prepare_prompt(context)
    trace_first_with_complete_role_guide(context, prepared)
    approved_guide = copy.deepcopy(context.first.guide)
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    payload = existing_tree_payload(context, prepared)
    new_requirement = copy.deepcopy(guide_leaf(payload))
    new_requirement.update(key='new-pending-guide', title='New pending validation')
    new_requirement['guide'].pop('role')
    payload['scopes'][0]['phases'][0]['stages'][0]['requirements'].append(new_requirement)

    apply(context, payload)

    context.first.refresh_from_db()
    pending = Requirement.objects.get(key='new-pending-guide')
    assert context.first.review_status == 'approved'
    assert context.first.guide == approved_guide
    assert str(context.first.context_id) == prepared['id']
    assert pending.review_status == 'pending'
    assert pending.stage.editorial_status == 'draft'
    client_requirements = delivery.overview(context.project.pk, context.client)['scopes'][0]['phases'][0]['stages'][0]['requirements']
    assert len(client_requirements) == 2


def test_cited_import_cannot_rewrite_an_approved_title(context):
    """Fails if a cited import rewrites the identity of an approved requirement."""
    prepared = prepare_prompt(context)
    trace_first_with_complete_role_guide(context, prepared)
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    payload = existing_tree_payload(context, prepared)
    guide_leaf(payload)['title'] = 'Replacement of approved guide'

    with pytest.raises(ValidationError, match='contenido publicado'):
        apply(context, payload)

    context.first.refresh_from_db()
    assert context.first.title == 'Guardar registro'
    assert context.first.review_status == 'approved'
