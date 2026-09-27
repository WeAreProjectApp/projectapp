import random
import uuid

from copy import deepcopy
from datetime import timedelta

from django.core.management.base import BaseCommand

from accounts.models import UserProfile
from content.demo_technical_document import DEMO_TECHNICAL_DOCUMENT_JSON
from django.core.files.base import ContentFile

from accounts.services import proposal_client_service
from content.models import (
    BusinessProposal,
    ContractTemplate,
    EmailLog,
    ProposalAlert,
    ProposalChangeLog,
    ProposalDocument,
    ProposalProjectStage,
    ProposalSection,
    ProposalSectionView,
    ProposalShareLink,
    ProposalViewEvent,
)
from content.services.hour_package_service import (
    seed_commercial_conditions_from_catalog,
)
from content.services.proposal_service import ProposalService
from content.services.proposal_stage_tracker import ProposalStageTracker
from content.fake_data import (
    add_seed_arguments,
    ensure_fake_data_allowed,
    seed_context,
    seed_global_random,
)

# Pool of realistic client data for random selection
CLIENT_NAMES = [
    'María García', 'Carlos Rodríguez', 'John Smith', 'Ana López',
    'Pedro Martínez', 'Laura Sánchez', 'Diego Torres', 'Valentina Ríos',
    'Santiago Herrera', 'Camila Vargas', 'Andrés Moreno', 'Isabella Cruz',
    'Felipe Ramírez', 'Daniela Ortiz', 'Mateo Gutiérrez', 'Sofía Mendoza',
    'Julián Castro', 'Paula Jiménez', 'Nicolás Rojas', 'Mariana Díaz',
]

CLIENT_PHONES = [
    '+573001234567', '+573109876543', '+573205551234', '+573154443322',
    '+573187776655', '+14155551234', '+573001112233', '+573209998877',
    '', '', '',  # some without phone
]

CLIENT_COMPANIES = [
    'Acme Corp', 'Globex Industries', 'Initech Solutions',
    'Umbrella Group', 'Stark Enterprises', 'Wayne Industries',
    'Soylent Foods', 'Hooli', 'Pied Piper', 'Aperture Science',
    'Tierra Viva S.A.S.', 'Constructora del Norte',
    'Clínica San Rafael', 'Logística Andina',
    '', '', '',  # some without company
]

PROJECT_TYPE_CHOICES = ['website', 'ecommerce', 'webapp', 'landing', 'redesign', 'other']
MARKET_TYPE_CHOICES = ['b2b', 'b2c', 'saas', 'retail', 'services', 'health', 'education', 'real_estate', 'other']

PROJECT_TYPES = [
    ('Landing Profesional', 3500000, 'COP'),
    ('E-Commerce — Tienda Online', 8500000, 'COP'),
    ('SaaS Dashboard', 5000, 'USD'),
    ('Portafolio Creativo', 2800000, 'COP'),
    ('Plataforma Educativa', 12000000, 'COP'),
    ('App Corporativa', 7500, 'USD'),
    ('Blog + SEO', 1900000, 'COP'),
    ('Marketplace MVP', 15000000, 'COP'),
    ('Sistema de Reservas', 4200000, 'COP'),
    ('Web Institucional', 3000000, 'COP'),
]

REJECTION_REASONS = [
    'budget', 'timing', 'chose_competitor', 'scope_mismatch',
    'internal_changes', 'other',
]

REJECTION_COMMENTS = [
    'El presupuesto excede lo aprobado por dirección.',
    'Decidimos postergar el proyecto hasta el próximo trimestre.',
    'Fuimos con otra agencia que ofrecía un paquete más completo.',
    'El alcance no cubre lo que necesitamos actualmente.',
    'Hubo cambios internos y el proyecto ya no es prioridad.',
    '',
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) Safari/17.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148',
    'Mozilla/5.0 (Linux; Android 14) Chrome/120.0 Mobile',
    'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) Safari/17.0',
]

# Aligned with ProposalService.get_hardcoded_defaults('es') for synthetic ProposalSectionView rows.
SECTION_TYPES = [
    (s['section_type'], s['title'])
    for s in ProposalService.get_hardcoded_defaults(language='es')
]

# Sections shown per view mode (mirrors displayPanels logic in proposal/[uuid]/index.vue).
# Technical mode shows only the technical document panels; commercial modes skip it.
_TECHNICAL_SECTION_TYPES = [
    ('technical_document', 'Detalle Técnico'),
    ('technical_document_public', 'Arquitectura / Stack'),
]
_LEGAL_SECTION_TYPES = [
    ('contract_terms_overview', 'Contrato y condiciones'),
    ('contract_terms_document', 'Borrador del contrato'),
]
_COMMERCIAL_SECTION_TYPES = [
    (st, title) for st, title in SECTION_TYPES if st != 'technical_document'
]

# Realistic distribution of view mode selection by clients.
_VIEW_MODE_POPULATION = ['executive', 'executive', 'executive',
                          'detailed', 'detailed', 'detailed', 'detailed', 'detailed',
                          'technical', 'technical', 'legal']
_VIEW_MODE_LABELS = {
    'executive': 'ejecutiva',
    'detailed': 'completa',
    'technical': 'técnica',
    'legal': 'contractual',
}

ALERT_TYPES = [
    'reminder', 'followup', 'call', 'meeting', 'custom',
    'discount_suggestion', 'post_expiration_visit',
]

STATUSES = list(BusinessProposal.Status.values)

# Contract data for proposals in negotiation or accepted, so the Documents tab
# can generate the single contract or the product and service contracts.
FAKE_CONTRACTOR_PARAMS = {
    'contract_source': 'default',
    'contractor_full_name': 'Project App S.A.S.',
    'contractor_nit': '900.000.000-0',
    'contractor_email': 'contratos@example.com',
    'bank_name': 'Banco de Pruebas',
    'bank_account_type': 'Ahorros',
    'bank_account_number': '000-000000-00',
    'contract_city': 'Medellín',
    'service_initial_term': 'doce (12) meses',
    'service_renewal_notice_days': 'treinta (30)',
    'service_termination_notice_days': 'treinta (30)',
}


class Command(BaseCommand):
    help = (
        'Create fake business proposals with all default sections; technical_document uses '
        'demo content for dev (public technical mode + panel JSON).'
    )

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=10)

    def handle(self, *args, **options):
        ensure_fake_data_allowed('create_fake_proposals')
        context = seed_context(options, 'proposals')
        self.seed_context = context
        seed_global_random(context)
        count = options['count']
        now = context.anchor_now
        existing_clients = list(UserProfile.objects.clients().order_by('pk'))
        # The canonical --replace flow starts from the same graph and therefore
        # always uses generation zero. Direct additive runs remain supported by
        # the historical command and receive a deterministic next generation.
        generation = BusinessProposal.objects.count() // max(1, count)

        created = 0
        for i in range(count):
            status = STATUSES[i % len(STATUSES)]
            existing_client = (
                existing_clients[i % len(existing_clients)]
                if existing_clients else None
            )
            client_name = (
                existing_client.user.get_full_name()
                or existing_client.company_name
                or existing_client.user.email
                if existing_client else CLIENT_NAMES[i % len(CLIENT_NAMES)]
            )
            project_type, investment, currency = PROJECT_TYPES[i % len(PROJECT_TYPES)]
            discount = random.choice([0, 10, 15, 20, 25])

            lang = random.choices(['es', 'en'], weights=[0.7, 0.3])[0]

            chosen_project_type = random.choice(PROJECT_TYPE_CHOICES)
            chosen_market_type = random.choice(MARKET_TYPE_CHOICES)

            data = {
                'uuid': context.uuid(f'proposal-{generation}-{i}'),
                'title': f'Propuesta {project_type} — {client_name.split()[0]}',
                'client_name': client_name,
                'client_email': (
                    existing_client.user.email if existing_client
                    else f'{client_name.split()[0].lower()}@example.com'
                ),
                'client_phone': (
                    existing_client.phone if existing_client
                    else random.choice(CLIENT_PHONES)
                ),
                'total_investment': investment,
                'currency': currency,
                'nationality': (
                    'COL' if currency == 'COP'
                    else random.choice(['EXT', 'USA'])
                ),
                'status': status,
                'discount_percent': discount,
                'expires_at': now + timedelta(days=random.randint(7, 45)),
                'language': lang,
                'project_type': chosen_project_type,
                'market_type': chosen_market_type,
                'email_intro': (
                    f'Esta propuesta resuelve para {client_name.split()[0]} la falta '
                    f'de una solución de {project_type.lower()}, mediante un alcance '
                    'claro de diseño, desarrollo, pruebas y despliegue, para reducir '
                    'reprocesos y acelerar la puesta en marcha del negocio.'
                ),
            }

            # Fill custom text when type is 'other'
            if chosen_project_type == 'other':
                data['project_type_custom'] = random.choice([
                    'Portal interno corporativo',
                    'Herramienta de gestión de inventarios',
                    'Sistema de turnos médicos',
                    'Plataforma de crowdfunding',
                ])
            if chosen_market_type == 'other':
                data['market_type_custom'] = random.choice([
                    'Agroindustria',
                    'Logística y transporte',
                    'Turismo y hotelería',
                    'ONG y fundaciones',
                ])

            # ~20% of non-draft proposals have automations paused
            if status != 'draft' and random.random() < 0.2:
                data['automations_paused'] = True

            # Negotiated deals carry contract data; every other cycle of
            # statuses closes with two documents (product + service).
            if status in ('negotiating', 'accepted'):
                data['contract_params'] = {
                    **FAKE_CONTRACTOR_PARAMS,
                    'client_full_name': client_name,
                    'client_cedula': f'1.000.{i:03d}.000',
                    'client_email': data['client_email'],
                    'contract_date': now.date().isoformat(),
                }
                if (i // len(STATUSES)) % 2:
                    data['contract_modality'] = BusinessProposal.ContractModality.SPLIT

            # Set realistic lifecycle fields per status
            if status == 'sent':
                data['sent_at'] = now - timedelta(days=random.randint(1, 5))
                data['last_activity_at'] = data['sent_at']
            elif status == 'viewed':
                data['sent_at'] = now - timedelta(days=random.randint(5, 10))
                data['first_viewed_at'] = now - timedelta(days=random.randint(1, 4))
                data['view_count'] = random.randint(1, 8)
                data['last_activity_at'] = data['first_viewed_at']
            elif status == 'accepted':
                data['sent_at'] = now - timedelta(days=random.randint(10, 20))
                data['first_viewed_at'] = now - timedelta(days=random.randint(5, 9))
                data['view_count'] = random.randint(3, 15)
                data['responded_at'] = now - timedelta(days=random.randint(1, 4))
                data['last_activity_at'] = data['responded_at']
            elif status == 'rejected':
                data['sent_at'] = now - timedelta(days=random.randint(10, 20))
                data['first_viewed_at'] = now - timedelta(days=random.randint(5, 9))
                data['view_count'] = random.randint(1, 5)
                data['responded_at'] = now - timedelta(days=random.randint(1, 4))
                data['rejection_reason'] = random.choice(REJECTION_REASONS)
                data['rejection_comment'] = random.choice(REJECTION_COMMENTS)
                data['last_activity_at'] = data['responded_at']
            elif status == 'negotiating':
                data['sent_at'] = now - timedelta(days=random.randint(5, 15))
                data['first_viewed_at'] = now - timedelta(days=random.randint(2, 4))
                data['view_count'] = random.randint(2, 10)
                data['responded_at'] = now - timedelta(days=random.randint(0, 2))
                data['last_activity_at'] = data['responded_at']
            elif status == 'expired':
                data['sent_at'] = now - timedelta(days=random.randint(30, 60))
                data['first_viewed_at'] = now - timedelta(days=random.randint(20, 29))
                data['view_count'] = random.randint(0, 3)
                data['expires_at'] = now - timedelta(days=random.randint(1, 10))
                data['last_activity_at'] = data.get('first_viewed_at') or data['sent_at']
            elif status == 'finished':
                # finished = accepted, then aged through the execution phase
                data['sent_at'] = now - timedelta(days=random.randint(45, 90))
                data['first_viewed_at'] = now - timedelta(days=random.randint(40, 80))
                data['view_count'] = random.randint(5, 20)
                data['responded_at'] = now - timedelta(days=random.randint(35, 70))
                data['last_activity_at'] = data['responded_at']

            # Resolve/create the canonical client profile so the new client FK
            # on BusinessProposal is populated. get_or_create_client_for_proposal
            # reuses existing profiles by email (case-insensitive), so repeated
            # CLIENT_NAMES share a single UserProfile — mirroring production.
            data['client'] = existing_client or (
                proposal_client_service.get_or_create_client_for_proposal(
                    name=client_name,
                    email=data['client_email'],
                    phone=data.get('client_phone', ''),
                    company=random.choice(CLIENT_COMPANIES),
                )
            )

            if i == count - 1:
                data['title'] = ('PropuestaExtremaSinEspacios' * 12)[:255]

            proposal = BusinessProposal.objects.create(**data)
            self.stdout.write(
                self.style.SUCCESS(
                    f'[{status:>8}] {proposal}'
                )
            )

            # --- Generate engagement data for non-draft proposals ---
            if status != 'draft':
                self._create_engagement_data(proposal, now)

            # --- Generate alerts for some proposals ---
            if status in ('sent', 'viewed', 'rejected', 'expired') and random.random() < 0.4:
                self._create_alerts(proposal, now)

            # --- Generate calculator interaction logs ---
            if status in ('viewed', 'accepted', 'negotiating') and random.random() < 0.5:
                self._create_calculator_logs(proposal)

            # --- Generate seller activity logs ---
            if status in ('viewed', 'accepted', 'negotiating', 'rejected') and random.random() < 0.6:
                self._create_seller_activity_logs(proposal, now)

            # --- Generate email history for proposals with email tabs ---
            if status in ('negotiating', 'accepted'):
                self._create_email_history(proposal, now)

            # --- Seed project stage rows for accepted/finished proposals ---
            if status in ('accepted', 'finished'):
                self._create_project_stages(proposal, now, status)

            # Create default sections (groups now stored in content_json)
            default_sections = ProposalService.get_default_sections(language=lang)
            for section_cfg in default_sections:
                cfg = deepcopy(section_cfg)
                if cfg['section_type'] == 'greeting':
                    cfg['content_json']['clientName'] = proposal.client_name
                if cfg['section_type'] == 'investment':
                    total = float(investment)
                    cur = currency
                    fmt = lambda n: f'${n:,.0f}'
                    cfg['content_json']['totalInvestment'] = fmt(total)
                    cfg['content_json']['currency'] = cur
                    cfg['content_json']['paymentOptions'] = [
                        {'label': f'40% al firmar el contrato ✍️', 'description': f'{fmt(total * 0.4)} {cur}'},
                        {'label': f'30% al aprobar el diseño final ✅', 'description': f'{fmt(total * 0.3)} {cur}'},
                        {'label': f'30% al desplegar el sitio web 🚀', 'description': f'{fmt(total * 0.3)} {cur}'},
                    ]
                if cfg['section_type'] == 'technical_document':
                    cfg['content_json'] = deepcopy(DEMO_TECHNICAL_DOCUMENT_JSON)
                if cfg['section_type'] == 'commercial_conditions':
                    cfg['content_json'] = seed_commercial_conditions_from_catalog(
                        cfg['content_json'],
                        nationality=proposal.nationality,
                        language=proposal.language,
                    )
                    # Leave the first proposal on a per-proposal manual rate so
                    # the «Tarifa por hora» tab has non-auto fake data to show:
                    # a raised base rate plus one package priced on its own.
                    if created == 0:
                        packages = cfg['content_json'].get('packages') or []
                        base = float(cfg['content_json'].get('hourlyRate') or 0)
                        cfg['content_json']['hourPackagesMode'] = 'manual'
                        cfg['content_json']['manualHourlyRate'] = round(base * 1.5) or 45000
                        cfg['content_json']['manualCurrency'] = (
                            cfg['content_json'].get('currency') or 'COP'
                        )
                        if packages and packages[-1].get('id') is not None:
                            cfg['content_json']['manualPackageRates'] = [{
                                'packageId': packages[-1]['id'],
                                'hourlyRate': round(base * 1.2) or 36000,
                            }]
                ProposalSection.objects.create(proposal=proposal, **cfg)

            # --- Seed a ProposalDocument for negotiating proposals ---
            if status == 'negotiating':
                self._seed_proposal_documents(proposal)

            created += 1

        # Ensure a default ContractTemplate exists
        self._ensure_contract_template()

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone: created {created} fake proposals '
                f'(statuses: {", ".join(STATUSES)}).'
            )
        )

    def _ensure_contract_template(self):
        """Create a default ContractTemplate if none exists."""
        if ContractTemplate.objects.filter(is_default=True).exists():
            return
        ContractTemplate.objects.create(
            name='Contrato Estándar',
            content_markdown=(
                '# CONTRATO DE PRESTACIÓN DE SERVICIOS\n\n'
                'Entre **{client_full_name}** (C.C. {client_cedula}) y '
                '**{contractor_full_name}** (NIT {contractor_nit}).\n\n'
                '**Correo contratante:** {client_email}\n\n'
                '**Correo contratista:** {contractor_email}\n\n'
                '**Ciudad:** {contract_city}\n\n'
                '**Banco:** {bank_name} — {bank_account_type} {bank_account_number}\n'
            ),
            service_content_markdown=(
                'Entre **{client_full_name}** (C.C. {client_cedula}) y '
                '**{contractor_full_name}** (NIT {contractor_nit}), servicio de hosting, '
                'mantenimiento y soporte por {service_initial_term}.\n'
            ),
            is_default=True,
        )
        self.stdout.write(self.style.SUCCESS('  Created default ContractTemplate'))

    def _seed_proposal_documents(self, proposal):
        """Seed one uploaded and one generated ProposalDocument for a proposal."""
        if ProposalDocument.objects.filter(proposal=proposal).exists():
            return
        # Uploaded document
        doc = ProposalDocument.objects.create(
            proposal=proposal,
            document_type=ProposalDocument.DOC_TYPE_LEGAL_ANNEX,
            title='Anexo legal de prueba',
            is_generated=False,
        )
        doc.file.save('anexo-legal.pdf', ContentFile(b'%PDF-1.4 fake annex'), save=True)

    def _create_engagement_data(self, proposal, now):
        """Generate ViewEvents, SectionViews, ChangeLogs, and ShareLinks."""
        sent_at = proposal.sent_at or (now - timedelta(days=10))

        # --- ViewEvents + SectionViews ---
        num_sessions = proposal.view_count or random.randint(1, 4)
        ips = [f'192.168.1.{random.randint(10, 250)}' for _ in range(3)]
        for s in range(min(num_sessions, 6)):
            session_time = sent_at + timedelta(
                days=random.randint(0, 5),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            view_mode = random.choice(_VIEW_MODE_POPULATION)
            event = ProposalViewEvent.objects.create(
                proposal=proposal,
                session_id=uuid.uuid4().hex[:16],
                ip_address=random.choice(ips),
                user_agent=random.choice(USER_AGENTS),
                view_mode=view_mode,
            )
            event.viewed_at = session_time
            ProposalViewEvent.objects.filter(pk=event.pk).update(
                viewed_at=session_time,
            )

            if view_mode == 'technical':
                sections_for_mode = _TECHNICAL_SECTION_TYPES
            elif view_mode == 'legal':
                sections_for_mode = _LEGAL_SECTION_TYPES
            else:
                sections_for_mode = _COMMERCIAL_SECTION_TYPES
            for sect_type, sect_title in sections_for_mode:
                subsection_key = ''
                if sect_type == 'contract_terms_document':
                    subsection_key = f'clause-{random.randint(1, 12):02d}'
                ProposalSectionView.objects.create(
                    view_event=event,
                    section_type=sect_type,
                    section_title=sect_title,
                    subsection_key=subsection_key,
                    time_spent_seconds=round(random.uniform(3, 120), 1),
                    entered_at=session_time + timedelta(
                        seconds=random.randint(0, 300),
                    ),
                    view_mode=view_mode,
                )

        # --- ChangeLogs ---
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='created',
            description=f'Proposal created for {proposal.client_name}.',
        )
        if proposal.sent_at:
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='sent',
                description=f'Proposal sent to {proposal.client_email}.',
            )
        if proposal.first_viewed_at:
            first_mode = random.choice(_VIEW_MODE_POPULATION)
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='viewed',
                actor_type='client',
                description=f'Vista en modo {_VIEW_MODE_LABELS[first_mode]}.',
            )
        if proposal.status == 'accepted':
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='accepted',
                description='Client accepted the proposal.',
            )
        elif proposal.status == 'rejected':
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='rejected',
                description=(
                    f'Client rejected: {proposal.rejection_reason}.'
                ),
            )
        elif proposal.status == 'negotiating':
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='negotiating',
                description='Client accepted with changes — negotiation started.',
            )
        elif proposal.status == 'expired':
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='expired',
                description='Proposal expired without a response.',
            )

        # Sprinkle additional lifecycle logs for realism
        if proposal.status in ('viewed', 'accepted', 'negotiating') and random.random() < 0.3:
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='commented',
                description=random.choice([
                    'Cliente dejó un comentario: "Me interesa pero tengo dudas sobre el cronograma."',
                    'Comentario del cliente: "¿Pueden incluir soporte post-lanzamiento?"',
                    'Nota del cliente: "Necesito consultarlo con mi socio."',
                ]),
            )
        if proposal.status in ('sent', 'viewed') and random.random() < 0.15:
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='resent',
                description='Proposal re-sent to the client after updates.',
            )
        if random.random() < 0.1:
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='duplicated',
                description='Proposal duplicated as a new draft.',
            )
        if proposal.status in ('rejected', 'expired') and random.random() < 0.2:
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='reengagement',
                description=random.choice([
                    'Reengagement email sent — client showed renewed interest.',
                    'Client revisited proposal after rejection. Reengagement triggered.',
                ]),
            )

        # --- ShareLinks (50% chance for viewed/accepted/rejected) ---
        if proposal.status in ('viewed', 'accepted', 'rejected'):
            if random.random() < 0.5:
                ProposalShareLink.objects.create(
                    uuid=self.seed_context.uuid(f'proposal-share-{proposal.uuid}'),
                    proposal=proposal,
                    shared_by_name=proposal.client_name,
                    shared_by_email=proposal.client_email,
                    recipient_name=f'Socio de {proposal.client_name.split()[0]}',
                    recipient_email=f'socio.{proposal.client_name.split()[0].lower()}@example.com',
                    view_count=random.randint(0, 5),
                    first_viewed_at=(
                        now - timedelta(days=random.randint(1, 3))
                        if random.random() < 0.7 else None
                    ),
                )

    def _create_alerts(self, proposal, now):
        """Generate ProposalAlert records for the proposal."""
        alert_type = random.choice(ALERT_TYPES)
        messages = {
            'reminder': f'Recordatorio: hacer seguimiento a {proposal.client_name} esta semana.',
            'followup': f'Seguimiento pendiente con {proposal.client_name} sobre la propuesta.',
            'call': f'Llamar a {proposal.client_name} para revisar estado de la propuesta.',
            'meeting': f'Agendar reunión con {proposal.client_name} para revisión de alcance.',
            'custom': f'Nota personalizada sobre {proposal.client_name}.',
            'discount_suggestion': f'{proposal.client_name} ha visitado la propuesta varias veces. Considerar ofrecer descuento.',
            'post_expiration_visit': f'{proposal.client_name} abrió la propuesta expirada. Señal de alto interés.',
        }
        ProposalAlert.objects.create(
            proposal=proposal,
            alert_type=alert_type,
            message=messages.get(alert_type, 'Alert'),
            alert_date=now - timedelta(days=random.randint(0, 5)),
        )

    def _create_calculator_logs(self, proposal):
        """Generate calculator interaction change logs."""
        import json
        modules = [
            'pwa_module', 'ai_module', 'reports_alerts_module',
            'kpi_dashboard_module', 'email_marketing_module',
            'conversion_tracking_module', 'i18n_module', 'gift_cards_module',
        ]
        selected = random.sample(modules, k=random.randint(2, 4))
        # kpi_dashboard_module is free and selected by default
        if 'kpi_dashboard_module' not in selected:
            selected.append('kpi_dashboard_module')
        deselected = [m for m in modules if m not in selected]

        # Confirmed interaction
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='calc_confirmed',
            description=json.dumps({
                'selected': selected,
                'deselected': deselected,
                'total': float(proposal.total_investment),
            }),
        )

        # 30% chance of also having an abandoned interaction before confirming
        if random.random() < 0.3:
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='calc_abandoned',
                description=json.dumps({
                    'selected': modules,
                    'deselected': [],
                    'total': float(proposal.total_investment),
                }),
            )

    def _create_seller_activity_logs(self, proposal, now):
        """Generate seller activity change logs (call, meeting, followup, note)."""
        activity_types = ['call', 'meeting', 'followup', 'note']
        descriptions = {
            'call': [
                'Llamada de seguimiento. Cliente interesado, pide más info sobre módulo PWA.',
                'Llamada inicial para presentar la propuesta. Buena recepción.',
                'Cliente solicitó llamada para aclarar dudas sobre el cronograma.',
                'Seguimiento telefónico. Pendiente aprobación de presupuesto interno.',
            ],
            'meeting': [
                'Reunión virtual para revisión de requerimientos funcionales.',
                'Demo del dashboard de KPIs al equipo directivo del cliente.',
                'Reunión presencial. Cliente quiere agregar módulo de email marketing.',
            ],
            'followup': [
                'Email de seguimiento con resumen de la reunión.',
                'Envío de caso de éxito similar al sector del cliente.',
                'Seguimiento post-demo. Cliente evaluando internamente.',
            ],
            'note': [
                'Cliente mencionó que compara con otra agencia. Reforzar propuesta de valor.',
                'Contacto del socio del cliente pidió información adicional.',
                'Presupuesto aprobado internamente, esperando firma.',
            ],
        }
        num_activities = random.randint(1, 3)
        ref_date = proposal.sent_at or (now - timedelta(days=10))
        for _ in range(num_activities):
            act_type = random.choice(activity_types)
            desc = random.choice(descriptions[act_type])
            activity_date = ref_date + timedelta(
                days=random.randint(1, 10),
                hours=random.randint(8, 18),
            )
            log = ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type=act_type,
                description=desc,
            )
            ProposalChangeLog.objects.filter(pk=log.pk).update(
                created_at=activity_date,
            )

    def _create_project_stages(self, proposal, now, status):
        """
        Seed two `ProposalProjectStage` rows (design + development) with
        realistic scenario distribution so the admin Cronograma tab has
        meaningful data in development.

        Scenarios (picked via weighted random):
        - `unscheduled` (15%) — admin hasn't filled dates yet
        - `design_early` (15%) — design in progress, <70% elapsed
        - `design_warning` (10%) — design ≥70% elapsed, warning email sent
        - `design_overdue` (10%) — design past `end_date`, first overdue alert sent
        - `dev_in_progress` (20%) — design completed, dev mid-window
        - `dev_overdue` (10%) — design completed, dev past end (multi-reminder)
        - `both_done` (20%) — both marked completed

        `finished` proposals always get the `both_done` scenario since they
        represent a fully closed project lifecycle.
        """
        # Delegate to the canonical catalog so rows match production.
        design = ProposalStageTracker.get_or_create_stage(proposal, 'design')
        development = ProposalStageTracker.get_or_create_stage(proposal, 'development')

        if status == 'finished':
            scenario = 'both_done'
        else:
            scenarios = [
                ('unscheduled', 15),
                ('design_early', 15),
                ('design_warning', 10),
                ('design_overdue', 10),
                ('dev_in_progress', 20),
                ('dev_overdue', 10),
                ('both_done', 20),
            ]
            choices, weights = zip(*scenarios)
            scenario = random.choices(choices, weights=weights)[0]

        today = now.date()
        design_duration_days = random.randint(7, 21)
        dev_duration_days = random.randint(14, 42)

        if scenario == 'unscheduled':
            # Both rows exist but no dates — exercises the "pending" UI state.
            return

        if scenario == 'design_early':
            # ~30% of design duration elapsed, no warning yet.
            elapsed = max(1, int(design_duration_days * 0.3))
            design.start_date = today - timedelta(days=elapsed)
            design.end_date = design.start_date + timedelta(days=design_duration_days)
            design.save(update_fields=['start_date', 'end_date', 'updated_at'])
            return

        if scenario == 'design_warning':
            # 80% elapsed, warning sent 1 day ago.
            elapsed = max(2, int(design_duration_days * 0.8))
            design.start_date = today - timedelta(days=elapsed)
            design.end_date = design.start_date + timedelta(days=design_duration_days)
            design.warning_sent_at = now - timedelta(days=1)
            design.save(update_fields=[
                'start_date', 'end_date', 'warning_sent_at', 'updated_at',
            ])
            return

        if scenario == 'design_overdue':
            # Ended 3 days ago, first overdue reminder sent today.
            design.start_date = today - timedelta(days=design_duration_days + 3)
            design.end_date = today - timedelta(days=3)
            design.warning_sent_at = now - timedelta(days=5)
            design.last_overdue_reminder_at = now
            design.save(update_fields=[
                'start_date', 'end_date', 'warning_sent_at',
                'last_overdue_reminder_at', 'updated_at',
            ])
            return

        # --- scenarios where design is completed and dev is the current stage ---
        design.start_date = today - timedelta(days=design_duration_days + 5)
        design.end_date = today - timedelta(days=5)
        design.completed_at = now - timedelta(days=4)
        design.save(update_fields=[
            'start_date', 'end_date', 'completed_at', 'updated_at',
        ])

        if scenario == 'dev_in_progress':
            # Dev started 5 days ago, mid-window.
            development.start_date = today - timedelta(days=5)
            development.end_date = development.start_date + timedelta(days=dev_duration_days)
            development.save(update_fields=[
                'start_date', 'end_date', 'updated_at',
            ])
            return

        if scenario == 'dev_overdue':
            # Dev ended 8 days ago, multiple overdue reminders sent.
            development.start_date = today - timedelta(days=dev_duration_days + 8)
            development.end_date = today - timedelta(days=8)
            development.warning_sent_at = now - timedelta(days=11)
            development.last_overdue_reminder_at = now - timedelta(days=2)
            development.save(update_fields=[
                'start_date', 'end_date', 'warning_sent_at',
                'last_overdue_reminder_at', 'updated_at',
            ])
            return

        # scenario == 'both_done'
        development.start_date = today - timedelta(days=dev_duration_days + 1)
        development.end_date = today - timedelta(days=1)
        development.completed_at = now
        development.save(update_fields=[
            'start_date', 'end_date', 'completed_at', 'updated_at',
        ])

    def _create_email_history(self, proposal, now):
        """Generate EmailLog entries for branded and proposal emails."""
        subjects_branded = [
            'Información adicional sobre tu proyecto',
            'Resumen de nuestra conversación',
            'Documentos adjuntos — Propuesta actualizada',
        ]
        subjects_proposal = [
            f'Propuesta actualizada: {proposal.title}',
            f'Seguimiento — {proposal.title}',
        ]
        ref_date = proposal.sent_at or (now - timedelta(days=10))

        # 1-2 branded emails
        for j in range(random.randint(1, 2)):
            log = EmailLog.objects.create(
                template_key='branded_email',
                recipient=proposal.client_email or f'{proposal.client_name.split()[0].lower()}@example.com',
                subject=random.choice(subjects_branded),
                proposal=proposal,
                status='sent',
                metadata={
                    'greeting': f'Hola {proposal.client_name}',
                    'sections': [
                        'Adjunto encontrarás la información que conversamos.',
                        'Quedamos atentos a cualquier duda.',
                    ],
                    'footer': 'Un abrazo, el equipo de Project App.',
                    'attachment_names': random.choice([[], ['propuesta.pdf'], ['contrato.pdf', 'anexo.pdf']]),
                },
            )
            EmailLog.objects.filter(pk=log.pk).update(
                sent_at=ref_date + timedelta(days=random.randint(1, 5), hours=random.randint(9, 17)),
            )

        # 1 proposal email (with change log)
        log = EmailLog.objects.create(
            template_key='proposal_email',
            recipient=proposal.client_email or f'{proposal.client_name.split()[0].lower()}@example.com',
            subject=random.choice(subjects_proposal),
            proposal=proposal,
            status='sent',
            metadata={
                'greeting': f'Hola {proposal.client_name}',
                'sections': ['Te compartimos la propuesta actualizada con los cambios solicitados.'],
                'footer': 'Quedamos atentos a tus comentarios.\nUn abrazo, el equipo de Project App.',
                'attachment_names': [],
            },
        )
        email_date = ref_date + timedelta(days=random.randint(2, 6), hours=random.randint(9, 17))
        EmailLog.objects.filter(pk=log.pk).update(sent_at=email_date)
        cl = ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type=ProposalChangeLog.ChangeType.EMAIL_SENT,
            actor_type=ProposalChangeLog.ActorType.SELLER,
            description=f'Correo enviado a {log.recipient}: {log.subject}',
        )
        ProposalChangeLog.objects.filter(pk=cl.pk).update(created_at=email_date)
