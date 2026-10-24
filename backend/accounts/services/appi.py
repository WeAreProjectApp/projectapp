"""Private, expiring conversations and asynchronous, quota-bound Appi turns."""
import re
import unicodedata
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from accounts.models_appi import AppiConversation, AppiTurn
from accounts.models_ai import PlatformAISettings
from accounts.services import appi_answers, appi_cache, appi_jev, appi_sources
from accounts.services.appi_catalog import routing_options
from accounts.services.platform_ai import AIConflict, cache_version, configuration, require_ai_feature
from accounts.services.platform_ai_quota import consume, redeem_chat_audio, refund, reserve, snapshot as quota_snapshot

RETENTION = timedelta(days=90)


def require_appi(actor, project_id=None):
    project = require_ai_feature(actor, 'chatbot', project_id, require_project=False)
    if project is not None and project.client_id != actor.pk:
        raise NotFound('Proyecto no disponible.')
    return project


def _conversations(actor):
    return AppiConversation.objects.filter(actor=actor, expires_at__gt=timezone.now()).filter(Q(project__isnull=True) | Q(project__client_id=actor.pk))


def conversation_for(actor, conversation_id):
    require_appi(actor)
    item = _conversations(actor).filter(pk=conversation_id).first()
    if not item:
        raise NotFound('Conversación no disponible.')
    require_appi(actor, item.project_id)
    return item


def conversation_data(item):
    return {'id': str(item.pk), 'project_id': item.project_id, 'language': item.language,
            'title': item.title, 'created_at': item.created_at.isoformat(), 'expires_at': item.expires_at.isoformat()}


def create_conversation(actor, values):
    require_appi(actor, values.get('project_id'))
    return AppiConversation.objects.create(actor=actor, project_id=values.get('project_id'), language=values['language'], expires_at=timezone.now() + RETENTION)


def list_conversations(actor):
    require_appi(actor)
    AppiConversation.objects.filter(actor=actor, expires_at__lte=timezone.now()).delete()
    return [conversation_data(item) for item in _conversations(actor)[:50]]


def _normal(question):
    return ' '.join(unicodedata.normalize('NFKC', question).casefold().split())


def _context(conversation, question):
    # Explicit questions reuse across conversations; follow-ups stay bound to a
    # previous typed selection. A whole transcript is never sent to a provider.
    if not re.search(r'\b(eso|esto|esa|ese|anterior|ellos|ellas|it|its|them|that|previous)\b', _normal(question)):
        return {}
    previous = conversation.turns.filter(status='ready').order_by('-created_at', '-id').first()
    return previous.query if previous else {}


def _valid_query(query):
    return isinstance(query, dict) and query.get('scenario') in routing_options() and query.get('topic', 'general') in appi_jev.CONTRACT_TOPICS


def _cached(actor, conversation, exact_key, config, version):
    if not config.chatbot_cache_enabled:
        return None
    hot = appi_cache.lookup(actor, conversation.project_id, 'exact', exact_key, config, version)
    if hot and hot.exact_key == exact_key:
        return hot
    return AppiTurn.objects.filter(actor=actor, conversation__project_id=conversation.project_id,
        conversation__expires_at__gt=timezone.now(), exact_key=exact_key, status='ready', expires_at__gt=timezone.now()).order_by('-created_at').first()


@transaction.atomic
def submit(actor, conversation_id, values):
    conversation = conversation_for(actor, conversation_id)
    # Match the shared quota lock order; concurrent conversations and audio
    # cannot bypass the per-client active-turn boundary.
    settings_row, _ = PlatformAISettings.objects.get_or_create(pk=1)
    PlatformAISettings.objects.select_for_update().get(pk=settings_row.pk)
    conversation = AppiConversation.objects.select_for_update().get(pk=conversation.pk)
    fingerprint = appi_sources.digest({'conversation': str(conversation.pk), 'question': values['question'], 'transcription': str(values.get('transcription_id') or '')})
    previous = AppiTurn.objects.filter(actor=actor, request_id=values['request_id']).first()
    if previous and previous.request_fingerprint != fingerprint:
        raise AIConflict('El identificador ya pertenece a otra consulta.')
    if previous and previous.status != 'failed':
        return previous
    if AppiTurn.objects.filter(actor=actor, status__in=['pending', 'processing']).exists():
        raise AIConflict('Espera a que termine la consulta actual.')
    context = _context(conversation, values['question'])
    exact_key = appi_sources.digest({'question': _normal(values['question']), 'project': conversation.project_id,
                                    'language': conversation.language, 'context': context, 'policy': appi_jev.POLICY_VERSION})
    if values.get('transcription_id'):
        quota = redeem_chat_audio(actor, values['transcription_id'], values['request_id'], project_id=conversation.project_id)
    else:
        quota = reserve(actor, values['request_id'], 'chatbot', fingerprint)
    fields = {'question': values['question'], 'language': conversation.language, 'request_fingerprint': fingerprint,
              'exact_key': exact_key, 'context_key': appi_sources.digest(context), 'query': {'context': context},
              'quota_id': quota.pk, 'expires_at': conversation.expires_at, 'status': 'pending', 'answer': {}}
    if previous:
        for key, value in fields.items():
            setattr(previous, key, value)
        previous.created_at = timezone.now()
        previous.save()
        turn = previous
    else:
        turn = AppiTurn.objects.create(conversation=conversation, actor=actor, request_id=values['request_id'], **fields)
    if not conversation.title:
        conversation.title = values['question'][:100]
        conversation.save(update_fields=['title'])
    from accounts.tasks_appi import process_appi_turn
    transaction.on_commit(lambda: process_appi_turn(str(turn.pk)))
    return turn


def _semantic_cached(actor, turn, query, dependency, config, version):
    if not config.chatbot_cache_enabled:
        return None
    hot = appi_cache.lookup(actor, turn.conversation.project_id, 'typed', dependency, config, version)
    if hot and hot.dependencies == dependency and hot.query == query:
        return hot
    # Exact typed parameters: never nearest-neighbour prose matching.
    candidates = AppiTurn.objects.filter(actor=actor, conversation__project_id=turn.conversation.project_id,
        status='ready', dependencies=dependency, expires_at__gt=timezone.now()).exclude(pk=turn.pk).order_by('-created_at')[:10]
    return next((item for item in candidates if item.query == query), None)


def process(turn_id):
    with transaction.atomic():
        turn = AppiTurn.objects.select_for_update().select_related('conversation', 'actor').filter(pk=turn_id, status='pending').first()
        if not turn:
            return
        turn.status = 'processing'
        turn.save(update_fields=['status'])
    try:
        actor, conversation = turn.actor, turn.conversation
        project = require_appi(actor, conversation.project_id)
        if turn.expires_at <= timezone.now():
            raise NotFound('La conversación expiró.')
        context = turn.query.get('context', {})
        config = configuration()
        token = cache_version('chatbot', config)
        cached = _cached(actor, conversation, turn.exact_key, config, token)
        query = cached.query if cached and _valid_query(cached.query) else appi_jev.classify(actor, project, turn.question, context)
        data = appi_sources.snapshot(actor, conversation.project_id, query, turn.language)
        if not cached and data['candidates'] and query['scenario'] in ('bugs', 'phase_status', 'deliverables', 'contract_clause'):
            selection = appi_jev.select_entity(actor, project, turn.question, data['candidates'], previous=context.get('entity_id'))
            if selection == 'uncertain':
                query = {'scenario': 'clarification', 'topic': 'general', 'explain': False}
            elif selection and selection != 'all':
                query['entity_id'] = selection
            data = appi_sources.snapshot(actor, conversation.project_id, query, turn.language)
        dependency = appi_answers.dependencies(query, data, turn.language, config=config, cache_token=token)
        if cached and cached.dependencies != dependency:
            cached = None
        cached = cached or _semantic_cached(actor, turn, query, dependency, config, token)
        response = {**cached.answer, 'provenance': 'cache'} if cached else appi_answers.answer(actor, project, turn.question, query, data, turn.language, config=config)
        # Reauthorization covers switch changes and transfers during provider I/O.
        require_appi(actor, conversation.project_id)
        fresh = appi_sources.snapshot(actor, conversation.project_id, query, turn.language)
        fresh_config = configuration()
        fresh_token = cache_version('chatbot', fresh_config)
        current_dependency = appi_answers.dependencies(query, fresh, turn.language, config=fresh_config, cache_token=fresh_token)
        if current_dependency != dependency:
            response = appi_answers.template_answer(query, fresh, turn.language)
        now = timezone.now()
        response.update(verified_at=now.isoformat(), project_ids=fresh['project_ids'])
        with transaction.atomic():
            persisted = AppiTurn.objects.select_for_update().filter(pk=turn.pk, status='processing', conversation__actor=actor).first()
            if persisted is None:
                refund(turn.quota_id)
                return
            persisted.query, persisted.answer, persisted.dependencies = query, response, current_dependency
            persisted.status, persisted.verified_at = 'ready', now
            persisted.save(update_fields=['query', 'answer', 'dependencies', 'status', 'verified_at'])
            consume(turn.quota_id)
        appi_cache.remember(persisted, fresh_config, actor=actor, project_id=conversation.project_id, version=fresh_token)
    except Exception:
        AppiTurn.objects.filter(pk=turn.pk, status='processing').update(status='failed', query={}, answer={})
        refund(turn.quota_id)
        raise


def turn_data(actor, turn, *, memo=None):
    base = {'id': str(turn.pk), 'request_id': str(turn.request_id), 'question': turn.question, 'status': turn.status,
            'created_at': turn.created_at.isoformat(), 'answer': None, 'freshness': 'unavailable'}
    if turn.status != 'ready':
        return base
    if not _valid_query(turn.query):
        return {**base, 'question': '', 'status': 'unavailable'}
    memo = memo if memo is not None else {}
    membership = ('projects', turn.conversation.project_id)
    if membership not in memo:
        memo[membership] = {project.pk for project in appi_sources.projects_for(actor, turn.conversation.project_id)}
    current_ids = memo[membership]
    if not set(turn.answer.get('project_ids', [])).issubset(current_ids):
        return {**base, 'question': '', 'status': 'unavailable'}
    key = appi_sources.digest({'project': turn.conversation.project_id, 'query': turn.query, 'language': turn.language})
    if key not in memo:
        try:
            if 'policy' not in memo:
                config = configuration()
                memo['policy'] = (config, cache_version('chatbot', config))
            current = appi_sources.snapshot(actor, turn.conversation.project_id, turn.query, turn.language, freshness_only=True)
            config, token = memo['policy']
            memo[key] = appi_answers.dependencies(turn.query, current, turn.language, config=config, cache_token=token)
            memo[('guide_available', key)] = current.get('guide_available', True)
        except APIException:
            memo[key] = None
    if memo[key] is None or (not memo.get(('guide_available', key), True) and turn.answer.get('actions')):
        return {**base, 'question': '', 'status': 'unavailable'}
    return {**base, 'answer': turn.answer, 'freshness': 'current' if memo[key] == turn.dependencies else 'stale'}


def detail(actor, conversation_id, before=None):
    conversation = conversation_for(actor, conversation_id)
    queryset = conversation.turns.filter(expires_at__gt=timezone.now()).order_by('-created_at', '-id')
    if before:
        boundary = conversation.turns.filter(pk=before).first()
        if boundary is None:
            raise NotFound('Página no disponible.')
        queryset = queryset.filter(Q(created_at__lt=boundary.created_at) | Q(created_at=boundary.created_at, id__lt=boundary.pk))
    page = list(queryset[:21])
    rows = page[:20]
    memo = {}
    return {'conversation': conversation_data(conversation), 'messages': [turn_data(actor, item, memo=memo) for item in reversed(rows)],
            'next_before': str(rows[-1].pk) if len(page) > 20 else None, 'quota': quota_snapshot(actor)}


def message(actor, conversation_id, turn_id):
    conversation = conversation_for(actor, conversation_id)
    turn = conversation.turns.filter(pk=turn_id, expires_at__gt=timezone.now()).first()
    if turn is None:
        raise NotFound('Consulta no disponible.')
    return {**turn_data(actor, turn), 'quota': quota_snapshot(actor)}


def delete_conversation(actor, conversation_id):
    item = conversation_for(actor, conversation_id)
    for quota_id in item.turns.filter(status__in=['pending', 'processing']).values_list('quota_id', flat=True):
        refund(quota_id)
    item.delete()


def cleanup():
    cutoff = timezone.now() - timedelta(minutes=5)
    for turn in AppiTurn.objects.filter(status__in=['pending', 'processing'], created_at__lt=cutoff).iterator():
        with transaction.atomic():
            if AppiTurn.objects.filter(pk=turn.pk, status__in=['pending', 'processing']).update(status='failed', query={}, answer={}):
                refund(turn.quota_id)
    AppiConversation.objects.filter(expires_at__lte=timezone.now()).delete()
