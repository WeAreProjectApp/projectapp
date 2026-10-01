"""Management command — enrich the platform graph with sub-models that the base
``seed_platform_data`` does not (or only sparsely) create.

Additive and idempotent: safe to run after ``seed_platform_data``. It tops up:

* ``PaymentHistory`` transition logs for every ``Payment`` lacking them,
* ``ProjectDataModelEntity`` rows per project (real data-model state),
* ``DeliverableClientFolder`` / ``DeliverableClientUpload`` / ``DeliverableFile``
  for a sample of deliverables,
* extra ``Notification`` rows up to a target volume,

and ensures admin-settings singletons exist (``CompanySettings``,
``EmailTemplateConfig``, default configs, a few ``SavedFilterTab``).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.management.commands._seed_helpers import ensure_delivery_stage, refresh_seed_publication
from accounts.models import (
    BugReport,
    ChangeRequest,
    CommunicationPanelPreference,
    Deliverable,
    DeliverableClientFolder,
    DeliverableClientUpload,
    DeliverableFile,
    Notification,
    Payment,
    PaymentHistory,
    Project,
    ProjectDataModelEntity,
    Requirement,
    SavedFilterTab,
    UserProfile,
)
from content.fake_data import add_seed_arguments, ensure_fake_data_allowed, seed_context

User = get_user_model()

# Coherent status paths per current Payment status (keys are status string values).
HISTORY_PATHS = {
    Payment.STATUS_PAID: [('pending', 'processing', 'system'), ('processing', 'paid', 'webhook')],
    Payment.STATUS_PROCESSING: [('pending', 'processing', 'wompi_link')],
    Payment.STATUS_FAILED: [('pending', 'processing', 'wompi_link'), ('processing', 'failed', 'webhook')],
    Payment.STATUS_OVERDUE: [('pending', 'overdue', 'system')],
    Payment.STATUS_PENDING: [('pending', 'pending', 'system')],
}

NOTIFICATION_SPECS = [
    (Notification.TYPE_DELIVERABLE_UPLOADED, 'Nuevo entregable disponible',
     'Se subió un nuevo entregable a tu proyecto.'),
    (Notification.TYPE_BUG_STATUS_CHANGED, 'Estado de reporte actualizado',
     'Tu reporte de error cambió de estado.'),
    (Notification.TYPE_CR_STATUS_CHANGED, 'Solicitud de cambio actualizada',
     'Tu solicitud de cambio fue evaluada por el equipo.'),
    (Notification.TYPE_REQUIREMENT_APPROVED, 'Requerimiento aprobado',
     'Un requerimiento fue aprobado y pasa a desarrollo.'),
    (Notification.TYPE_COMMENT_ADDED, 'Nuevo comentario',
     'Hay un nuevo comentario en tu proyecto.'),
    (Notification.TYPE_GENERAL, 'Bienvenido a la plataforma',
     'Gracias por confiar en nosotros. Aquí verás el avance de tu proyecto.'),
]

ENTITY_SPECS = [
    ('Usuario', 'Cuenta de acceso a la plataforma.', 'email, nombre, rol, fecha_registro', 'Tiene muchos Pedidos'),
    ('Producto', 'Ítem del catálogo.', 'nombre, precio, stock, categoria', 'Pertenece a una Categoría'),
    ('Pedido', 'Orden de compra del cliente.', 'numero, total, estado, fecha', 'Pertenece a un Usuario'),
    ('Pago', 'Transacción asociada a un pedido.', 'monto, metodo, estado, referencia_wompi', 'Pertenece a un Pedido'),
    ('Categoría', 'Agrupación de productos.', 'nombre, slug, orden', 'Tiene muchos Productos'),
]


class Command(BaseCommand):
    help = 'Enrich the platform graph with payment history, data-model entities, ' \
           'deliverable uploads, notifications and admin-settings singletons.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--notifications', type=int, default=40,
            help='Target total number of notifications (default: 40).',
        )
        add_seed_arguments(parser, count_default=60)

    def handle(self, *args, **options):
        ensure_fake_data_allowed('enrich_platform_data')
        context = seed_context(options, 'platform-enrichment')
        rng = context.rng
        admin = User.objects.filter(is_staff=True).first()

        self._representative_volume(admin, options['count'], context)
        self._payment_history(rng)
        self._data_model_entities(admin)
        self._deliverable_uploads(rng, admin)
        self._notifications(rng, options['notifications'])
        self._admin_settings(admin)

        self.stdout.write(self.style.SUCCESS('Platform graph enriched.'))

    def _representative_volume(self, admin, target, context):
        """Top up the busiest project so every platform list can paginate."""

        project = (
            Project.objects.filter(client__isnull=False)
            .select_related('client')
            .order_by('pk')
            .first()
        )
        if not project or not admin:
            self.stdout.write(self.style.WARNING(
                '  Platform volume skipped: a client project and staff actor are required.',
            ))
            return

        target = max(1, target)
        stage = ensure_delivery_stage(project, context=context, actor=admin)
        client = project.client

        requirement_count = Requirement.objects.filter(stage__phase__scope__contract__project=project).count()
        requirement_rows = []
        for index in range(requirement_count, target):
            title = f'[Volume] Requerimiento representativo {index + 1:03d}'
            if index == target - 1:
                title = ('RequerimientoExtremoSinEspacios' * 12)[:300]
            requirement_rows.append(Requirement(
                stage=stage, key=f'fake-volume-{index + 1:03d}', title=title,
                description='Caso funcional para probar volumen, filtros y extremos.',
                guide={
                    'role': 'Cliente responsable de validar',
                    'environment': 'Ambiente demo',
                    'preparation': 'Entrar con la cuenta ficticia asignada.',
                    'data': 'Elegir un registro de demostración.',
                    'steps': ['Abrir la vista', 'Filtrar el listado', 'Revisar el detalle'],
                    'expected_result': 'El registro elegido aparece con sus datos completos.',
                    'failure_signals': 'Si falta el registro, reportar el filtro utilizado.',
                },
                review_status=Requirement.ReviewStatus.IN_REVIEW, order=index,
            ))
        Requirement.objects.bulk_create(requirement_rows)
        refresh_seed_publication(stage, actor=admin)

        categories = [value for value, _ in Deliverable.CATEGORY_CHOICES]
        deliverable_count = Deliverable.objects.filter(project=project).count()
        deliverable_rows = []
        for index in range(deliverable_count, target):
            deliverable_rows.append(Deliverable(
                project=project,
                category=categories[index % len(categories)],
                title=f'[Volume] Entregable representativo {index + 1:03d}',
                description='Entregable lógico sin archivo real para el ambiente demo.',
                source_epic_key=f'fake-volume-{index + 1:03d}',
                source_epic_title=f'Módulo representativo {index % 8 + 1}',
                current_version=index % 4 + 1,
                uploaded_by=admin,
                is_archived=index % 19 == 0,
                archived_at=(
                    context.anchor_now if index % 19 == 0 else None
                ),
            ))
        Deliverable.objects.bulk_create(deliverable_rows)

        change_statuses = [value for value, _ in ChangeRequest.STATUS_CHOICES]
        change_priorities = [value for value, _ in ChangeRequest.PRIORITY_CHOICES]
        change_count = ChangeRequest.objects.filter(project=project).count()
        change_rows = []
        for index in range(change_count, target):
            change_rows.append(ChangeRequest(
                project=project,
                created_by=client,
                title=f'[Volume] Solicitud de cambio {index + 1:03d}',
                description='Cambio representativo para validar estados y filtros.',
                module_or_screen=f'Módulo {index % 8 + 1}',
                suggested_priority=change_priorities[index % len(change_priorities)],
                is_urgent=index % 9 == 0,
                status=change_statuses[index % len(change_statuses)],
                estimated_cost=(index + 1) * 100000,
                estimated_time=f'{index % 5 + 1} días',
                is_archived=index % 23 == 0,
                archived_at=(
                    context.anchor_now if index % 23 == 0 else None
                ),
            ))
        ChangeRequest.objects.bulk_create(change_rows)

        bug_statuses = [value for value, _ in BugReport.STATUS_CHOICES]
        severities = [value for value, _ in BugReport.SEVERITY_CHOICES]
        environments = [value for value, _ in BugReport.ENV_CHOICES]
        bug_count = BugReport.objects.filter(project=project).count()
        bug_rows = []
        for index in range(bug_count, target):
            bug_rows.append(BugReport(
                project=project,
                reported_by=client,
                title=f'[Volume] Incidente representativo {index + 1:03d}',
                description='Fallo simulado que permite probar el ciclo completo de bugs.',
                severity=severities[index % len(severities)],
                steps_to_reproduce=['Abrir la vista', 'Ejecutar la acción', 'Observar el resultado'],
                expected_behavior='La operación finaliza correctamente.',
                actual_behavior='La operación muestra el fallo simulado.',
                environment=environments[index % len(environments)],
                device_browser=f'Navegador demo {index % 6 + 1}',
                is_recurring=index % 3 == 0,
                status=bug_statuses[index % len(bug_statuses)],
                is_archived=index % 29 == 0,
                archived_at=(
                    context.anchor_now if index % 29 == 0 else None
                ),
            ))
        BugReport.objects.bulk_create(bug_rows)

        self.stdout.write(self.style.SUCCESS(
            '  Representative platform volume: '
            f'{Requirement.objects.filter(stage__phase__scope__contract__project=project).count()} requirements, '
            f'{Deliverable.objects.filter(project=project).count()} deliverables, '
            f'{ChangeRequest.objects.filter(project=project).count()} changes, '
            f'{BugReport.objects.filter(project=project).count()} bugs.',
        ))

    def _payment_history(self, rng):
        with_history = set(PaymentHistory.objects.values_list('payment_id', flat=True))
        rows = []
        for payment in Payment.objects.exclude(id__in=with_history):
            path = HISTORY_PATHS.get(payment.status, HISTORY_PATHS[Payment.STATUS_PENDING])
            rows += [
                PaymentHistory(
                    payment=payment, from_status=from_s, to_status=to_s,
                    source=source, metadata={'seed': True},
                )
                for from_s, to_s, source in path
            ]
        PaymentHistory.objects.bulk_create(rows)
        self.stdout.write(self.style.SUCCESS(f'  PaymentHistory rows created: {len(rows)}'))

    def _data_model_entities(self, admin):
        seeded = set(ProjectDataModelEntity.objects.values_list('project_id', flat=True))
        rows = []
        for project in Project.objects.exclude(id__in=seeded):
            rows += [
                ProjectDataModelEntity(
                    project=project, name=name, description=desc,
                    key_fields=key_fields, relationship=relationship,
                )
                for name, desc, key_fields, relationship in ENTITY_SPECS
            ]
        ProjectDataModelEntity.objects.bulk_create(rows)
        self.stdout.write(self.style.SUCCESS(f'  ProjectDataModelEntity rows created: {len(rows)}'))

    def _deliverable_uploads(self, rng, admin):
        folders = uploads = files = 0
        deliverables = list(Deliverable.objects.select_related('project').all())
        for deliverable in deliverables:
            client = deliverable.project.client if deliverable.project_id else None
            # Attachment files (admin-provided) for ~half of deliverables.
            if rng.random() < 0.5 and not deliverable.attachment_files.exists():
                DeliverableFile.objects.create(
                    deliverable=deliverable,
                    file=f'deliverables/files/{deliverable.pk}/anexo.pdf',
                    title='Anexo de referencia',
                    category=deliverable.category,
                    uploaded_by=admin,
                )
                files += 1
            # Client upload folder + PDFs for ~40% of deliverables.
            if client and rng.random() < 0.4 and not deliverable.client_folders.exists():
                folder = DeliverableClientFolder.objects.create(
                    deliverable=deliverable,
                    name='Documentos del cliente',
                    created_by=client,
                    order=0,
                )
                folders += 1
                for k in range(rng.randint(1, 2)):
                    DeliverableClientUpload.objects.create(
                        deliverable=deliverable,
                        folder=folder,
                        file=f'deliverables/client/{deliverable.pk}/comprobante-{k + 1}.pdf',
                        title=f'Comprobante {k + 1}',
                        uploaded_by=client,
                    )
                    uploads += 1
        self.stdout.write(self.style.SUCCESS(
            f'  Deliverable client folders={folders} uploads={uploads} attachment files={files}'))

    def _notifications(self, rng, target):
        existing = Notification.objects.count()
        if existing >= target:
            self.stdout.write(self.style.SUCCESS(
                f'  Notifications already at {existing} (>= {target}) — skipped'))
            return
        projects = list(Project.objects.select_related('client').all())
        client_users = [p.client for p in projects if p.client_id]
        if not client_users:
            client_users = [
                p.user for p in UserProfile.objects.filter(
                    role=UserProfile.ROLE_CLIENT).select_related('user')
            ]
        if not client_users:
            self.stdout.write(self.style.WARNING('  No client users — notifications skipped'))
            return

        rows = []
        for i in range(target - existing):
            ntype, title, message = NOTIFICATION_SPECS[i % len(NOTIFICATION_SPECS)]
            user = rng.choice(client_users)
            project = rng.choice(projects) if projects else None
            rows.append(Notification(
                user=user,
                type=ntype,
                title=title,
                message=message,
                project=project if (project and project.client_id == user.id) else None,
                is_read=rng.random() < 0.4,
            ))
        Notification.objects.bulk_create(rows)
        self.stdout.write(self.style.SUCCESS(f'  Notifications created: {len(rows)}'))

    def _admin_settings(self, admin):
        from content.models import (
            CompanySettings,
            DiagnosticDefaultConfig,
            EmailTemplateConfig,
            ProposalDefaultConfig,
        )

        CompanySettings.objects.get_or_create(
            pk=1,
            defaults={
                'contractor_full_name': 'ProjectApp S.A.S.',
                'contractor_nit': '901.234.567-8',
                'contractor_email': 'contratos@projectapp.dev',
                'bank_name': 'Bancolombia',
                'bank_account_type': 'Ahorros',
                'bank_account_number': '123-456789-00',
                'contract_city': 'Bogotá',
            },
        )
        for key in ('proposal_sent', 'proposal_reminder'):
            EmailTemplateConfig.objects.get_or_create(
                template_key=key, defaults={'content_overrides': {}, 'is_active': True})

        # Default configs are usually created by data migrations; ensure-exist defensively.
        for lang in ('es', 'en'):
            ProposalDefaultConfig.objects.get_or_create(language=lang)
            DiagnosticDefaultConfig.objects.get_or_create(language=lang)

        if admin:
            CommunicationPanelPreference.objects.update_or_create(
                user=admin,
                defaults={
                    'navigation_mode': CommunicationPanelPreference.NAVIGATION_CLIENT,
                    'thread_order': CommunicationPanelPreference.ORDER_TITLE,
                    'page_size': 50,
                    'default_channel': CommunicationPanelPreference.CHANNEL_EMAIL,
                    'show_manual_help': False,
                    'navigation_width': 336,
                },
            )
            SavedFilterTab.objects.get_or_create(
                user=admin, view='proposal', name='Aceptadas',
                defaults={'filters': {'status': ['accepted']}, 'order': 0},
            )
            SavedFilterTab.objects.get_or_create(
                user=admin, view='client', name='Onboarding pendiente',
                defaults={'filters': {'is_onboarded': False}, 'order': 0},
            )
        self.stdout.write(self.style.SUCCESS('  Admin settings ensured.'))
