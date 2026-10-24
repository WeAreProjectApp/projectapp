"""Whitelisted, client-readable projections. No provider sees ORM objects or secrets."""
import hashlib
import json
import unicodedata
from collections import Counter

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from redis.exceptions import RedisError
from rest_framework.exceptions import NotFound

from accounts.models import BugReport, ContractAmendment, Deliverable, Project, ProjectContract
from accounts.services.appi_catalog import CONTRACT_TOPICS, GUIDES
from accounts.services.platform_ai import ai_capabilities


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def text(language, es, en):
    return en if language == 'en' else es


def projects_for(actor, project_id=None):
    queryset = Project.objects.filter(client_id=actor.pk).select_related('current_state').order_by('id')
    if project_id is not None:
        queryset = queryset.filter(pk=project_id)
    rows = list(queryset)
    if project_id is not None and not rows:
        raise NotFound('Proyecto no disponible.')
    return rows


def _source(identifier, label, href, **metadata):
    return {'id': identifier, 'label': label, 'href': href, **metadata}


def _normalized(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(char))


def _contract_fragments(node, topic, *, extract=True):
    """Read the exact signed artifact; never fall back to live text after signing."""
    from accounts.services.delivery_contract_sources import approval_contract_source, signed_contract_source
    from accounts.services.delivery_source_extraction import extract_prompt_source

    doc = node.document if node.document_id else None
    if doc and (doc.project_id not in (None, node.project.pk) or doc.client_user_id not in (None, node.project.client_id)):
        return [], 'unavailable'
    source = signed_contract_source(node)
    if source is None and node.approval_file_id:
        source = approval_contract_source(node)
    if source is None and doc and doc.signed_at:
        return [], 'signed_source_missing'
    if source is not None:
        raw, filename, markdown, blocks = source['raw'], source.get('filename', 'signed-contract.pdf'), '', None
    else:
        original = doc or node.proposal_document
        if original is None:
            return [], 'unavailable'
        file = doc.generated_file if doc else original.file
        raw, filename, markdown, blocks = None, '', '', None
        if file:
            try:
                with file.open('rb') as stream:
                    raw = stream.read(15 * 1024 * 1024 + 1)
                filename = file.name
            except (OSError, ValueError):
                return [], 'unavailable'
        elif doc:
            markdown, blocks = doc.content_markdown, doc.content_json
    key = digest({'raw': hashlib.sha256(raw).hexdigest() if raw is not None else None, 'markdown': markdown, 'blocks': blocks})
    if not extract:
        return [], key
    cache_key = 'appi:contract:' + digest({'actor': node.project.client_id, 'project': node.project.pk, 'source': key})
    try:
        extracted = cache.get(cache_key)
    except (RedisError, OSError, ValueError, TypeError):
        extracted = None
    if extracted is None:
        extracted = extract_prompt_source(raw, filename, markdown, blocks)
        try:
            cache.set(cache_key, extracted, 3600)
        except (RedisError, OSError, ValueError, TypeError):
            pass
    terms = [_normalized(term) for term in CONTRACT_TOPICS.get(topic, ())]
    fragments = [item for item in extracted.get('fragments', []) if not terms or any(
        term in _normalized(item.get('locator', '') + ' ' + item.get('text', '')) for term in terms)]
    return fragments[:6], key


def _base(actor, project_id, language):
    projects = projects_for(actor, project_id)
    return projects, {
        'scope_label': projects[0].name if project_id else text(language, 'Mis proyectos', 'My projects'),
        'facts': [], 'sources': [], 'actions': [], 'candidates': [],
        'project_ids': [project.pk for project in projects], 'basis': {},
    }


def _fact(result, value):
    result['facts'].append({'id': f'f{len(result["facts"]) + 1}', 'text': value})


def _guide(actor, project_id, scenario, language, result, projects):
    from accounts.services.platform_help_targets import TARGETS

    key = scenario.removeprefix('guide_')
    target_key, _, es, _ = GUIDES[key]
    target = TARGETS[target_key]
    capabilities = ai_capabilities(actor)
    requires_project = '{scope_label}' in es
    available = not requires_project or project_id is not None
    if key == 'voice_report':
        available = available and capabilities['voice_reporting']['available']
    if key == 'access' and project_id:
        from accounts.services.project_client_access import can_view_client_access
        available = available and can_view_client_access(projects[0])
    route = target.get('route')
    if available and route:
        href = route.format(project_id=project_id)
        result['actions'] = [{'label': text(language, 'Abrir en la plataforma', 'Open in platform'), 'href': href, 'target_key': target_key}]
        result['sources'] = [_source('guide:' + key, text(language, 'Guía de uso de la plataforma', 'Platform usage guide'), href)]
    result['guide_available'] = available
    result['guide_requires_project'] = requires_project
    result['basis'] = {'target': target, 'available': available, 'project_ids': result['project_ids'],
                       'scope_label': result['scope_label']}
    return result


def _project_summary(result, projects, actor, language, *, health=False):
    counts = {row['project_id']: row['total'] for row in BugReport.objects.filter(
        project__client_id=actor.pk, project_id__in=result['project_ids'], is_archived=False,
        status__in=('reported', 'confirmed', 'fixing', 'qa'),
    ).values('project_id').annotate(total=Count('id'))}
    values = []
    today = timezone.localdate()
    for project in projects:
        row = {'id': project.pk, 'name': project.name, 'status': project.status_display, 'progress': project.progress,
               'start_date': project.start_date, 'estimated_end_date': project.estimated_end_date,
               'open_bugs': counts.get(project.pk, 0)}
        values.append(row)
        if len(result['facts']) >= 20:
            continue
        _fact(result, text(language,
            f'{project.name}: {row["status"]}. Avance registrado: {project.progress} %. Bugs abiertos: {row["open_bugs"]}.',
            f'{project.name}: {row["status"]}. Recorded progress: {project.progress}%. Open bugs: {row["open_bugs"]}.'))
        if project.estimated_end_date:
            _fact(result, text(language, f'Fecha estimada de {project.name}: {project.estimated_end_date.isoformat()}.',
                               f'Estimated date for {project.name}: {project.estimated_end_date.isoformat()}.'))
            if health and project.estimated_end_date < today and project.progress < 100:
                _fact(result, text(language, 'La fecha estimada ya pasó y el avance registrado es menor al 100 %.',
                                   'The estimated date has passed and recorded progress is below 100%.'))
        result['sources'].append(_source(f'project:{project.pk}', project.name, f'/platform/projects/{project.pk}'))
    result['basis'] = {'projects': values, 'total': len(projects)}
    if health:
        result['basis']['today'] = today
    result['total'] = len(projects)
    return result


def _bugs(result, actor, query, language):
    rows = list(BugReport.objects.filter(project__client_id=actor.pk, project_id__in=result['project_ids'], is_archived=False)
                .order_by('id').values('id', 'project_id', 'title', 'status', 'severity', 'description', 'updated_at'))
    result['candidates'] = [{'id': row['id'], 'title': row['title']} for row in rows]
    result['basis'] = {'bugs': rows}
    selected = [row for row in rows if str(row['id']) == str(query.get('entity_id'))] if query.get('entity_id') else rows
    counts = Counter(row['status'] for row in selected)
    _fact(result, text(language, f'Bugs registrados: {len(selected)}. Por estado: ', f'Recorded bugs: {len(selected)}. By status: ') +
          ', '.join(f'{dict(BugReport.STATUS_CHOICES).get(key, key)}: {value}' for key, value in sorted(counts.items())))
    for row in selected[:20]:
        _fact(result, f'#{row["id"]} {row["title"]} — {dict(BugReport.STATUS_CHOICES).get(row["status"], row["status"])} ({row["severity"]}).')
        if query.get('entity_id') and row['description']:
            _fact(result, row['description'][:4000])
        href = f'/platform/projects/{row["project_id"]}/bugs'
        result['sources'].append(_source(f'bug:{row["id"]}', row['title'], href))
    result['total'] = len(selected)
    return result


def _delivery(result, actor, project_id, query, language):
    if not project_id:
        result['needs_project'] = True
        result['basis'] = {'project_ids': result['project_ids']}
        return result
    from accounts.services.delivery_workflow import overview
    # Reuse the canonical client publication projection, never the administrative tree.
    workspace = overview(project_id, actor)
    phases = [phase for scope in workspace['scopes'] for phase in scope['phases']]
    rows = [{'id': phase['id'], 'title': phase['title'], 'status': phase['status'], 'stages': [
        {'id': stage['id'], 'title': stage['title'], 'status': stage['status'], 'publication_id': stage['publication_id'],
         'requirements': [{'id': item['id'], 'title': item['title'], 'status': item['review_status']} for item in stage['requirements']]}
        for stage in phase['stages']]} for phase in phases]
    result['candidates'] = [{'id': row['id'], 'title': row['title']} for row in rows]
    result['basis'] = {'phases': rows}
    selected = [row for row in rows if str(row['id']) == str(query.get('entity_id'))] if query.get('entity_id') else rows
    for row in selected[:20]:
        _fact(result, f'{row["title"]}: {row["status"]}.')
        for stage in row['stages'][:20]:
            pending = [item['title'] for item in stage['requirements'] if item['status'] != 'approved']
            _fact(result, text(language, f'Etapa {stage["title"]}: {stage["status"]}. Pendientes de aprobación: {len(pending)}.',
                               f'Stage {stage["title"]}: {stage["status"]}. Pending approval: {len(pending)}.'))
            if pending:
                _fact(result, ', '.join(pending[:20]))
    result['sources'] = [_source(f'delivery:{project_id}', text(language, 'Seguimiento publicado', 'Published delivery workspace'), f'/platform/projects/{project_id}/delivery')]
    result['total'] = len(selected)
    return result


def _deliverables(result, actor, query, language):
    rows = list(Deliverable.objects.filter(project__client_id=actor.pk, project_id__in=result['project_ids'], is_archived=False)
                .exclude(category__in=Deliverable.ADMIN_ONLY_CATEGORIES).order_by('id')
                .values('id', 'project_id', 'title', 'category', 'current_version', 'updated_at'))
    result['basis'] = {'deliverables': rows}
    result['candidates'] = [{'id': row['id'], 'title': row['title']} for row in rows]
    selected = [row for row in rows if str(row['id']) == str(query.get('entity_id'))] if query.get('entity_id') else rows
    for row in selected[:20]:
        _fact(result, f'{row["title"]} — v{row["current_version"]} ({row["category"]}).')
        result['sources'].append(_source(f'deliverable:{row["id"]}', row['title'], f'/platform/projects/{row["project_id"]}/deliverables/{row["id"]}'))
    result['total'] = len(selected)
    return result


def _contracts(result, actor, project_id, query, language, *, freshness_only=False):
    contracts = list(ProjectContract.objects.filter(project__client_id=actor.pk, project_id__in=result['project_ids'], client_visible=True)
                .select_related('project', 'document', 'proposal_document').prefetch_related('signature_evidence').order_by('id'))
    amendments = list(ContractAmendment.objects.filter(contract__in=contracts, client_visible=True)
        .select_related('contract__project', 'document', 'proposal_document').prefetch_related('signature_evidence').order_by('id'))
    rows = [(f'contract:{node.pk}', node) for node in contracts] + [(f'amendment:{node.pk}', node) for node in amendments]
    result['candidates'] = [{'id': key, 'title': node.title} for key, node in rows]
    result['basis'] = {'contracts': [{'id': key, 'title': node.title, 'version': node.version} for key, node in rows]}
    selected = [(key, node) for key, node in rows if key == str(query.get('entity_id'))] if query.get('entity_id') else rows
    for source_id, node in selected[:20]:
        href = f'/platform/projects/{node.project.pk}/delivery'
        evidence = next(iter(node.signature_evidence.all()), None)
        signed_at = evidence.signed_at if evidence else node.document.signed_at if node.document_id else None
        _fact(result, node.title + (text(language, ' — firmado: ', ' — signed: ') + signed_at.isoformat() if signed_at else text(language, ' — sin firma acreditada.', ' — no recorded signature.')))
        result['basis'].setdefault('signatures', []).append({'id': source_id, 'date': signed_at})
        result['sources'].append(_source(source_id, node.title, href))
        if query.get('topic', 'general') != 'general':
            fragments, fingerprint = _contract_fragments(node, query['topic'], extract=not freshness_only)
            result['basis'].setdefault('fragments', []).append({'id': source_id, 'fingerprint': fingerprint})
            for fragment in fragments:
                _fact(result, fragment.get('locator', '') + '\n' + fragment.get('text', '')[:2500])
            if not fragments:
                _fact(result, text(language, 'No hay un fragmento verificable de ese tema. Consulta la copia contractual o pregunta al equipo.',
                                   'No verifiable passage is available for this topic. Read the contractual copy or ask the team.'))
    result['total'] = len(selected)
    return result


def snapshot(actor, project_id, query, language, *, freshness_only=False):
    projects, result = _base(actor, project_id, language)
    scenario = query['scenario']
    if scenario.startswith('guide_'):
        return _guide(actor, project_id, scenario, language, result, projects)
    if scenario in ('out_of_scope', 'clarification'):
        result['basis'] = {'scenario': scenario}
        return result
    if not projects:
        result['needs_project'] = True
        result['basis'] = {'project_ids': []}
        return result
    if scenario in ('project_status', 'project_health'):
        _project_summary(result, projects, actor, language, health=scenario == 'project_health')
        if scenario == 'project_health' and project_id:
            delivery = _delivery({**result, 'facts': [], 'sources': [], 'basis': {}}, actor, project_id, {}, language)
            for item in delivery['facts']:
                _fact(result, item['text'])
            result['basis']['delivery'] = delivery['basis']
            result['sources'].extend(delivery['sources'])
    elif scenario == 'bugs':
        _bugs(result, actor, query, language)
    elif scenario == 'phase_status':
        _delivery(result, actor, project_id, query, language)
    elif scenario == 'deliverables':
        _deliverables(result, actor, query, language)
    elif scenario == 'contract_clause':
        _contracts(result, actor, project_id, query, language, freshness_only=freshness_only)
    if not result['facts'] and not result.get('needs_project'):
        _fact(result, text(language, 'No hay información publicada disponible para esta consulta.', 'No published information is available for this query.'))
    if result.get('total', 0) > 20:
        _fact(result, text(language, f'Se muestran hasta 20 elementos de {result["total"]}; abre las fuentes para consultar el listado completo.',
                           f'Showing up to 20 of {result["total"]} items; open the sources for the complete list.'))
    result['basis']['project_ids'] = result['project_ids']
    return result
