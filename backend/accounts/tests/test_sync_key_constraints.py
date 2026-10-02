from dataclasses import dataclass

import pytest
from django.db import IntegrityError, transaction

from accounts.models import (
    DataModelEntity,
    Deliverable,
    Project,
    ProjectPhase,
    SavedFilterTab,
)
from content.models.business_proposal import BusinessProposal


@dataclass(frozen=True)
class ConstraintCase:
    create: object
    first_scope: object
    second_scope: object


def _projects(client_user):
    return (
        Project.objects.create(name='Constraint project A', client=client_user),
        Project.objects.create(name='Constraint project B', client=client_user),
    )


def _phase(project, suffix):
    proposal = BusinessProposal.objects.create(
        title=f'Constraint proposal {suffix}',
        client_name='Constraint client',
    )
    return ProjectPhase.objects.create(
        project=project,
        business_proposal=proposal,
        order=1,
    )


def _deliverable_case(admin_user, client_user):
    project_a, project_b = _projects(client_user)
    return ConstraintCase(
        create=lambda scope, key: Deliverable.objects.create(
            project=scope,
            title='Constraint deliverable',
            uploaded_by=admin_user,
            source_epic_key=key,
        ),
        first_scope=project_a,
        second_scope=project_b,
    )


def _data_model_entity_case(admin_user, client_user):
    project_a, project_b = _projects(client_user)
    deliverable_a = Deliverable.objects.create(
        project=project_a,
        title='Constraint deliverable A',
        uploaded_by=admin_user,
    )
    deliverable_b = Deliverable.objects.create(
        project=project_b,
        title='Constraint deliverable B',
        uploaded_by=admin_user,
    )
    return ConstraintCase(
        create=lambda scope, key: DataModelEntity.objects.create(
            deliverable=scope,
            name='Constraint entity',
            source_entity_name=key,
        ),
        first_scope=deliverable_a,
        second_scope=deliverable_b,
    )


def _saved_filter_tab_case(admin_user, client_user):
    return ConstraintCase(
        create=lambda scope, key: SavedFilterTab.objects.create(
            user=scope[0],
            view=scope[1],
            name='Constraint tab',
            builtin_key=key,
        ),
        first_scope=(admin_user, SavedFilterTab.VIEW_PROPOSAL),
        second_scope=(admin_user, SavedFilterTab.VIEW_CLIENT),
    )


@pytest.fixture(
    params=(
        _deliverable_case,
        _data_model_entity_case,
        _saved_filter_tab_case,
    ),
    ids=('deliverable', 'data-model-entity', 'saved-filter-tab'),
)
def constraint_case(request, admin_user, client_user):
    return request.param(admin_user, client_user)


@pytest.mark.django_db
def test_non_blank_sync_key_is_unique_within_scope(constraint_case):
    constraint_case.create(constraint_case.first_scope, 'stable-key')

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            constraint_case.create(constraint_case.first_scope, 'stable-key')


@pytest.mark.django_db
def test_non_blank_sync_key_can_repeat_across_scopes(constraint_case):
    first = constraint_case.create(constraint_case.first_scope, 'stable-key')
    second = constraint_case.create(constraint_case.second_scope, 'stable-key')

    assert first.pk != second.pk


@pytest.mark.django_db
def test_blank_sync_key_can_repeat_within_scope(constraint_case):
    first = constraint_case.create(constraint_case.first_scope, '')
    second = constraint_case.create(constraint_case.first_scope, '')

    assert first.pk != second.pk
