"""Preview and atomically purge a project's exclusive dependency graph.

Every row is inventoried, only explicit categories may be removed, and
protected leaves are removed before parents. Mutable roots may be retained
under the client's non-operational retention context.
Commercial proposals and independent mail/history evidence are retained.
"""

from collections import defaultdict
import json

from django.db import models, transaction
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import PermissionDenied

from accounts.models import Project
from content.api_errors import ProposalActionError
from content.models import AccountingChangeLog, DocumentThread, DocumentThreadItem, IncomeRecord, PocketMovement
from content.services import accounting_service
from content.services.entity_history import capture_instance, historical_write
from content.services.project_deletion_catalog import CATEGORIES
from content.services.project_file_cleanup import (
    deferred_project_cleanup, project_row_files, schedule_project_files,
)
from content.services.project_service import log_project_event, project_snapshot


# These are independent commercial/audit/catalog roots, never project-owned.
RETAINED_MODELS = {
    'content.businessproposal', 'content.emailattachmentsnapshot',
    'content.linktreetemplate', 'content.contracttemplate',
    'content.entityhistory', 'content.entityrevision', 'content.accountingchangelog',
    'content.proposalapprovalfile', 'accounts.billingcontextevent',
    'accounts.deliverypromptcontext', 'accounts.deliverypromptsource',
    'accounts.deliveryevidenceemail', 'accounts.deliveryevidenceemailfile',
    'accounts.deliveryevidenceemailattempt',
}

RETENTION_BLOCK_MESSAGES = {
    'content.proposalapprovalfile': 'El paquete aprobado de una propuesta protege estos datos y debe conservarse.',
    'accounts.billingcontextevent': 'El historial de decisiones de facturación protege estos datos y debe conservarse.',
    'accounts.deliverypromptcontext': 'El contexto de fuentes capturado protege estos datos y debe conservarse.',
    'accounts.deliverypromptsource': 'Una fuente capturada protege estos datos y debe conservarse.',
    'accounts.deliveryevidenceemail': 'La evidencia de cierre por correo protege estos datos y debe conservarse.',
    'accounts.deliveryevidenceemailfile': 'Un archivo de evidencia de cierre protege estos datos y debe conservarse.',
}

# Non-CASCADE containment is explicit, so an attachment found through a
# document cannot silently pull in evidence owned by a different project.
OWNERS = {
    'accounts.contractamendment': ('contract',),
    'accounts.deliveryscope': ('contract',),
    'accounts.deliveryphase': ('scope',),
    'accounts.deliverystage': ('phase',),
    'accounts.requirement': ('stage',),
    'accounts.deliverypublication': ('stage',),
    'accounts.deliverydocumentsnapshot': ('publication', 'link'),
    'accounts.requirementreview': ('publication', 'requirement'),
    'accounts.deliveryreviewdocumentevidence': ('review',),
    'accounts.deliverypromptsource': ('context',),
    'accounts.contractsignatureevidence': ('contract', 'amendment'),
    'accounts.hostingevidencegroup': ('hosting',),
    'accounts.hostingevidence': ('group',),
    'accounts.projecthostingaccountingsource': ('hosting',),
    'accounts.payment': ('subscription',),
    'accounts.paymenthistory': ('payment',),
    'accounts.deliveryevidenceemailfile': ('email',),
    'accounts.deliveryevidenceemailattempt': ('email',),
    'content.incomerecord': ('expected_income',),
    'content.documentthreaditem': ('thread',),
    'monitoring.source': ('resource',),
    'monitoring.case': ('source',),
    'monitoring.report': ('source',),
    'monitoring.delivery': ('source', 'case'),
    'monitoring.caseactivity': ('case',),
}

FORCE_DEPENDENCY_LABELS = {
    model: (category['key'], category['label']) for model, category in CATEGORIES.items()
}



class ProjectForceDeleteError(ProposalActionError):
    def __init__(self, message, *, code, preview=None):
        super().__init__(message, code=code)
        self.preview = preview


def require_superuser(actor):
    from content.mcp.context import current_mcp_context
    if current_mcp_context() is not None:
        raise PermissionDenied('La eliminación forzada sólo está disponible en el panel.')
    if not getattr(actor, 'is_superuser', False):
        raise PermissionDenied('Sólo un superusuario puede forzar la eliminación de proyectos.')


def _key(row):
    return (type(row), row.pk)


class ProjectDeletionPlan:
    def __init__(self, project, *, lock=False, delete_keys=()):
        self.project = project
        self.lock = lock
        self.rows = {_key(project): project}
        self.conflicts = []
        self.shared_money = set()
        self.requires = defaultdict(set)
        self.delete_keys = sorted(set(delete_keys))
        self._expand()
        self._include_money_movements()
        self._include_document_threads()
        self._check_owners()
        self.inventory = self.rows.copy()
        known_keys = {CATEGORIES[model._meta.label_lower]['key']
                      for model, _ in self.inventory if model._meta.label_lower in CATEGORIES}
        if set(self.delete_keys) - known_keys:
            self._conflict(project, 'La selección contiene datos que no aparecen en esta revisión.')
        for (model, _), row in self.inventory.items():
            if model is not Project and model._meta.label_lower not in CATEGORIES:
                self._conflict(row, 'Hay información relacionada aún no clasificada. No se puede eliminar de forma segura.')
        self.rows = {key: row for key, row in self.inventory.items()
                     if key[0] is Project or CATEGORIES.get(key[0]._meta.label_lower, {}).get('key') in self.delete_keys}
        self._check_selection()
        self.layers, self.cycle_links = self._deletion_order()

    def _read(self, queryset):
        queryset = queryset.order_by('pk')
        return list(queryset.select_for_update() if self.lock else queryset)

    def _expand(self):
        """Query each model/relation frontier once, including folder descendants."""
        frontier = defaultdict(set)
        frontier[Project].add(self.project.pk)
        while frontier:
            next_frontier = defaultdict(set)
            for model, ids in frontier.items():
                for relation in model._meta.related_objects:
                    child = relation.related_model
                    if relation.many_to_many or child._meta.label_lower in RETAINED_MODELS:
                        continue
                    query = child._base_manager.filter(**{f'{relation.field.name}__in': ids})
                    for row in self._read(query):
                        if _key(row) not in self.rows:
                            self.rows[_key(row)] = row
                            next_frontier[child].add(row.pk)
            frontier = next_frontier

    def _conflict(self, row, message):
        value = {'key': row._meta.label_lower, 'id': str(row.pk), 'message': message}
        if value not in self.conflicts:
            self.conflicts.append(value)

    def _include_money_movements(self):
        movement_ids = {
            row.pocket_movement_id for row in self.rows.values()
            if isinstance(row, (IncomeRecord, accounting_service.ExpenseRecord))
            and row.pocket_movement_id
        }
        for movement in self._read(PocketMovement.objects.filter(pk__in=movement_ids)):
            incomes = self._read(movement.income_records.all())
            expenses = self._read(accounting_service.ExpenseRecord.objects.filter(pocket_movement=movement))
            if any(_key(row) not in self.rows for row in incomes + expenses):
                self.shared_money.add(_key(movement))
                self.rows[_key(movement)] = movement
            else:
                self.rows[_key(movement)] = movement

    def _include_document_threads(self):
        thread_ids = {row.thread_id for row in self.rows.values()
                      if isinstance(row, DocumentThreadItem)}
        for thread in self._read(DocumentThread.objects.filter(pk__in=thread_ids)):
            if any(_key(item) not in self.rows for item in self._read(thread.items.all())):
                self._conflict(thread, 'Un hilo documental contiene documentos ajenos al proyecto. Resuelve ese vínculo antes de eliminar.')
            else:
                self.rows[_key(thread)] = thread

    def _check_owners(self):
        included_models = {model for model, _ in self.rows}
        included_ids = defaultdict(set)
        for model, pk in self.rows:
            included_ids[model].add(pk)
        for row in self.rows.values():
            if getattr(row, 'managed_client_id', None):
                self._conflict(row, 'La organización general del cliente debe conservarse. Separa los datos del proyecto antes de eliminar.')
            owner_names = OWNERS.get(row._meta.label_lower, ())
            for field in row._meta.concrete_fields:
                if not isinstance(field, models.ForeignKey):
                    continue
                parent = field.remote_field.model
                parent_id = getattr(row, field.attname)
                if parent_id is None:
                    continue
                if parent is Project and parent_id != self.project.pk:
                    self._conflict(row, 'Hay información vinculada a otro proyecto. Resuelve ese vínculo antes de eliminar.')
                if field.name in ('client', 'client_user'):
                    expected_id = (self.project.client_id if parent._meta.label_lower == 'auth.user'
                                   else getattr(self.project.client, 'profile', None))
                    expected_id = getattr(expected_id, 'pk', expected_id)
                    if parent_id != expected_id:
                        self._conflict(row, 'Hay información de otro cliente dentro de las dependencias. Resuelve ese vínculo antes de eliminar.')
                is_owner = field.name in owner_names or (
                    field.remote_field.on_delete is models.CASCADE
                    and parent in included_models
                )
                if is_owner and (parent, parent_id) not in self.rows:
                    self._conflict(row, 'Hay evidencia o información compartida fuera de este proyecto. Resuelve ese vínculo antes de eliminar.')
            # Retained legal evidence and catalog mirrors must never be
            # bypassed by a purge of their protected live source.
            for relation in row._meta.get_fields(include_hidden=True):
                if not isinstance(relation, (models.ManyToOneRel, models.OneToOneRel)):
                    continue
                child = relation.related_model
                # related_name='+' references do not appear in
                # related_objects. Never detach another live entity through
                # a hidden backlink (for example another card's active version).
                if relation.hidden and not child._meta.auto_created:
                    external = child._base_manager.filter(**{relation.field.name: row.pk}).exclude(
                        pk__in=included_ids[child],
                    )
                    if self._read(external):
                        self._conflict(row, 'Otra entidad conserva una referencia compartida a estos datos. Resuelve ese vínculo antes de eliminar.')
                if (relation.related_model._meta.label_lower in RETAINED_MODELS
                        and not relation.many_to_many
                        and relation.field.remote_field.on_delete in (models.PROTECT, models.RESTRICT)):
                    if relation.related_model._base_manager.filter(**{relation.field.name: row.pk}).exists():
                        self._conflict(row, RETENTION_BLOCK_MESSAGES.get(
                            relation.related_model._meta.label_lower,
                            'Hay una plantilla compartida o evidencia independiente protegida que debe conservarse.',
                        ))

    def _require(self, parent, child):
        parent_category = CATEGORIES.get(parent._meta.label_lower)
        child_category = CATEGORIES.get(child._meta.label_lower)
        if parent_category and child_category:
            self.requires[parent_category['key']].add(child_category['key'])
            self._conflict(child, f"Para eliminar «{parent_category['label']}» también debes elegir «{child_category['label']}», porque no se puede conservar sin ese dato.")
        else:
            self._conflict(child, 'Una dependencia protegida impide eliminar los datos seleccionados.')

    def _check_selection(self):
        for key, row in self.inventory.items():
            for field in row._meta.concrete_fields:
                if not isinstance(field, models.ForeignKey):
                    continue
                parent_key = (field.remote_field.model, getattr(row, field.attname))
                if parent_key not in self.rows or key in self.rows:
                    continue
                if parent_key[0] is Project and hasattr(row, 'retention_context_id'):
                    continue
                if field.remote_field.on_delete in (models.CASCADE, models.PROTECT, models.RESTRICT):
                    self._require(self.rows[parent_key], row)
        for key, row in self.inventory.items():
            if not isinstance(row, (IncomeRecord, accounting_service.ExpenseRecord)) or not row.pocket_movement_id:
                continue
            movement_key = (PocketMovement, row.pocket_movement_id)
            if key in self.rows and movement_key not in self.rows:
                self._require(row, self.inventory[movement_key])
            if movement_key in self.rows and key not in self.rows:
                self._require(self.inventory[movement_key], row)
            if (key in self.rows or movement_key in self.rows) and movement_key in self.shared_money:
                self._conflict(row, 'Un movimiento del bolsillo incluye registros ajenos al proyecto. Resuelve el abono compartido antes de eliminar.')

    def _deletion_order(self):
        children = {key: set() for key in self.rows}
        links = {}
        for key, row in self.rows.items():
            for field in row._meta.concrete_fields:
                if not isinstance(field, models.ForeignKey):
                    continue
                parent = (field.remote_field.model, getattr(row, field.attname))
                if parent in children:
                    children[parent].add(key)
                    links[(key, parent)] = field
        layers, breaks = [], []
        remaining = set(self.rows)
        while remaining:
            leaves = {key for key in remaining if not children[key] & remaining}
            if leaves:
                layers.append(sorted(leaves, key=lambda key: (key[0]._meta.label_lower, str(key[1]))))
                remaining -= leaves
                continue
            # Break ONLY nullable links inside the owned cycle. Billing has
            # one such pointer from ProjectHosting back to its source.
            optional = [(child, parent, field) for (child, parent), field in links.items()
                        if child in remaining and parent in remaining and field.null
                        and child in children[parent]]
            if not optional:
                self._conflict(self.project, 'Las dependencias contienen un ciclo protegido que no se puede eliminar de forma segura.')
                break
            for child, parent, field in optional:
                children[parent].discard(child)
                breaks.append((child, field))
        return layers, breaks

    def payload(self, actor):
        counts = defaultdict(int)
        fingerprint = []
        for (model, _), row in sorted(self.inventory.items(), key=lambda item: (item[0][0]._meta.label_lower, str(item[0][1]))):
            fingerprint.append((model._meta.label_lower, [
                (field.attname, getattr(row, field.attname)) for field in model._meta.concrete_fields
            ]))
            if model is not Project and model._meta.label_lower in CATEGORIES:
                counts[model._meta.label_lower] += 1
        dependencies = []
        for model, count in sorted(counts.items()):
            category = CATEGORIES[model]
            dependencies.append({**category, 'count': count,
                                 'selected': category['key'] in self.delete_keys,
                                 'requires': sorted(self.requires[category['key']])})
        digest = salted_hmac('project-force-delete', json.dumps(
            [actor.pk, fingerprint, self.delete_keys, self.conflicts], sort_keys=True, default=str,
        ), algorithm='sha256').hexdigest()
        return {
            'project': {'id': self.project.pk, 'name': self.project.name},
            'force': True, 'can_delete': not self.conflicts, 'delete_keys': self.delete_keys,
            'dependencies': dependencies, 'blockers': self.conflicts, 'impact_token': digest,
            'consequences': [
                'La ficha operativa del proyecto se elimina: nombre, descripción, URLs, fechas, avance y configuración.',
                'Lo no seleccionado queda bajo el mismo cliente, sin proyecto, para consulta y descarga.',
                'Se detienen nuevos cobros y avisos automáticos asociados al proyecto eliminado. Los importes y el historial conservados no cambian.',
            ],
        }


def forced_deletion_preview(project, *, actor, delete_keys=()):
    require_superuser(actor)
    return ProjectDeletionPlan(project, delete_keys=delete_keys).payload(actor)


@historical_write
@transaction.atomic
def force_delete_project(project_id, *, actor, confirmation, impact_token, delete_keys):
    require_superuser(actor)
    if confirmation != 'DELETE':
        raise ProjectForceDeleteError('Escribe exactamente DELETE en mayúsculas.', code='project_delete_confirmation_required')
    project = Project.objects.select_for_update().get(pk=project_id)
    plan = ProjectDeletionPlan(project, lock=True, delete_keys=delete_keys)
    preview = plan.payload(actor)
    if not impact_token or not constant_time_compare(impact_token, preview['impact_token']):
        raise ProjectForceDeleteError('Las dependencias cambiaron. Revisa el alcance y escribe DELETE de nuevo.', code='stale_project_delete_preview', preview=preview)
    if preview['blockers']:
        raise ProjectForceDeleteError('El proyecto tiene datos compartidos que deben resolverse antes de eliminar.', code='project_force_delete_blocked', preview=preview)

    from content.services.project_retention_service import retain_project_records
    retained = retain_project_records(plan, actor)
    files = []
    for row in plan.rows.values():
        capture_instance(row)
        files.extend(project_row_files(row))
        entity_type = next((kind for kind, model in accounting_service.ENTITY_MODELS.items()
                            if type(row) is model), None)
        if entity_type:
            if entity_type == AccountingChangeLog.EntityType.POCKET:
                accounting_service._log_pocket_removal(row, actor)
            else:
                accounting_service.log_entity_removal(entity_type, row, actor)
    audit = log_project_event(project, AccountingChangeLog.Action.DELETED, project_snapshot(project), actor)
    audit.changes += [{'field': 'forced_deletion', 'label': 'Eliminación forzada',
                      'old': {'dependencies': preview['dependencies'], 'delete_keys': plan.delete_keys},
                      'new': {'retention_context': retained.pk if retained else None, 'automations_stopped': True}}]
    audit.save(update_fields=['changes'])

    with deferred_project_cleanup():
        for (model, pk), field in plan.cycle_links:
            # Only internal nullable cycle edges; immutable external records
            # are neither rewritten nor used to expand the deletion scope.
            model._base_manager.filter(pk=pk).update(**{field.attname: None})
        for layer in plan.layers:
            grouped = defaultdict(list)
            for model, pk in layer:
                grouped[model].append(pk)
            for model, ids in grouped.items():
                model._base_manager.filter(pk__in=ids).delete()
    schedule_project_files(files)
