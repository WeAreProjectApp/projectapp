"""Business logic for managing ProjectPhase rows."""
from django.db import transaction
from rest_framework import serializers

from accounts.models import Project, ProjectPhase
from content.models import BusinessProposal


class PhaseError(Exception):
    """Service-level error with a stable code + optional payload extras."""

    def __init__(self, code: str, http_status: int = 400, extra: dict | None = None):
        self.code = code
        self.http_status = http_status
        self.extra = extra or {}
        super().__init__(code)


def list_phases(project):
    """Returns the project's phases as a QuerySet ordered by ``order``."""
    return project.phases.select_related('business_proposal').order_by('order')


def retained_source_name(proposal):
    """An existing retained source cannot silently become a new commercial phase."""
    if proposal.deliverable_id and proposal.deliverable.retention_context_id:
        return proposal.deliverable.retention_context.project_name
    phase = proposal.project_phases.select_for_update().filter(
        retention_context__isnull=False,
    ).select_related('retention_context').first()
    return phase.retention_context.project_name if phase else None


def _proposal_error(message, code='proposal_context'):
    return PhaseError(code, extra={'code': code, 'detail': message, 'proposal_id': message})


def _validate_proposal_link(project, proposal, *, approval_request_id=None):
    retained_name = retained_source_name(proposal)
    if retained_name is not None:
        raise _proposal_error(
            f'La propuesta conserva recursos del proyecto eliminado «{retained_name}». '
            'Esos datos quedan en consulta y no se incorporan como fase de otro proyecto.',
            'retained_proposal',
        )
    coherent = (proposal.client_id and proposal.client.user_id == project.client_id
                and proposal.deliverable_id and proposal.deliverable.project_id == project.pk
                and not proposal.project_phases.select_for_update().exclude(project=project).exists())
    if not coherent:
        raise _proposal_error('Usa primero la revisión de aprobación o reasignación para vincular esta propuesta al proyecto y cliente correctos.')
    if proposal.status in ('accepted', 'finished'):
        return
    manifest = proposal.platform_approval_manifest
    confirmed_transition = (
        proposal.status == 'negotiating' and isinstance(approval_request_id, str)
        and bool(approval_request_id) and isinstance(manifest, dict)
        and manifest.get('request_id') == approval_request_id
        and manifest.get('project_id') == project.pk
        and manifest.get('client_profile_id') == proposal.client_id
    )
    if not confirmed_transition:
        raise _proposal_error('La propuesta debe estar aceptada o finalizada antes de agregar una fase.')


@transaction.atomic
def add_phase(project, proposal, order: int | None = None, *, approval_request_id=None) -> ProjectPhase:
    """Add only a reviewed proposal; a pending acceptance needs its exact approval claim.

    The internal approval_request_id is never read from an HTTP/MCP payload.
    Historical accepted/finished links remain valid without a new manifest.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    proposal = BusinessProposal.objects.select_for_update().select_related(
        'client', 'deliverable__retention_context',
    ).get(pk=proposal.pk)
    _validate_proposal_link(project, proposal, approval_request_id=approval_request_id)
    phases = ProjectPhase.objects.select_for_update().filter(project=project)
    if phases.filter(business_proposal=proposal).exists():
        raise PhaseError('duplicate_proposal')
    if order is None:
        max_order = phases.order_by('-order', '-id').values_list('order', flat=True).first() or 0
        order = max_order + 1
    else:
        try:
            order = serializers.IntegerField(min_value=1).run_validation(order)
        except serializers.ValidationError:
            raise PhaseError('invalid_order', extra={'order': 'Usa una posición entera mayor que cero.'})
    return ProjectPhase.objects.create(
        project=project, business_proposal=proposal, order=order,
    )


@transaction.atomic
def remove_phase(project, phase_id: int) -> None:
    """Remove an unbound phase while preserving delivery and hosting history."""
    project = Project.objects.select_for_update().get(pk=project.pk)
    try:
        phase = ProjectPhase.objects.select_for_update().get(project=project, id=phase_id)
    except ProjectPhase.DoesNotExist:
        raise PhaseError('phase_not_found', http_status=404)
    if phase.delivery_phases.select_for_update().exists() or phase.hosting_activated_at or phase.hosting_start_date:
        message = 'Esta fase tiene entrega o hosting asociado. Conserva esas relaciones antes de desvincularla.'
        raise PhaseError('phase_bound', extra={'code': 'phase_bound', 'detail': message, 'phase_id': message})
    phase.delete()
    for new_order, ph in enumerate(project.phases.select_for_update().order_by('order'), start=1):
        if ph.order != new_order:
            ph.order = new_order
            ph.save(update_fields=['order'])


def reorder_phases(project, items: list[dict]) -> None:
    """Bulk-rewrite phase ordering. ``items`` is a list of ``{id, order}`` pairs
    covering every existing phase of the project. Atomic."""
    given_ids = {item['id'] for item in items}
    existing_ids = set(project.phases.values_list('id', flat=True))
    if given_ids != existing_ids:
        raise PhaseError('invalid_phase_id', extra={
            'expected': sorted(existing_ids), 'received': sorted(given_ids),
        })
    with transaction.atomic():
        for item in items:
            ProjectPhase.objects.filter(id=item['id']).update(order=item['order'])
