"""Proposal rules (PR*).

PR1 re-copies the client snapshot with ``sync_snapshot`` and PR7 renumbers
sections with the panel's ``bulk_update`` of ``order``. Project links (PR3,
PR5) are corrected by the proposal reassignment tools, which keep phases,
resources and approved files with their own preview.
"""
from collections import defaultdict
from decimal import Decimal

from content.services.data_integrity.catalog import register_fixer, rule
from content.services.data_integrity.fixes.base import Fixer, change
from content.services.data_integrity.hashing import normalized
from content.services.data_integrity.scope import PHASE, PROFILE, PROJECT, PROPOSAL, SECTION, client_label
from content.services.data_integrity.types import (
    EXISTING_TOOL, REORDER, REPORT_ONLY, SYNC_COPY, Finding, RecordRef,
)

DELIVERABLE = 'accounts.deliverable'
CENT = Decimal('0.01')
SNAPSHOT_FIELDS = ('client_name', 'client_phone', 'client_email')
SNAPSHOT_LABELS = {'client_name': 'el nombre', 'client_phone': 'el teléfono', 'client_email': 'el correo'}


def _proposals(scope, queryset):
    return scope.limit(queryset, PROPOSAL)


def _titles(pks):
    from content.models import BusinessProposal
    return dict(BusinessProposal._base_manager.filter(pk__in=pks).values_list('pk', 'title'))


def _joined(parts):
    return parts[0] if len(parts) == 1 else f'{", ".join(parts[:-1])} y {parts[-1]}'


def _reassignment_tool(name, proposal_id):
    return {'connector': 'proposals', 'name': name, 'arguments': {'proposal_id': proposal_id}}


# ── PR1 · stale client snapshot ──────────────────────────────────────────────

def expected_snapshot(profile):
    """What ``sync_snapshot`` writes for this client; the email only when it is real."""
    from accounts.models import UserProfile
    from accounts.services.proposal_client_service import build_client_display_name
    values = {'client_name': build_client_display_name(profile), 'client_phone': profile.phone or ''}
    email = profile.user.email
    if email and not email.endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN):
        values['client_email'] = email
    return values


def _stale_snapshot(proposal):
    return {name: [getattr(proposal, name), value] for name, value in expected_snapshot(proposal.client).items()
            if getattr(proposal, name) != value}


@rule(id='PR1', domain='proposals', severity='low', fix_kinds=(SYNC_COPY,),
      title='Datos del cliente desactualizados en la propuesta',
      description='La propuesta guarda una copia del nombre, el teléfono y el correo de su cliente, y esa copia '
                  'ya no coincide con la ficha del cliente. Se vuelve a copiar desde la ficha; un correo '
                  'provisional del cliente no reemplaza el que tiene la propuesta.')
def detect_stale_snapshot(scope):
    from content.models import BusinessProposal
    rows = _proposals(scope, BusinessProposal._base_manager.filter(client__isnull=False))
    for proposal in rows.select_related('client__user').order_by('pk'):
        stale = _stale_snapshot(proposal)
        if not stale:
            continue
        client = client_label(proposal.client)
        verb = 'no coincide' if len(stale) == 1 else 'no coinciden'
        yield Finding(
            rule_id='PR1',
            subjects=(RecordRef(PROPOSAL, proposal.pk, proposal.title), RecordRef(PROFILE, proposal.client_id, client)),
            evidence={'proposal': proposal.pk, 'client': proposal.client_id, 'stale': stale},
            message=f'En la propuesta «{proposal.title}», {_joined([SNAPSHOT_LABELS[name] for name in stale])} '
                    f'de {client} {verb} con su ficha de cliente.',
        )


class SnapshotSyncFixer(Fixer):
    kind = SYNC_COPY
    fields = {PROPOSAL: SNAPSHOT_FIELDS}

    def plan(self, finding, params, *, actor):
        from content.models import BusinessProposal
        proposal = BusinessProposal._base_manager.select_related('client__user').get(pk=finding.evidence['proposal'])
        stale = _stale_snapshot(proposal) if proposal.client_id else {}
        return self.new_plan(
            params, closure=[(PROPOSAL, proposal.pk)], context={'proposal': proposal.pk},
            changes=[change(proposal, name, before, after, proposal.title)
                     for name, (before, after) in sorted(stale.items())],
        )

    def apply(self, plan, *, actor):
        from accounts.services.proposal_client_service import sync_snapshot
        from content.models import BusinessProposal
        sync_snapshot(BusinessProposal._base_manager.select_related('client__user').get(pk=plan.context['proposal']))


register_fixer('PR1', SnapshotSyncFixer())


# ── PR2 · proposal without client ────────────────────────────────────────────

@rule(id='PR2', domain='proposals', severity='medium', fix_kinds=(REPORT_ONLY,),
      title='Propuesta sin cliente',
      description='La propuesta no está asociada a ningún cliente, así que no aparece en su ficha ni en sus '
                  'totales. Se asigna el cliente a mano desde la propuesta.')
def detect_without_client(scope):
    from content.models import BusinessProposal
    rows = _proposals(scope, BusinessProposal._base_manager.filter(client__isnull=True))
    for pk, title, client_name in rows.order_by('pk').values_list('pk', 'title', 'client_name'):
        named = f' (a nombre de «{client_name}»)' if client_name else ''
        yield Finding(rule_id='PR2', subjects=(RecordRef(PROPOSAL, pk, title),), evidence={'proposal': pk},
                      message=f'La propuesta «{title}»{named} no está asociada a ningún cliente.')


# ── PR3 · proposal, project and phases disagree ─────────────────────────────

def _mismatch_reasons(client_user, phases, deliverable):
    """Why the proposal's phases and its deliverable's project disagree, in a fixed order."""
    reasons = []
    projects = {project_id for _, project_id, _ in phases}
    if client_user is not None and any(owner != client_user for _, _, owner in phases):
        reasons.append('phase_other_client')
    if len(projects) > 1:
        reasons.append('multiple_projects')
    if deliverable is not None:
        if deliverable[0] not in projects:
            reasons.append('deliverable_without_phase')
        if projects - {deliverable[0]}:
            reasons.append('phase_outside_deliverable')
    return reasons


def _mismatch_message(title, reasons, deliverable_name):
    parts = {
        'phase_other_client': 'tiene fases en proyectos de otro cliente',
        'multiple_projects': 'tiene fases repartidas entre varios proyectos',
        'deliverable_without_phase': f'el proyecto de su entregable («{deliverable_name}») no tiene su fase',
        'phase_outside_deliverable': f'tiene fases fuera del proyecto de su entregable («{deliverable_name}»)',
    }
    return f'La propuesta «{title}» {_joined([parts[reason] for reason in reasons])}.'


@rule(id='PR3', domain='proposals', severity='high', fix_kinds=(EXISTING_TOOL,),
      title='Propuesta, proyecto y fases que no coinciden',
      description='La propuesta tiene fases en varios proyectos o en un proyecto de otro cliente, el proyecto de su entregable no '
                  'tiene la fase de la propuesta o hay fases fuera de ese proyecto. Se corrige con la '
                  'reasignación de proyecto de la propuesta, que tiene su propia vista previa.')
def detect_project_mismatch(scope):
    from accounts.models import Project, ProjectPhase
    from content.models import BusinessProposal
    ids = scope.ids_for(PROPOSAL)
    phases = ProjectPhase._base_manager.filter(project__isnull=False, retention_context__isnull=True)
    linked = BusinessProposal._base_manager.filter(deliverable__project__isnull=False,
                                                   deliverable__retention_context__isnull=True)
    if ids is not None:
        phases, linked = phases.filter(business_proposal_id__in=ids), linked.filter(pk__in=ids)
    by_proposal = defaultdict(list)
    for phase_id, proposal_id, project_id, owner in phases.order_by('pk').values_list(
            'pk', 'business_proposal_id', 'project_id', 'project__client_id'):
        by_proposal[proposal_id].append((phase_id, project_id, owner))
    deliverables = {pk: (project_id, owner) for pk, project_id, owner in linked.values_list(
        'pk', 'deliverable__project_id', 'deliverable__project__client_id')}
    candidates = set(by_proposal) | set(deliverables)
    proposals = {row.pk: row for row in BusinessProposal._base_manager.filter(pk__in=candidates).select_related('client')}
    found = []
    for pk in sorted(candidates):
        proposal = proposals[pk]
        client_user = proposal.client.user_id if proposal.client_id else None
        reasons = _mismatch_reasons(client_user, by_proposal.get(pk, []), deliverables.get(pk))
        if reasons:
            found.append((proposal, client_user, reasons))
    projects = set()
    for proposal, _, _ in found:
        projects |= {project_id for _, project_id, _ in by_proposal.get(proposal.pk, [])}
        projects |= {deliverables[proposal.pk][0]} if proposal.pk in deliverables else set()
    names = dict(Project._base_manager.filter(pk__in=projects).values_list('pk', 'name'))
    for proposal, client_user, reasons in found:
        own = by_proposal.get(proposal.pk, [])
        deliverable = deliverables.get(proposal.pk)
        involved = sorted({project_id for _, project_id, _ in own} | ({deliverable[0]} if deliverable else set()))
        yield Finding(
            rule_id='PR3',
            subjects=(RecordRef(PROPOSAL, proposal.pk, proposal.title),
                      *(RecordRef(PROJECT, project_id, names.get(project_id, '')) for project_id in involved),
                      *(RecordRef(PHASE, phase_id) for phase_id, _, _ in own)),
            evidence={'proposal': proposal.pk, 'client_user': client_user,
                      'deliverable_project': list(deliverable) if deliverable else None,
                      'phases': [list(phase) for phase in own], 'reasons': reasons},
            message=_mismatch_message(proposal.title, reasons, names.get(deliverable[0], '') if deliverable else ''),
            tool=_reassignment_tool('preview_proposal_project_reassignment', proposal.pk),
        )


# ── PR4 · accepted proposal without project ──────────────────────────────────

@rule(id='PR4', domain='proposals', severity='low', fix_kinds=(REPORT_ONLY,),
      title='Propuesta aceptada sin proyecto',
      description='La propuesta está aceptada o finalizada, pero no tiene fase en ningún proyecto ni entregable. '
                  'Se revisa a mano desde la aprobación de la propuesta.')
def detect_accepted_without_project(scope):
    from accounts.models import ProjectPhase
    from content.models import BusinessProposal
    statuses = (BusinessProposal.Status.ACCEPTED, BusinessProposal.Status.FINISHED)
    rows = _proposals(scope, BusinessProposal._base_manager.filter(status__in=statuses, deliverable__isnull=True)
                      .exclude(pk__in=ProjectPhase._base_manager.values('business_proposal_id')))
    for pk, title, status in rows.order_by('pk').values_list('pk', 'title', 'status'):
        label = BusinessProposal.status_label_es(status).lower()
        yield Finding(rule_id='PR4', subjects=(RecordRef(PROPOSAL, pk, title),),
                      evidence={'proposal': pk, 'status': status},
                      message=f'La propuesta «{title}» está {label}, pero no tiene fase en ningún proyecto ni '
                              'entregable.')


# ── PR5 · proposal bound to a deleted project ────────────────────────────────

@rule(id='PR5', domain='proposals', severity='medium', fix_kinds=(EXISTING_TOOL,),
      title='Propuesta ligada a un proyecto eliminado',
      description='El entregable o una fase de la propuesta quedó conservado de un proyecto que se eliminó. Se '
                  'traslada a un proyecto vigente del mismo cliente con la reasignación de proyecto de la '
                  'propuesta.')
def detect_retained_links(scope):
    from accounts.models import Deliverable, ProjectPhase
    from content.models import ProjectRetentionContext
    ids = scope.ids_for(PROPOSAL)
    deliverables = Deliverable._base_manager.filter(retention_context__isnull=False, business_proposal__isnull=False)
    phases = ProjectPhase._base_manager.filter(retention_context__isnull=False)
    if ids is not None:
        deliverables = deliverables.filter(business_proposal__pk__in=ids)
        phases = phases.filter(business_proposal_id__in=ids)
    found = defaultdict(lambda: {'deliverable': None, 'phases': []})
    for pk, context_id, proposal_id in deliverables.values_list('pk', 'retention_context_id', 'business_proposal__id'):
        found[proposal_id]['deliverable'] = [pk, context_id]
    for pk, context_id, proposal_id in phases.order_by('pk').values_list('pk', 'retention_context_id',
                                                                         'business_proposal_id'):
        found[proposal_id]['phases'].append([pk, context_id])
    used = {proposal_id: {context for _, context in links['phases']}
            | ({links['deliverable'][1]} if links['deliverable'] else set())
            for proposal_id, links in found.items()}
    deleted = dict(ProjectRetentionContext._base_manager.filter(pk__in=set().union(*used.values()))
                   .values_list('pk', 'project_name'))
    titles = _titles(found)
    for proposal_id, links in sorted(found.items()):
        count = len(links['phases'])
        parts = (['su entregable'] if links['deliverable'] else []) + (
            [f'{count} fase' if count == 1 else f'{count} fases'] if count else [])
        names = ', '.join(f'«{deleted.get(context, "")}»' for context in sorted(used[proposal_id]))
        where = f'al proyecto eliminado {names}' if len(used[proposal_id]) == 1 else f'a los proyectos eliminados {names}'
        title = titles.get(proposal_id, '')
        yield Finding(
            rule_id='PR5',
            subjects=(RecordRef(PROPOSAL, proposal_id, title),
                      *([RecordRef(DELIVERABLE, links['deliverable'][0])] if links['deliverable'] else []),
                      *(RecordRef(PHASE, phase_id) for phase_id, _ in links['phases'])),
            evidence={'proposal': proposal_id, 'deliverable': links['deliverable'], 'phases': links['phases']},
            message=f'La propuesta «{title}» sigue ligada {where} a través de {_joined(parts)}.',
            tool=_reassignment_tool('reassign_proposal_project', proposal_id),
        )


# ── PR7 · sections sharing an order ──────────────────────────────────────────

@rule(id='PR7', domain='proposals', severity='low', fix_kinds=(REORDER,),
      title='Secciones de la propuesta con el mismo orden',
      description='Dos o más secciones de una propuesta tienen el mismo número de orden, así que su posición no '
                  'es fija. Se renumeran seguidas conservando el orden en que se ven hoy.')
def detect_section_order(scope):
    from content.models import ProposalSection
    rows = ProposalSection._base_manager.all()
    ids = scope.ids_for(PROPOSAL)
    if ids is not None:
        rows = rows.filter(proposal_id__in=ids)
    by_proposal = defaultdict(list)
    for pk, proposal_id, order, title in rows.order_by('proposal_id', 'order', 'pk').values_list(
            'pk', 'proposal_id', 'order', 'title'):
        by_proposal[proposal_id].append((pk, order, title))
    broken = {pk: sections for pk, sections in by_proposal.items()
              if len({order for _, order, _ in sections}) < len(sections)}
    titles = _titles(broken)
    for proposal_id, sections in sorted(broken.items()):
        start = sections[0][1]
        orders = [order for _, order, _ in sections]
        shared = sorted({order for order in orders if orders.count(order) > 1})
        yield Finding(
            rule_id='PR7',
            subjects=(RecordRef(PROPOSAL, proposal_id, titles.get(proposal_id, '')),
                      *(RecordRef(SECTION, pk, title) for pk, _, title in sections)),
            evidence={'proposal': proposal_id, 'orders': [[pk, order] for pk, order, _ in sections]},
            message=f'En «{titles.get(proposal_id, "")}» varias secciones comparten el orden '
                    f'{_joined([str(order) for order in shared])}; se renumeran del {start} al '
                    f'{start + len(sections) - 1}.',
            suggestion={'orders': {str(pk): start + index for index, (pk, _, _) in enumerate(sections)}},
        )


def _write_orders(orders):
    """The panel's reorder write (``bulk_reorder_sections``): one ``bulk_update`` of ``order``."""
    from content.models import ProposalSection
    sections = list(ProposalSection._base_manager.filter(pk__in=list(orders)).order_by('pk'))
    for section in sections:
        section.order = orders[section.pk]
    if sections:
        # Match the panel's narrow, history-tracked reorder: do not run content
        # cleanup in save() or rewrite any approved section evidence.
        ProposalSection.objects.bulk_update(sections, ['order'])


class SectionOrderFixer(Fixer):
    kind = REORDER
    fields = {SECTION: ('order',)}

    def plan(self, finding, params, *, actor):
        from content.models import ProposalSection
        sections = list(ProposalSection._base_manager.filter(proposal_id=finding.evidence['proposal'])
                        .order_by('order', 'pk'))
        start = sections[0].order if sections else 0
        target = {section.pk: start + index for index, section in enumerate(sections)}
        return self.new_plan(
            params, closure=[(SECTION, section.pk) for section in sections], context={'orders': target},
            changes=[change(section, 'order', section.order, target[section.pk], section.title)
                     for section in sections if section.order != target[section.pk]],
        )

    def apply(self, plan, *, actor):
        _write_orders(plan.context['orders'])

    def revert(self, step, *, actor):
        _write_orders({item['pk']: item['before'] for item in step['items']
                       if item['field'] == 'order' and not item['guard']})


register_fixer('PR7', SectionOrderFixer())


# ── PR8 · repeated proposals ─────────────────────────────────────────────────

@rule(id='PR8', domain='proposals', severity='low', fix_kinds=(REPORT_ONLY,), group=True,
      title='Propuestas repetidas',
      description='Dos o más propuestas del mismo cliente tienen el mismo título, inversión y moneda: '
                  'probablemente se creó la misma propuesta más de una vez. Se revisan a mano.')
def detect_repeated_proposals(scope):
    from accounts.models import UserProfile
    from content.models import BusinessProposal
    groups = defaultdict(list)
    rows = (BusinessProposal._base_manager.filter(client__isnull=False).order_by('pk')
            .values_list('pk', 'client_id', 'title', 'total_investment', 'currency'))
    for pk, client_id, title, investment, currency in rows:
        groups[(client_id, normalized(title), str(Decimal(investment or 0).quantize(CENT)), currency)].append(
            (pk, title))
    repeated = {key: members for key, members in groups.items()
                if len(members) > 1 and scope.touches(PROPOSAL, [pk for pk, _ in members])}
    clients = {profile.pk: profile for profile in UserProfile._base_manager.filter(
        pk__in={key[0] for key in repeated}).select_related('user')}
    for (client_id, key, investment, currency), members in sorted(repeated.items()):
        yield Finding(
            rule_id='PR8',
            subjects=tuple(RecordRef(PROPOSAL, pk, title) for pk, title in members),
            evidence={'client': client_id, 'key': key, 'investment': investment, 'currency': currency,
                      'proposals': [pk for pk, _ in members]},
            message=f'{len(members)} propuestas de {client_label(clients[client_id])} se llaman '
                    f'«{members[0][1]}» y tienen la misma inversión ({investment} {currency}).',
        )
