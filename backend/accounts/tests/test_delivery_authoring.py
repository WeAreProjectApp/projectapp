"""Only valid, project-owned draft JSON can cross the import boundary."""
import copy

import pytest
from django.contrib.auth.models import User
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import DeliveryScope, Project, ProjectContract, Requirement
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import GUIDE, build_delivery_context, prepare_prompt, publish, version
from content.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    return build_delivery_context()


def payload(context):
    return {'schema_version': 1, 'scopes': [{
        'key': 'new-scope', 'title': 'Ampliación', 'contract_id': context.contract.pk,
        'phases': [{'key': 'new-phase', 'title': 'Fase adicional', 'stages': [{
            'key': 'new-stage', 'title': 'Etapa nueva', 'requirements': [{
                'key': 'new-guide', 'title': 'Validación nueva', 'guide': GUIDE,
            }],
        }]}],
    }]}


def test_preview_does_not_create_draft_rows(context):
    count = Requirement.objects.count()

    response = delivery.import_payload(context.project.pk, context.admin, payload(context), 0)

    assert response['valid'] is True
    assert response['summary']['requirements'] == 1
    assert Requirement.objects.count() == count


def test_apply_creates_an_ordered_draft_tree(context):
    response = delivery.import_payload(context.project.pk, context.admin, payload(context), 0, apply=True, request_id='import')

    requirement = Requirement.objects.get(key='new-guide')
    assert requirement.stage.phase.scope.contract_id == context.contract.pk
    assert requirement.review_status == 'pending'
    assert requirement.stage.editorial_status == 'draft'
    assert response['version'] == 1


def test_repeated_apply_keeps_one_tree(context):
    data = payload(context)
    first = delivery.import_payload(context.project.pk, context.admin, data, 0, apply=True, request_id='import')

    second = delivery.import_payload(context.project.pk, context.admin, data, 0, apply=True, request_id='import')

    assert first == second
    assert Requirement.objects.filter(key='new-guide').count() == 1


def test_authoring_prompt_includes_human_contract_context(context):
    response = prepare_prompt(context)

    assert 'Alcance acordado.' in response['prompt']
    assert response['schema']['properties']['schema_version']['const'] == 2
    assert response['schema']['additionalProperties'] is False


def test_import_cannot_inject_review_state(context):
    data = payload(context)
    data['scopes'][0]['phases'][0]['stages'][0]['requirements'][0]['review_status'] = 'approved'

    with pytest.raises(ValidationError, match='campos no permitidos'):
        delivery.import_payload(context.project.pk, context.admin, data, 0, apply=True, request_id='bad-import')

    assert not Requirement.objects.filter(key='new-guide').exists()


def test_import_rejects_boolean_schema_version(context):
    data = payload(context)
    data['schema_version'] = True

    with pytest.raises(ValidationError, match='schema_version'):
        delivery.import_payload(context.project.pk, context.admin, data, 0)


def test_import_rejects_non_string_identifier(context):
    data = payload(context)
    data['scopes'][0]['key'] = {'nested': 'invalid'}

    with pytest.raises(ValidationError):
        delivery.import_payload(context.project.pk, context.admin, data, 0)


def test_import_rejects_duplicate_sibling_identifiers(context):
    data = payload(context)
    data['scopes'].append(copy.deepcopy(data['scopes'][0]))

    with pytest.raises(ValidationError, match='duplicados'):
        delivery.import_payload(context.project.pk, context.admin, data, 0)


def test_import_rolls_back_a_foreign_contract(context):
    other_user = User.objects.create_user('foreign-client', 'foreign@example.test')
    other_project = Project.objects.create(client=other_user, name='Foreign project')
    document = Document.objects.create(project=other_project, client_user=other_user, title='Foreign contract')
    contract = ProjectContract.objects.create(project=other_project, key='foreign', title='Foreign', document=document)
    data = payload(context)
    foreign_scope = copy.deepcopy(data['scopes'][0])
    foreign_scope.update(key='foreign-scope', contract_id=contract.pk)
    data['scopes'].append(foreign_scope)

    with pytest.raises(NotFound):
        delivery.import_payload(context.project.pk, context.admin, data, 0, apply=True, request_id='cross-project')

    assert not DeliveryScope.objects.filter(key='new-scope').exists()


def test_import_cannot_replace_a_published_scope(context):
    publish(context)
    data = payload(context)
    data['scopes'][0]['key'] = context.scope.key

    with pytest.raises(ValidationError, match='borradores sin publicar'):
        delivery.import_payload(context.project.pk, context.admin, data, version(context))


def test_client_cannot_import_guides(context):
    with pytest.raises(PermissionDenied):
        delivery.import_payload(context.project.pk, context.client, payload(context), 0)


def test_signed_contract_identity_is_frozen_before_first_publication(context):
    with pytest.raises(ValidationError, match='identidad'):
        delivery.mutate_node(context.project.pk, context.admin, 'contracts',
                             {'expected_version': 0, 'key': 'replacement'}, context.contract.pk)

    context.contract.refresh_from_db()
    assert context.contract.key == 'contrato'
