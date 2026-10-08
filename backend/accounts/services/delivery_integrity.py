"""Validate prospective ancestry without rewriting captured guide provenance."""
from copy import copy
from types import SimpleNamespace

from rest_framework.exceptions import NotFound

from accounts.models import DeliveryPromptContext, Requirement
from accounts.services.delivery_access import fail


def validate_stage_destination(stage, phase):
    """An existing draft cannot reopen a phase already approved by its client."""
    from accounts.services.delivery_workflow import _phase_approved

    if (stage is None or stage.phase_id != phase.pk) and _phase_approved(phase):
        fail('La fase aprobada está congelada. Registra otra fase.', 'approved_frozen')


def validate_amendment_destination(amendment, contract):
    """An amendment cannot leave scopes attached to a different contract."""
    if amendment.contract_id != contract.pk and amendment.scopes.select_for_update().exclude(
        contract_id=contract.pk,
    ).exists():
        fail('El otrosí debe conservar el contrato de los alcances que lo utilizan.', 'amendment_contract')


def validate_applicable_amendment(scope):
    """Reject historical inconsistent ancestry at the publication boundary too."""
    if scope.amendment_id and scope.amendment.contract_id != scope.contract_id:
        fail('El otrosí debe modificar el contrato de este alcance.', 'amendment_contract')


def validate_requirement_contexts(project, requirements, *, prospective_scope=None):
    """Share loaded contexts while proving each guide's effective scope and citations."""
    from accounts.services.delivery_authoring import requirement_provenance

    requirements = list(requirements)
    contexts = {context.pk: context for context in DeliveryPromptContext.objects.filter(
        project=project, pk__in={req.context_id for req in requirements if req.context_id},
    ).prefetch_related('sources')}
    for requirement in requirements:
        if not requirement.context_id and not requirement.source_references:
            continue
        context = contexts.get(requirement.context_id)
        if requirement.context_id and context is None:
            raise NotFound('Contexto de autoría no encontrado.')
        scope = prospective_scope or requirement.stage.phase.scope
        stage = SimpleNamespace(phase=SimpleNamespace(scope=scope))
        requirement_provenance(project, stage, {
            'context_id': requirement.context_id, 'source_references': requirement.source_references,
            'guide': requirement.guide,
        }, requirement, _context=context)


def validate_ancestor_change(project, kind, node, values):
    """Check retained descendants even when a PATCH/import omits their guides."""
    from accounts.services.delivery_workflow import _node

    if node is None:
        return
    if kind == 'scopes':
        fields = ('contract_id', 'amendment_id', 'key')
        if not any(field in values and values[field] != getattr(node, field) for field in fields):
            return
        scope = copy(node)
        for field in fields:
            if field in values:
                setattr(scope, field, values[field])
        query = {'stage__phase__scope_id': node.pk}
    elif kind == 'phases' and values.get('scope_id', node.scope_id) != node.scope_id:
        scope = _node(project, 'scopes', values['scope_id'])
        query = {'stage__phase_id': node.pk}
    elif kind == 'stages' and values.get('phase_id', node.phase_id) != node.phase_id:
        scope = _node(project, 'phases', values['phase_id']).scope
        query = {'stage_id': node.pk}
    else:
        return
    requirements = Requirement.objects.filter(**query).select_related('stage__phase__scope')
    validate_requirement_contexts(project, requirements, prospective_scope=scope)
