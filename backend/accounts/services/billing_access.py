"""Ownership boundaries shared by billing REST, Panel and MCP."""
from django.db.models import F, Q
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from accounts.models import Project


class BillingConflict(APIException):
    status_code = 409
    default_detail = 'El contexto de cobro cambió. Actualiza antes de continuar.'
    default_code = 'billing_conflict'


def invalid(message):
    raise ValidationError({'detail': message})


def is_billing_admin(actor):
    profile = getattr(actor, 'profile', None)
    return bool(actor and actor.is_authenticated and actor.is_active and (
        actor.is_superuser or (profile and profile.is_admin)
    ))


def require_billing_admin(actor):
    if not is_billing_admin(actor):
        raise PermissionDenied('Solo administración puede asociar o conciliar cobros.')


def billing_project(project_id, actor, *, lock=False):
    if not actor or not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied('Se requiere una cuenta activa.')
    qs = Project.objects.select_related('client')
    if lock:
        qs = qs.select_for_update()
    if not is_billing_admin(actor):
        qs = qs.filter(client=actor)
    project = qs.filter(pk=project_id).first()
    if not project:
        raise NotFound('Proyecto no encontrado.')
    return project


def coherent_documents(qs):
    """An inconsistent historical relation never grants a second owner access."""
    qs = qs.filter(Q(client_user__isnull=True) | Q(project__isnull=True)
                   | Q(client_user_id=F('project__client_id')))
    for relation, client_path in (
        ('hosting_record', 'client__user_id'), ('income_record', 'client__user_id'),
    ):
        qs = qs.filter(Q(**{f'{relation}__client__isnull': True})
                       | (Q(client_user__isnull=True) | Q(client_user_id=F(f'{relation}__{client_path}'))))
        qs = qs.filter(Q(**{f'{relation}__project__isnull': True})
                       | Q(project_id=F(f'{relation}__project_id')))
        qs = qs.filter(Q(**{f'{relation}__client__isnull': True}) | Q(project__isnull=True)
                       | Q(project__client_id=F(f'{relation}__{client_path}')))
    return qs.filter(
        Q(billing_context__isnull=True)
        | Q(billing_context__nature='contract', billing_context__contract__project_id=F('project_id'))
        | Q(billing_context__nature='hosting', billing_context__hosting__project_id=F('project_id')),
    ).filter(Q(billing_context__amendment__isnull=True)
             | Q(billing_context__amendment__contract_id=F('billing_context__contract_id')))


def documents_for_actor(qs, actor):
    if is_billing_admin(actor):
        return qs
    if not actor or not actor.is_authenticated or not actor.is_active:
        return qs.none()
    return coherent_documents(qs).filter(
        Q(client_user=actor) | Q(project__client=actor),
    ).exclude(commercial_status='draft')
