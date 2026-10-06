"""Own seed/reset helpers; never grant client access automatically."""
from content.fake_data import ensure_fake_data_allowed
from django.db.models import Q

from accounts.models_project_client_access import (
    ProjectClientAccessEvent, ProjectClientAccessPolicy,
)
from accounts.models_project_ideas import (
    ProjectIdea, ProjectIdeaCollection, ProjectIdeaCollectionItem,
)
from accounts.services import project_idea_collections as collections, project_ideas as ideas


def seed_project_collaboration(project, context, actor):
    ensure_fake_data_allowed('seed_project_collaboration')
    if not project.client.is_active:
        return
    request_id = context.uuid(f'project:{project.pk}:client-idea')
    suggestion = ideas.create_idea(project.pk, project.client, {
        'text': 'Evaluar un tablero adicional en un contrato futuro.', 'request_id': str(request_id)})
    ProjectClientAccessPolicy.objects.get_or_create(project=project)
    if not actor or not actor.is_active or not actor.is_staff:
        return
    team = ideas.create_idea(project.pk, actor, {
        'text': 'Revisar alternativas antes de definir un nuevo contrato.',
        'request_id': str(context.uuid(f'project:{project.pk}:team-idea'))}, channel='panel')
    if team['revision_number'] == 1:
        team = ideas.edit_idea(project.pk, actor, team['id'], {
            'text': 'Comparar alternativas con el cliente antes de definir un contrato futuro.',
            'expected_version': team['version']}, channel='panel')
    if not team['archived']:
        ideas.archive_idea(project.pk, actor, team['id'], {'expected_version': team['version']}, channel='panel')
    collection_request = context.uuid(f'project:{project.pk}:idea-collection')
    if ProjectIdeaCollection.objects.filter(project=project, request_id=collection_request).exists():
        return
    collections.create_collection(project.pk, actor, {
        'title': 'Ideas conservadas para evaluación futura',
        'request_id': str(collection_request),
        'items': [{'idea_id': suggestion['id'], 'expected_version': suggestion['version']}]}, channel='panel')


def clear_fake_project_collaboration(projects, *, retention_context_ids=()):
    ensure_fake_data_allowed('clear_fake_project_collaboration')
    owners = Q(project__in=projects) | Q(retention_context_id__in=retention_context_ids)
    collection_ids = list(ProjectIdeaCollection.objects.filter(owners).values_list('pk', flat=True))
    # Frozen items protect their original suggestions; clear these first.
    ProjectIdeaCollectionItem.objects.filter(collection_id__in=collection_ids).delete()
    ProjectIdeaCollection.objects.filter(pk__in=collection_ids).delete()
    ProjectIdea.objects.filter(owners).delete()
    ProjectClientAccessEvent.objects.filter(owners).delete()
    ProjectClientAccessPolicy.objects.filter(owners).delete()
