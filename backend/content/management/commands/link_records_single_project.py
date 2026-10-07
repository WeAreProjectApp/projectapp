"""Rellena el proyecto de registros históricos cuando es inequívoco.

La pasada retroactiva del requisito de coherencia cliente/proyecto: ingresos,
hostings y documentos (cuentas de cobro incluidas) que tienen cliente pero no
proyecto reciben el proyecto de su cliente SOLO cuando ese cliente tiene
exactamente UN proyecto activo — la misma regla que el auto-select del
formulario (``ProjectSelect``), así la pasada nunca enlaza una fila que la
propia UI no habría enlazado. Con 2+ proyectos activos, o ninguno activo,
la fila se salta y se reporta: adivinar identidades viola el criterio PA-25,
y el residuo queda visible en los contadores y en la oferta del módulo
Proyectos para resolverse a mano.

Solo se LLENAN proyectos vacíos — jamás se cambia uno existente, ni el
cliente, ni el snapshot ``customer_project_name``/PDF de una cuenta emitida
(el documento emitido es un hecho; su FK de proyecto es metadata
organizativa). Cada fila escrita deja su entrada de auditoría en
AccountingChangeLog, a diferencia del precedente ``link_documents_from_folders``
(anterior al vocabulario de auditoría F5).

Dry-run por defecto: imprime el plan completo (con conteos por módulo y los
saltos con su razón) sin escribir nada. Con --apply escribe en una
transacción, re-verificando fila a fila que el proyecto siga vacío.
Idempotente: una segunda corrida reporta 0. En producción requiere
DJANGO_SETTINGS_MODULE=projectapp.settings_prod.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Project
from content.models import Document, HostingRecord, IncomeRecord
from content.services import accounting_service
from content.services.accounting_service import EntityType
from content.services.document_type_codes import COLLECTION_ACCOUNT


class Command(BaseCommand):
    help = (
        'Asigna a los registros con cliente y sin proyecto (ingresos, '
        'hostings y documentos) el único proyecto activo de su cliente. '
        'Dry-run por defecto; --apply escribe. Producción: '
        'DJANGO_SETTINGS_MODULE=projectapp.settings_prod.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Aplica el plan (por defecto sólo se imprime).',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']

        # user_id -> [proyectos activos]. La clave es el User (el keyspace de
        # Project.client y Document.client_user); los registros contables
        # llegan vía client.user_id.
        active_by_user = defaultdict(list)
        for project in Project.objects.filter(status=Project.STATUS_ACTIVE):
            active_by_user[project.client_id].append(project)

        def target_for(user_id):
            projects = active_by_user.get(user_id, [])
            return projects[0] if len(projects) == 1 else None

        plans = {}      # module -> [(pk, project)]
        skipped = defaultdict(lambda: defaultdict(int))  # razón -> módulo -> n
        totals = {}

        def scan(module, tag, rows, user_id_of, label_of):
            rows = list(rows)
            totals[module] = len(rows)
            plan = []
            for row in rows:
                user_id = user_id_of(row)
                project = target_for(user_id)
                if project is None:
                    actives = len(active_by_user.get(user_id, []))
                    reason = (
                        'cliente sin proyectos activos' if actives == 0
                        else f'{actives} proyectos activos (ambiguo)'
                    )
                    skipped[reason][module] += 1
                    continue
                plan.append((row.pk, project))
                self.stdout.write(
                    f'[{tag}] #{row.pk} {label_of(row)} → '
                    f'Proyecto #{project.pk} "{project.name}"',
                )
            plans[module] = plan

        unlinked = {
            'ingresos': IncomeRecord.objects.filter(client__isnull=False, project__isnull=True),
            'hostings': HostingRecord.objects.filter(client__isnull=False, project__isnull=True),
            'documentos': Document.objects.filter(
                client_user__isnull=False, project__isnull=True, is_archived=False,
            ),
        }
        # Lo conservado de un proyecto eliminado es de sólo consulta: guardarlo
        # abortaría toda la transacción de --apply. Se reporta y no se enlaza.
        for module, rows in unlinked.items():
            retained = rows.filter(retention_context__isnull=False).count()
            if retained:
                skipped['datos conservados de un proyecto eliminado'][module] += retained

        scan(
            'ingresos', 'ingreso',
            unlinked['ingresos'].filter(retention_context__isnull=True)
            .select_related('client__user'),
            lambda row: row.client.user_id,
            lambda row: f'"{row.concept}"',
        )
        scan(
            'hostings', 'hosting',
            unlinked['hostings'].filter(retention_context__isnull=True)
            .select_related('client__user'),
            lambda row: row.client.user_id,
            lambda row: f'"{row.display_label}"',
        )
        # Cuentas y documentos comparten el modelo; la etiqueta distingue.
        scan(
            'documentos', 'documento',
            unlinked['documentos'].filter(retention_context__isnull=True)
            .select_related('document_type'),
            lambda row: row.client_user_id,
            lambda row: (
                f'{row.public_number or row.title} (cuenta de cobro)'
                if getattr(row.document_type, 'code', None) == COLLECTION_ACCOUNT
                else f'"{row.title}"'
            ),
        )

        for reason, by_module in sorted(skipped.items()):
            detail = ', '.join(
                f'{count} {module}' for module, count in sorted(by_module.items())
            )
            self.stdout.write(f'[skip] {reason}: {detail}')
        self.stdout.write(
            'Resumen: '
            + '; '.join(
                f'{module} {len(plans[module])}/{totals[module]} por enlazar'
                for module in ('ingresos', 'hostings', 'documentos')
            ),
        )

        if not apply_changes:
            self.stdout.write(
                'Dry-run: nada se escribió. Ejecuta con --apply para aplicar.',
            )
            return

        applied = {module: 0 for module in plans}
        with transaction.atomic():
            for module, model, entity_type in (
                ('ingresos', IncomeRecord, EntityType.INCOME),
                ('hostings', HostingRecord, EntityType.HOSTING),
            ):
                project_by_pk = dict(plans[module])
                # Re-check fila a fila: sólo se llena lo que SIGUE vacío —
                # una fila que ganó proyecto entre el plan y la escritura se
                # respeta (fill-only, nunca overwrite).
                rows = (
                    model.objects
                    .filter(pk__in=project_by_pk, project__isnull=True)
                    .select_related('client__user', 'project')
                )
                for row in rows:
                    old_values = accounting_service.snapshot_values(
                        row, entity_type,
                    )
                    row.project = project_by_pk[row.pk]
                    row.save(update_fields=['project', 'updated_at'])
                    accounting_service.log_entity_diff(
                        entity_type, row, old_values, user=None,
                    )
                    applied[module] += 1

            documents_by_project = defaultdict(list)
            for pk, project in plans['documentos']:
                documents_by_project[project].append(pk)
            for project, pks in documents_by_project.items():
                still_null = list(
                    Document.objects
                    .filter(pk__in=pks, project__isnull=True)
                    .values_list('pk', flat=True),
                )
                updated = accounting_service.assign_project_to_documents(
                    still_null, project, user=None,
                )
                applied['documentos'] += len(updated)

        self.stdout.write(self.style.SUCCESS(
            'Aplicado: '
            + '; '.join(
                f'{applied[module]} {module}'
                for module in ('ingresos', 'hostings', 'documentos')
            )
            + '.',
        ))
