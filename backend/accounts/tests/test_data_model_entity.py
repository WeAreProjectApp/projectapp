"""
Tests for DataModelEntity and ProjectDataModelEntity models and their serializers.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from accounts.models import (
    DataModelEntity,
    Deliverable,
    Project,
    ProjectDataModelEntity,
    UserProfile,
)
from accounts.serializers import (
    DataModelEntitySerializer,
    ProjectDataModelEntitySerializer,
    ProjectDataModelEntityItemSerializer,
    ProjectDataModelUploadSerializer,
)

User = get_user_model()


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def admin_user():
    user = User.objects.create_user(
        username='admin@dme.com', email='admin@dme.com', password='pass',
    )
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True)
    return user


@pytest.fixture
def client_user(admin_user):
    user = User.objects.create_user(
        username='client@dme.com', email='client@dme.com', password='pass',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT,
        is_onboarded=True, created_by=admin_user,
    )
    return user


@pytest.fixture
def project(client_user):
    return Project.objects.create(name='Test Project', client=client_user)


@pytest.fixture
def deliverable(project, admin_user):
    return Deliverable.objects.create(
        project=project,
        title='Test Deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        file=None,
        uploaded_by=admin_user,
    )


# =========================================================================
# 1A — DataModelEntity model tests
# =========================================================================


@pytest.mark.django_db
class TestDataModelEntityModel:
    def test_create_with_required_fields(self, deliverable):
        entity = DataModelEntity.objects.create(
            deliverable=deliverable,
            name='User',
        )

        assert entity.id is not None
        assert entity.name == 'User'
        assert entity.description == ''
        assert entity.key_fields == ''
        assert entity.source_entity_name == ''
        assert entity.synced_from_proposal is False
        assert entity.is_archived is False
        assert entity.archived_at is None

    def test_str_includes_name_and_deliverable_id(self, deliverable):
        entity = DataModelEntity.objects.create(
            deliverable=deliverable,
            name='Order',
        )

        assert str(entity) == f'Order (deliverable={deliverable.id})'

    def test_ordering_is_by_name_ascending(self, deliverable):
        DataModelEntity.objects.create(deliverable=deliverable, name='Zeta')
        DataModelEntity.objects.create(deliverable=deliverable, name='Alpha')
        DataModelEntity.objects.create(deliverable=deliverable, name='Milo')

        names = list(DataModelEntity.objects.filter(
            deliverable=deliverable,
        ).values_list('name', flat=True))
        assert names == ['Alpha', 'Milo', 'Zeta']

    def test_unique_constraint_blocks_duplicate_source_entity_name_per_deliverable(
        self, deliverable,
    ):
        DataModelEntity.objects.create(
            deliverable=deliverable,
            name='User',
            source_entity_name='User',
        )

        with pytest.raises(IntegrityError):
            DataModelEntity.objects.create(
                deliverable=deliverable,
                name='User',
                source_entity_name='User',
            )

    def test_blank_source_entity_name_allows_duplicates(self, deliverable):
        DataModelEntity.objects.create(
            deliverable=deliverable,
            name='Manual1',
            source_entity_name='',
        )
        DataModelEntity.objects.create(
            deliverable=deliverable,
            name='Manual2',
            source_entity_name='',
        )

        count = DataModelEntity.objects.filter(
            deliverable=deliverable,
            source_entity_name='',
        ).count()
        assert count == 2

    def test_same_source_entity_name_allowed_across_different_deliverables(
        self, project, admin_user,
    ):
        d1 = Deliverable.objects.create(
            project=project, title='D1',
            category=Deliverable.CATEGORY_DOCUMENTS,
            file=None, uploaded_by=admin_user,
        )
        d2 = Deliverable.objects.create(
            project=project, title='D2',
            category=Deliverable.CATEGORY_DOCUMENTS,
            file=None, uploaded_by=admin_user,
        )

        DataModelEntity.objects.create(
            deliverable=d1, name='User', source_entity_name='User',
        )
        DataModelEntity.objects.create(
            deliverable=d2, name='User', source_entity_name='User',
        )

        assert DataModelEntity.objects.filter(source_entity_name='User').count() == 2

    def test_soft_delete_sets_is_archived_and_archived_at(self, deliverable):
        entity = DataModelEntity.objects.create(
            deliverable=deliverable, name='OldEntity',
        )
        now = timezone.now()

        entity.is_archived = True
        entity.archived_at = now
        entity.save(update_fields=['is_archived', 'archived_at'])

        entity.refresh_from_db()
        assert entity.is_archived is True
        assert entity.archived_at == now

    def test_cascade_delete_removes_entities_when_deliverable_deleted(
        self, deliverable,
    ):
        entity = DataModelEntity.objects.create(
            deliverable=deliverable, name='Cascaded',
        )
        entity_id = entity.id

        deliverable.delete()

        assert not DataModelEntity.objects.filter(id=entity_id).exists()


# =========================================================================
# 1A — ProjectDataModelEntity model tests
# =========================================================================


@pytest.mark.django_db
class TestProjectDataModelEntityModel:
    def test_create_with_required_fields(self, project):
        entity = ProjectDataModelEntity.objects.create(
            project=project,
            name='Invoice',
        )

        assert entity.id is not None
        assert entity.name == 'Invoice'
        assert entity.description == ''
        assert entity.key_fields == ''
        assert entity.relationship == ''

    def test_str_includes_name_and_project_id(self, project):
        entity = ProjectDataModelEntity.objects.create(
            project=project, name='Payment',
        )

        assert str(entity) == f'Payment (project={project.id})'

    def test_ordering_is_by_name_ascending(self, project):
        ProjectDataModelEntity.objects.create(project=project, name='Zulu')
        ProjectDataModelEntity.objects.create(project=project, name='Alpha')

        names = list(
            ProjectDataModelEntity.objects.filter(project=project).values_list('name', flat=True)
        )
        assert names == ['Alpha', 'Zulu']

    def test_direct_project_delete_is_protected_by_project_entity(self, project):
        """Fails if a direct deletion cascades through project data definitions instead of requiring review."""
        entity = ProjectDataModelEntity.objects.create(
            project=project, name='WillBeGone',
        )

        with pytest.raises(ProtectedError) as error:
            project.delete()

        assert entity in error.value.protected_objects
        entity.refresh_from_db()
        assert entity.project_id == project.pk
        assert Project.objects.filter(pk=project.pk).exists()

    def test_relationship_field_stores_long_text(self, project):
        rel = '1:N with Order, M:N with Product'
        entity = ProjectDataModelEntity.objects.create(
            project=project, name='Cart', relationship=rel,
        )

        entity.refresh_from_db()
        assert entity.relationship == rel


# =========================================================================
# 1B — Serializer tests
# =========================================================================


@pytest.mark.django_db
class TestDataModelEntitySerializer:
    def test_serializer_exposes_expected_fields(self, deliverable):
        entity = DataModelEntity.objects.create(
            deliverable=deliverable,
            name='Customer',
            description='A customer entity',
            key_fields='id, email',
            source_entity_name='Customer',
            synced_from_proposal=True,
        )

        data = DataModelEntitySerializer(entity).data

        assert set(data.keys()) == {
            'id', 'name', 'description', 'key_fields',
            'source_entity_name', 'synced_from_proposal',
            'created_at', 'updated_at',
        }

    def test_serializer_does_not_expose_deliverable_id(self, deliverable):
        entity = DataModelEntity.objects.create(
            deliverable=deliverable, name='Hidden',
        )

        data = DataModelEntitySerializer(entity).data

        assert 'deliverable' not in data
        assert 'deliverable_id' not in data

    def test_serializer_does_not_expose_is_archived(self, deliverable):
        entity = DataModelEntity.objects.create(
            deliverable=deliverable, name='Archived',
            is_archived=True,
        )

        data = DataModelEntitySerializer(entity).data

        assert 'is_archived' not in data


@pytest.mark.django_db
class TestProjectDataModelEntitySerializer:
    def test_serializer_exposes_expected_fields(self, project):
        entity = ProjectDataModelEntity.objects.create(
            project=project,
            name='Order',
            description='An order entity',
            key_fields='id, total',
            relationship='1:N with Customer',
        )

        data = ProjectDataModelEntitySerializer(entity).data

        assert set(data.keys()) == {
            'id', 'name', 'description', 'key_fields',
            'relationship', 'created_at', 'updated_at',
        }

    def test_serializer_does_not_expose_project_id(self, project):
        entity = ProjectDataModelEntity.objects.create(
            project=project, name='Hidden',
        )

        data = ProjectDataModelEntitySerializer(entity).data

        assert 'project' not in data
        assert 'project_id' not in data


class TestProjectDataModelEntityItemSerializer:
    def test_valid_payload_with_name_only(self):
        serializer = ProjectDataModelEntityItemSerializer(data={'name': 'User'})

        assert serializer.is_valid()
        assert serializer.validated_data['name'] == 'User'
        assert serializer.validated_data['description'] == ''
        assert serializer.validated_data['keyFields'] == ''
        assert serializer.validated_data['relationship'] == ''

    def test_valid_payload_with_all_fields(self):
        payload = {
            'name': 'Product',
            'description': 'A product',
            'keyFields': 'id, sku',
            'relationship': '1:N with Order',
        }
        serializer = ProjectDataModelEntityItemSerializer(data=payload)

        assert serializer.is_valid()

    def test_missing_name_fails_validation(self):
        serializer = ProjectDataModelEntityItemSerializer(data={'description': 'no name'})

        assert not serializer.is_valid()
        assert 'name' in serializer.errors

    def test_name_required_rejects_blank(self):
        serializer = ProjectDataModelEntityItemSerializer(data={'name': ''})

        assert not serializer.is_valid()
        assert 'name' in serializer.errors


class TestProjectDataModelUploadSerializer:
    def test_valid_entities_list_passes(self):
        payload = {
            'entities': [
                {'name': 'User'},
                {'name': 'Product', 'keyFields': 'id, sku'},
            ],
        }
        serializer = ProjectDataModelUploadSerializer(data=payload)

        assert serializer.is_valid()
        assert len(serializer.validated_data['entities']) == 2

    def test_missing_entities_key_fails(self):
        serializer = ProjectDataModelUploadSerializer(data={})

        assert not serializer.is_valid()
        assert 'entities' in serializer.errors

    def test_entity_with_missing_name_fails(self):
        payload = {'entities': [{'description': 'no name here'}]}
        serializer = ProjectDataModelUploadSerializer(data=payload)

        assert not serializer.is_valid()

    def test_empty_entities_list_passes(self):
        serializer = ProjectDataModelUploadSerializer(data={'entities': []})

        assert serializer.is_valid()
        assert serializer.validated_data['entities'] == []
