"""Service layer for the WebAppDiagnostic feature.

Diagnostics are modeled as a sequence of JSON-driven ``DiagnosticSection``
rows (one per section_type). A seed from ``content.seeds.diagnostic_template``
populates a new diagnostic with the default narrative; from there the admin
edits each section through the section editor.
"""

from __future__ import annotations

from copy import deepcopy

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.services.proposal_client_service import build_client_display_name
from content.models import (
    DiagnosticChangeLog,
    DiagnosticDefaultConfig,
    DiagnosticSection,
    WebAppDiagnostic,
)
from content.seeds.diagnostic_template import default_sections
from content.utils import format_cop_email


DEFAULT_PAYMENT_INITIAL_PCT = 60
DEFAULT_PAYMENT_FINAL_PCT = 40
DEFAULT_EXPIRATION_DAYS = 21
DEFAULT_REMINDER_DAYS = 7
DEFAULT_URGENCY_REMINDER_DAYS = 14


def get_hardcoded_section_specs() -> list[dict]:
    """Return the hardcoded section specs used when no DB defaults exist."""
    return list(default_sections())


def get_default_config(language: str = 'es'):
    """Return the persisted ``DiagnosticDefaultConfig`` for *language* or None."""
    return DiagnosticDefaultConfig.objects.filter(language=language).first()


def get_default_expiration_days(language: str = 'es') -> int:
    """Expiration window (days) from the language config, or the fallback."""
    config = get_default_config(language)
    if config and config.expiration_days:
        return config.expiration_days
    return DEFAULT_EXPIRATION_DAYS


def compute_default_expires_at(language: str = 'es'):
    """Absolute expiry datetime = now + configured expiration window."""
    from datetime import timedelta
    return timezone.now() + timedelta(days=get_default_expiration_days(language))


def get_default_section_specs(language: str = 'es') -> list[dict]:
    """Return the section specs to seed: DB config if present, otherwise the hardcoded seed."""
    config = get_default_config(language)
    if config and isinstance(config.sections_json, list) and config.sections_json:
        return list(config.sections_json)
    return get_hardcoded_section_specs()


def _classify_size(value: int, thresholds: tuple[int, int]) -> str:
    low, high = thresholds
    if value <= 0:
        return ''
    if value < low:
        return 'Pequeña'
    if value <= high:
        return 'Mediana'
    return 'Grande'


def build_render_context(diagnostic: WebAppDiagnostic) -> dict:
    """Build the variable map used by section components to hydrate headings.

    Kept for backward compatibility with email templates and for the
    radiography section renderer which shows pricing/metrics pulled from
    ``diagnostic.radiography`` + pricing fields.
    """
    radiography = diagnostic.radiography or {}
    payment = diagnostic.payment_terms or {}
    initial_pct = payment.get('initial_pct')
    final_pct = payment.get('final_pct')
    if initial_pct is None or final_pct is None:
        cfg = get_default_config(diagnostic.language)
        if cfg is not None:
            if initial_pct is None:
                initial_pct = cfg.payment_initial_pct
            if final_pct is None:
                final_pct = cfg.payment_final_pct
    stack = radiography.get('stack', {}) or {}
    backend_stack = stack.get('backend', {}) or {}
    frontend_stack = stack.get('frontend', {}) or {}
    modules = radiography.get('modules') or []

    if isinstance(modules, list) and modules:
        modules_list = '\n'.join(
            f'{i}. {m}' for i, m in enumerate(modules, start=1)
        )
        modules_count = len(modules)
    else:
        modules_list = ''
        modules_count = radiography.get('modules_count', 0) or 0

    entities = radiography.get('entities_count', 0) or 0
    routes = radiography.get('routes_total', 0) or 0
    fe_routes = radiography.get('frontend_routes_count', 0) or 0
    components = radiography.get('components_count', 0) or 0
    integrations = radiography.get('external_integrations', 0) or 0

    size_label = ''
    if diagnostic.size_category:
        size_label = WebAppDiagnostic.SizeCategory(diagnostic.size_category).label

    return {
        'client_name': diagnostic.client_name or build_client_display_name(diagnostic.client),
        'investment_amount': format_cop_email(diagnostic.investment_amount),
        'currency': diagnostic.currency or '',
        'payment_initial_pct': initial_pct if initial_pct is not None else '',
        'payment_final_pct': final_pct if final_pct is not None else '',
        'duration_label': diagnostic.duration_label or '',
        'size_category_label': size_label,

        'stack_backend_name': backend_stack.get('name', ''),
        'stack_backend_version': backend_stack.get('version', ''),
        'stack_frontend_name': frontend_stack.get('name', ''),
        'stack_frontend_version': frontend_stack.get('version', ''),

        'migrations_count': radiography.get('migrations_count', ''),
        'entities_count': entities,
        'routes_total': routes,
        'routes_public': radiography.get('routes_public', ''),
        'routes_protected': radiography.get('routes_protected', ''),
        'controllers_count': radiography.get('controllers_count', ''),
        'controllers_disconnected': radiography.get('controllers_disconnected', ''),
        'frontend_routes_count': fe_routes,
        'components_count': components,
        'external_integrations': integrations,
        'modules_count': modules_count,
        'modules_list': modules_list,
        'test_files_count': radiography.get('test_files_count', ''),
        'test_coverage_label': radiography.get('test_coverage_label', ''),
        'ci_files_count': radiography.get('ci_files_count', ''),
        'docker_files_count': radiography.get('docker_files_count', ''),

        'entities_size': _classify_size(int(entities or 0), (15, 50)),
        'routes_size': _classify_size(int(routes or 0), (30, 100)),
        'frontend_routes_size': _classify_size(int(fe_routes or 0), (15, 50)),
        'components_size': _classify_size(int(components or 0), (20, 80)),
        'integrations_size': _classify_size(int(integrations or 0), (3, 7)),
        'modules_size': _classify_size(int(modules_count or 0), (4, 8)),
    }


def seed_sections(
    diagnostic: WebAppDiagnostic,
    config: DiagnosticDefaultConfig | None = None,
) -> list[DiagnosticSection]:
    """Create the default sections for a diagnostic.

    Pulls specs from *config* (or the persisted ``DiagnosticDefaultConfig``
    for the diagnostic's language when not supplied); otherwise falls back to
    the hardcoded JSON seed. Skips any spec whose ``section_type`` is not a
    valid choice.
    """
    if config is not None and isinstance(config.sections_json, list) and config.sections_json:
        specs = list(config.sections_json)
    else:
        specs = get_default_section_specs(diagnostic.language)

    valid_types = {value for value, _ in DiagnosticSection.SectionType.choices}
    rows = []
    for spec in specs:
        section_type = spec.get('section_type')
        if section_type not in valid_types:
            continue
        rows.append(DiagnosticSection(
            diagnostic=diagnostic,
            section_type=section_type,
            title=spec.get('title', ''),
            order=spec.get('order', 0),
            is_enabled=spec.get('is_enabled', True),
            visibility=spec.get('visibility', DiagnosticSection.Visibility.BOTH),
            content_json=deepcopy(spec.get('content_json') or {}),
            text_formats=deepcopy(spec.get('text_formats') or {}),
        ))
    return DiagnosticSection.objects.bulk_create(rows)


def reset_section(section: DiagnosticSection) -> DiagnosticSection:
    """Restore a single section's ``content_json`` from the active defaults."""
    language = section.diagnostic.language
    for spec in get_default_section_specs(language):
        if spec.get('section_type') == section.section_type:
            section.content_json = deepcopy(spec.get('content_json') or {})
            section.text_formats = deepcopy(spec.get('text_formats') or {})
            section.title = spec.get('title', section.title)
            section.visibility = spec.get('visibility', section.visibility)
            section.is_enabled = spec.get('is_enabled', section.is_enabled)
            section.save(update_fields=[
                'content_json', 'text_formats', 'title', 'visibility', 'is_enabled',
            ])
            return section
    return section


@transaction.atomic
def create_diagnostic(
    *,
    client,
    language: str = 'es',
    title: str = '',
    created_by=None,
) -> WebAppDiagnostic:
    """Create a diagnostic and seed its 8 JSON sections."""
    if not title:
        title = f'Diagnóstico — {build_client_display_name(client)}'

    config = get_default_config(language)
    if config:
        currency = config.default_currency or WebAppDiagnostic.Currency.COP
        investment_amount = config.default_investment_amount
        duration_label = config.default_duration_label or ''
        payment_terms = {
            'initial_pct': config.payment_initial_pct,
            'final_pct': config.payment_final_pct,
        }
    else:
        currency = WebAppDiagnostic.Currency.COP
        investment_amount = None
        duration_label = ''
        payment_terms = {
            'initial_pct': DEFAULT_PAYMENT_INITIAL_PCT,
            'final_pct': DEFAULT_PAYMENT_FINAL_PCT,
        }

    diagnostic = WebAppDiagnostic.objects.create(
        client=client,
        language=language,
        title=title,
        client_name=build_client_display_name(client),
        client_email=client.user.email or '',
        client_phone=client.phone or '',
        client_company=client.company_name or '',
        currency=currency,
        investment_amount=investment_amount,
        duration_label=duration_label,
        payment_terms=payment_terms,
        created_by=created_by,
    )
    seed_sections(diagnostic, config=config)
    log_change(
        diagnostic,
        change_type=DiagnosticChangeLog.ChangeType.CREATED,
        description='Diagnóstico creado desde plantilla.',
        actor_type=DiagnosticChangeLog.ActorType.SELLER,
    )
    return diagnostic


def transition_status(
    diagnostic: WebAppDiagnostic,
    new_status: str,
    *,
    actor_type: str = '',
) -> WebAppDiagnostic:
    """Validate transition + stamp the matching timestamp."""
    if not diagnostic.can_transition_to(new_status):
        raise ValueError(
            f'invalid_transition: {diagnostic.status} → {new_status}'
        )

    update_fields = ['status', 'updated_at']
    old_status = diagnostic.status
    diagnostic.status = new_status
    now = timezone.now()

    if new_status == WebAppDiagnostic.Status.SENT:
        if diagnostic.initial_sent_at is None:
            diagnostic.initial_sent_at = now
            update_fields.append('initial_sent_at')
            # Stamp the expiry window on the first send (consumes the
            # language config's expiration_days).
            if diagnostic.expires_at is None:
                diagnostic.expires_at = compute_default_expires_at(
                    diagnostic.language,
                )
                update_fields.append('expires_at')
        else:
            diagnostic.final_sent_at = now
            update_fields.append('final_sent_at')
    elif new_status in (
        WebAppDiagnostic.Status.ACCEPTED,
        WebAppDiagnostic.Status.REJECTED,
    ):
        diagnostic.responded_at = now
        update_fields.append('responded_at')

    diagnostic.save(update_fields=update_fields)

    log_change(
        diagnostic,
        change_type=DiagnosticChangeLog.ChangeType.STATUS_CHANGE,
        field_name='status',
        old_value=old_status,
        new_value=new_status,
        description=f'Estado: {old_status} → {new_status}',
        actor_type=actor_type or DiagnosticChangeLog.ActorType.SYSTEM,
    )
    return diagnostic


def register_view(diagnostic: WebAppDiagnostic) -> WebAppDiagnostic:
    """Increment view_count and refresh last_viewed_at."""
    WebAppDiagnostic.objects.filter(pk=diagnostic.pk).update(
        view_count=F('view_count') + 1,
        last_viewed_at=timezone.now(),
    )
    diagnostic.refresh_from_db(fields=['view_count', 'last_viewed_at'])
    return diagnostic


def log_change(
    diagnostic: WebAppDiagnostic,
    *,
    change_type: str,
    description: str = '',
    field_name: str = '',
    old_value: str = '',
    new_value: str = '',
    actor_type: str = '',
) -> DiagnosticChangeLog:
    """Append a DiagnosticChangeLog entry for this diagnostic."""
    return DiagnosticChangeLog.objects.create(
        diagnostic=diagnostic,
        change_type=change_type,
        description=description or '',
        field_name=field_name or '',
        old_value=str(old_value or ''),
        new_value=str(new_value or ''),
        actor_type=actor_type or '',
    )


# Statuses whose sections are shown to the client on the public page.
PUBLIC_VISIBLE_STATUSES = frozenset({
    WebAppDiagnostic.Status.SENT,
    WebAppDiagnostic.Status.VIEWED,
    WebAppDiagnostic.Status.NEGOTIATING,
    WebAppDiagnostic.Status.ACCEPTED,
    WebAppDiagnostic.Status.REJECTED,
})

# Statuses the public endpoint serves at all. EXPIRED/FINISHED are served
# (200, no sections) so the client sees the terminal empty-state instead of a
# 404; DRAFT stays hidden.
PUBLIC_SERVABLE_STATUSES = PUBLIC_VISIBLE_STATUSES | frozenset({
    WebAppDiagnostic.Status.EXPIRED,
    WebAppDiagnostic.Status.FINISHED,
})


def visible_sections(diagnostic: WebAppDiagnostic):
    """Return sections to expose on the public client view."""
    if diagnostic.status not in PUBLIC_VISIBLE_STATUSES:
        return []
    sections = sorted(
        diagnostic.sections.filter(is_enabled=True),
        key=lambda s: s.order,
    )
    phase = 'final' if diagnostic.final_sent_at else 'initial'
    allowed = {phase, 'both'}
    return [s for s in sections if s.visibility in allowed]


BULK_ACTIONS = frozenset({'delete', 'finish'})


def bulk_action(ids, action: str) -> int:
    """Apply *action* to the diagnostics in *ids*; return how many changed.

    ``delete`` removes the rows. ``finish`` moves ACCEPTED diagnostics to
    FINISHED via :func:`transition_status` and silently skips the ones whose
    status does not allow it (the caller reports the affected count).
    """
    qs = WebAppDiagnostic.objects.filter(pk__in=ids)
    affected = 0

    if action == 'delete':
        affected = qs.count()
        qs.delete()
    elif action == 'finish':
        for diagnostic in qs:
            if not diagnostic.can_transition_to(WebAppDiagnostic.Status.FINISHED):
                continue
            transition_status(
                diagnostic, WebAppDiagnostic.Status.FINISHED,
                actor_type=DiagnosticChangeLog.ActorType.SELLER,
            )
            affected += 1

    return affected


def build_scorecard(diagnostic: WebAppDiagnostic) -> dict:
    """Pre-send readiness scorecard (parity with the proposals scorecard).

    Blockers gate the admin send actions; the rest are quality nudges.
    Shape: {score 1-10, checks[{key,label,passed,blocker}], blockers,
    can_send, total_checks, passed_checks}.
    """
    sections = list(diagnostic.sections.filter(is_enabled=True))
    enabled_count = len(sections)

    def _has_content(section) -> bool:
        content = section.content_json
        return bool(content) and content != {}

    with_content = sum(1 for s in sections if _has_content(s))
    content_ratio = with_content / enabled_count if enabled_count else 0
    radiography_enabled = any(s.section_type == 'radiography' for s in sections)

    checks = [
        {
            'key': 'client_email',
            'label': 'Email del cliente',
            'passed': bool(diagnostic.client_email and diagnostic.client_email.strip()),
            'blocker': True,
        },
        {
            'key': 'client_name',
            'label': 'Nombre del cliente',
            'passed': bool(diagnostic.client_name and diagnostic.client_name.strip()),
            'blocker': True,
        },
        {
            'key': 'investment_amount',
            'label': 'Inversión > $0',
            'passed': bool(diagnostic.investment_amount and diagnostic.investment_amount > 0),
            'blocker': True,
        },
        {
            'key': 'enabled_sections',
            'label': 'Al menos 1 sección habilitada',
            'passed': enabled_count >= 1,
            'blocker': True,
        },
    ]
    if radiography_enabled:
        checks.append({
            'key': 'radiography',
            'label': 'Radiografía completada',
            'passed': bool(diagnostic.radiography),
            'blocker': True,
        })
    checks.extend([
        {
            'key': 'title',
            'label': 'Título del diagnóstico',
            'passed': bool(diagnostic.title and diagnostic.title.strip()),
            'blocker': False,
        },
        {
            'key': 'sections_content',
            'label': f'Secciones con contenido ({with_content}/{enabled_count})',
            'passed': content_ratio >= 0.5,
            'blocker': False,
        },
        {
            'key': 'client_phone',
            'label': 'Teléfono del cliente (para WhatsApp)',
            'passed': bool(diagnostic.client_phone and diagnostic.client_phone.strip()),
            'blocker': False,
        },
        {
            'key': 'language',
            'label': 'Idioma configurado',
            'passed': bool(diagnostic.language),
            'blocker': False,
        },
        {
            'key': 'payment_terms',
            'label': 'Formas de pago definidas',
            'passed': bool(diagnostic.payment_terms),
            'blocker': False,
        },
    ])

    passed_count = sum(1 for c in checks if c['passed'])
    blockers = [c for c in checks if c['blocker'] and not c['passed']]
    return {
        'score': max(1, round(passed_count / len(checks) * 10)),
        'checks': checks,
        'blockers': blockers,
        'can_send': not blockers,
        'total_checks': len(checks),
        'passed_checks': passed_count,
    }
