"""Factories and flow helpers shared by the data-integrity tests."""
import uuid

from accounts.models import Project, ProjectPhase
from content.models import BusinessProposal
from content.services.data_integrity import engine
from content.services.data_integrity.scope import resolve_scope


def make_project(profile, name='Kore'):
    return Project.objects.create(name=name, client=profile.user)


def make_proposal(profile, title='Propuesta', **kwargs):
    values = {'client_name': profile.user.get_full_name() or 'Cliente', 'client_email': profile.user.email,
              'status': 'accepted'}
    values.update(kwargs)
    return BusinessProposal.objects.create(title=title, client=profile, **values)


def make_phase(project, proposal, order):
    return ProjectPhase.objects.create(project=project, business_proposal=proposal, order=order)


def scan(scope_kind='all', scope_id=None, **filters):
    return [finding for _, finding in engine.scan(resolve_scope(scope_kind, scope_id), **filters)]


def only(findings, rule_id):
    return [finding for finding in findings if finding.rule_id == rule_id]


def selection(finding, fix_kind=None, **params):
    entry = {'fingerprint': finding.fingerprint, 'rule_id': finding.rule_id, 'params': params}
    if fix_kind:
        entry['fix_kind'] = fix_kind
    return entry


def apply(actor, selections, *, scope=None, reason='Prueba de integridad', request_id=None):
    scope = scope or resolve_scope('all')
    preview = engine.preview_fixes(scope, selections, actor=actor)
    result = engine.apply_fixes(scope, selections, actor=actor, reason=reason,
                                request_id=request_id or uuid.uuid4().hex,
                                expected_impact_hash=preview['impact_hash'])
    return preview, result


def undo(actor, operation_id, *, request_id=None):
    preview = engine.preview_undo(operation_id)
    result = engine.undo_operation(operation_id, actor=actor, reason='Deshacer en prueba',
                                   request_id=request_id or uuid.uuid4().hex,
                                   expected_impact_hash=preview['impact_hash'])
    return preview, result
