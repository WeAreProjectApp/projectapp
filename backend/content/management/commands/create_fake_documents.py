"""Management command — create fake Document graph for local / demo use.

Builds the full commercial documents feature with business sense:

* one ``IssuerProfile`` (legal entity),
* a **hierarchical** ``DocumentFolder`` tree (exercises the folder/parent feature),
* a palette of ``DocumentTag`` labels,
* ``Document`` records split between markdown notes and collection accounts;
  each account is created from its ``IncomeRecord`` origin and carries a coherent
  ``DocumentItem``, a ``DocumentCollectionAccount`` 1:1 extension and a
  ``DocumentPaymentMethod``.

Collection accounts are pushed through their real lifecycle
(draft → issued → paid / cancelled / overdue) via ``collection_account_service``
so ``public_number`` is allocated exactly like in production.

Re-running skips creation if fake documents already exist; the canonical
orchestrator uses ``--replace`` for a byte-for-byte reproducible refresh.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import Project
from accounts.services.proposal_client_service import build_client_display_name
from content.models import (
    Document,
    DocumentFolder,
    DocumentThread,
    DocumentState,
    DocumentTag,
    DocumentType,
    IncomeRecord,
)
from content.fake_data import add_seed_arguments, ensure_fake_data_allowed, seed_context
from content.services import collection_account_service as ca_service
from content.services import collection_account_create_service as ca_create_service
from content.services.accounting_service import paid_amount_subquery
from content.services.document_content import build_content_json
from content.services.document_thread_service import create_document_thread
from content.services.document_type_codes import COLLECTION_ACCOUNT, MARKDOWN
from content.services.document_note_service import (
    create_note,
    delete_notes,
    finish_note,
    restore_note,
)
from content.services.document_state_service import (
    correct_opened_at,
    open_state,
)

User = get_user_model()


# ── Static pools ──────────────────────────────────────────────────────────

FOLDER_TREE = [
    ('Comercial', [
        ('2026', [
            ('Cuentas de cobro', []),
            ('Facturas', []),
        ]),
        ('Contratos', []),
    ]),
    ('Documentación', [
        ('Manuales', []),
        ('Anexos', []),
    ]),
]

TAGS = [
    ('Urgente', DocumentTag.Color.RED),
    ('Pagado', DocumentTag.Color.EMERALD),
    ('Pendiente', DocumentTag.Color.YELLOW),
    ('Cliente VIP', DocumentTag.Color.PURPLE),
    ('Interno', DocumentTag.Color.GRAY),
    ('Revisar', DocumentTag.Color.BLUE),
]

BILLING_CONCEPTS = [
    'Desarrollo de plataforma web — Fase 1',
    'Anticipo de proyecto (40%)',
    'Saldo final de proyecto (30%)',
    'Mensualidad de hosting y mantenimiento',
    'Soporte técnico y ajustes funcionales',
    'Diseño UX/UI e identidad visual',
    'Integración de pasarela de pagos',
    'Migración y puesta en producción',
]

MARKDOWN_DOCS = [
    ('Manual de uso del panel de administración',
     '# Manual del panel\n\nGuía rápida para gestionar propuestas, clientes y documentos.\n\n## Acceso\nIngrese con su usuario de administrador.\n'),
    ('Acta de inicio de proyecto',
     '# Acta de inicio\n\nSe deja constancia del arranque del proyecto, alcance y entregables acordados.\n'),
    ('Política de tratamiento de datos',
     '# Tratamiento de datos\n\nDescribe cómo se recolectan, usan y protegen los datos personales.\n'),
    ('Guía de marca y lineamientos visuales',
     '# Guía de marca\n\nColores, tipografías y uso del logotipo para piezas digitales.\n'),
    ('Anexo técnico — arquitectura de la solución',
     '# Anexo técnico\n\nStack: Django + Nuxt + MySQL. Describe módulos, integraciones y despliegue.\n'),
    ('Checklist de entrega y aceptación',
     '# Checklist de entrega\n\n- [ ] Pruebas de aceptación\n- [ ] Capacitación\n- [ ] Puesta en producción\n'),
]

def _ensure_issuer():
    from content.models import IssuerProfile

    issuer, _ = IssuerProfile.objects.get_or_create(
        name='ProjectApp',
        defaults={
            'legal_name': 'ProjectApp S.A.S.',
            'identification_type': 'NIT',
            'identification_number': '901.234.567-8',
            'email': 'facturacion@projectapp.dev',
            'phone': '+57 300 123 4567',
            'address': 'Calle 123 #45-67',
            'city': 'Bogotá',
            'country': 'CO',
            'public_number_prefix': 'PA',
        },
    )
    return issuer


def _ensure_folders():
    """Create the folder tree, return a flat list of leaf folders."""
    leaves = []

    def walk(specs, parent):
        for name, children in specs:
            # `is_archived=False` en el lookup: si una corrida previa archivó
            # esta carpeta, se crea una activa en vez de reusar la archivada.
            folder, _ = DocumentFolder.objects.get_or_create(
                name=name, parent=parent, is_archived=False,
                defaults={'order': 0, 'creation_source': 'system', 'creation_operation': 'create_fake_documents'},
            )
            if children:
                walk(children, folder)
            else:
                leaves.append(folder)

    walk(FOLDER_TREE, None)
    return leaves


def _ensure_tags():
    tags = []
    for name, color in TAGS:
        tag, _ = DocumentTag.objects.get_or_create(name=name, defaults={'color': color})
        tags.append(tag)
    return tags


def _doc_type(code, name):
    dt, _ = DocumentType.objects.get_or_create(code=code, defaults={'name': name})
    return dt


def _client_candidates():
    """Return (project, client_user) pairs usable for collection accounts."""
    return [
        (project, project.client)
        for project in Project.objects.select_related('client').order_by('pk')
        if project.client_id
    ]


def _collection_income_candidates():
    """Seed full-value accounts from incomes that have not received payments."""
    return list(
        IncomeRecord.objects.filter(
            kind=IncomeRecord.Kind.EXPECTED,
            client__isnull=False,
            project__isnull=False,
            collection_documents__isnull=True,
        ).annotate(paid_amount=paid_amount_subquery())
        .filter(paid_amount=0)
        .select_related('client__user', 'project').order_by('pk')
    )


class Command(BaseCommand):
    help = 'Create a fake Document graph (issuer, folders, tags, markdown + collection accounts).'

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=40)

    def handle(self, *args, **options):
        ensure_fake_data_allowed('create_fake_documents')
        self.seed_context = seed_context(options, 'documents')
        count = max(1, options['count'])

        if Document.objects.count() >= count:
            self.stdout.write(self.style.WARNING(
                f'{Document.objects.count()} documents already exist — skipped. '
                'Run delete_fake_data --confirm first to regenerate.'
            ))
            return

        rng = self.seed_context.rng
        admin = User.objects.filter(is_staff=True).first()
        issuer = _ensure_issuer()
        leaves = _ensure_folders()
        tags = _ensure_tags()
        md_type = _doc_type(MARKDOWN, 'Documento markdown')
        _doc_type(COLLECTION_ACCOUNT, 'Cuenta de cobro')
        clients = _client_candidates()

        if not clients:
            call_command(
                'create_fake_clients_projects',
                '--count', str(max(8, min(count, 60))),
                '--seed', str(self.seed_context.seed),
                '--anchor-date', self.seed_context.anchor_date.isoformat(),
                verbosity=0,
            )
            clients = _client_candidates()
        if not clients:
            raise RuntimeError('No project-backed clients are available for documents.')

        signable_count = 2 if count >= 3 else 0
        n_markdown = max(1, count // 3 - signable_count)
        n_collection = max(0, count - n_markdown - signable_count)

        eligible_incomes = _collection_income_candidates()
        if len(eligible_incomes) < n_collection:
            call_command(
                'create_fake_accounting',
                # Two unpaid rows in each 24-row cycle have a project.
                '--count', str(max(count, 60, n_collection * 12 + 12)),
                '--seed', str(self.seed_context.seed),
                '--anchor-date', self.seed_context.anchor_date.isoformat(),
                verbosity=0,
            )
            eligible_incomes = _collection_income_candidates()
            clients = _client_candidates()
        if len(eligible_incomes) < n_collection:
            raise RuntimeError(
                f'Need {n_collection} eligible incomes for collection accounts; '
                f'found {len(eligible_incomes)}.',
            )
        created_md = 0
        created_ca = 0

        # ── Markdown documents ────────────────────────────────────────────
        md_folders = [f for f in leaves if f.name in ('Manuales', 'Anexos')] or leaves
        for i in range(n_markdown):
            title_base, body = MARKDOWN_DOCS[i % len(MARKDOWN_DOCS)]
            cycle = i // len(MARKDOWN_DOCS)
            title = f'{title_base}{" v" + str(cycle + 1) if cycle else ""}'
            status = rng.choices(
                [Document.Status.PUBLISHED, Document.Status.DRAFT, Document.Status.ARCHIVED],
                weights=[6, 3, 1],
            )[0]
            project, client_user = rng.choice(clients)
            profile = getattr(client_user, 'profile', None)
            client_name = build_client_display_name(profile) if profile else ''
            doc = Document(
                uuid=self.seed_context.uuid(f'markdown-{i}'),
                document_type=md_type,
                folder=(rng.choice(md_folders) if i % 2 == 0 else None),
                title=title,
                status=status,
                is_client_visible=(status == Document.Status.PUBLISHED),
                content_markdown=body,
                language=Document.Language.ES,
                project=project,
                client_user=client_user,
                client_name=client_name,
                client_email_subject=(
                    f'Entrega de {title}' if i % 3 == 0 else ''
                ),
                client_email_body=(
                    'Buen día:\n\nLe compartimos el documento para su revisión. '
                    'Quedamos atentos a sus comentarios.' if i % 3 == 0 else ''
                ),
                client_whatsapp_message=(
                    'Buen día. Le enviamos un correo con el documento y los '
                    'puntos que puede revisar. Quedamos atentos.' if i % 3 == 0 else ''
                ),
                client_custom_notes=(
                    [
                        {
                            'title': 'Seguimiento de entrega',
                            'content': (
                                'Confirmar la recepción y registrar los '
                                'comentarios del cliente.'
                            ),
                        },
                        {
                            'title': 'Próximo paso',
                            'content': 'Agendar la revisión final cuando el cliente responda.',
                        },
                    ]
                    if i % 4 == 0 else []
                ),
                created_by=admin,
                updated_by=admin,
            )
            # Los documentos fake deben ser descargables como PDF igual que los
            # reales: sin `content_json` el bug queda invisible al probar.
            doc.content_json = build_content_json(doc, body)
            doc.save()
            doc.tags.add(*rng.sample(tags, k=rng.randint(1, 2)))
            self._apply_markdown_workflow(doc, i, admin)
            created_md += 1

        # ── Collection accounts ───────────────────────────────────────────
        from accounts.management.commands._billing_seed_helpers import billing_seed_actor, collection_context_for_seed
        billing_actor = billing_seed_actor(admin)
        # Lifecycle buckets across the generated accounts.
        lifecycles = self._lifecycle_plan(n_collection)

        for i in range(n_collection):
            lifecycle = lifecycles[i]
            income = eligible_incomes[i]
            project = income.project
            client_user = income.client.user
            concept = BILLING_CONCEPTS[i % len(BILLING_CONCEPTS)]
            currency = 'COP'
            account_data = {
                'uuid': self.seed_context.uuid(f'collection-account-{i}'),
                'client_profile_id': income.client_id,
                'income_record_id': income.pk,
                'billing_concept': concept,
                'currency': currency,
                'city': 'Bogotá',
                'notes': 'Generado para demo local.',
                'terms_and_conditions': (
                    'Pago dentro del plazo indicado. Valores en pesos colombianos.'
                ),
                'payment_term_days': rng.choice([8, 15, 30]),
                'items': [{
                    'description': concept,
                    'quantity': Decimal('1'),
                    'amount': income.total_amount,
                    'amount_mode': 'vat_included',
                }],
            }
            account_data.update(collection_context_for_seed(project, i, context=self.seed_context, actor=billing_actor))
            if lifecycle == 'draft':
                doc = ca_create_service.create_income_collection_account_draft(
                    account_data,
                    acting_user=billing_actor,
                )
            else:
                issue_age_days = {
                    'issued': 5,
                    'overdue': rng.choice([45, 90]),
                }.get(lifecycle, rng.choice([15, 45, 90]))
                doc = ca_create_service.create_income_collection_account(
                    account_data,
                    acting_user=billing_actor,
                    issued_on=self.seed_context.anchor_date - timedelta(
                        days=issue_age_days,
                    ),
                )
            doc.tags.add(*rng.sample(tags, k=rng.randint(1, 2)))
            self._apply_income_lifecycle(doc, lifecycle, admin)
            created_ca += 1

        # ── Client-portal signable contracts (unsigned + signed) ─────────────
        self._create_signable_documents(
            admin, md_type, leaves, target_count=signable_count,
        )

        # ── Estado archivado de demo ────────────────────────────────────────
        archived = self._archive_demo_state(leaves, md_type, admin)

        # ── Hilos documentales ──────────────────────────────────────────────
        thread_count = self._create_document_threads(admin)

        self.stdout.write(self.style.SUCCESS(
            f'Documents created: {created_md} markdown + {created_ca} collection accounts. '
            f'Issuer "{issuer.name}", {len(leaves)} leaf folders, {len(tags)} tags. '
            f'Archivados de demo: {archived}. Hilos documentales: {thread_count}.'
        ))

    # ── helpers ────────────────────────────────────────────────────────────

    def _apply_markdown_workflow(self, document, index, actor):
        """Populate realistic concurrent state episodes for UI validation."""
        now = self.seed_context.anchor_now
        draft = document.state_episodes.filter(
            state__system_key='draft', closed_at__isnull=True,
        ).first()
        if draft:
            correct_opened_at(draft, now - timedelta(days=20), actor=actor)

        scenario = index % 6
        cycle_key = {
            0: 'draft',
            1: 'sent',
            2: 'in_review',
            3: 'sent',
            4: 'sent',
            5: 'closed',
        }[scenario]
        if cycle_key != 'draft':
            state = DocumentState.objects.filter(system_key=cycle_key).first()
            if state:
                open_state(
                    document,
                    state,
                    actor=actor,
                    opened_at=now - timedelta(days=12 if cycle_key == 'sent' else 5),
                )

        if scenario == 0:
            create_note(
                document,
                title='Prueba temporal 1',
                content='Observación de prueba pendiente de limpiar.',
                actor=actor,
            )
            create_note(
                document,
                title='Prueba temporal 2',
                content='Duplicado de prueba para validar la limpieza masiva.',
                actor=actor,
            )
            return

        if scenario not in (3, 4):
            return
        note = create_note(
            document,
            title='Observación del cliente',
            content='Ajustar el dato señalado antes del siguiente envío.',
            actor=actor,
            mark_needs_fix=True,
        )
        if note.episode:
            correct_opened_at(
                note.episode, now - timedelta(days=3), actor=actor,
            )
        if scenario == 4:
            finish_note(
                note,
                actor=actor,
                resolution_note='Dato corregido y verificado.',
                close_linked_state=True,
                move_cycle_to_bug_attended=True,
            )
            restored = create_note(
                document,
                title='Texto recuperado',
                content='Ejemplo de una observación restaurada desde la papelera.',
                actor=actor,
            )
            delete_notes(document, note_ids=[restored.id], actor=actor)
            restore_note(restored, actor=actor)
        else:
            test_notes = [
                create_note(
                    document,
                    title=f'Prueba eliminada {number}',
                    content='Ruido de prueba conservado sólo en la papelera recuperable.',
                    actor=actor,
                )
                for number in (1, 2)
            ]
            delete_notes(
                document,
                note_ids=[item.id for item in test_notes],
                actor=actor,
            )

    def _archive_demo_state(self, leaves, md_type, admin):
        """Deja archivados de demo que cubren los casos que la UI debe mostrar.

        Usa el servicio real (no escribe los campos a mano) para que la data
        generada ejercite la misma cascada que el panel. Incluye a propósito el
        caso de la memoria: un documento archivado A MANO dentro de una carpeta
        que después se archiva entera — al desarchivar la carpeta ese debe
        quedarse archivado, y sin este fixture no es observable en QA ni E2E.
        """
        from datetime import timedelta

        from content.services import document_archive_service as archive_svc

        summary = []

        # 1. Documentos archivados sueltos, en carpetas que siguen activas:
        #    demuestran que los contadores de carpeta excluyen lo archivado.
        loose = list(
            Document.objects.filter(
                document_type=md_type, is_archived=False, folder__isnull=False,
            ).order_by('id')[:3]
        )
        for doc in loose:
            archive_svc.archive_document(doc)
        summary.append(f'{len(loose)} sueltos')

        # 2. Una carpeta CON contenido archivada en cascada, con un documento
        #    previamente archivado a mano dentro.
        target = next(
            (
                f for f in leaves
                if not f.is_archived
                and Document.objects.filter(folder=f, is_archived=False).count() >= 2
            ),
            None,
        )
        if target:
            pre_archived = (
                Document.objects
                .filter(folder=target, is_archived=False)
                .order_by('id')
                .first()
            )
            archive_svc.archive_document(pre_archived)
            counts = archive_svc.archive_folder(target)
            summary.append(
                f'carpeta "{target.name}" (+{counts["documents"]} docs, '
                f'1 pre-archivado que NO debe volver)'
            )

        # 3. Un subárbol archivado de DOS niveles. Sin él, la vista de
        #    archivados no tiene nada que navegar: la carpeta se vería como
        #    contenedor pero no habría subcarpeta adentro a la que entrar, ni
        #    forma de comprobar que restaurar algo de dentro reabre la cadena.
        nested_parent = next(
            (
                f for f in DocumentFolder.objects.filter(
                    is_archived=False,
                    parent__isnull=True,
                    managed_project__isnull=True,
                )
                if DocumentFolder.objects.filter(parent=f, is_archived=False).exists()
                and f.pk != getattr(target, 'pk', None)
            ),
            None,
        )
        if nested_parent:
            counts = archive_svc.archive_folder(nested_parent)
            summary.append(
                f'subárbol "{nested_parent.name}" '
                f'(+{counts["folders"]} subcarpetas, +{counts["documents"]} docs)'
            )

        # 4. Escalonar las fechas para que el orden Recientes/Más antiguos sea
        #    demostrable: el servicio siempre estampa `timezone.now()`.
        now = self.seed_context.anchor_now
        for offset_days, doc_ids in (
            (1, [d.pk for d in loose[:1]]),
            (7, [d.pk for d in loose[1:2]]),
            (30, [d.pk for d in loose[2:3]]),
        ):
            if doc_ids:
                Document.objects.filter(pk__in=doc_ids).update(
                    archived_at=now - timedelta(days=offset_days),
                )

        return ', '.join(summary) if summary else 'ninguno'

    def _create_document_threads(self, actor):
        """Create cross-folder histories with archived and generated records."""
        if DocumentThread.objects.exists():
            return DocumentThread.objects.count()

        sources = Document.objects.filter(metadata__billing_fixture='source').values('pk')
        available = list(
            Document.objects.exclude(pk__in=sources).select_related('document_type')
            .order_by('id')
        )
        used = set()
        scenarios = []

        # Different association signatures prove that a thread is not owned by
        # a folder, client or project.
        cross_scope = []
        signatures = set()
        for document in available:
            signature = (
                document.folder_id,
                document.client_user_id,
                document.project_id,
            )
            if signature in signatures:
                continue
            cross_scope.append(document)
            signatures.add(signature)
            if len(cross_scope) == 3:
                break
        if len(cross_scope) >= 2:
            scenarios.append(('Entrega, revisión y aprobación', cross_scope))
            used.update(document.pk for document in cross_scope)

        generated = next((
            document for document in available
            if document.pk not in used
            and document.document_type
            and document.document_type.code == COLLECTION_ACCOUNT
            and document.commercial_status != Document.CommercialStatus.DRAFT
        ), None)
        ordinary = next((
            document for document in available
            if document.pk not in used
            and document.document_type
            and document.document_type.code == MARKDOWN
            and not document.is_archived
        ), None)
        if ordinary is None:
            ordinary = next((
                document for document in available
                if document.pk not in used
                and document.document_type
                and document.document_type.code == MARKDOWN
            ), None)
        if generated and ordinary:
            scenarios.append(('Soporte de entrega y cuenta emitida', [ordinary, generated]))
            used.update((ordinary.pk, generated.pk))

        archived = next((
            document for document in available
            if document.pk not in used and document.is_archived
        ), None)
        active = [
            document for document in available
            if document.pk not in used and not document.is_archived
        ][:2]
        if archived and active:
            scenarios.append(('Antecedentes archivados y corrección', [archived, *active]))

        offsets = (45, 18, 3)
        for title, documents in scenarios:
            create_document_thread(
                title=title,
                items=[
                    {
                        'document_id': document.pk,
                        'occurred_on': (
                            self.seed_context.anchor_date
                            - timedelta(days=offsets[index % len(offsets)])
                        ),
                    }
                    for index, document in enumerate(documents)
                ],
                actor=actor,
            )
        return len(scenarios)

    # Repeating cycle with business-realistic weights: ~1 draft, 4 issued,
    # 6 paid, 2 overdue, 1 cancelled per 14 accounts.
    _LIFECYCLE_CYCLE = (
        ['draft'] + ['issued'] * 4 + ['paid'] * 6 + ['overdue'] * 2 + ['cancelled']
    )

    def _lifecycle_plan(self, n):
        """Spread accounts across lifecycle states with business-realistic weights."""
        cycle = self._LIFECYCLE_CYCLE
        return [cycle[i % len(cycle)] for i in range(n)]

    def _apply_income_lifecycle(self, document, lifecycle, actor):
        """Apply only real post-issuance transitions to a coherent fixture."""
        if lifecycle == 'paid':
            ca_service.mark_collection_account_paid(document, acting_user=actor)
        elif lifecycle == 'cancelled':
            ca_service.mark_collection_account_cancelled(document, acting_user=actor)

    def _create_signable_documents(self, admin, md_type, leaves, *, target_count):
        """Create one unsigned + one signed contract for a project-backed client.

        Exercises the client-portal signature flow (/platform/documents): a
        published, signature-required contract the client must accept, plus an
        already-signed sibling carrying the acceptance stamp. Idempotent — guarded
        by (title, project, requires_signature) so re-runs never duplicate.
        """
        if target_count <= 0:
            return

        project = (
            Project.objects.filter(client__isnull=False)
            .select_related('client')
            .order_by('id')
            .first()
        )
        if not project or not project.client_id:
            self.stdout.write(self.style.WARNING(
                '  No project-backed client found — skipping signable documents. '
                'Run seed_platform_data first.'
            ))
            return

        client_user = project.client
        client_full_name = (
            (getattr(client_user, 'get_full_name', lambda: '')() or '').strip()
            or client_user.email
        )
        contract_folder = (
            next((f for f in leaves if f.name == 'Contratos'), None)
            or (leaves[0] if leaves else None)
        )

        created = 0

        # Unsigned, signature-required contract (client must sign in the portal).
        unsigned_title = 'Contrato de servicios'
        if target_count >= 1 and not Document.objects.filter(
            title=unsigned_title, project=project, requires_signature=True,
        ).exists():
            unsigned = Document(
                uuid=self.seed_context.uuid('signable-unsigned'),
                document_type=md_type,
                folder=contract_folder,
                title=unsigned_title,
                status=Document.Status.PUBLISHED,
                is_client_visible=True,
                language=Document.Language.ES,
                content_markdown=(
                    '# Contrato de servicios\n\n'
                    'Contrato de prestación de servicios de desarrollo web. '
                    'Por favor revise y firme para dar inicio al proyecto.\n'
                ),
                project=project,
                client_user=client_user,
                client_name=client_full_name,
                requires_signature=True,
                created_by=admin,
                updated_by=admin,
            )
            unsigned.content_json = build_content_json(unsigned)
            unsigned.save()
            created += 1

        # Already-signed contract (acceptance stamp filled in).
        signed_title = 'Contrato de servicios firmado'
        if target_count >= 2 and not Document.objects.filter(
            title=signed_title, project=project, requires_signature=True,
        ).exists():
            signed = Document(
                uuid=self.seed_context.uuid('signable-signed'),
                document_type=md_type,
                folder=contract_folder,
                title=signed_title,
                status=Document.Status.PUBLISHED,
                is_client_visible=True,
                language=Document.Language.ES,
                content_markdown=(
                    '# Contrato de servicios\n\n'
                    'Contrato de prestación de servicios de desarrollo web '
                    '(aceptado por el cliente).\n'
                ),
                project=project,
                client_user=client_user,
                client_name=client_full_name,
                requires_signature=True,
                signed_at=self.seed_context.anchor_now,
                signed_by=client_user,
                signature_name=client_full_name,
                signature_ip='127.0.0.1',
                signature_user_agent='Mozilla/5.0 (fake-data)',
                created_by=admin,
                updated_by=admin,
            )
            signed.content_json = build_content_json(signed)
            signed.save()
            created += 1

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'  Signable documents created: {created} '
                f'(client "{client_full_name}", project "{project.name}").'
            ))
        else:
            self.stdout.write('  Signable documents already present — skipped.')
