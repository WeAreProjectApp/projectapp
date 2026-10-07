"""Project data-model imports shared by REST and MCP, with a read-only preview."""
from accounts.models import ProjectDataModelEntity
from accounts.serializers import (
    ProjectDataModelEntitySerializer,
    ProjectDataModelUploadSerializer,
)
from accounts.services.delivery_access import (
    DeliveryConflict,
    project_for_actor,
    require_admin,
)
from accounts.services.platform_resource_operations import perform, workspace_version


def list_entities(project_id, actor):
    project = project_for_actor(project_id, actor)
    return list(ProjectDataModelEntitySerializer(ProjectDataModelEntity.objects.filter(project=project), many=True).data)


def template(project_id, actor):
    project_for_actor(project_id, actor)
    return {'entities': [{'name': 'ExampleEntity', 'description': 'Brief description of the entity',
                         'keyFields': 'id, name, created_at', 'relationship': '1:N with OtherEntity'}]}


def _validated(data):
    serializer = ProjectDataModelUploadSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def preview(project_id, actor, data, expected_version):
    require_admin(actor)
    project = project_for_actor(project_id, actor)
    values = _validated(data)
    version = workspace_version(project)
    if type(expected_version) is not int or expected_version != version:
        raise DeliveryConflict()
    return {'project_id': project.pk, 'version': version, 'client_id': project.client_id,
            'before': list_entities(project.pk, actor), 'after': values['entities']}


def import_entities(project_id, actor, data, **operation):
    require_admin(actor)
    values = _validated(data)

    def change(project):
        ProjectDataModelEntity.objects.filter(project=project).delete()
        ProjectDataModelEntity.objects.bulk_create([
            ProjectDataModelEntity(project=project, name=item['name'], description=item['description'],
                                   key_fields=item['keyFields'], relationship=item['relationship'])
            for item in values['entities']
        ])
        return list_entities(project.pk, actor)

    return perform(project_id, actor, 'data-model:import', values, change, **operation)
