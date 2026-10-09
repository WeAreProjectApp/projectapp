"""Shared pytest fixtures for the content app test suite.

Provides reusable fixtures for API clients, model instances,
and authenticated users following the project testing standards.
"""
import sys
from decimal import Decimal
from types import ModuleType
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.test import APIClient

from content.models import (
    BlogPost,
    BusinessProposal,
    CompanySettings,
    Contact,
    ContractTemplate,
    PortfolioWork,
    ProposalDocument,
    ProposalSection,
    ProposalShareLink,
)

User = get_user_model()


# ── Global mocks ──

@pytest.fixture(autouse=True)
def _skip_mx_validation(monkeypatch):
    """Bypass DNS MX lookups in all tests, even when dnspython is unavailable."""
    if 'dns' not in sys.modules:
        dns_module = ModuleType('dns')
        dns_resolver_module = ModuleType('dns.resolver')
        dns_exception_module = ModuleType('dns.exception')

        class _DummyResolver:
            lifetime = 2.0

            def resolve(self, *_args, **_kwargs):
                return []

        dns_resolver_module.Resolver = _DummyResolver
        dns_resolver_module.NoAnswer = type('NoAnswer', (Exception,), {})
        dns_resolver_module.NXDOMAIN = type('NXDOMAIN', (Exception,), {})
        dns_resolver_module.NoNameservers = type('NoNameservers', (Exception,), {})
        dns_exception_module.Timeout = type('Timeout', (Exception,), {})

        dns_module.resolver = dns_resolver_module
        dns_module.exception = dns_exception_module

        monkeypatch.setitem(sys.modules, 'dns', dns_module)
        monkeypatch.setitem(sys.modules, 'dns.resolver', dns_resolver_module)
        monkeypatch.setitem(sys.modules, 'dns.exception', dns_exception_module)

    with patch('content.utils.check_domain_mx', return_value=True):
        yield


@pytest.fixture(autouse=True)
def _reset_throttle_cache():
    """Isolate DRF throttle state between tests.

    The MCP endpoint uses an AnonRateThrottle ('mcp' scope, 60/min) that keys by
    client IP and stores its request history in the cache. Under the test client
    every request shares one IP, so without a reset the bucket accumulates across
    the whole suite and later MCP calls get 429 — the response then has no
    'result' key and assertions on ``response.data['result']`` raise KeyError.
    Clearing the cache around each test keeps throttle state per-test.
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


# ── API Clients ──

@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Staff user for admin-gated endpoints."""
    return User.objects.create_user(
        username='admin_test',
        email='admin@test.com',
        password='testpass123',
        is_staff=True,
    )


@pytest.fixture
def admin_client(api_client, admin_user):
    """Authenticated DRF API client with admin (staff) privileges."""
    api_client.force_authenticate(user=admin_user)
    return api_client


# ── Content Model Fixtures ──

@pytest.fixture
def contact(db):
    """A sample contact message."""
    return Contact.objects.create(
        email='client@example.com',
        phone_number='+573001234567',
        subject='Project inquiry',
        message='I need a web application.',
        budget='5-10K',
    )


@pytest.fixture
def portfolio_work(db):
    """A sample portfolio work entry (without actual image file)."""
    return PortfolioWork.objects.create(
        title_en='Client Portal',
        title_es='Portal de Cliente',
        project_url='https://example.com/client-portal',
        category_title_en='Web Application',
        category_title_es='Aplicación Web',
    )


@pytest.fixture
def published_portfolio_work(db):
    """A published portfolio work with content_json."""
    return PortfolioWork.objects.create(
        title_en='MOOSER Hotel',
        title_es='MOOSER Hotel: Experiencia digital',
        excerpt_en='Digital experience for an alpine hotel.',
        excerpt_es='Experiencia digital para un hotel alpino.',
        project_url='https://mooser-hotel.com',
        content_json_es={
            'problem': {'title': 'El Desafío', 'description': 'Desc ES.', 'highlights': ['H1']},
            'solution': {'title': 'Solución', 'description': 'Sol ES.', 'highlights': ['S1']},
            'results': {'title': 'Resultados', 'description': 'Res ES.', 'highlights': ['R1'], 'testimonial_video_url': ''},
        },
        content_json_en={
            'problem': {'title': 'The Challenge', 'description': 'Desc EN.', 'highlights': ['H1']},
            'solution': {'title': 'Solution', 'description': 'Sol EN.', 'highlights': ['S1']},
            'results': {'title': 'Results', 'description': 'Res EN.', 'highlights': ['R1'], 'testimonial_video_url': ''},
        },
        is_published=True,
    )


@pytest.fixture
def draft_portfolio_work(db):
    """An unpublished (draft) portfolio work."""
    return PortfolioWork.objects.create(
        title_en='Secret Project',
        title_es='Proyecto Secreto',
        project_url='https://example.com/secret',
        is_published=False,
    )


@pytest.fixture
def blog_post(db):
    """A published blog post with bilingual content."""
    return BlogPost.objects.create(
        title_es='Tendencias de IA en 2026',
        title_en='AI Trends in 2026',
        excerpt_es='Un resumen de las tendencias más importantes.',
        excerpt_en='A summary of the most important trends.',
        content_es='<p>Contenido completo en español.</p>',
        content_en='<p>Full content in English.</p>',
        sources=[{'name': 'OpenAI', 'url': 'https://openai.com'}],
        is_published=True,
        published_at=timezone.now(),
    )


@pytest.fixture
def draft_blog_post(db):
    """An unpublished (draft) blog post."""
    return BlogPost.objects.create(
        title_es='Borrador de artículo',
        title_en='Draft article',
        excerpt_es='Extracto del borrador.',
        excerpt_en='Draft excerpt.',
        content_es='<p>Contenido borrador.</p>',
        content_en='<p>Draft content.</p>',
        is_published=False,
    )


@pytest.fixture
def blog_post_with_json(db):
    """A published blog post with structured JSON content."""
    return BlogPost.objects.create(
        title_es='Post con JSON estructurado',
        title_en='Post with structured JSON',
        excerpt_es='Resumen del post JSON.',
        excerpt_en='JSON post excerpt.',
        content_json_es={
            'intro': 'Introducción en español.',
            'sections': [
                {'heading': 'Sección 1', 'content': 'Contenido de la sección 1.'},
                {'heading': 'Sección 2', 'list': ['Item A', 'Item B']},
            ],
            'conclusion': 'Conclusión.',
            'cta': 'Contáctanos.',
        },
        content_json_en={
            'intro': 'Introduction in English.',
            'sections': [
                {'heading': 'Section 1', 'content': 'Section 1 content.'},
            ],
            'conclusion': 'Conclusion.',
            'cta': 'Contact us.',
        },
        category='technology',
        read_time_minutes=8,
        is_featured=True,
        is_published=True,
        published_at=timezone.now(),
    )


@pytest.fixture
def proposal(db):
    """A sample business proposal in draft status."""
    return BusinessProposal.objects.create(
        title='Web Application Development',
        client_name='Acme Corp',
        client_email='contact@acme.com',
        email_intro='Esta propuesta centraliza la operación de Acme para reducir reprocesos.',
        client_phone='+573001234567',
        language='es',
        total_investment=Decimal('15000.00'),
        currency='COP',
        status='draft',
        expires_at=timezone.now() + timezone.timedelta(days=30),
        reminder_days=5,
        discount_percent=20,
        project_type='webapp',
        market_type='b2b',
    )


@pytest.fixture
def sent_proposal(db):
    """A proposal that has been sent to the client."""
    now = timezone.now()
    return BusinessProposal.objects.create(
        title='Mobile App Development',
        client_name='Beta Inc',
        client_email='info@beta.com',
        email_intro='Esta propuesta agiliza la operación móvil de Beta y mejora su atención.',
        client_phone='+14155551234',
        language='en',
        total_investment=Decimal('25000.00'),
        currency='USD',
        status='sent',
        sent_at=now,
        last_activity_at=now,
        expires_at=now + timezone.timedelta(days=15),
        project_type='webapp',
        market_type='saas',
    )


@pytest.fixture
def expired_proposal(db):
    """A proposal that has expired."""
    return BusinessProposal.objects.create(
        title='Expired Project',
        client_name='Old Client',
        client_email='old@client.com',
        language='es',
        total_investment=Decimal('5000.00'),
        currency='COP',
        status='expired',
        expires_at=timezone.now() - timezone.timedelta(days=1),
    )


@pytest.fixture
def rejected_proposal(db):
    """A proposal that has been rejected by the client."""
    now = timezone.now()
    return BusinessProposal.objects.create(
        title='Rejected Project',
        client_name='Declined Client',
        client_email='declined@client.com',
        language='es',
        total_investment=Decimal('8000.00'),
        currency='COP',
        status='rejected',
        rejection_reason='presupuesto alto',
        sent_at=now - timezone.timedelta(days=5),
        first_viewed_at=now - timezone.timedelta(days=3),
        view_count=2,
        responded_at=now - timezone.timedelta(days=1),
        last_activity_at=now - timezone.timedelta(days=1),
        expires_at=now + timezone.timedelta(days=10),
        project_type='website',
        market_type='services',
    )


@pytest.fixture
def viewed_proposal(db):
    """A proposal that has been viewed by the client."""
    now = timezone.now()
    return BusinessProposal.objects.create(
        title='Viewed Project',
        client_name='Viewer Client',
        client_email='viewer@client.com',
        language='es',
        total_investment=Decimal('12000.00'),
        currency='COP',
        status='viewed',
        sent_at=now - timezone.timedelta(days=3),
        first_viewed_at=now - timezone.timedelta(hours=6),
        view_count=4,
        last_activity_at=now - timezone.timedelta(hours=6),
        expires_at=now + timezone.timedelta(days=20),
        project_type='ecommerce',
        market_type='b2c',
    )


@pytest.fixture
def negotiating_proposal(db):
    """A proposal in negotiation — client accepted with changes."""
    now = timezone.now()
    return BusinessProposal.objects.create(
        title='Negotiating Project',
        client_name='Negotiator Client',
        client_email='negotiator@client.com',
        language='es',
        total_investment=Decimal('18000.00'),
        currency='COP',
        status='negotiating',
        sent_at=now - timezone.timedelta(days=8),
        first_viewed_at=now - timezone.timedelta(days=5),
        view_count=6,
        responded_at=now - timezone.timedelta(days=1),
        last_activity_at=now - timezone.timedelta(days=1),
        expires_at=now + timezone.timedelta(days=12),
        project_type='webapp',
        market_type='b2b',
    )


@pytest.fixture
def accepted_proposal(db):
    """A proposal that has been accepted."""
    now = timezone.now()
    return BusinessProposal.objects.create(
        title='Accepted Project',
        client_name='Accepted Client',
        client_email='accepted@client.com',
        language='es',
        total_investment=Decimal('20000.00'),
        currency='COP',
        status='accepted',
        sent_at=now - timezone.timedelta(days=10),
        first_viewed_at=now - timezone.timedelta(days=7),
        view_count=8,
        responded_at=now - timezone.timedelta(days=2),
        last_activity_at=now - timezone.timedelta(days=2),
        expires_at=now + timezone.timedelta(days=10),
        project_type='webapp',
        market_type='b2b',
    )


@pytest.fixture
def share_link(db, sent_proposal):
    """A share link for a sent proposal."""
    return ProposalShareLink.objects.create(
        proposal=sent_proposal,
        shared_by_name='Alice',
        shared_by_email='alice@company.com',
    )


@pytest.fixture
def proposal_section(db, proposal):
    """A sample proposal section."""
    return ProposalSection.objects.create(
        proposal=proposal,
        section_type='greeting',
        title='Welcome',
        order=0,
        is_enabled=True,
        content_json={'heading': 'Welcome to our proposal'},
    )


# ── Contract & Document Fixtures ──

@pytest.fixture
def contract_template(db):
    """A default contract template with placeholders."""
    return ContractTemplate.objects.create(
        name='Standard Contract',
        content_markdown=(
            '# CONTRATO DE PRESTACION DE SERVICIOS\n\n'
            'Entre {client_full_name}, CC {client_cedula}, y '
            '{contractor_full_name}, NIT {contractor_nit}.\n\n'
            'Ciudad: {contract_city}. Fecha: {contract_date}.'
        ),
        service_content_markdown=(
            'Servicio de hosting entre {client_full_name} y {contractor_full_name} '
            'por {service_initial_term}.'
        ),
        is_default=True,
    )


@pytest.fixture
def proposal_document(db, negotiating_proposal):
    """A user-uploaded proposal document."""
    doc = ProposalDocument.objects.create(
        proposal=negotiating_proposal,
        document_type=ProposalDocument.DOC_TYPE_LEGAL_ANNEX,
        title='Legal annex',
        is_generated=False,
    )
    doc.file.save('legal_annex.pdf', ContentFile(b'%PDF-1.4 fake'), save=True)
    return doc


@pytest.fixture
def generated_contract_document(db, negotiating_proposal):
    """A system-generated contract PDF document."""
    doc = ProposalDocument.objects.create(
        proposal=negotiating_proposal,
        document_type=ProposalDocument.DOC_TYPE_CONTRACT,
        title='Contrato de desarrollo de software',
        is_generated=True,
    )
    doc.file.save('contract.pdf', ContentFile(b'%PDF-1.4 fake contract'), save=True)
    return doc


@pytest.fixture
def company_settings(db):
    """Pre-configured company settings singleton."""
    obj, _ = CompanySettings.objects.update_or_create(
        pk=1,
        defaults={
            'contractor_full_name': 'CARLOS MARIO BLANCO PEREZ',
            'contractor_nit': '1.037.635.428',
            'contractor_email': 'team@projectapp.co',
            'bank_name': 'Bancolombia',
            'bank_account_type': 'Ahorros',
            'bank_account_number': '26292039530',
            'contract_city': 'Medellín',
        },
    )
    return obj


# ── Accounting Module Fixtures ──

@pytest.fixture
def superuser(db):
    """Superuser for accounting-gated endpoints."""
    return User.objects.create_superuser(
        username='super_test',
        email='super@test.com',
        password='testpass123',
    )


@pytest.fixture
def super_client(api_client, superuser):
    """Authenticated DRF API client with superuser privileges."""
    api_client.force_authenticate(user=superuser)
    return api_client


@pytest.fixture
def accounting_settings(db, notification_recipients):
    """Settings singleton with notifications on and two active recipients.

    The recipients live in their own table now, but every sender reads both
    (master switch here, destinations there), so the fixture keeps handing
    out a state where email actually goes out.
    """
    from content.models import AccountingSettings

    obj = AccountingSettings.load()
    obj.notifications_enabled = True
    obj.save()
    return obj


@pytest.fixture
def notification_recipients(db):
    """The two active recipients most accounting email tests assume.

    Migration 0191 seeds the two production inboxes into every fresh test
    database, so they are cleared first: a test that asserts who an email
    reached has to own the whole list.
    """
    from content.models import NotificationRecipient

    NotificationRecipient.objects.all().delete()
    return [
        NotificationRecipient.objects.create(email=email, is_active=True)
        for email in ('carlos@test.com', 'gustavo@test.com')
    ]


@pytest.fixture
def make_notification_recipient(db):
    """Factory for NotificationRecipient rows."""
    from content.models import NotificationRecipient

    def _make(email, **kwargs):
        defaults = {'is_active': True}
        defaults.update(kwargs)
        return NotificationRecipient.objects.create(email=email, **defaults)

    return _make


@pytest.fixture
def make_income(db):
    """Factory for IncomeRecord rows with sensible defaults."""
    from datetime import date

    from content.models import IncomeRecord

    def _make(**kwargs):
        defaults = {
            'concept': 'Kore v2 (Fase 1) - Inicio 40%',
            'kind': IncomeRecord.Kind.EXPECTED,
            'period_date': date(2026, 3, 1),
            'total_amount': Decimal('1000000.00'),
            'gustavo_amount': Decimal('500000.00'),
            'carlos_amount': Decimal('500000.00'),
        }
        defaults.update(kwargs)
        return IncomeRecord.objects.create(**defaults)

    return _make


@pytest.fixture
def make_expense(db):
    """Factory for ExpenseRecord rows with sensible defaults."""
    from datetime import date

    from content.models import ExpenseRecord

    def _make(**kwargs):
        defaults = {
            'concept': 'Claude Code 20x',
            'period_date': date(2026, 3, 1),
            'total_amount': Decimal('800000.00'),
            'gustavo_amount': Decimal('400000.00'),
            'carlos_amount': Decimal('400000.00'),
        }
        defaults.update(kwargs)
        return ExpenseRecord.objects.create(**defaults)

    return _make


@pytest.fixture
def make_client_profile(db):
    """Factory for client UserProfiles (accounting incomes, filters, totals)."""
    from accounts.models import UserProfile

    counter = {'n': 0}

    def _make(company='Acme SAS', **kwargs):
        counter['n'] += 1
        suffix = counter['n']
        user = User.objects.create_user(
            username=kwargs.pop('username', f'client{suffix}@example.com'),
            email=kwargs.pop('email', f'client{suffix}@example.com'),
            first_name=kwargs.pop('first_name', 'Ana'),
            last_name=kwargs.pop('last_name', f'Cliente{suffix}'),
        )
        return UserProfile.objects.create(
            user=user,
            role=UserProfile.ROLE_CLIENT,
            company_name=company,
            **kwargs,
        )

    return _make


@pytest.fixture
def diag_client_profile(db):
    """A client UserProfile suitable for attaching to a WebAppDiagnostic."""
    from accounts.models import UserProfile

    user = User.objects.create_user(
        username='diag_client', email='diag@example.com',
        first_name='Ana', last_name='Cliente',
    )
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': UserProfile.ROLE_CLIENT, 'company_name': 'Acme'},
    )
    return profile


@pytest.fixture
def diagnostic(db, diag_client_profile):
    """A send-ready WebAppDiagnostic (passes the pre-send scorecard gate)."""
    from content.services import diagnostic_service

    diag = diagnostic_service.create_diagnostic(
        client=diag_client_profile, language='es',
    )
    diag.client_name = 'Ana Cliente'
    diag.client_email = 'ana@example.com'
    diag.investment_amount = 1_000_000
    diag.radiography = {
        'stack': {'backend': {'framework': 'Django'}, 'frontend': {'framework': 'Vue'}},
        'modules': ['Auth', 'Reports'],
        'entities_count': 12,
    }
    diag.save(update_fields=[
        'client_name', 'client_email', 'investment_amount', 'radiography',
    ])
    return diag


@pytest.fixture
def non_deferring_constraints():
    """Reproduce the constraint semantics production actually runs on.

    SQLite reports ``can_defer_constraint_checks = True``, so Django skips the
    ``UPDATE ... SET <fk> = NULL`` that ``deletion.CASCADE`` emits before
    deleting the rows behind a *nullable* CASCADE FK. MySQL reports False and
    emits it — which is why a CHECK constraint spanning those columns blows up
    in production while the suite stays green. Opt in to exercise that path.
    """
    from django.db import connection

    features = connection.features
    original = features.can_defer_constraint_checks
    features.can_defer_constraint_checks = False
    try:
        yield connection
    finally:
        features.can_defer_constraint_checks = original

# Shared contract-template fixtures keep transport and generation tests in their layers.
from content.tests.contract_template_fixtures import (
    source_237_markdown, coherent_template, initialized_contract_mirrors, proposals_mcp,
)
from content.tests.building_with_us_fixtures import (
    building_with_us_program, building_with_us_mcp, changed_building_with_us_program,
)
