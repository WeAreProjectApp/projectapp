"""Versioned suggestions without contractual side effects."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from accounts.models_project_ideas import ProjectIdea, ProjectIdeaRevision
from accounts.serializers_project_ideas import IdeaArchiveSerializer, IdeaCreateSerializer, IdeaEditSerializer, validated
from accounts.services.project_collaboration_access import CollaborationConflict, actor_label, check_version, is_admin, paginate, project_for_actor


def _ideas(project, actor, channel):
    qs = ProjectIdea.objects.filter(project=project)
    return qs if is_admin(actor, channel) else qs.filter(recipient_id=project.client_id)


def _idea(project, actor, idea_id, channel, *, lock=False):
    qs = _ideas(project, actor, channel)
    if lock:
        qs = qs.select_for_update()
    idea = qs.filter(pk=idea_id).first()
    if idea is None:
        raise NotFound('Idea no encontrada.')
    return idea


def serialize_idea(idea, actor, channel='platform'):
    editable = (idea.origin == 'team' and is_admin(actor, channel)) or (idea.origin == 'client' and idea.author_id == actor.pk and not is_admin(actor, channel))
    return {'id': idea.pk, 'project_id': idea.project_id, 'text': idea.text, 'author': idea.author_label,
            'origin': idea.origin, 'created_at': idea.created_at, 'updated_at': idea.updated_at,
            'revision_number': idea.revision_number, 'version': idea.version,
            'archived': idea.archived_at is not None, 'can_edit': bool(editable and not idea.archived_at)}


def list_ideas(project_id, actor, *, channel='platform', page=1):
    project = project_for_actor(project_id, actor, channel=channel)
    return paginate(_ideas(project, actor, channel), page, lambda idea: serialize_idea(idea, actor, channel))


def get_idea(project_id, actor, idea_id, *, channel='platform'):
    project = project_for_actor(project_id, actor, channel=channel)
    return serialize_idea(_idea(project, actor, idea_id, channel), actor, channel)


@transaction.atomic
def create_idea(project_id, actor, data, *, channel='platform'):
    project = project_for_actor(project_id, actor, channel=channel, lock=True)
    values = validated(IdeaCreateSerializer, data)
    existing = ProjectIdea.objects.filter(project=project, author=actor, request_id=values['request_id']).first()
    if existing:
        original = existing.revisions.get(number=1)
        if original.text != values['text'] or existing.recipient_id != project.client_id:
            raise CollaborationConflict('Esta petición ya corresponde a otra idea.')
        return serialize_idea(existing, actor, channel)
    team = is_admin(actor, channel)
    idea = ProjectIdea.objects.create(project=project, recipient=project.client, author=actor,
                                     author_label=actor_label(actor, team=team), origin='team' if team else 'client', **values)
    ProjectIdeaRevision.objects.create(idea=idea, number=1, text=idea.text, editor=actor, editor_label=idea.author_label)
    return serialize_idea(idea, actor, channel)


@transaction.atomic
def edit_idea(project_id, actor, idea_id, data, *, channel='platform'):
    project = project_for_actor(project_id, actor, channel=channel, lock=True)
    idea = _idea(project, actor, idea_id, channel, lock=True)
    values = validated(IdeaEditSerializer, data)
    if not serialize_idea(idea, actor, channel)['can_edit']:
        raise PermissionDenied('Solo puedes corregir una idea activa de tu autoría o del equipo.')
    check_version(idea, values['expected_version'])
    idea.text = values['text']
    idea.version += 1
    idea.revision_number += 1
    idea.save(update_fields=['text', 'version', 'revision_number', 'updated_at'])
    ProjectIdeaRevision.objects.create(idea=idea, number=idea.revision_number, text=idea.text,
                                      editor=actor, editor_label=actor_label(actor, team=is_admin(actor, channel)))
    return serialize_idea(idea, actor, channel)


@transaction.atomic
def archive_idea(project_id, actor, idea_id, data, *, restore=False, channel='platform'):
    project = project_for_actor(project_id, actor, channel=channel, admin=True, lock=True)
    idea = _idea(project, actor, idea_id, channel, lock=True)
    values = validated(IdeaArchiveSerializer, data)
    check_version(idea, values['expected_version'])
    idea.archived_at = None if restore else timezone.now()
    idea.archived_by = None if restore else actor
    idea.version += 1
    idea.save(update_fields=['archived_at', 'archived_by', 'version', 'updated_at'])
    return serialize_idea(idea, actor, channel)


def revisions(project_id, actor, idea_id, *, channel='platform', page=1):
    project = project_for_actor(project_id, actor, channel=channel)
    idea = _idea(project, actor, idea_id, channel)
    return paginate(idea.revisions.order_by('-number'), page, lambda revision: {
        'number': revision.number, 'text': revision.text, 'editor': revision.editor_label, 'created_at': revision.created_at})
