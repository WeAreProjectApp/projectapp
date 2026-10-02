"""Product-role guides retain sourced access cases through real publication."""
import copy

import pytest
from django.core.files.base import ContentFile
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from accounts.models import DeliveryPublication, DeliveryStage, Requirement
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_authoring_helpers import (
    build_authoring_context, captured_citation, guide_leaf, guides_payload, manual_payload, pdf_bytes,
)
from accounts.tests.delivery_helpers import RECORDED_AT, prepare_prompt, version

pytestmark = pytest.mark.django_db
ROLE_TEXT = 'Operator creates records. Reviewer checks records. Operator cannot review. Reviewer cannot create.'


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        yield build_authoring_context()


def prepare_roles(context):
    context.document.generated_file.save('roles.pdf', ContentFile(pdf_bytes(ROLE_TEXT)), save=True)
    return prepare_prompt(context)


def role_payload(prepared):
    payload = guides_payload(prepared)
    operator = payload['scopes'][0]['phases'][0]['stages'][0]
    operator.update(key='operator-stage', title='Create a record as Operator')
    first = operator['requirements'][0]
    first.update(key='create-record', title='Create a record', source_references=[captured_citation(prepared, 'contract')])
    first['guide'].update(role='Operator', access='Use the Operator test account.',
                          allowed_actions='See the list and create a record.', blocked_actions='Cannot open the review screen.',
                          steps=['Create a record with the supplied test data.'], expected_result='The record appears in the list.',
                          blocked_steps=['Open the review screen with the same account.'], blocked_result='Access is denied.',
                          dependencies='')
    reviewer = copy.deepcopy(operator)
    reviewer.update(key='reviewer-stage', title='Check the record as Reviewer')
    second = reviewer['requirements'][0]
    second.update(key='check-record', title='Check the existing record')
    second['guide'].update(role='Reviewer', access='Use the Reviewer test account.',
                           allowed_actions='See the created record and check it.', blocked_actions='Cannot create records.',
                           steps=['Open the record created in operator-stage.'], expected_result='The existing record is shown.',
                           blocked_steps=['Try opening the create-record screen.'], blocked_result='The create action is unavailable.',
                           dependencies='Complete operator-stage before reviewer-stage; use the same test record.')
    payload['scopes'][0]['phases'][0]['stages'].append(reviewer)
    return payload


def apply(context, payload):
    return delivery.import_payload(context.project.pk, context.admin, payload, version(context),
                                   apply=True, request_id='product-role-import')


def publish_stage(context, key):
    stage = DeliveryStage.objects.get(key=key)
    delivery.publish_stage(context.project.pk, context.admin, stage.pk,
                           {'expected_version': version(context), 'request_id': f'publish-{key}'})
    return stage


def test_role_guides_keep_cross_role_dependencies_in_client_publication(context):
    """Fails if grouping roles duplicates requirements or drops their shared workflow dependency."""
    prepared = prepare_roles(context)
    apply(context, role_payload(prepared))
    publish_stage(context, 'operator-stage')
    publish_stage(context, 'reviewer-stage')

    result = delivery.overview(context.project.pk, context.client)

    stages = result['scopes'][0]['phases'][0]['stages']
    assert [item['requirements'][0]['key'] for item in stages] == ['create-record', 'check-record']
    assert stages[1]['requirements'][0]['guide']['dependencies'] == 'Complete operator-stage before reviewer-stage; use the same test record.'
    assert Requirement.objects.filter(key__in=['create-record', 'check-record']).count() == 2


@pytest.mark.parametrize('stage_key,role,blocked_action,blocked_result', [
    ('operator-stage', 'Operator', 'Cannot open the review screen.', 'Access is denied.'),
    ('reviewer-stage', 'Reviewer', 'Cannot create records.', 'The create action is unavailable.'),
])
def test_client_role_guide_keeps_blocked_case(context, stage_key, role, blocked_action, blocked_result):
    """Fails if the public guide loses the product role or its denied-access verification."""
    prepared = prepare_roles(context)
    apply(context, role_payload(prepared))
    stage = publish_stage(context, stage_key)

    result = delivery.overview(context.project.pk, context.client)

    published = next(item for item in result['scopes'][0]['phases'][0]['stages'] if item['id'] == stage.pk)
    guide = published['requirements'][0]['guide']
    assert guide['role'] == role
    assert guide['blocked_actions'] == blocked_action
    assert guide['blocked_result'] == blocked_result
    assert len(guide['blocked_steps']) == 1


def test_sources_without_product_roles_publish_without_inventing_client_role(context):
    """Fails if a role-free contract produces a guessed Platform client role or cannot publish."""
    prepared = prepare_prompt(context)
    payload = guides_payload(prepared)
    apply(context, payload)

    stage = publish_stage(context, 'etapa-1')
    result = delivery.overview(context.project.pk, context.client)

    published = result['scopes'][0]['phases'][0]['stages'][0]
    assert published['id'] == stage.pk
    assert 'role' not in prepared['template']['scopes'][0]['phases'][0]['stages'][0]['requirements'][0]['guide']
    assert 'role' not in published['requirements'][0]['guide']
    assert published['requirements'][0]['guide']['blocked_steps'] == []


@pytest.mark.parametrize(('field', 'missing_value'), [
    ('access', ''),
    ('allowed_actions', ''),
    ('blocked_actions', ''),
    ('blocked_steps', []),
    ('blocked_result', ''),
])
def test_publish_rejects_sourced_role_guide_missing_access_case(
    context, field, missing_value,
):
    """Fails if publishing accepts a sourced role guide without one access-case field."""
    prepared = prepare_roles(context)
    payload = role_payload(prepared)
    payload['scopes'][0]['phases'][0]['stages'][0]['requirements'][0]['guide'][field] = missing_value
    apply(context, payload)
    stage = DeliveryStage.objects.get(key='operator-stage')
    requirement = stage.requirements.get()
    before = (
        stage.editorial_status,
        stage.version,
        requirement.review_status,
        requirement.version,
        DeliveryPublication.objects.count(),
        version(context),
    )

    with pytest.raises(ValidationError, match='Completa') as caught:
        publish_stage(context, 'operator-stage')

    stage.refresh_from_db()
    requirement.refresh_from_db()
    assert str(caught.value.detail['code']) == 'guide_incomplete'
    assert (
        stage.editorial_status,
        stage.version,
        requirement.review_status,
        requirement.version,
        DeliveryPublication.objects.count(),
        version(context),
    ) == before


@pytest.mark.parametrize('role', ['Cliente', 'Platform administrator'])
def test_cited_import_rejects_unsourced_product_role(context, role):
    """Fails if Platform profiles can be asserted as product roles without captured evidence."""
    prepared = prepare_prompt(context)
    payload = guides_payload(prepared)
    guide_leaf(payload)['guide']['role'] = role

    with pytest.raises(ValidationError, match='rol del producto'):
        apply(context, payload)

    assert Requirement.objects.count() == 2
    assert version(context) == 0


def test_role_grouping_rejects_duplicated_requirement_identity(context):
    """Fails if assigning one requirement to multiple roles duplicates the agreed scope."""
    prepared = prepare_roles(context)
    payload = role_payload(prepared)
    payload['scopes'][0]['phases'][0]['stages'][1]['requirements'][0]['key'] = 'create-record'

    with pytest.raises(ValidationError, match='No dupliques'):
        apply(context, payload)

    assert Requirement.objects.count() == 2
    assert version(context) == 0


def test_manual_v1_keeps_legacy_role_wording(context):
    """Fails if enforcing sourced generation prevents compatible manual JSON v1 authoring."""
    prepared = prepare_prompt(context)
    payload = manual_payload(prepared)
    guide_leaf(payload)['guide']['role'] = 'Existing manual role'

    apply(context, payload)

    assert Requirement.objects.get(key='validacion-1').guide['role'] == 'Existing manual role'


def test_approved_product_role_guide_cannot_be_reassigned(context):
    """Fails if a fully approved role guide can be rewritten while preparing another role grouping."""
    prepared = prepare_roles(context)
    apply(context, role_payload(prepared))
    stage = publish_stage(context, 'operator-stage')
    requirement = stage.requirements.get()
    delivery.review_stage(context.project.pk, context.client, stage.pk, {
        'expected_version': version(context), 'request_id': 'approve-product-role',
        'decisions': [{'requirement_id': requirement.pk, 'version': requirement.version, 'decision': 'approved'}],
    })

    with pytest.raises(ValidationError, match='aprobado'):
        delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
            'expected_version': version(context), 'guide': {'role': 'Reviewer'},
        }, requirement.pk)

    requirement.refresh_from_db()
    assert requirement.review_status == 'approved'
    assert requirement.guide['role'] == 'Operator'
