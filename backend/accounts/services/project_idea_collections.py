"""Internal, immutable copies for considering a future contract."""
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models_project_ideas import ProjectIdea, ProjectIdeaCollection, ProjectIdeaCollectionItem
from accounts.serializers_project_ideas import IdeaCollectionSerializer, validated
from accounts.services.project_collaboration_access import CollaborationConflict, actor_label, check_version, paginate, project_for_actor


def serialize_collection(collection, *, summary=False):
    result = {'id': collection.pk, 'project_id': collection.project_id, 'title': collection.title,
            'created_by': collection.creator_label, 'created_at': collection.created_at}
    if not summary:
        result['items'] = [{'idea_id': item.idea_id, 'revision_number': item.revision_number,
                       'source_version': item.source_version, 'text': item.text, 'author': item.author_label,
                       'created_at': item.idea_created_at} for item in collection.items.all()]
    result['item_count'] = collection.item_count if summary else len(result['items'])
    return result


def list_collections(project_id, actor, *, channel='platform', page=1):
    project = project_for_actor(project_id, actor, channel=channel, admin=True)
    return paginate(project.idea_collections.annotate(item_count=Count('items')).order_by('-created_at', '-pk'), page,
                    lambda collection: serialize_collection(collection, summary=True))


def get_collection(project_id, actor, collection_id, *, channel='platform'):
    project = project_for_actor(project_id, actor, channel=channel, admin=True)
    collection = project.idea_collections.prefetch_related('items').filter(pk=collection_id).first()
    if collection is None:
        raise NotFound('Recopilación no encontrada.')
    return serialize_collection(collection)


@transaction.atomic
def create_collection(project_id, actor, data, *, channel='platform'):
    project = project_for_actor(project_id, actor, channel=channel, admin=True, lock=True)
    values = validated(IdeaCollectionSerializer, data)
    previous = project.idea_collections.filter(created_by=actor, request_id=values['request_id']).first()
    if previous:
        selection = [(item.idea_id, item.source_version) for item in previous.items.all()]
        incoming = [(item['idea_id'], item['expected_version']) for item in values['items']]
        if previous.title != values['title'] or selection != incoming or previous.recipient_id != project.client_id:
            raise CollaborationConflict('Esta petición ya corresponde a otra recopilación.')
        return serialize_collection(previous)
    ideas = {idea.pk: idea for idea in ProjectIdea.objects.select_for_update().filter(
        project=project, recipient_id=project.client_id, pk__in=[item['idea_id'] for item in values['items']])}
    for selection in values['items']:
        idea = ideas.get(selection['idea_id'])
        if idea is None:
            raise NotFound('Una idea no pertenece al proyecto y cliente seleccionados.')
        check_version(idea, selection['expected_version'])
    snapshots = [{'idea_id': item['idea_id'], 'revision_number': ideas[item['idea_id']].revision_number,
                  'source_version': item['expected_version'], 'text': ideas[item['idea_id']].text,
                  'author': ideas[item['idea_id']].author_label, 'created_at': ideas[item['idea_id']].created_at}
                 for item in values['items']]
    size = len(json.dumps({'title': values['title'], 'items': snapshots}, cls=DjangoJSONEncoder,
                          ensure_ascii=False).encode('utf-8'))
    if size > 190_000:
        raise ValidationError({'items': 'La recopilación es demasiado extensa. Divide la selección en varias recopilaciones.'})
    collection = ProjectIdeaCollection.objects.create(project=project, recipient=project.client,
        title=values['title'], created_by=actor, creator_label=actor_label(actor, team=True), request_id=values['request_id'])
    ProjectIdeaCollectionItem.objects.bulk_create([
        ProjectIdeaCollectionItem(collection=collection, idea=ideas[item['idea_id']],
            revision_number=ideas[item['idea_id']].revision_number, source_version=item['expected_version'], position=position,
            text=ideas[item['idea_id']].text, author_label=ideas[item['idea_id']].author_label,
            idea_created_at=ideas[item['idea_id']].created_at)
        for position, item in enumerate(values['items'])])
    return serialize_collection(collection)
