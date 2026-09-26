import logging
from copy import deepcopy
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from content.technical_document_defaults import EMPTY_TECHNICAL_DOCUMENT_JSON

logger = logging.getLogger(__name__)

#: Default copy for the hosting free-month gift block, per proposal language.
#: Single source of truth: seeded into DEFAULT_SECTIONS at creation time AND
#: resolved at read time by ``normalize_hosting_plan`` so the panel form, the
#: public view and the PDF always show the same sentence. Keep the two
#: languages in sync when editing.
HOSTING_FREE_MONTH_NOTES = {
    'es': (
        'Los cobros del hosting inician el día 1° de cada mes. Desde la '
        'entrega de tu proyecto hasta tu primer cobro, el hosting es gratis: '
        'siempre te regalamos como mínimo un mes completo.'
    ),
    'en': (
        'Hosting billing starts on the 1st of each month. From your project '
        'delivery until your first charge, hosting is free: we always gift '
        'you at least one full month.'
    ),
}


def default_free_month_note(language):
    """Return the free-month copy for ``language`` (Spanish is the fallback)."""
    return HOSTING_FREE_MONTH_NOTES.get(language or 'es', HOSTING_FREE_MONTH_NOTES['es'])


def _coerce_free_months(value):
    """Read ``freeMonths`` as an int. Legacy content stores it as a string."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


@transaction.atomic
def duplicate_proposal(source, *, via_mcp=False):
    """Deep-copy a proposal with one shared panel/MCP field contract."""
    from content.models import (
        BusinessProposal,
        ProposalChangeLog,
        ProposalSection,
    )

    duplicate = BusinessProposal.objects.create(
        title=f'{source.title.removesuffix(" (copia)")} (copia)',
        client_name=source.client_name,
        client_email=source.client_email,
        client_phone=source.client_phone,
        slug='',
        language=source.language,
        total_investment=source.total_investment,
        currency=source.currency,
        nationality=source.nationality,
        hosting_percent=source.hosting_percent,
        hosting_discount_nine_month=source.hosting_discount_nine_month,
        hosting_discount_semiannual=source.hosting_discount_semiannual,
        hosting_discount_quarterly=source.hosting_discount_quarterly,
        project_type=source.project_type,
        market_type=source.market_type,
        project_type_custom=source.project_type_custom,
        market_type_custom=source.market_type_custom,
        selected_modules=deepcopy(source.selected_modules),
        contract_params=deepcopy(source.contract_params),
        status=BusinessProposal.Status.DRAFT,
        expires_at=source.expires_at,
        reminder_days=source.reminder_days,
        urgency_reminder_days=source.urgency_reminder_days,
        discount_percent=source.discount_percent,
        show_contract_terms=source.show_contract_terms,
        is_active=True,
        view_count=0,
        first_viewed_at=None,
        sent_at=None,
        reminder_sent_at=None,
        urgency_email_sent_at=None,
    )

    for section in source.sections.all().order_by('order'):
        section_content = deepcopy(section.content_json or {})
        if section.section_type == ProposalSection.SectionType.INVESTMENT:
            section_content['hostingPlan'] = normalize_hosting_plan(
                duplicate, section_content.get('hostingPlan') or {},
            )
        ProposalSection.objects.create(
            proposal=duplicate,
            section_type=section.section_type,
            title=section.title,
            order=section.order,
            is_enabled=section.is_enabled,
            is_wide_panel=section.is_wide_panel,
            content_json=section_content,
        )

    suffix = ' via MCP' if via_mcp else ''
    ProposalChangeLog.objects.create(
        proposal=duplicate,
        change_type='duplicated',
        actor_type='seller',
        description=(
            f'Duplicated from proposal "{source.title}" (ID {source.id}){suffix}.'
        ),
    )
    return duplicate


def flatten_terms_clauses(clauses):
    """Flatten [{'label', 'text'}] into the legacy single-string `terms` value.

    `terms_clauses` is the canonical shape for the value-added module terms,
    but `terms` is kept in sync so proposals that were never migrated (and any
    consumer that only knows the old key) keep rendering the same content.
    One line per clause, the label emphasised with the `**bold**` markers both
    renderers already understand (web: utils/renderInlineBold.js, PDF:
    pdf_utils._draw_line_with_links).
    """
    if not isinstance(clauses, (list, tuple)):
        return ''
    lines = []
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        text = (clause.get('text') or '').strip()
        if not text:
            continue
        label = (clause.get('label') or '').strip()
        lines.append(f'**{label}.** {text}' if label else text)
    return '\n'.join(lines)


def _clauses(*pairs):
    """Build a terms_clauses list from (label, text) pairs."""
    return [{'label': label, 'text': text} for label, text in pairs]


SCOPE_CLAUSE_FIELDS = ('scopeTitle', 'scopeParagraphs')


def enforce_scope_clause(new_content, default_content):
    """Force the scope-of-work clause from the resolved language defaults.

    ``scopeTitle``/``scopeParagraphs`` are legal boilerplate owned by the
    defaults (admin-editable through ``ProposalDefaultConfig``), not by the
    seller. JSON/MCP payloads are routinely composed from stale snapshots —
    a downloaded template, a previous proposal — so a payload carrying this
    section would otherwise reinject a superseded clause into a brand-new
    proposal, silently downgrading its legal text.

    Everything else the payload states about the section — packages, hourly
    rate, effort badge, titles — still wins.
    """
    if not isinstance(new_content, dict) or not isinstance(default_content, dict):
        return new_content

    for field in SCOPE_CLAUSE_FIELDS:
        if field in default_content:
            new_content[field] = deepcopy(default_content[field])

    return new_content


def enforce_technical_item_coverage(section_payloads, technical_content_json):
    """Refuse a technical document that leaves commercial items untraced.

    ``requirement.linked_item_ids`` is the contract between the functional
    requirements and the technical detail: it powers the client-facing "view
    requirements" modal, the PDF, and the scope item each platform requirement
    inherits on project handoff. The admin editor already blocks a save that
    breaks it (``TechnicalDocumentEditor.vue``), but the JSON/MCP import had no
    equivalent check, so a payload could land with every link empty and the
    traceability would disappear without a single error — exactly what the
    seller prompt warns about with "a changed or missing id silently breaks
    that traceability".

    Applies to the update path only. On creation the functional requirements
    are the payload merged with the language template, so the required set
    would include items the caller never authored; by the time a technical
    document is written the proposal already carries the seller's own scope.

    No-op when the document carries no epics: a proposal without a technical
    detail has nothing to trace.
    """
    from content.api_errors import ProposalActionError
    from content.services.proposal_module_links import (
        build_item_link_options,
        build_technical_item_coverage,
    )

    if not isinstance(technical_content_json, dict):
        return
    if not (technical_content_json.get('epics') or []):
        return

    options = build_item_link_options(section_payloads)
    if not options:
        return

    coverage = build_technical_item_coverage(options, technical_content_json)
    missing = coverage['missingRequired']
    if not missing:
        return

    shown = ', '.join(entry['label'] for entry in missing[:8])
    if len(missing) > 8:
        shown += f' (+{len(missing) - 8} más)'
    raise ProposalActionError(
        f'El detalle técnico no cubre {len(missing)} de '
        f'{coverage["requiredCount"]} ítems de los requerimientos funcionales: '
        f'{shown}.',
        code='technical_item_coverage_incomplete',
        hint=(
            'Cada ítem debe estar referenciado por al menos un requerimiento '
            'técnico en "linked_item_ids". Sin ese enlace el cliente no ve el '
            'detalle técnico del ítem y la trazabilidad se pierde en silencio.'
        ),
    )


def merge_value_added_legal_terms(new_content, previous_content):
    """Keep the value-added legal terms when an incoming payload omits them.

    JSON/MCP payloads carry seller copy (``module_ids``, ``justifications``),
    but the seller prompt never documents ``conditions``/``general_terms``. A
    payload that simply round-trips the visible fields would therefore wipe the
    legal wording from the proposal without anyone noticing. Anything the
    payload does state explicitly still wins; only the gaps are filled.

    ``previous_content`` is the stored content_json on update, or the language
    defaults on creation.
    """
    if not isinstance(new_content, dict) or not isinstance(previous_content, dict):
        return new_content

    previous_conds = previous_content.get('conditions')
    if isinstance(previous_conds, dict):
        conds = new_content.get('conditions')
        if not isinstance(conds, dict):
            conds = {}
        for module_id, previous_cond in previous_conds.items():
            if module_id not in conds:
                conds[module_id] = deepcopy(previous_cond)
        if conds:
            new_content['conditions'] = conds

    if not new_content.get('general_terms'):
        previous_general = previous_content.get('general_terms')
        if isinstance(previous_general, dict):
            new_content['general_terms'] = deepcopy(previous_general)

    return new_content


# Per-proposal hour-rate settings, owned by the «Tarifa por hora» panel tab.
MANUAL_HOUR_RATE_FIELDS = (
    'hourPackagesMode',
    'hourPackagesEnabled',
    'manualHourlyRate',
    'manualCurrency',
    'manualPackageRates',
)


def preserve_manual_hour_rate_keys(new_content, previous_content):
    """Keep a proposal's manual hour-rate settings across a JSON replace.

    The manual rate is set in the panel tab and is documented nowhere in the
    seller prompt or the JSON templates, so every payload omits it. Since the
    JSON update path replaces ``content_json`` wholesale, one save from the
    JSON tab would otherwise reset the proposal to catalog pricing without any
    sign that something was lost. A payload that *does* state a field still
    wins.
    """
    if not isinstance(new_content, dict) or not isinstance(previous_content, dict):
        return new_content

    for field in MANUAL_HOUR_RATE_FIELDS:
        if field not in new_content and field in previous_content:
            new_content[field] = deepcopy(previous_content[field])

    return new_content


def _module_condition(clauses, *, min_price_usd=None, min_price_cop=None,
                      duration_months=None, discretionary_note=''):
    """Build one `conditions[module_id]` entry.

    `terms` is always derived from `terms_clauses` so the two can never drift.
    """
    return {
        'min_price_usd': min_price_usd,
        'min_price_cop': min_price_cop,
        'duration_months': duration_months,
        'discretionary_note': discretionary_note,
        'terms_clauses': deepcopy(clauses),
        'terms': flatten_terms_clauses(clauses),
    }


# ---------------------------------------------------------------------------
# Legal texts for the value-added modules section.
#
# Each module's terms are a list of categorised clauses ({label, text}) instead
# of a single paragraph, so the client can tell the nature of each obligation
# apart (eligibility, scope, term, third-party dependency, liability). The very
# same list feeds the public web modal and the PDF annex — one source, two
# renderers — and `**bold**` markers work in both.
#
# ES and EN are independent literals and MUST stay in parity.
# ---------------------------------------------------------------------------

_KPI_CLAUSES_ES = _clauses(
    ('Naturaleza del beneficio',
     'El Dashboard de KPIs y Métricas se otorga como una **liberalidad comercial** '
     'incluida dentro del precio total del proyecto. No constituye un servicio '
     'contratado de forma independiente y su no aplicación no genera descuento, '
     'reembolso, crédito ni compensación económica alguna a favor del cliente.'),
    ('Elegibilidad',
     'Aplica exclusivamente a proyectos cuya inversión total supere los **1.500 USD** '
     '(o su equivalente en COP), calculada sobre el valor efectivo del proyecto en la '
     'moneda de esta propuesta.'),
    ('Condición de viabilidad',
     'Su implementación está sujeta a que la lógica de negocio del proyecto permita y '
     'haga pertinente la definición y medición de indicadores clave. Si el negocio no '
     'cuenta con indicadores que tenga sentido medir, el beneficio **no resulta '
     'exigible**.'),
    ('Requisito de disponibilidad de datos',
     'Este módulo **captura, cuantifica y procesa datos** para exponerlos de forma '
     'resumida como indicadores. Su entrega presupone que el sistema genere '
     'información susceptible de ser medida. **Si no existe data que procesar ni '
     'magnitudes que cuantificar, el módulo no es técnicamente entregable, aun cuando '
     'el valor del proyecto habilite el beneficio.**'),
    ('Alcance y límites',
     'Comprende hasta **8 KPIs, 4 gráficos y 5 alertas**, definidos de común acuerdo '
     'durante el levantamiento de requerimientos. Todo indicador, visualización o '
     'alerta adicional constituye un requerimiento independiente y se cotiza por '
     'separado.'),
    ('Exclusiones',
     'No comprende la depuración, migración o saneamiento de datos históricos '
     'preexistentes, ni la integración con fuentes de datos externas no contempladas '
     'dentro del alcance aprobado.'),
)

_ANALYTICS_CLAUSES_ES = _clauses(
    ('Naturaleza del beneficio',
     'El Módulo de Analítica se otorga como una **liberalidad comercial** incluida '
     'dentro del precio total del proyecto. No constituye un servicio contratado de '
     'forma independiente y su no aplicación no genera descuento, reembolso, crédito '
     'ni compensación económica alguna a favor del cliente.'),
    ('Elegibilidad',
     'Aplica exclusivamente a proyectos cuya inversión total supere los **1.800 USD** '
     '(o su equivalente en COP), calculada sobre el valor efectivo del proyecto en la '
     'moneda de esta propuesta.'),
    ('Condición de viabilidad',
     'Su implementación está sujeta a que exista tráfico o comportamiento de usuarios '
     'que resulte pertinente analizar. Si el proyecto no genera actividad susceptible '
     'de análisis, el beneficio **no resulta exigible**.'),
    ('Requisito de disponibilidad de datos',
     'Este módulo **captura, cuantifica y procesa** eventos de uso para exponerlos de '
     'forma agregada. **La ausencia o insuficiencia de datos impide la entrega del '
     'módulo, aun cuando el valor del proyecto habilite el beneficio**, sin que ello '
     'constituya incumplimiento.'),
    ('Alcance y límites',
     'Comprende hasta **6 reportes estándar** con datos de los últimos **12 meses**. '
     'Los reportes personalizados adicionales constituyen requerimientos '
     'independientes y se cotizan por separado.'),
    ('Dependencia de proveedores externos',
     'Cuando la analítica se apoye en plataformas o servicios de terceros, su '
     'funcionamiento queda supeditado a la disponibilidad, condiciones técnicas y '
     'políticas que dichos terceros definan de forma unilateral.'),
    ('Exclusiones',
     'No comprende auditorías de calidad de datos, ni la adecuación del proyecto a '
     'normativas o certificaciones específicas exigidas por terceros.'),
)

_ADMIN_CLAUSES_ES = _clauses(
    ('Naturaleza del beneficio',
     'El Módulo Administrativo se otorga como una **liberalidad comercial** incluida '
     'dentro del precio total del proyecto y **sin monto mínimo de inversión**. No '
     'constituye un servicio contratado de forma independiente.'),
    ('Condición de viabilidad',
     'Su implementación está sujeta a que la lógica de negocio del proyecto permita '
     'administrar contenido u operación de forma autónoma.'),
    ('Alcance y límites',
     'Se circunscribe a las entidades, flujos y gestores de contenido **expresamente '
     'listados en la sección de requerimientos funcionales** de esta propuesta.'),
    ('Exclusiones',
     'Toda entidad, flujo o gestor no listado dentro del alcance aprobado constituye '
     'un requerimiento independiente y se cotiza por separado.'),
)

_MANUAL_CLAUSES_ES = _clauses(
    ('Naturaleza del beneficio',
     'El Manual de Usuario Interactivo se otorga como una **liberalidad comercial** '
     'incluida dentro del precio total del proyecto y **sin monto mínimo de '
     'inversión**.'),
    ('Alcance y límites',
     'Documenta los procesos, flujos y roles comprendidos en el alcance aprobado, con '
     'un máximo de **15 artículos** y **una (1)** actualización de contenido.'),
    ('Vigencia de la actualización incluida',
     'La actualización de contenido incluida deberá solicitarse **a más tardar al '
     'cierre del proyecto**. Las actualizaciones posteriores constituyen '
     'requerimientos independientes y se cotizan por separado.'),
    ('Exclusiones',
     'No comprende capacitación presencial o sincrónica, producción de material '
     'audiovisual, ni traducción del contenido a otros idiomas.'),
)

_AI_CLAUSES_ES = _clauses(
    ('Naturaleza del beneficio',
     'La Automatización con Asistente de IA consiste en **integrar un proceso que hoy '
     'se ejecuta de forma manual con un asistente de IA (Claude o ChatGPT)**, de modo '
     'que pueda controlarse desde el chat del asistente y ejecutarse de forma '
     'desatendida mediante tareas programadas dentro del propio asistente. Se otorga '
     'como una **liberalidad comercial** incluida dentro del precio total del '
     'proyecto.'),
    ('Elegibilidad',
     'Aplica exclusivamente a proyectos cuya inversión total supere los **2.900 USD** '
     '(o su equivalente en COP), calculada sobre el valor efectivo del proyecto en la '
     'moneda de esta propuesta.'),
    ('Condición de viabilidad',
     'Su implementación está sujeta a que la lógica de negocio del proyecto permita y '
     'haga pertinente automatizar el proceso conectándolo a un asistente de IA.'),
    ('Requisito de disponibilidad de datos',
     'La automatización opera sobre datos e información del sistema. **Si el proceso '
     'no expone datos susceptibles de ser consultados o modificados de forma '
     'estructurada, no es técnicamente automatizable, aun cuando el valor del proyecto '
     'habilite el beneficio.**'),
    ('Alcance y límites',
     'Comprende **un (1) proceso de negocio**, definido de común acuerdo durante el '
     'levantamiento de requerimientos. Todo proceso adicional constituye un '
     'requerimiento independiente y se cotiza por separado.'),
    ('Vigencia',
     'El beneficio está disponible por un periodo de **6 meses contados a partir de la '
     'fecha de despliegue del proyecto en producción** (puesta en operación), y **no** '
     'desde la aceptación de esta propuesta ni desde la suscripción del contrato. '
     'Vencido dicho término, la continuidad del servicio se cotiza por separado.'),
    ('Dependencia de proveedores externos',
     'La integración depende de que el proveedor del asistente de IA (Anthropic para '
     'Claude u OpenAI para ChatGPT) **ofrezca y mantenga disponible** dicha capacidad '
     'de integración, en los planes, condiciones técnicas y términos de servicio que '
     'ese proveedor determine de forma unilateral. Su disponibilidad, alcance y '
     'continuidad son ajenos a nuestro control.'),
    ('Exclusión de responsabilidad',
     'Si el proveedor del asistente restringe, modifica, suspende o discontinúa esa '
     'capacidad de integración, o condiciona su uso a planes, cupos o requisitos '
     'distintos, la automatización podrá dejar de estar disponible total o '
     'parcialmente. **Dicha circunstancia no constituye incumplimiento** de nuestra '
     'parte y no genera responsabilidad, indemnización, reembolso ni obligación de '
     'sustitución a nuestro cargo.'),
    ('Costos de terceros',
     'Las suscripciones, licencias o consumos que cobre el proveedor del asistente de '
     'IA son por cuenta exclusiva del cliente y no están incluidos en el precio del '
     'proyecto.'),
)

_VALUE_ADDED_GENERAL_TERMS_ES = {
    'title': 'Disposiciones generales aplicables a los módulos incluidos',
    'clauses': _clauses(
        ('Naturaleza de los beneficios',
         'Los módulos descritos en esta sección se otorgan como una **liberalidad '
         'comercial** incluida dentro del precio total del proyecto y no fueron '
         'cotizados de forma separada. Su no aplicación no da lugar a descuento, '
         'reembolso, crédito ni compensación económica alguna.'),
        ('Condición de viabilidad y pertinencia técnica',
         'Cada módulo se implementa **únicamente si la lógica de negocio del proyecto '
         'lo permite** y si su incorporación resulta técnica y funcionalmente '
         'pertinente. Dicha valoración se realiza durante el levantamiento de '
         'requerimientos y se documenta como parte del alcance.'),
        ('Disponibilidad y suficiencia de datos',
         'Los módulos de KPIs, analítica y automatización con IA **operan sobre '
         'datos**: los capturan, los cuantifican y los procesan para exponer '
         'información resumida. En consecuencia, su entrega presupone la existencia de '
         'datos suficientes y pertinentes. **La ausencia o insuficiencia de datos '
         'impide la entrega del módulo, aun cuando el valor del proyecto satisfaga el '
         'umbral de elegibilidad**, sin que ello constituya incumplimiento.'),
        ('Dependencia de proveedores y servicios de terceros',
         'Cuando un módulo dependa de plataformas, APIs o servicios prestados por '
         'terceros, su funcionamiento queda supeditado a la disponibilidad, '
         'condiciones técnicas, políticas comerciales y términos de servicio que esos '
         'terceros definan de forma unilateral. **No respondemos por su modificación, '
         'suspensión o discontinuación.**'),
        ('Ausencia de garantía sobre resultados de negocio',
         'Los módulos son herramientas de gestión, medición y automatización. **No se '
         'garantiza resultado comercial alguno**, ni incremento de ventas, ahorro o '
         'rendimiento derivado de su uso.'),
        ('Tratamiento de datos personales',
         'Cuando la operación de un módulo implique tratamiento de datos personales, '
         'el cliente actúa como **responsable** del tratamiento y nosotros como '
         '**encargados**, en los términos de la **Ley 1581 de 2012** y del **Decreto '
         '1074 de 2015**. Corresponde al cliente contar con las autorizaciones, '
         'políticas y avisos de privacidad exigidos por la normativa aplicable.'),
        ('Fuerza mayor y caso fortuito',
         'No habrá responsabilidad por el incumplimiento o el retardo derivado de '
         'hechos constitutivos de **fuerza mayor o caso fortuito**, conforme al '
         'artículo 64 del Código Civil colombiano, incluidas las fallas de proveedores '
         'de infraestructura o de servicios de terceros.'),
        ('Intransferibilidad y no canje',
         'Los beneficios son personales del cliente y del proyecto descritos en esta '
         'propuesta. **No son acumulables** entre propuestas, **no son cedibles** a '
         'terceros y **no son canjeables por dinero**, descuento ni por otros '
         'entregables.'),
        ('Modificación por cambio de alcance',
         'Toda variación del alcance aprobado que afecte la viabilidad, el '
         'dimensionamiento o los límites de un módulo dará lugar a la revisión de las '
         'condiciones aquí previstas.'),
        ('Prevalencia del contrato y vigencia',
         'Estas condiciones complementan la propuesta comercial y su detalle técnico. '
         'En caso de discrepancia, **prevalece lo pactado en el contrato** suscrito '
         'entre las partes. Las condiciones aquí descritas se entienden vigentes por '
         'el término de validez de esta propuesta.'),
    ),
}

_KPI_CLAUSES_EN = _clauses(
    ('Nature of the benefit',
     'The KPIs & Metrics Dashboard is granted as a **commercial courtesy** included '
     'within the total price of the project. It is not an independently contracted '
     'service, and its non-application gives rise to no discount, refund, credit or '
     'financial compensation whatsoever in favour of the client.'),
    ('Eligibility',
     'It applies exclusively to projects whose total investment exceeds **1,500 USD** '
     '(or its equivalent in COP), calculated on the effective value of the project in '
     'the currency of this proposal.'),
    ('Feasibility condition',
     'Its implementation is subject to the project business logic allowing and '
     'warranting the definition and measurement of key indicators. If the business has '
     'no indicators worth measuring, the benefit **is not enforceable**.'),
    ('Data availability requirement',
     'This module **captures, quantifies and processes data** in order to surface it '
     'in summarised form as indicators. Its delivery presupposes that the system '
     'produces information capable of being measured. **If there is no data to process '
     'and no magnitudes to quantify, the module is not technically deliverable, even '
     'where the value of the project enables the benefit.**'),
    ('Scope and limits',
     'It covers up to **8 KPIs, 4 charts and 5 alerts**, agreed upon during '
     'requirements gathering. Any additional indicator, visualisation or alert '
     'constitutes an independent requirement and is quoted separately.'),
    ('Exclusions',
     'It does not cover the cleansing, migration or remediation of pre-existing '
     'historical data, nor integration with external data sources not contemplated '
     'within the approved scope.'),
)

_ANALYTICS_CLAUSES_EN = _clauses(
    ('Nature of the benefit',
     'The Analytics Module is granted as a **commercial courtesy** included within the '
     'total price of the project. It is not an independently contracted service, and '
     'its non-application gives rise to no discount, refund, credit or financial '
     'compensation whatsoever in favour of the client.'),
    ('Eligibility',
     'It applies exclusively to projects whose total investment exceeds **1,800 USD** '
     '(or its equivalent in COP), calculated on the effective value of the project in '
     'the currency of this proposal.'),
    ('Feasibility condition',
     'Its implementation is subject to the existence of traffic or user behaviour '
     'worth analysing. If the project generates no activity capable of analysis, the '
     'benefit **is not enforceable**.'),
    ('Data availability requirement',
     'This module **captures, quantifies and processes** usage events in order to '
     'surface them in aggregate form. **The absence or insufficiency of data prevents '
     'delivery of the module, even where the value of the project enables the '
     'benefit**, and this shall not constitute a breach.'),
    ('Scope and limits',
     'It covers up to **6 standard reports** with data from the last **12 months**. '
     'Additional custom reports constitute independent requirements and are quoted '
     'separately.'),
    ('Third-party provider dependency',
     'Where analytics relies on third-party platforms or services, its operation is '
     'subject to the availability, technical conditions and policies that those third '
     'parties unilaterally define.'),
    ('Exclusions',
     'It does not cover data quality audits, nor bringing the project into line with '
     'specific regulations or certifications required by third parties.'),
)

_ADMIN_CLAUSES_EN = _clauses(
    ('Nature of the benefit',
     'The Admin Module is granted as a **commercial courtesy** included within the '
     'total price of the project and **with no minimum investment**. It is not an '
     'independently contracted service.'),
    ('Feasibility condition',
     'Its implementation is subject to the project business logic allowing content or '
     'operations to be administered autonomously.'),
    ('Scope and limits',
     'It is confined to the entities, flows and content managers **expressly listed in '
     'the functional requirements section** of this proposal.'),
    ('Exclusions',
     'Any entity, flow or manager not listed within the approved scope constitutes an '
     'independent requirement and is quoted separately.'),
)

_MANUAL_CLAUSES_EN = _clauses(
    ('Nature of the benefit',
     'The Interactive User Manual is granted as a **commercial courtesy** included '
     'within the total price of the project and **with no minimum investment**.'),
    ('Scope and limits',
     'It documents the processes, flows and roles comprised within the approved scope, '
     'up to a maximum of **15 articles** and **one (1)** content update.'),
    ('Term of the included update',
     'The included content update must be requested **no later than project closure**. '
     'Subsequent updates constitute independent requirements and are quoted '
     'separately.'),
    ('Exclusions',
     'It does not cover in-person or synchronous training, audiovisual material '
     'production, or translation of the content into other languages.'),
)

_AI_CLAUSES_EN = _clauses(
    ('Nature of the benefit',
     'AI Assistant Automation consists of **integrating a process currently performed '
     'manually with an AI assistant (Claude or ChatGPT)**, so that it can be driven '
     'from the assistant chat and run unattended via scheduled tasks within the '
     'assistant itself. It is granted as a **commercial courtesy** included within the '
     'total price of the project.'),
    ('Eligibility',
     'It applies exclusively to projects whose total investment exceeds **2,900 USD** '
     '(or its equivalent in COP), calculated on the effective value of the project in '
     'the currency of this proposal.'),
    ('Feasibility condition',
     'Its implementation is subject to the project business logic allowing and '
     'warranting automation of the process by connecting it to an AI assistant.'),
    ('Data availability requirement',
     'The automation operates on system data and information. **If the process does '
     'not expose data capable of being queried or modified in a structured way, it is '
     'not technically automatable, even where the value of the project enables the '
     'benefit.**'),
    ('Scope and limits',
     'It covers **one (1) business process**, agreed upon during requirements '
     'gathering. Any additional process constitutes an independent requirement and is '
     'quoted separately.'),
    ('Term',
     'The benefit is available for a period of **6 months counted from the date the '
     'project is deployed to production** (go-live), and **not** from acceptance of '
     'this proposal nor from execution of the contract. Once that term expires, '
     'continuity of the service is quoted separately.'),
    ('Third-party provider dependency',
     'The integration depends on the AI assistant provider (Anthropic for Claude or '
     'OpenAI for ChatGPT) **offering and keeping available** that integration '
     'capability, under the plans, technical conditions and terms of service that the '
     'provider unilaterally determines. Its availability, scope and continuity are '
     'beyond our control.'),
    ('Limitation of liability',
     'Should the assistant provider restrict, modify, suspend or discontinue that '
     'integration capability, or condition its use on different plans, quotas or '
     'requirements, the automation may cease to be available in whole or in part. '
     '**Such circumstance does not constitute a breach** on our part and gives rise to '
     'no liability, indemnity, refund or obligation to provide a substitute on our '
     'account.'),
    ('Third-party costs',
     'Subscriptions, licences or usage charged by the AI assistant provider are borne '
     'exclusively by the client and are not included in the price of the project.'),
)

_VALUE_ADDED_GENERAL_TERMS_EN = {
    'title': 'General provisions applicable to the included modules',
    'clauses': _clauses(
        ('Nature of the benefits',
         'The modules described in this section are granted as a **commercial '
         'courtesy** included within the total price of the project and were not '
         'quoted separately. Their non-application gives rise to no discount, refund, '
         'credit or financial compensation whatsoever.'),
        ('Feasibility and technical relevance condition',
         'Each module is implemented **only if the project business logic allows it** '
         'and if its incorporation is technically and functionally relevant. That '
         'assessment is carried out during requirements gathering and documented as '
         'part of the scope.'),
        ('Data availability and sufficiency',
         'The KPIs, analytics and AI automation modules **operate on data**: they '
         'capture it, quantify it and process it in order to surface summarised '
         'information. Their delivery therefore presupposes the existence of '
         'sufficient and relevant data. **The absence or insufficiency of data '
         'prevents delivery of the module, even where the value of the project meets '
         'the eligibility threshold**, and this shall not constitute a breach.'),
        ('Dependency on third-party providers and services',
         'Where a module depends on platforms, APIs or services provided by third '
         'parties, its operation is subject to the availability, technical conditions, '
         'commercial policies and terms of service that those third parties '
         'unilaterally define. **We are not liable for their modification, suspension '
         'or discontinuation.**'),
        ('No warranty as to business results',
         'The modules are management, measurement and automation tools. **No '
         'commercial result is warranted**, nor any increase in sales, savings or '
         'performance derived from their use.'),
        ('Personal data processing',
         'Where the operation of a module involves the processing of personal data, '
         'the client acts as **data controller** and we act as **data processor**, '
         'under **Law 1581 of 2012** and **Decree 1074 of 2015** of Colombia. It is '
         'incumbent on the client to hold the authorisations, policies and privacy '
         'notices required by the applicable regulations.'),
        ('Force majeure and fortuitous event',
         'There shall be no liability for non-performance or delay arising from events '
         'constituting **force majeure or a fortuitous event**, under article 64 of '
         'the Colombian Civil Code, including failures of infrastructure providers or '
         'third-party services.'),
        ('Non-transferability and no cash equivalent',
         'The benefits are personal to the client and the project described in this '
         'proposal. They **are not cumulative** across proposals, **are not '
         'assignable** to third parties and **are not exchangeable for cash**, '
         'discounts or other deliverables.'),
        ('Amendment upon change of scope',
         'Any variation of the approved scope affecting the feasibility, sizing or '
         'limits of a module shall give rise to a review of the conditions set out '
         'herein.'),
        ('Precedence of the contract and validity',
         'These conditions supplement the commercial proposal and its technical '
         'detail. In the event of any discrepancy, **the terms agreed in the contract** '
         'executed between the parties shall prevail. The conditions described herein '
         'are understood to be in force for the validity period of this proposal.'),
    ),
}


# ---------------------------------------------------------------------------
# Default section configurations extracted from existing Vue component props.
# Each entry maps to the content_json stored in ProposalSection.
# ---------------------------------------------------------------------------

DEFAULT_SECTIONS = [
    {
        'section_type': 'greeting',
        'title': '👋 Saludo',
        'order': 0,
        'is_wide_panel': False,
        'content_json': {
            'proposalTitle': '',
            'clientName': '',
            'inspirationalQuote': '',
        },
    },
    {
        'section_type': 'executive_summary',
        'title': '🧾 Lo que vas a lograr',
        'order': 1,
        'is_wide_panel': False,
        'content_json': {
            'index': '1',
            'title': 'Resumen ejecutivo',
            'paragraphs': [
                'Nuestra propuesta contempla el diseño y desarrollo de un sitio web profesional.',
            ],
            'highlightsTitle': 'Incluye',
            'highlights': [
                'Diseño visual personalizado',
                'Desarrollo web responsivo',
                'Optimización SEO básica',
            ],
        },
    },
    {
        'section_type': 'context_diagnostic',
        'title': '🧩 Tu situación actual y la oportunidad',
        'order': 2,
        'is_wide_panel': False,
        'content_json': {
            'index': '2',
            'title': 'Contexto y diagnóstico',
            'paragraphs': [
                'El cliente busca fortalecer su presencia digital con un sitio web que refleje su identidad profesional.',
            ],
            'issuesTitle': 'Desafíos identificados',
            'issues': [
                'Ausencia de presencia digital profesional',
                'Dificultad para captar clientes en línea',
            ],
            'opportunityTitle': '<strong>Oportunidad</strong>',
            'opportunity': (
                'Crear una plataforma digital que genere confianza y convierta visitantes en clientes.'
            ),
        },
    },
    {
        'section_type': 'conversion_strategy',
        'title': '🚀 Cómo vamos a lograrlo',
        'order': 3,
        'is_wide_panel': False,
        'content_json': {
            'index': '3',
            'title': 'Enfoque propuesto y estrategia de conversión',
            'intro': (
                'La página se construirá como una herramienta para generar confianza '
                'y convertir visitas en conversaciones.'
            ),
            'steps': [
                {
                    'title': '👀 Captar atención en los primeros segundos',
                    'bullets': [
                        'Mensaje principal claro: qué hace el cliente y a quién ayuda',
                        'Beneficio directo visible',
                        'Botón visible de contacto',
                    ],
                },
                {
                    'title': '🤝 Construir confianza rápidamente',
                    'bullets': [
                        'Sección breve de "Quién soy"',
                        'Señales de credibilidad',
                        'Lenguaje simple, centrado en resolver problemas reales',
                    ],
                },
                {
                    'title': '🧾 Presentar servicios como "soluciones"',
                    'bullets': [
                        'Servicios organizados por necesidades',
                        'Para cada servicio: qué incluye / para quién es',
                        'Contenido corto y escaneable',
                    ],
                },
                {
                    'title': '🖼️ Mantener contenido fresco',
                    'bullets': [
                        'Autogestión para actualizar imágenes y/o videos',
                        'Ideal para renovar material sin ayuda técnica',
                    ],
                },
            ],
            'resultTitle': '🎯 Resultado esperado',
            'result': (
                'Una página que no solo "se vea bonita", sino que genere contactos, '
                'transmita profesionalismo y haga fácil que la gente diga: "Listo, le escribo".'
            ),
        },
    },
    {
        'section_type': 'roi_projection',
        'title': '📈 Proyección de retorno y beneficios',
        'order': 4,
        'is_wide_panel': False,
        'content_json': {
            'index': '4',
            'title': 'Proyección de retorno y beneficios',
            'subtitle': (
                'Lo que esta inversión puede generar para tu negocio — '
                'métricas clave del modelo financiero.'
            ),
            'kpis': [],
            'methodology': '',
            'scenariosTitle': 'Escenarios proyectados al primer año',
            'scenarios': [],
            'ctaNote': '',
        },
    },
    {
        'section_type': 'investment',
        'title': '💰 Tu inversión y cómo pagar',
        'order': 5,
        'is_wide_panel': False,
        'content_json': {
            'index': '4',
            'title': 'Inversión y Formas de Pago',
            'introText': 'La inversión total para este proyecto es:',
            'totalInvestment': '',
            'currency': 'COP',
            'whatsIncluded': [
                {'icon': '🎨', 'title': 'Diseño', 'description': 'UX/UI enfocado en conversión'},
                {'icon': '⚙️', 'title': 'Desarrollo', 'description': 'Implementación completa del proyecto'},
                {'icon': '🚀', 'title': 'Despliegue y Entrega', 'description': 'Despliegue en producción y puesta en marcha'},
            ],
            'paymentOptions': [
                {'label': '40% al firmar el contrato ✍️', 'description': ''},
                {'label': '30% al aprobar el diseño final ✅', 'description': ''},
                {'label': '30% al desplegar el sitio web 🚀', 'description': ''},
            ],
            'hostingPlan': {
                'title': 'Hosting, Mantenimiento y Soporte',
                'description': 'Infraestructura optimizada para proyectos de alto rendimiento y disponibilidad:',
                'specs': [
                    {'icon': '🧠', 'label': 'vCPU', 'value': '4 núcleos de vCPU'},
                    {'icon': '🧮', 'label': 'RAM', 'value': '8 GB de RAM dedicada'},
                    {'icon': '💾', 'label': 'Almacenamiento', 'value': '100 GB de almacenamiento NVMe'},
                    {'icon': '🌐', 'label': 'Ancho de banda', 'value': '4 TB mensual'},
                    {'icon': '📍', 'label': 'Centros de datos', 'value': 'EE.UU., Brasil, Francia, Lituania e India'},
                    {'icon': '🧬', 'label': 'Compatibilidad', 'value': 'Linux (Ubuntu)'},
                ],
                'hostingPercent': 80,
                'billingTiers': [
                    {
                        'frequency': 'nine_month',
                        'months': 9,
                        'discountPercent': 40,
                        'label': 'Cada 9 meses',
                        'badge': 'Máximo descuento',
                    },
                    {
                        'frequency': 'semiannual',
                        'months': 6,
                        'discountPercent': 20,
                        'label': 'Semestral',
                        'badge': '20% dcto',
                    },
                    {
                        'frequency': 'quarterly',
                        'months': 3,
                        'discountPercent': 10,
                        'label': 'Trimestral',
                        'badge': '10% dcto',
                    },
                ],
                'renewalNote': (
                    'Renovaciones para cada año de renovación (a partir del segundo año): '
                    'el costo se ajusta una vez al año tomando como referencia el porcentaje '
                    'en que aumentó el SMLMV (Salario Mínimo Legal Mensual Vigente en Colombia) '
                    'ese año, más un 8% fijo, aplicado sobre el costo del año anterior:\n\n'
                    'Costo de renovación = Costo del año anterior × '
                    '(1 + (% de aumento del SMLMV + 8%))\n\n'
                    'Por ejemplo, si el SMLMV aumentó 5%, el incremento total sería '
                    '5% + 8% = 13%. Si venías pagando $100.000 COP, el nuevo costo sería '
                    '$113.000 COP (un aumento de $13.000).'
                ),
                'coverageNote': (
                    'El costo de hosting cubre tres componentes: el mantenimiento técnico '
                    'de la plataforma (actualizaciones de seguridad, parches y optimización '
                    'de base de datos), el soporte ante incidencias o bugs, y los recursos '
                    'computacionales necesarios para que todo funcione (servidor, '
                    'almacenamiento, ancho de banda y certificados SSL).'
                ),
                'freeMonths': 1,
                'freeMonthsVisible': True,
                'freeMonthNote': HOSTING_FREE_MONTH_NOTES['es'],
            },
            'paymentMethods': [
                'Transferencia bancaria',
                'Nequi / Daviplata',
            ],
            'modules': [],
            'valueReasons': [
                'Diseño hecho a medida',
                'Código optimizado',
                'Soporte post-lanzamiento',
            ],
        },
    },
    {
        'section_type': 'timeline',
        'title': '⏳ Cuándo lo tendrás listo',
        'order': 7,
        'is_wide_panel': True,
        'content_json': {
            'index': '6',
            'title': 'Cronograma del Proyecto',
            'introText': 'El proyecto se desarrollará en las siguientes fases:',
            'totalDuration': 'Aproximadamente 1 mes',
            'phases': [
                {
                    'title': '🎨 Diseño',
                    'duration': '1 semana',
                    'weeks': 'Semana 1',
                    'circleColor': 'bg-purple-600',
                    'statusColor': 'bg-purple-100 text-purple-700',
                    'description': 'Diseño visual personalizado en Figma, revisiones y ajustes.',
                    'tasks': ['Moodboard y paleta de colores', 'Diseño UI en alta fidelidad', 'Revisiones con el cliente'],
                    'milestone': 'Diseño aprobado',
                },
                {
                    'title': '💻 Desarrollo',
                    'duration': '2 semanas',
                    'weeks': 'Semanas 2-3',
                    'circleColor': 'bg-green-600',
                    'statusColor': 'bg-green-100 text-green-700',
                    'description': 'Codificación nativa, integración de pasarelas y correos.',
                    'tasks': ['Frontend responsivo', 'Backend y base de datos', 'Integraciones'],
                    'milestone': 'MVP funcional',
                },
                {
                    'title': '🚀 QA y Lanzamiento',
                    'duration': '3 días',
                    'weeks': 'Semana 4',
                    'circleColor': 'bg-orange-600',
                    'statusColor': 'bg-orange-100 text-orange-700',
                    'description': 'Pruebas finales, ajustes y publicación.',
                    'tasks': ['Pruebas en múltiples navegadores', 'Ajustes finales', 'Despliegue a producción'],
                    'milestone': 'Sitio en producción',
                },
                {
                    'title': '📦 Entrega y despliegue',
                    'duration': '3 días',
                    'weeks': 'Semana 4',
                    'circleColor': 'bg-pink-600',
                    'statusColor': 'bg-pink-100 text-pink-700',
                    'description': 'Configuración del dominio, entrega de documentación y cierre.',
                    'tasks': ['Configuración de dominio y SSL', 'Entrega de documentación', 'Capacitación al cliente'],
                    'milestone': 'Entrega final 💫',
                },
            ],
        },
    },
    {
        'section_type': 'design_ux',
        'title': '🎨 Una experiencia visual que enamora',
        'order': 8,
        'is_wide_panel': False,
        'content_json': {
            'index': '7',
            'title': 'Diseño Visual y Experiencia de Usuario',
            'paragraphs': [
                'El desarrollo web será concebido como una experiencia digital profesional.',
                'Cada sección será creada cuidadosamente para generar un recorrido fluido.',
            ],
            'focusTitle': 'Estructura que resalta',
            'focusItems': [
                'Presentación clara del servicio',
                'Integración con redes sociales',
                'Espacio para agendar citas o consultas',
            ],
            'objectiveTitle': '<strong>Objetivo</strong>',
            'objective': (
                'Inspirar confianza desde el primer momento, reflejando autenticidad '
                'y la profundidad del mensaje.'
            ),
        },
    },
    {
        'section_type': 'creative_support',
        'title': '🤝 Te acompañamos en cada paso',
        'order': 9,
        'is_wide_panel': False,
        'content_json': {
            'index': '8',
            'title': 'Acompañamiento Creativo Personalizado',
            'paragraphs': [
                'Durante todo el proceso, el cliente contará con el acompañamiento cercano de nuestro equipo.',
                'El proceso será colaborativo, cálido y empático.',
            ],
            'includesTitle': 'Incluye',
            'includes': [
                '💡 Sesiones de revisión y retroalimentación sobre diseño y estructura.',
                '🎨 Apoyo en la selección de paleta de colores, tipografía y estilo visual.',
                '🕊 Adaptaciones según la evolución de las ideas.',
                '🔗 Aseguramiento de coherencia entre estética, contenido y propósito.',
            ],
            'closing': (
                'Cada decisión será una co-creación, en la que el cliente podrá participar '
                'activamente para que el resultado final refleje fielmente su mensaje.'
            ),
        },
    },
    {
        'section_type': 'value_added_modules',
        'title': '🎁 Incluido sin costo adicional',
        'order': 11,
        'is_wide_panel': False,
        'content_json': {
            'index': '11',
            'title': 'Lo que sumamos a tu proyecto sin costo extra',
            'intro': (
                'Estos módulos no se cobran aparte. Se incluyen porque creemos que todo '
                'entregable debería venir con las herramientas mínimas para operarlo, '
                'medirlo y entenderlo desde el día uno.'
            ),
            'module_ids': ['admin_module', 'manual_module', 'kpi_dashboard_module', 'analytics_dashboard', 'ai_automation_module'],
            'justifications': {
                'admin_module': 'Para que no dependas de un desarrollador cada vez que necesites cambiar contenido.',
                'analytics_dashboard': 'Para que sepas cómo se comporta tu audiencia sin contratar herramientas externas.',
                'kpi_dashboard_module': 'Para tomar decisiones con datos en tiempo real, no con intuición.',
                'manual_module': 'Para que cualquier persona del equipo entienda el sistema sin sesiones de capacitación.',
                'ai_automation_module': 'Para que un proceso que hoy haces a mano lo controles desde el chat de un asistente de IA y se ejecute solo con tareas programadas.',
            },
            # Per-module gating/terms (Req 3). Keys are module ids. Each benefit
            # applies solo si la lógica de negocio lo permite y tiene sentido
            # medir/automatizar. Los mínimos se comparan contra el total efectivo
            # en la moneda de la propuesta ("condicionado", nunca se oculta).
            # The legal wording lives in the _*_CLAUSES_ES catalog above.
            'conditions': {
                'kpi_dashboard_module': _module_condition(
                    _KPI_CLAUSES_ES,
                    min_price_usd=1500,
                    min_price_cop=6000000,
                    discretionary_note='Se implementa si la lógica de negocio permite y tiene sentido definir y medir KPIs.',
                ),
                'analytics_dashboard': _module_condition(
                    _ANALYTICS_CLAUSES_ES,
                    min_price_usd=1800,
                    min_price_cop=7200000,
                    discretionary_note='Se implementa si la lógica de negocio permite y tiene sentido recolectar y analizar datos de uso.',
                ),
                'admin_module': _module_condition(
                    _ADMIN_CLAUSES_ES,
                    discretionary_note='Se implementa si la lógica de negocio permite gestionar contenido u operación de forma autónoma.',
                ),
                'manual_module': _module_condition(
                    _MANUAL_CLAUSES_ES,
                    discretionary_note='Se implementa sobre los procesos y roles definidos dentro del alcance de la propuesta.',
                ),
                'ai_automation_module': _module_condition(
                    _AI_CLAUSES_ES,
                    min_price_usd=2900,
                    min_price_cop=10400000,
                    duration_months=6,
                    discretionary_note='Se implementa si la lógica de negocio permite y tiene sentido automatizar el proceso conectándolo a un asistente de IA.',
                ),
            },
            # Cross-cutting legal provisions rendered after the module cards in
            # both the web section and the PDF annex.
            'general_terms': deepcopy(_VALUE_ADDED_GENERAL_TERMS_ES),
            'footer_note': 'Total adicional: $0. Ya está cotizado dentro del precio del proyecto.',
        },
    },
    {
        'section_type': 'functional_requirements',
        'title': '🧩 Todo lo que incluye tu proyecto',
        'order': 10,
        'is_wide_panel': True,
        'content_json': {
            'index': '10',
            'title': 'Requerimientos Funcionales del Proyecto',
            'intro': 'A continuación se detallan los requerimientos funcionales del proyecto.',
            'groups': [
                {
                    'id': 'views',
                    'icon': '🖥️',
                    'title': 'Vistas',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Cada vista es una pantalla o sección del sitio. Su propósito es guiar al visitante '
                        'para conocer la propuesta de valor y facilitar el contacto o la acción deseada.'
                    ),
                    'items': [
                        {'icon': '🏠', 'name': 'Inicio (Página de Aterrizaje)', 'description': 'Es la primera impresión del sitio. Aquí se presenta de forma clara la identidad de la marca, con un mensaje atractivo, llamado a la acción, y acceso rápido a las secciones principales.'},
                        {'icon': 'ℹ️', 'name': 'Acerca de Nosotros', 'description': 'Página dedicada a compartir la historia, misión, visión y valores de la empresa o proyecto. Ideal para generar confianza con el visitante.'},
                        {'icon': '📞', 'name': 'Contacto', 'description': 'Sección con un formulario para que los usuarios puedan enviar mensajes, junto con información de contacto (teléfono, correo, dirección) y un mapa si se desea incluir.'},
                        {'icon': '📜', 'name': 'Términos y Condiciones', 'description': 'Página para informar a los usuarios sobre las políticas del sitio, manejo de datos personales y términos de uso. Incluye un checkbox para aceptación, garantizando el cumplimiento de las normativas vigentes.'},
                        {'icon': '🛒', 'name': 'Categorías', 'description': 'Sección para mostrar las categorías disponibles de productos, permitiendo a los usuarios explorar los diferentes tipos de productos que ofrece el sitio.'},
                        {'icon': '🗂️', 'name': 'Catálogo por Categoría', 'description': 'Permite a los usuarios explorar los productos dentro de una categoría específica, facilitando la navegación y selección de productos relacionados.'},
                        {'icon': '📦', 'name': 'Vista de Productos', 'description': 'Muestra los detalles de un producto seleccionado, incluyendo imágenes, precio, características, descripciones y opciones para agregar al carrito.'},
                        {'icon': '🛒', 'name': 'Carrito de Compra', 'description': 'Permite a los usuarios ver los productos que han agregado, ajustar cantidades, eliminar artículos y proceder al pago.'},
                        {'icon': '📜', 'name': 'Historial de Compras', 'description': 'Permite a los usuarios revisar las compras realizadas, incluyendo detalles como fecha, monto y productos adquiridos.'},
                        {'icon': '👤', 'name': 'Registro de Usuario', 'description': 'Permite a los usuarios crear una cuenta para acceder a funciones personalizadas, como historial de compras y productos favoritos.'},
                        {'icon': '🔐', 'name': 'Inicio de Sesión', 'description': 'Proporciona acceso a usuarios registrados para gestionar sus compras y preferencias.'},
                        {'icon': '❤️', 'name': 'Lista de deseos Favoritos', 'description': 'Permite a los usuarios guardar productos para una rápida referencia en futuras visitas.'},
                        {'icon': '📝', 'name': 'Perfil del Usuario', 'description': 'Sección donde los usuarios pueden ver y actualizar su información personal, historial de compras y configuraciones de cuenta.'},
                    ],
                },
                {
                    'id': 'components',
                    'icon': '🧩',
                    'title': 'Componentes',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Los componentes son elementos visuales o funcionales que se reutilizan en varias '
                        'secciones del sitio. Esto mantiene una experiencia coherente y optimiza el desarrollo.'
                    ),
                    'items': [
                        {'icon': '🔝', 'name': 'Encabezado (Header)', 'description': 'Incluye el logotipo, menú de navegación y acceso rápido a redes sociales o secciones clave del sitio.'},
                        {'icon': '🔚', 'name': 'Pie de página (Footer)', 'description': 'Contiene información adicional como derechos de autor, políticas, enlaces a redes sociales y otros recursos útiles.'},
                        {'icon': '🎯', 'name': 'Carrusel de Productos destacados', 'description': 'Destaca productos seleccionados como promociones, ofertas especiales o productos estacionales para mejorar la visibilidad y el interés de los clientes.'},
                        {'icon': '🎁', 'name': 'Carrusel de lista de deseos destacadas', 'description': 'Destaca listas de deseos seleccionados como promociones, ofertas especiales o productos estacionales para mejorar la visibilidad y el interés de los clientes.'},
                        {'icon': '❓', 'name': 'Preguntas Frecuentes (FAQ)', 'description': 'Sección para responder las preguntas más comunes de los clientes y resolver dudas de manera rápida y eficiente.'},
                    ],
                },
                {
                    'id': 'features',
                    'icon': '⚙️',
                    'title': 'Funcionalidades Específicas',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Las funcionalidades son acciones o comportamientos interactivos del sitio web. '
                        'Le dan vida y dinamismo a la página, permitiendo que funcione de forma práctica y útil.'
                    ),
                    'items': [
                        {'icon': '🔑', 'name': 'Registro con Google', 'description': 'Alta de cuenta en un solo clic con la cuenta de Google del usuario (OAuth). Captura nombre y correo verificados sin formularios largos — clave para conocer los datos reales de los clientes interesados desde el primer contacto. 🔐📧'},
                        {'icon': '🔓', 'name': 'Inicio de Sesión con Google', 'description': 'Acceso inmediato para usuarios ya registrados con su cuenta de Google, sin contraseñas adicionales que recordar ni recuperar. Menos fricción en cada visita recurrente. ⚡'},
                        {'icon': '🔎', 'name': 'Buscador Avanzado con Filtros Dinámicos', 'description': 'Los usuarios podrán filtrar inmuebles por zonas, rango de precios, metros cuadrados y características específicas. Esta navegación intuitiva ahorra tiempo al cliente y califica mejor el interés. 🔍📍'},
                        {'icon': '💬', 'name': 'WhatsApp Directo por Propiedad', 'description': 'En cada ficha de inmueble habrá un botón de contacto inmediato. Al hacer clic, se recibirá un mensaje predeterminado indicando exactamente por qué propiedad está preguntando el cliente. 📲⚡'},
                        {'icon': '🖼️', 'name': 'Visualización Enriquecida y Galerías', 'description': 'Sistema de visualización de alta calidad con zoom interactivo y carga optimizada para que las imágenes de los inmuebles luzcan impecables sin afectar la velocidad del sitio. 📸✨'},
                        {'icon': '📩', 'name': 'Notificaciones Automáticas', 'description': 'El sistema enviará correos de confirmación automáticos cuando un usuario se registre o envíe una solicitud de información, manteniendo el contacto activo desde el primer segundo. 📩✅'},
                    ],
                },
                {
                    'id': 'cross_cutting_features',
                    'icon': '🔗',
                    'title': 'Funcionalidades Transversales',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Capacidades de calidad que atraviesan varias vistas, componentes y flujos. '
                        'Este catálogo es un punto de partida: debe adaptarse al negocio, la etapa '
                        'del producto y el alcance real de cada propuesta.'
                    ),
                    'items': [
                        {'icon': '📱', 'name': 'Diseño Responsive', 'description': 'La experiencia se adapta a los tamaños de pantalla y formas de interacción definidos para el proyecto, priorizando los dispositivos relevantes para sus usuarios.'},
                        {'icon': '♿', 'name': 'Accesibilidad', 'description': 'La interfaz contempla navegación, contraste, etiquetas y estados comprensibles según el público y el nivel de accesibilidad acordado.'},
                        {'icon': '🧭', 'name': 'Usabilidad Consistente', 'description': 'Los patrones de interacción y retroalimentación se mantienen coherentes entre las vistas y los flujos incluidos en el alcance.'},
                        {'icon': '⚡', 'name': 'Rendimiento', 'description': 'Las pantallas y los recursos se optimizan para ofrecer tiempos de respuesta adecuados al contenido, tráfico y dispositivos esperados.'},
                        {'icon': '🛡️', 'name': 'Seguridad', 'description': 'Los accesos, formularios y operaciones sensibles aplican controles proporcionales a los riesgos y roles definidos para el proyecto.'},
                        {'icon': '🔒', 'name': 'Privacidad de Datos', 'description': 'La captura, el uso y la conservación de datos se limitan a lo necesario y se ajustan a las obligaciones aplicables al negocio.'},
                        {'icon': '🌐', 'name': 'Compatibilidad entre Navegadores', 'description': 'La experiencia se valida en los navegadores y versiones acordados según la audiencia y las condiciones reales de uso.'},
                    ],
                },
                {
                    'id': 'admin_module',
                    'icon': '🛠️',
                    'title': 'Módulo Administrativo',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'El módulo administrativo permite gestionar el contenido y la operación del sitio '
                        'sin depender de desarrollo técnico. El alcance cubre únicamente los gestores '
                        'listados en esta propuesta; gestores adicionales se cotizan como ampliación.'
                    ),
                    'items': [
                        {'icon': '📂', 'name': 'Gestor de Productos', 'description': 'Crear, editar y eliminar productos o contenidos principales.'},
                        {'icon': '🗂️', 'name': 'Gestor de Categorías', 'description': 'Organización del catálogo por categorías o colecciones.'},
                        {'icon': '👥', 'name': 'Gestor de Usuarios', 'description': 'Administración de cuentas de usuario.'},
                        {'icon': '📝', 'name': 'Gestor de Blogs', 'description': 'Publicación y gestión de artículos o contenido editorial.'},
                        {'icon': '❤️', 'name': 'Gestor de Favoritos', 'description': 'Gestión de listas de deseos o favoritos de usuarios.'},
                    ],
                },
                {
                    'id': 'analytics_dashboard',
                    'icon': '📊',
                    'title': 'Módulo de Analítica',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Dashboard de reportes inteligentes y métricas en tiempo real para entender '
                        'el comportamiento de los visitantes y tomar decisiones basadas en datos. '
                        'Incluye hasta 6 reportes estándar (los listados aquí) con datos de los '
                        'últimos 12 meses; reportes personalizados adicionales se cotizan aparte.'
                    ),
                    'items': [
                        {
                            'icon': '🔥',
                            'name': 'Páginas y Productos Más Visitados',
                            'description': (
                                'Identifica qué secciones y productos generan más interés. '
                                'Permite priorizar contenido, reorganizar el catálogo y potenciar '
                                'lo que realmente atrae a tus visitantes.'
                            ),
                        },
                        {
                            'icon': '🔄',
                            'name': 'Visitantes Nuevos vs Recurrentes',
                            'description': (
                                'Diferencia entre quienes llegan por primera vez y quienes regresan. '
                                'Te ayuda a medir la fidelización y evaluar si tus estrategias de '
                                'retención están funcionando.'
                            ),
                        },
                        {
                            'icon': '📱',
                            'name': 'Dispositivos de tu Audiencia',
                            'description': (
                                'Conoce desde qué dispositivos navegan tus usuarios: móvil, tablet o escritorio. '
                                'Esto permite optimizar la experiencia para el dispositivo más usado por tu público.'
                            ),
                        },
                        {
                            'icon': '🌍',
                            'name': 'Origen Geográfico',
                            'description': (
                                'Visualiza de qué ciudades o países provienen tus visitantes. '
                                'Ideal para enfocar campañas publicitarias y entender dónde está '
                                'tu mercado real.'
                            ),
                        },
                        {
                            'icon': '🔗',
                            'name': 'Fuentes de Tráfico',
                            'description': (
                                'Descubre cómo llegan los usuarios a tu sitio: búsqueda orgánica, '
                                'redes sociales, enlaces directos o campañas pagadas. Permite invertir '
                                'mejor tu presupuesto de marketing.'
                            ),
                        },
                        {
                            'icon': '📈',
                            'name': 'Tendencia de Visitas',
                            'description': (
                                'Gráfico de evolución de visitas en el tiempo. Permite detectar picos, '
                                'medir el impacto de campañas y entender patrones estacionales de tu audiencia.'
                            ),
                        },
                    ],
                },
                {
                    'id': 'kpi_dashboard_module',
                    'icon': '📊',
                    'title': 'Dashboard de KPIs y Métricas',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Panel de control complementario al módulo de analítica, con indicadores '
                        'clave de rendimiento en tiempo real para monitorear la salud de tu '
                        'negocio y tomar decisiones basadas en datos. Incluye hasta 8 KPIs y '
                        '4 gráficos, definidos junto al cliente al inicio del proyecto.'
                    ),
                    'items': [
                        {'icon': '📈', 'name': 'KPIs en tiempo real', 'description': 'Visualiza los indicadores más importantes de tu negocio actualizados al instante: ventas, conversiones, tráfico y más. Hasta 8 indicadores definidos junto al cliente.'},
                        {'icon': '📊', 'name': 'Gráficos interactivos', 'description': 'Dashboards visuales con gráficos de línea, barras y torta que permiten filtrar por período, categoría o segmento. Hasta 4 gráficos incluidos.'},
                        {'icon': '🔔', 'name': 'Alertas de rendimiento', 'description': 'Notificaciones automáticas cuando un KPI cae por debajo del umbral definido o supera una meta establecida. Hasta 5 alertas configuradas dentro del alcance.'},
                        {'icon': '📥', 'name': 'Exportación de reportes', 'description': 'Descarga reportes en CSV para compartir con tu equipo o stakeholders sin necesidad de acceder al sistema.'},
                    ],
                },
                {
                    'id': 'manual_module',
                    'icon': '📘',
                    'title': 'Manual de Usuario Interactivo',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Manual/wiki interactivo no técnico, con índice navegable y buscador, '
                        'que describe los procesos, flujos, dependencias, roles y responsabilidades '
                        'de tu aplicación. Pensado para que cualquier persona del equipo pueda '
                        'entender el sistema sin pedir ayuda al desarrollador. Cubre los procesos '
                        'y roles del alcance aprobado, con hasta 15 artículos de documentación y '
                        'una (1) actualización incluida al momento de la entrega.'
                    ),
                    'items': [
                        {'icon': '🔎', 'name': 'Buscador y navegación por índice', 'description': 'Encuentra cualquier proceso, vista o rol en segundos.'},
                        {'icon': '🧭', 'name': 'Procesos y flujos paso a paso', 'description': 'Cada flujo del sistema documentado en lenguaje claro, sin tecnicismos.'},
                        {'icon': '👥', 'name': 'Roles y responsabilidades', 'description': 'Quién hace qué dentro de la aplicación y qué permisos tiene cada rol.'},
                        {'icon': '🔗', 'name': 'Dependencias y reglas de negocio', 'description': 'Cómo se relacionan los módulos entre sí y qué reglas aplican.'},
                    ],
                },
                {
                    'id': 'ai_automation_module',
                    'icon': '🤖',
                    'title': 'Automatización con Asistente de IA',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Tomamos un (1) proceso que hoy realizas de forma manual y lo automatizamos '
                        'conectándolo a un asistente de IA (Claude o ChatGPT). Desde el chat podrás '
                        'controlar el proceso y, mediante tareas programadas dentro del propio '
                        'asistente, dejar que se ejecute solo.'
                    ),
                    'items': [
                        {'icon': '💬', 'name': 'Control desde el chat', 'description': 'Ejecuta y supervisa el proceso conversando con el asistente de IA, sin entrar al sistema.'},
                        {'icon': '⏰', 'name': 'Tareas programadas', 'description': 'El propio asistente ejecuta el proceso de forma automática según la programación que definas.'},
                        {'icon': '🔗', 'name': 'Integración con tu proceso actual', 'description': 'Conectamos la automatización directamente sobre el flujo manual que ya usas hoy.'},
                    ],
                },
            ],
            'additionalModules': [
                {
                    'id': 'integration_electronic_invoicing',
                    'icon': '🧾',
                    'title': 'Facturación Electrónica e Integración DIAN (Integración API)',
                    'is_visible': True,
                    'description': (
                        'Conexión de la plataforma con el sistema de facturación del cliente para generar, '
                        'enviar, consultar y reconciliar comprobantes electrónicos desde los flujos operativos '
                        'del negocio. Incluye sincronización de clientes, productos, impuestos, facturas, '
                        'notas crédito/débito y documentos soporte, con trazabilidad del estado fiscal y '
                        'soporte para automatizaciones vía API.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 60,
                    'is_invite': False,
                    'items': [
                        {'icon': '📄', 'name': 'Generación de comprobantes electrónicos', 'description': 'Creación automática de facturas, notas crédito/débito y documentos soporte desde los flujos operativos del negocio.'},
                        {'icon': '🔄', 'name': 'Sincronización de datos fiscales', 'description': 'Sincronización bidireccional de clientes, productos, impuestos y comprobantes con el sistema de facturación.'},
                        {'icon': '📊', 'name': 'Trazabilidad del estado fiscal', 'description': 'Consulta y seguimiento del estado de cada comprobante: emitido, aceptado, rechazado o en proceso ante la DIAN.'},
                        {'icon': '🔗', 'name': 'Integración con proveedores colombianos', 'description': 'Conexión con Siigo, Alegra u otros proveedores con presencia y API documentada en Colombia.'},
                        {'icon': '⚙️', 'name': 'Automatizaciones vía API', 'description': 'Flujos automáticos para reconciliación de pagos, emisión de facturas al completar pedidos y notificaciones de estado fiscal.'},
                    ],
                },
                {
                    'id': 'integration_regional_payments',
                    'icon': '🇨🇴',
                    'title': 'Pasarela de Pago Regional (Colombia) (Integración API)',
                    'is_visible': True,
                    'description': (
                        'Integración con pasarelas de pago con presencia en el mercado colombiano '
                        'para facilitar transacciones locales con múltiples métodos de pago.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'is_invite': False,
                    'items': [
                        {'icon': '💳', 'name': 'PayU', 'description': 'Una de las más usadas en Colombia, permite pagos con tarjeta, PSE, Efecty, Baloto, Nequi, Daviplata.'},
                        {'icon': '🏦', 'name': 'Wompi (Bancolombia)', 'description': 'Excelente opción local con soporte para PSE, tarjetas, Nequi y botón Bancolombia.'},
                        {'icon': '💰', 'name': 'ePayco', 'description': 'Alternativa colombiana fácil de integrar, soporta múltiples métodos de pago como PSE, tarjetas y recaudos físicos.'},
                    ],
                },
                {
                    'id': 'integration_international_payments',
                    'icon': '🌎',
                    'title': 'Pasarela de Pago Internacional (Integración API)',
                    'is_visible': True,
                    'description': (
                        'Integración con pasarelas de pago internacionales para facilitar '
                        'transacciones globales con tarjeta de crédito/débito y cuentas internacionales.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'is_invite': False,
                    'items': [
                        {'icon': '💳', 'name': 'Stripe', 'description': 'Ideal para recibir pagos con tarjeta de crédito/débito, muy usada a nivel mundial. Soporta suscripciones, pagos únicos y múltiples divisas.'},
                        {'icon': '🅿️', 'name': 'PayPal', 'description': 'Plataforma reconocida globalmente, permite pagos con saldo PayPal, tarjeta y cuentas internacionales.'},
                    ],
                },
                {
                    'id': 'pwa_module',
                    'icon': '📱',
                    'title': 'Aplicación Móvil Instalable (PWA)',
                    'is_visible': True,
                    'description': (
                        'Convierte tu sitio web en una aplicación instalable que funciona '
                        'incluso sin conexión a internet. Ofrece una experiencia nativa '
                        'directamente desde el navegador, sin necesidad de tiendas de aplicaciones.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 40,
                    'items': [
                        {'icon': '📲', 'name': 'Instalación en dispositivo', 'description': 'Los usuarios pueden instalar tu sitio como una app en su celular o computador, con acceso directo desde la pantalla de inicio.'},
                        {'icon': '📡', 'name': 'Funcionamiento offline', 'description': 'El sitio sigue siendo accesible sin conexión a internet, mostrando contenido previamente cargado y sincronizando datos al reconectarse.'},
                        {'icon': '🔔', 'name': 'Notificaciones push', 'description': 'Envía notificaciones directas al dispositivo del usuario para mantenerlo informado sobre novedades, promociones o actualizaciones.'},
                        {'icon': '🎨', 'name': 'Pantalla de carga personalizada', 'description': 'Splash screen con la identidad visual de tu marca al abrir la aplicación, generando una experiencia profesional desde el primer instante.'},
                        {'icon': '🔄', 'name': 'Sincronización en segundo plano', 'description': 'Los datos se sincronizan automáticamente cuando el dispositivo recupera la conexión, garantizando información actualizada sin intervención del usuario.'},
                        {'icon': '⬆️', 'name': 'Actualización automática', 'description': 'La aplicación se actualiza de forma transparente sin que el usuario tenga que hacer nada, siempre con la versión más reciente.'},
                    ],
                },
                {
                    'id': 'corporate_branding_module',
                    'icon': '🎨',
                    'title': 'Identidad Visual e Imagen Corporativa',
                    'is_visible': True,
                    'description': (
                        'Aplicamos tu identidad visual de forma consistente en cada punto de contacto del '
                        'sistema — correos, documentos, redes sociales y pantallas internas — para que tu '
                        'marca se perciba profesional y coherente en todo lugar donde tus clientes interactúan.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': True,
                    'selected': True,
                    'price_percent': 35,
                    'items': [
                        {'icon': '✉️', 'name': 'Correos transaccionales con identidad corporativa', 'description': 'Plantillas HTML con logo, colores, tipografía y firma de marca aplicadas en todos los correos del sistema — bienvenida, confirmaciones, alertas, recuperación de contraseña y notificaciones — en lugar de correos en texto plano o genéricos.'},
                        {'icon': '📄', 'name': 'PDFs y exportables con branding', 'description': 'Facturas, reportes, certificados, recibos y descargas Excel/CSV generados desde el sistema con encabezado con logo, paleta corporativa y pie de marca. Cada documento que sale de la plataforma refuerza la imagen profesional del negocio.'},
                        {'icon': '🔗', 'name': 'Tarjetas de previsualización en redes (Open Graph)', 'description': 'Cuando alguien comparte un link del sitio o una propuesta en WhatsApp, Facebook, LinkedIn o X, aparece una tarjeta con logo, imagen y colores de marca — no un link plano. Impacto directo en percepción y CTR.'},
                        {'icon': '🖥️', 'name': 'Pantallas del sistema con identidad de marca', 'description': 'Páginas de error (404, 500), mantenimiento, login y estados de carga (loading, skeletons) con identidad visual y mensajes en la voz de la marca, en vez de las pantallas genéricas del framework.'},
                        {'icon': '🔎', 'name': 'Metadatos estructurados para buscadores e IA', 'description': 'JSON-LD Organization con logo, colores, redes sociales y datos de contacto — para que Google, Bing y asistentes como ChatGPT o Perplexity muestren correctamente la marca en panel de conocimiento, resultados enriquecidos y citaciones.'},
                    ],
                },
                {
                    'id': 'ai_module',
                    'icon': '🤖',
                    'title': 'Integración y Automatización con IA',
                    'is_visible': True,
                    'description': (
                        'Potencia tu proyecto con inteligencia artificial. Exploramos juntos '
                        'cómo adaptar soluciones de IA a las necesidades específicas de tu negocio.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 0,
                    'is_invite': True,
                    'invite_note': (
                        '🤝 Te invitamos a una llamada personalizada donde exploraremos '
                        'juntos cómo la inteligencia artificial puede transformar tu negocio. '
                        'Conocerás nuestras soluciones, cómo las adaptamos a tu caso particular, '
                        'y los costos asociados — sin compromiso.'
                    ),
                    'items': [
                        {'icon': '⚡', 'name': 'Automatizaciones', 'description': 'Flujos de trabajo inteligentes que ejecutan tareas repetitivas de forma autónoma, liberando tiempo para lo que realmente importa.'},
                        {'icon': '📊', 'name': 'Análisis de datos con lenguaje natural', 'description': 'Consulta tus datos usando preguntas en español o inglés y obtén respuestas claras, gráficos y reportes sin necesidad de conocimientos técnicos.'},
                        {'icon': '✍️', 'name': 'Generación de contenido', 'description': 'Creación asistida de textos, descripciones de productos, artículos de blog y comunicaciones, manteniendo el tono y estilo de tu marca.'},
                        {'icon': '💬', 'name': 'Comunicación inteligente', 'description': 'Chatbots y asistentes virtuales que atienden a tus clientes 24/7, responden preguntas frecuentes y escalan conversaciones cuando es necesario.'},
                        {'icon': '📄', 'name': 'Procesamiento de documentos', 'description': 'Extracción y clasificación automática de información desde facturas, contratos y formularios, reduciendo el trabajo manual y los errores.'},
                        {'icon': '🔍', 'name': 'Búsqueda e investigación', 'description': 'Motor de búsqueda semántico que entiende la intención del usuario y devuelve resultados relevantes, no solo coincidencias de texto.'},
                        {'icon': '🛡️', 'name': 'Seguridad y moderación', 'description': 'Detección automática de contenido inapropiado, spam y actividad sospechosa para mantener tu plataforma segura y confiable.'},
                        {'icon': '⚙️', 'name': 'Optimización de procesos', 'description': 'Análisis inteligente de tus operaciones para identificar cuellos de botella, sugerir mejoras y automatizar decisiones rutinarias.'},
                        {'icon': '🎓', 'name': 'Aprendizaje y capacitación', 'description': 'Sistemas adaptativos que personalizan la experiencia de aprendizaje según el ritmo y nivel de cada usuario.'},
                        {'icon': '🔮', 'name': 'Predicción y forecasting', 'description': 'Modelos predictivos que anticipan tendencias, demanda y comportamiento de clientes para tomar decisiones más informadas.'},
                        {'icon': '🔗', 'name': 'Integración y orquestación', 'description': 'Conexión inteligente entre tus herramientas y servicios existentes, coordinando flujos de datos y acciones entre múltiples plataformas.'},
                    ],
                },
                {
                    'id': 'integration_conversion_tracking',
                    'icon': '📡',
                    'title': 'Conversiones Inteligentes (Meta & Google Ads) (Integración API)',
                    'is_visible': True,
                    'description': (
                        'Maximiza el retorno de tu inversión publicitaria con seguimiento '
                        'de conversiones server-side. Tu sitio web reporta cada acción '
                        'valiosa directamente a Meta y Google, sin depender de cookies '
                        'ni del navegador del visitante.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 0,
                    'is_invite': True,
                    'invite_note': (
                        '🤝 Te invitamos a una llamada donde analizaremos tu estrategia '
                        'publicitaria actual y diseñaremos juntos la integración server-side '
                        'con Meta y Google Ads. Verás cómo maximizar tu ROAS con datos '
                        'de conversión precisos — sin compromiso.'
                    ),
                    'items': [
                        {'icon': '🔗', 'name': 'Conexión directa con Meta Conversions API', 'description': 'Cada conversión se envía desde tu servidor directamente a Meta, permitiendo que Facebook e Instagram identifiquen qué anuncios generaron resultados reales, incluso con bloqueadores de anuncios.'},
                        {'icon': '📊', 'name': 'Conexión directa con Google Enhanced Conversions', 'description': 'Las conversiones se reportan desde el servidor con datos encriptados del cliente. Google asocia cada conversión con el clic original del anuncio y optimiza las pujas automáticas con información real.'},
                        {'icon': '🛡️', 'name': 'Inmune a bloqueadores y restricciones de cookies', 'description': 'A diferencia del tracking tradicional, este módulo funciona desde tu servidor. No lo afectan los bloqueadores de anuncios, las restricciones de iOS 14+ ni la eliminación de cookies de terceros.'},
                        {'icon': '🔄', 'name': 'Deduplicación automática de eventos', 'description': 'El sistema mantiene el tracking del navegador como respaldo y sincroniza ambas fuentes con un identificador único. Meta y Google eliminan duplicados automáticamente.'},
                        {'icon': '🎯', 'name': 'Eventos de conversión personalizados', 'description': 'Se configuran los eventos que importan para tu negocio: formulario enviado, clic en WhatsApp, llamada agendada, propuesta vista, propuesta aceptada. Cada uno con su valor monetario para calcular ROAS real.'},
                        {'icon': '📈', 'name': 'Panel de estado de conversiones', 'description': 'Visualiza desde tu panel administrativo el estado de cada evento enviado: confirmado, pendiente o fallido. Incluye diagnóstico de calidad de matching.'},
                    ],
                },
                {
                    'id': 'biometric_verification_module',
                    'icon': '🪪',
                    'title': 'Verificación y Validación Biométrica (Integración API)',
                    'is_visible': True,
                    'description': (
                        'Valida que la persona detrás de la pantalla es realmente quien dice ser, '
                        'combinando lectura del documento de identidad, reconocimiento facial y '
                        'prueba de vida. Reduce fraude, cumple requisitos de KYC y agiliza el '
                        'onboarding digital de tus clientes y/o usuarios internos.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 0,
                    'is_invite': True,
                    'invite_note': (
                        '🤝 Te invitamos a una llamada donde definimos juntos el alcance de la '
                        'verificación biométrica y validación de identidad para tu negocio. '
                        'La integración la realiza un proveedor especializado que factura el '
                        'servicio directamente al cliente final — nosotros conectamos la solución '
                        'a tu plataforma, sin compromiso.'
                    ),
                    'items': [
                        {'icon': '🪪', 'name': 'Lectura y validación de documento', 'description': 'Captura del documento de identidad (anverso y reverso) con OCR y validación de campos, formatos y autenticidad.'},
                        {'icon': '👤', 'name': 'Reconocimiento facial', 'description': 'Comparación biométrica entre la foto del documento y un selfie en vivo del usuario para confirmar coincidencia de identidad.'},
                        {'icon': '🎬', 'name': 'Prueba de vida (liveness)', 'description': 'Detección activa o pasiva de que la persona está físicamente presente, evitando suplantación con fotos, videos o máscaras.'},
                        {'icon': '🛡️', 'name': 'Antifraude y KYC', 'description': 'Reglas de aceptación, listas de control y trazabilidad por intento — alineado con buenas prácticas de KYC y cumplimiento.'},
                        {'icon': '⚡', 'name': 'Onboarding digital sin fricción', 'description': 'Flujo end-to-end embebido en tu plataforma: el usuario se valida en minutos desde su celular o computador, sin trámites presenciales.'},
                        {'icon': '📊', 'name': 'Panel de verificaciones', 'description': 'Vista administrativa con el estado de cada verificación (aprobada, rechazada, pendiente), evidencias y motivo, lista para auditoría.'},
                    ],
                },
                {
                    'id': 'behavior_tracking_module',
                    'icon': '👣',
                    'title': 'Rastreo de Comportamiento de Usuarios',
                    'is_visible': True,
                    'description': (
                        'Descubre cómo usan realmente tu plataforma: cuándo entran tus usuarios, '
                        'qué vistas abren y cuánto tiempo pasan en cada una. Es la misma capacidad '
                        'que nosotros usamos para entender el interés en nuestras propuestas, '
                        'instalada en tu propio producto y con datos 100% tuyos. Alcance incluido: '
                        'rastreo de hasta 15 vistas, panel con hasta 8 KPIs y 4 gráficos, y '
                        'retención de datos de 12 meses.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 30,
                    'items': [
                        {'icon': '📍', 'name': 'Registro de sesiones y aperturas', 'description': 'Captura cada sesión de uso: cuándo entra el usuario, desde qué dispositivo y si es su primera visita o está regresando. Todo de primera mano (first-party), sin cookies de terceros ni herramientas externas.'},
                        {'icon': '🖥️', 'name': 'Vistas abiertas y tiempo por vista', 'description': 'Registra qué vistas o secciones abre cada usuario y cuántos segundos permanece en cada una. Cubre hasta 15 vistas del sistema, definidas junto al cliente al inicio del proyecto.'},
                        {'icon': '🔥', 'name': 'Mapa de interés por vista', 'description': 'Ranking de las vistas con mayor y menor atención según tiempo acumulado y número de visitas — para saber qué funciona y qué pasa desapercibido, sin instalar nada adicional.'},
                        {'icon': '🚪', 'name': 'Embudo de recorrido con abandonos', 'description': 'Visualiza el recorrido de los usuarios entre las vistas rastreadas y detecta en qué paso abandonan. Incluye un (1) embudo principal definido junto al cliente sobre las vistas rastreadas.'},
                        {'icon': '📊', 'name': 'Panel de comportamiento integrado', 'description': 'Dashboard dentro de tu propio panel administrativo con hasta 8 KPIs y 4 gráficos: sesiones, tiempo promedio, vistas más abiertas y desglose por dispositivo. Sin licencias externas ni suscripciones.'},
                        {'icon': '📱', 'name': 'Desglose por dispositivo', 'description': 'Identifica desde qué dispositivo usan tu plataforma — móvil, tablet o escritorio — para priorizar mejoras donde tus usuarios realmente están.'},
                        {'icon': '🗄️', 'name': 'Datos propios con retención de 12 meses', 'description': 'Los eventos se almacenan en tu propia base de datos y se conservan los últimos 12 meses. No incluye grabación de pantalla, mapas de calor de clics ni rastreo entre sitios de terceros.'},
                    ],
                },
                {
                    'id': 'reports_alerts_module',
                    'icon': '📬',
                    'title': 'Reportes y Alertas vía Correo o WhatsApp',
                    'is_visible': True,
                    'description': (
                        'Mantente informado en todo momento con reportes automáticos y alertas '
                        'personalizadas que llegan directamente a tu correo o WhatsApp.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'items': [
                        {'icon': '📧', 'name': 'Reportes automáticos por correo', 'description': 'Recibe resúmenes periódicos con las métricas clave de tu negocio directamente en tu bandeja de entrada, sin tener que entrar al sistema.'},
                        {'icon': '🔔', 'name': 'Alertas personalizadas', 'description': 'Configura notificaciones para eventos importantes: nuevas ventas, registros de usuarios, stock bajo, o cualquier métrica que definas.'},
                        {'icon': '💚', 'name': 'Integración con WhatsApp', 'description': 'Recibe alertas y reportes instantáneos en tu número de WhatsApp a través de la API oficial, ideal para estar al tanto desde el mismo canal donde atiendes a tus clientes.'},
                        {'icon': '⏰', 'name': 'Programación de envíos', 'description': 'Define la frecuencia y horario de tus reportes: diario, semanal, mensual o en tiempo real según tus necesidades.'},
                        {'icon': '📋', 'name': 'Resumen ejecutivo periódico', 'description': 'Informe consolidado con las métricas más relevantes de tu proyecto, diseñado para una lectura rápida y toma de decisiones ágil.'},
                    ],
                },
                {
                    'id': 'email_marketing_module',
                    'icon': '📧',
                    'title': 'Integración de Email Marketing',
                    'is_visible': True,
                    'description': (
                        'Conecta tu sitio web con plataformas de email marketing para '
                        'automatizar campañas, segmentar audiencias y aumentar la '
                        'conversión de visitantes en clientes.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 10,
                    'items': [
                        {'icon': '📬', 'name': 'Captura de leads', 'description': 'Formularios optimizados y pop-ups inteligentes para capturar emails de visitantes interesados en tu contenido o productos.'},
                        {'icon': '🔄', 'name': 'Automatizaciones de email', 'description': 'Secuencias automáticas de bienvenida, carritos abandonados, seguimiento post-compra y re-engagement de usuarios inactivos.'},
                        {'icon': '🎯', 'name': 'Segmentación de audiencia', 'description': 'Clasifica a tus suscriptores por comportamiento, intereses y datos demográficos para enviar mensajes relevantes y personalizados.'},
                        {'icon': '📊', 'name': 'Analítica de campañas', 'description': 'Métricas detalladas de apertura, clics, conversiones y ROI de cada campaña para optimizar tu estrategia de comunicación.'},
                        {'icon': '🔗', 'name': 'Integración con plataformas', 'description': 'Conexión nativa con Mailchimp, SendGrid, Brevo u otras plataformas líderes de email marketing según tus necesidades.'},
                    ],
                },
                {
                    'id': 'qr_generator_module',
                    'icon': '🔳',
                    'title': 'Generador de Códigos QR',
                    'is_visible': True,
                    'description': (
                        'Convierte cualquier enlace, texto o acción en un código QR listo para '
                        'imprimir, compartir o pegar donde tu negocio lo necesite. Pensado para '
                        'que conectes el mundo físico con tu plataforma digital sin fricción — '
                        'desde una mesa de restaurante hasta el empaque de tu producto.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 25,
                    'items': [
                        {'icon': '⚡', 'name': 'Generación instantánea', 'description': 'Crea códigos QR desde URLs, textos, contactos vCard, redes WiFi, números de WhatsApp o cualquier flujo interno de la plataforma — en segundos.'},
                        {'icon': '🎨', 'name': 'Personalización con tu marca', 'description': 'Aplica los colores corporativos, agrega tu logo al centro y elige formatos (PNG, SVG, PDF) listos para imprimir en alta resolución sin perder calidad.'},
                        {'icon': '🔄', 'name': 'Códigos dinámicos editables', 'description': 'Cambia a dónde apunta un QR ya impreso sin tener que reimprimirlo. Ideal para menús de temporada, promociones, eventos y campañas que evolucionan.'},
                        {'icon': '📊', 'name': 'Tracking de escaneos', 'description': 'Mide cuántas veces se escanea cada código, desde qué dispositivo y en qué momento — perfecto para evaluar el desempeño de campañas físicas, vallas, flyers y empaques.'},
                        {'icon': '🗂️', 'name': 'Biblioteca de códigos', 'description': 'Todos los QR generados quedan organizados en un panel, agrupados por campaña o propósito, listos para reutilizar, descargar o desactivar cuando ya no apliquen.'},
                        {'icon': '🚀', 'name': 'Casos de uso listos para activar', 'description': 'Menú digital, link a WhatsApp, registro a eventos, descarga de catálogo, login rápido, encuestas, propinas o reseñas — preconfigurados para arrancar el mismo día.'},
                    ],
                },
                {
                    'id': 'content_generator_module',
                    'icon': '✍️',
                    'title': 'Generador de Contenido con IA y Calendario Editorial',
                    'is_visible': True,
                    'description': (
                        'Mantén tu marca activa y consistente sin depender de inspiración diaria. '
                        'La IA redacta blogs, correos y publicaciones para redes sociales con la '
                        'voz de tu negocio, y un calendario editorial te permite planear, programar '
                        'y publicar en automático — todo desde un solo panel, con vista mensual o '
                        'semanal de lo que viene.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 30,
                    'items': [
                        {'icon': '🤖', 'name': 'Redacción asistida con IA', 'description': 'Generación de borradores de blogs, newsletters, emails y posts a partir de un brief simple. Ajusta tono, extensión y formato con un par de clics.'},
                        {'icon': '🎙️', 'name': 'Voz de marca y plantillas', 'description': 'Define tu identidad editorial una vez (tono, estilo, palabras prohibidas, llamados a la acción) y la IA respeta esa voz en cada pieza que genera.'},
                        {'icon': '🌐', 'name': 'Multicanal: blog, email y redes', 'description': 'Una misma idea se adapta automáticamente al formato del canal: post largo para blog, asunto y cuerpo para email, copy corto para Instagram, LinkedIn o X.'},
                        {'icon': '📅', 'name': 'Calendario editorial visual', 'description': 'Vista mensual y semanal con todas las piezas planeadas, en borrador, programadas y publicadas. Arrastra y suelta para reorganizar fechas en segundos.'},
                        {'icon': '⏰', 'name': 'Programación y publicación automática', 'description': 'Agenda cada pieza para una fecha y hora específica. El sistema publica solo en el blog, envía el correo o postea en las redes conectadas — sin intervención manual.'},
                        {'icon': '📊', 'name': 'Panel de seguimiento', 'description': 'Estado de cada publicación (borrador, programada, publicada, fallida), métricas básicas de desempeño y posibilidad de reagendar o duplicar piezas con un clic.'},
                        {'icon': '🔗', 'name': 'Integración con tus canales', 'description': 'Conexión con tu blog, proveedor de email y redes sociales para que todo lo planeado en el calendario salga publicado en los canales que tu audiencia ya frecuenta.'},
                    ],
                },
                {
                    'id': 'i18n_module',
                    'icon': '🌍',
                    'title': 'Multi-idioma y Localización Regional',
                    'is_visible': True,
                    'description': (
                        'Sistema de internacionalización nativo que permite servir tu sitio '
                        'en múltiples idiomas con flujo de traducción integrado, formatos '
                        'de moneda y fecha regionales, y la posibilidad de mostrar catálogos '
                        'o precios diferentes por país.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 15,
                    'items': [
                        {'icon': '🌐', 'name': 'Soporte multi-idioma nativo', 'description': 'Estructura preparada para servir todo el contenido del sitio en dos o más idiomas, con selector de idioma visible y persistencia de preferencia del usuario.'},
                        {'icon': '💱', 'name': 'Formatos regionales de moneda y fecha', 'description': 'Adaptación automática de formatos numéricos, monedas y fechas según la región del visitante o el idioma seleccionado.'},
                        {'icon': '🛒', 'name': 'Catálogos y precios por país', 'description': 'Posibilidad de mostrar productos, precios y disponibilidad diferenciados por región geográfica o mercado objetivo.'},
                        {'icon': '📝', 'name': 'Flujo de traducción integrado', 'description': 'Panel administrativo para gestionar las traducciones de cada sección sin necesidad de intervención técnica, con indicador de contenido pendiente por traducir.'},
                        {'icon': '🔍', 'name': 'Detección automática de idioma', 'description': 'El sitio detecta el idioma preferido del navegador del visitante y lo redirige automáticamente a la versión correspondiente, mejorando la experiencia desde el primer momento.'},
                    ],
                },
                {
                    'id': 'live_chat_module',
                    'icon': '💬',
                    'title': 'Chat en Vivo First-Party',
                    'is_visible': True,
                    'description': (
                        'Sistema de chat en tiempo real completamente alojado en la infraestructura '
                        'del cliente — sin Intercom, Drift ni LiveChat — donde los agentes atienden '
                        'desde el mismo panel administrativo. Los datos son 100% propios, sin costos '
                        'de suscripción crecientes ni riesgo de que la herramienta muestre anuncios '
                        'de competidores.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 40,
                    'items': [
                        {'icon': '🔌', 'name': 'Widget de chat embebido', 'description': 'Componente flotante integrado en el sitio web que permite al visitante iniciar una conversación en tiempo real sin salir de la página que está navegando.'},
                        {'icon': '🖥️', 'name': 'Panel de agente en el admin', 'description': 'Los agentes atienden las conversaciones directamente desde el panel administrativo del sitio, sin necesidad de aplicaciones externas ni cuentas adicionales.'},
                        {'icon': '📡', 'name': 'Comunicación en tiempo real (WebSocket)', 'description': 'Mensajes instantáneos bidireccionales entre visitante y agente mediante conexión persistente, sin retrasos ni necesidad de recargar la página.'},
                        {'icon': '🗄️', 'name': 'Historial de conversaciones propio', 'description': 'Todas las conversaciones se almacenan en la base de datos del cliente, con búsqueda, filtros por fecha y exportación. Los datos son 100% propiedad del cliente.'},
                        {'icon': '🤖', 'name': 'Respuestas automáticas configurables', 'description': 'Mensajes de bienvenida, respuestas fuera de horario y FAQ automatizadas que mantienen la atención activa incluso cuando no hay agentes disponibles.'},
                        {'icon': '🔔', 'name': 'Notificaciones de nuevos chats', 'description': 'Alertas en tiempo real al agente cuando un visitante inicia una conversación o envía un mensaje nuevo, garantizando tiempos de respuesta mínimos.'},
                    ],
                },
                {
                    'id': 'dark_mode_module',
                    'icon': '🌙',
                    'title': 'Modo Oscuro y Claro',
                    'is_visible': True,
                    'description': (
                        'El sistema alterna automáticamente entre modo claro y oscuro según la '
                        'preferencia del dispositivo del usuario, y recuerda su elección. Reduce la '
                        'fatiga visual y le da un acabado moderno a la plataforma.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'items': [
                        {'icon': '🎨', 'name': 'Paleta de colores dual', 'description': 'Diseño de dos sistemas de color completos (claro y oscuro) con variables CSS que se alternan de forma instantánea, manteniendo coherencia visual en ambos modos.'},
                        {'icon': '⚙️', 'name': 'Detección automática de preferencia del sistema', 'description': 'El sitio detecta la preferencia de tema del sistema operativo del usuario (prefers-color-scheme) y aplica el modo correspondiente desde la primera visita.'},
                        {'icon': '💾', 'name': 'Persistencia de elección del usuario', 'description': 'La preferencia manual del usuario se almacena y respeta en futuras visitas, prevaleciendo sobre la configuración del sistema operativo.'},
                        {'icon': '🔄', 'name': 'Transición fluida entre modos', 'description': 'Animación suave y elegante al alternar entre modo claro y oscuro, sin parpadeos ni saltos visuales que interrumpan la experiencia de navegación.'},
                        {'icon': '🖼️', 'name': 'Adaptación de imágenes y multimedia', 'description': 'Las imágenes, íconos y elementos gráficos se ajustan automáticamente al modo activo, optimizando contraste y legibilidad en cada contexto.'},
                    ],
                },
                {
                    'id': 'gift_cards_module',
                    'icon': '🎁',
                    'title': 'Gift Cards y Vouchers Digitales',
                    'is_visible': False,
                    'description': (
                        'Creación, venta y canje de tarjetas de regalo digitales con saldo '
                        'configurable, diseño de marca y código único verificable en checkout. '
                        'Genera ingresos anticipados y captura nuevos clientes a través '
                        'de los compradores existentes.'
                    ),
                    'is_calculator_module': False,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'items': [
                        {'icon': '💳', 'name': 'Creación y venta de gift cards', 'description': 'Los clientes pueden comprar tarjetas de regalo digitales con saldo configurable directamente desde tu sitio web, con proceso de pago integrado.'},
                        {'icon': '✅', 'name': 'Canje en checkout con código único', 'description': 'Cada gift card genera un código único verificable que el destinatario puede aplicar durante el proceso de compra como método de pago parcial o total.'},
                        {'icon': '📊', 'name': 'Historial de saldo y movimientos', 'description': 'Tanto el comprador como el destinatario pueden consultar el saldo disponible, movimientos realizados y fecha de vencimiento de cada tarjeta.'},
                        {'icon': '🎨', 'name': 'Diseño de marca personalizado', 'description': 'Las gift cards se generan con la identidad visual de tu marca, incluyendo logo, colores y mensaje personalizable del comprador para el destinatario.'},
                        {'icon': '⏰', 'name': 'Vencimiento configurable', 'description': 'Define políticas de vencimiento por tipo de tarjeta: sin vencimiento, 6 meses, 1 año, o personalizado. Incluye notificaciones automáticas antes de la expiración.'},
                    ],
                },
            ],
        },
    },
    {
        'section_type': 'development_stages',
        'title': '📌 Así avanzamos juntos',
        'order': 12,
        'is_wide_panel': True,
        'content_json': {
            'index': '11',
            'title': 'Etapas de contratación y desarrollo',
            'intro': 'Nuestro proceso está diseñado para ofrecer claridad, confianza y acompañamiento en cada fase 🧭:',
            'currentLabel': 'Actual',
            'stages': [
                {
                    'icon': '✉️',
                    'title': 'Propuesta Comercial',
                    'description': 'Presentación formal de la propuesta técnica y económica (etapa actual).',
                    'current': True,
                },
                {
                    'icon': '🧾',
                    'title': 'Borrador de Contrato',
                    'description': 'Envío del documento que establece los términos, condiciones y compromisos.',
                },
                {
                    'icon': '✍️',
                    'title': 'Formalización del Contrato',
                    'description': 'Firma del acuerdo y confirmación del inicio oficial del proyecto.',
                },
                {
                    'icon': '🎨',
                    'title': 'Etapa de Diseño',
                    'description': 'Creación del prototipo visual en Figma con reuniones de revisión.',
                },
                {
                    'icon': '💻',
                    'title': 'Etapa de Desarrollo',
                    'description': 'Implementación del diseño en código nativo, optimizado para la mejor experiencia.',
                },
                {
                    'icon': '🚀',
                    'title': 'Despliegue del Proyecto',
                    'description': 'Publicación del sitio web en producción y revisión final.',
                },
                {
                    'icon': '💖',
                    'title': 'Entrega Final',
                    'description': 'Sitio en línea y validado, cierre del ciclo de transformación digital.',
                },
            ],
        },
    },
    {
        'section_type': 'process_methodology',
        'title': '⚙️ Proceso y Metodología',
        'order': 6,
        'is_wide_panel': False,
        'content_json': {
            'index': '5',
            'title': 'Proceso y Metodología',
            'intro': 'Trabajamos con un proceso estructurado que garantiza transparencia, calidad y entrega a tiempo en cada etapa del proyecto.',
            'activeStep': 0,
            'steps': [
                {
                    'icon': '🔍',
                    'title': 'Discovery',
                    'description': 'Investigamos tu negocio, competidores y usuarios para definir la estrategia ideal.',
                    'clientAction': 'Tu aporte: briefing inicial',
                },
                {
                    'icon': '🎨',
                    'title': 'Diseño UX/UI',
                    'description': 'Creamos prototipos interactivos en Figma con iteraciones hasta la aprobación visual.',
                    'clientAction': 'Tu aporte: feedback de diseño',
                },
                {
                    'icon': '💻',
                    'title': 'Desarrollo',
                    'description': 'Implementamos con código limpio, arquitectura escalable y las mejores prácticas.',
                    'clientAction': '',
                },
                {
                    'icon': '🧪',
                    'title': 'QA y Testing',
                    'description': 'Pruebas exhaustivas de funcionalidad, rendimiento, seguridad y compatibilidad.',
                    'clientAction': 'Tu aporte: pruebas de aceptación',
                },
                {
                    'icon': '🚀',
                    'title': 'Lanzamiento',
                    'description': 'Despliegue en producción, monitoreo post-lanzamiento y capacitación del equipo.',
                    'clientAction': '',
                },
            ],
        },
    },
    {
        'section_type': 'proposal_summary',
        'title': '📋 Resumen de la Propuesta',
        'order': 13,
        'is_wide_panel': False,
        'content_json': {
            'index': '12',
            'title': 'Resumen de la Propuesta',
            'subtitle': 'Los datos clave de esta propuesta en un vistazo:',
            'kpis': [
                {'value': '+40%', 'label': 'Incremento esperado en conversión web', 'source': 'HubSpot 2024'},
                {'value': '3x', 'label': 'Retorno estimado de inversión a 12 meses', 'source': 'Análisis interno'},
                {'value': '-60%', 'label': 'Reducción en tiempo de gestión manual', 'source': 'McKinsey Digital 2023'},
            ],
            '_kpi_note': (
                'Los KPIs son personalizables por cliente. Incluye métricas relevantes '
                'para el sector del cliente con fuentes verificables. Estos aparecerán '
                'como tarjetas destacadas al inicio del resumen.'
            ),
            'cards': [
                {
                    'icon': '💰',
                    'title': 'Inversión',
                    'description': 'Monto total del proyecto según la propuesta económica.',
                    'source': 'total_investment',
                },
                {
                    'icon': '⏱️',
                    'title': 'Tiempo Estimado',
                    'description': 'Duración aproximada del proyecto desde el kickoff hasta la entrega.',
                    'source': 'timeline_duration',
                },
                {
                    'icon': '🛡️',
                    'title': 'Garantía',
                    'description': '1 año de garantía incluida sobre el desarrollo entregado.',
                    'source': 'static',
                },
                {
                    'icon': '🧑‍💻',
                    'title': 'Soporte',
                    'description': 'Equipo dedicado de diseño, desarrollo y soporte post-lanzamiento.',
                    'source': 'static',
                },
                {
                    # Resume la CLÁUSULA VIGÉSIMA SEGUNDA del contrato. La última
                    # frase no es opcional: el contrato condiciona estos tiempos a
                    # que el servicio de hosting y soporte esté vigente.
                    'icon': '🚨',
                    'title': 'Atención de incidentes',
                    'description': (
                        'Incidente crítico: respuesta en 4 horas hábiles y '
                        'restablecimiento en 1 día hábil. Medio: 1 y 5 días '
                        'hábiles. Bajo: 3 y 9 días hábiles. Incluye monitoreo '
                        'permanente, respaldos e informe de cierre. Aplica '
                        'mientras el servicio de hosting y soporte esté vigente.'
                    ),
                    'source': 'static',
                },
                {
                    'icon': '📅',
                    'title': 'Vigencia',
                    'description': 'Vigencia de la propuesta a partir de su envío.',
                    'source': 'expires_at',
                },
            ],
        },
    },
    {
        'section_type': 'final_note',
        'title': '📝 Nuestro compromiso contigo',
        'order': 14,
        'is_wide_panel': False,
        'content_json': {
            'index': '13',
            'title': 'Nota Final y Próximos Pasos',
            'message': (
                'Creemos firmemente que esta propuesta representa una oportunidad excepcional '
                'para transformar tu presencia digital y alcanzar tus objetivos de negocio.'
            ),
            'personalNote': (
                'Estamos emocionados por la posibilidad de trabajar contigo y ayudarte '
                'a llevar tu negocio al siguiente nivel.'
            ),
            'teamName': 'El equipo de Project App',
            'teamRole': 'Tu socio en transformación digital',
            'contactEmail': 'team@projectapp.co',
            'commitmentBadges': [
                {
                    'icon': '🤝',
                    'title': 'Compromiso Total',
                    'description': 'Dedicación completa a tu proyecto hasta lograr resultados excepcionales',
                },
                {
                    'icon': '💯',
                    'title': 'Garantía de Calidad',
                    'description': 'Revisiones ilimitadas hasta tu completa satisfacción',
                },
                {
                    'icon': '🎯',
                    'title': 'Enfoque en Resultados',
                    'description': 'Medimos nuestro éxito por el impacto en tu negocio',
                },
            ],
            'validityMessage': (
                'Esta propuesta tiene una vigencia limitada a partir de su fecha de envío. '
                'Los precios y condiciones pueden estar sujetos a cambios después de este período.'
            ),
            'thankYouMessage': (
                'Apreciamos sinceramente la oportunidad de presentarte esta propuesta. '
                'Esperamos con entusiasmo la posibilidad de trabajar contigo.'
            ),
        },
    },
    {
        'section_type': 'next_steps',
        'title': '✅ ¿Listo para empezar?',
        'order': 15,
        'is_wide_panel': False,
        'content_json': {
            'index': '14',
            'title': 'Próximos pasos',
            'introMessage': (
                'Estamos listos para comenzar este viaje juntos. '
                'Aquí te explicamos cómo dar el siguiente paso:'
            ),
            'steps': [
                {
                    'title': 'Revisión y Preguntas',
                    'description': 'Revisa la propuesta y envíanos cualquier pregunta o ajuste que necesites.',
                },
                {
                    'title': 'Reunión de Confirmación',
                    'description': 'Agendamos una llamada para alinear detalles finales y firmar el contrato.',
                },
                {
                    'title': '¡Comenzamos!',
                    'description': 'Iniciamos el proyecto con la reunión de kickoff.',
                },
            ],
            'ctaMessage': (
                'Contáctanos hoy mismo y comencemos a trabajar en tu proyecto. '
                'Estamos a solo un mensaje de distancia.'
            ),
            'primaryCTA': {
                'text': 'Contactar por WhatsApp',
                'link': 'https://wa.me/573238122373',
            },
            'secondaryCTA': {
                'text': 'Agendar Reunión',
                'link': 'https://calendly.com/projectapp',
            },
            'contactMethods': [
                {
                    'icon': '📧',
                    'title': 'Email',
                    'value': 'team@projectapp.co',
                    'link': 'mailto:team@projectapp.co',
                },
                {
                    'icon': '📱',
                    'title': 'WhatsApp',
                    'value': '+57 323 812 2373',
                    'link': 'https://wa.me/573238122373',
                },
                {
                    'icon': '🌐',
                    'title': 'Website',
                    'value': 'www.projectapp.co',
                    'link': 'https://projectapp.co',
                },
            ],
            'validityMessage': (
                'Esta propuesta tiene una vigencia limitada a partir de su fecha de envío. '
                'Los precios y condiciones pueden estar sujetos a cambios después de este período.'
            ),
            'thankYouMessage': (
                'Apreciamos sinceramente la oportunidad de presentarte esta propuesta. '
                'Esperamos con entusiasmo la posibilidad de trabajar contigo.'
            ),
        },
    },
    {
        'section_type': 'technical_document',
        'title': '🔧 Detalle técnico',
        'order': 16,
        'is_wide_panel': True,
        'content_json': deepcopy(EMPTY_TECHNICAL_DOCUMENT_JSON),
    },
    {
        # PDF-only appendix: hour packages + scope-exclusion clause.
        # No web component; excluded from the public carousel.
        'section_type': 'commercial_conditions',
        'title': '📑 Condiciones comerciales',
        'order': 17,
        'is_wide_panel': False,
        'content_json': {
            'index': '17',
            'title': 'Condiciones comerciales',
            'packagesTitle': 'Paquetes de horas para requerimientos posteriores',
            'packagesIntro': (
                'Para requerimientos de esfuerzo bajo o medio-bajo posteriores a la entrega, '
                'ofrecemos bolsas de horas con tarifa preferencial. A mayor paquete, menor '
                'es el costo por hora.'
            ),
            'hourlyRate': 30000,
            'currency': 'COP',
            'packages': [
                {'name': 'Hora Puntual', 'hours': 1, 'discountPercent': 0, 'note': 'Para un ajuste express.'},
                {'name': 'Paquete Ágil', 'hours': 20, 'discountPercent': 10, 'note': 'Para iteraciones cortas.'},
                {'name': 'Paquete Pro', 'hours': 60, 'discountPercent': 20, 'note': 'Para mejoras continuas.'},
                {'name': 'Paquete Premium', 'hours': 180, 'discountPercent': 30, 'note': 'Para la evolución sostenida del producto.'},
            ],
            'effortBadge': (
                'Todo requerimiento de esfuerzo medio o superior se cotiza como un requerimiento '
                'independiente, fuera de estos paquetes.'
            ),
            'scopeTitle': 'Alcance del trabajo aprobado',
            'scopeParagraphs': [
                'El trabajo aprobado y cotizado corresponde únicamente a lo descrito dentro del '
                'alcance de esta propuesta comercial y de su detalle técnico. Cualquier conversación, '
                'mensaje, correo electrónico, reunión, idea, recurso, archivo, referencia o solicitud '
                'que surja **antes o durante** el proyecto y que no esté explícitamente descrita dentro '
                'de dicho alcance no constituye, por sí sola, un compromiso de implementación ni hace '
                'parte del trabajo contratado.',
                'Lo anterior no limita la comunicación: podemos conversar y explorar ideas libremente. '
                'Sin embargo, para que una funcionalidad, cambio o entregable pase a formar parte del '
                'trabajo aprobado, debe quedar documentado y cotizado como parte del alcance, y '
                'formalizarse mediante un otrosí al contrato o mediante un contrato independiente. Esto '
                'protege a ambas partes: evita malentendidos sobre lo '
                'que está incluido, mantiene el proyecto enfocado y asegura que cada esfuerzo adicional '
                'se planifique y se remunere de forma justa.',
                'En consecuencia, los tiempos, costos y garantías de esta propuesta aplican solamente '
                'sobre el alcance descrito. Todo lo que lo exceda se gestionará mediante los paquetes '
                'de horas anteriores (para esfuerzos bajos o medio-bajos) o como una cotización '
                'independiente (para esfuerzos medios o superiores).',
                'La ejecución de cualquier actividad no comprendida en el alcance no lo modifica, no '
                'genera derecho a exigir prestaciones similares en el futuro ni implica renuncia a lo '
                'aquí establecido.',
            ],
        },
    },
]

DEFAULT_SECTIONS_EN = [
    {
        'section_type': 'greeting',
        'title': '👋 Greeting',
        'order': 0,
        'is_wide_panel': False,
        'content_json': {
            'proposalTitle': '',
            'clientName': '',
            'inspirationalQuote': '',
        },
    },
    {
        'section_type': 'executive_summary',
        'title': '🧾 Executive Summary',
        'order': 1,
        'is_wide_panel': False,
        'content_json': {
            'index': '1',
            'title': 'Executive Summary',
            'paragraphs': [
                'Our proposal covers the design and development of a professional website.',
            ],
            'highlightsTitle': 'Includes',
            'highlights': [
                'Custom visual design',
                'Responsive web development',
                'Basic SEO optimization',
            ],
        },
    },
    {
        'section_type': 'context_diagnostic',
        'title': '🧩 Context & Diagnostic',
        'order': 2,
        'is_wide_panel': False,
        'content_json': {
            'index': '2',
            'title': 'Context & Diagnostic',
            'paragraphs': [
                'The client seeks to strengthen their digital presence with a website that reflects their professional identity.',
            ],
            'issuesTitle': 'Identified Challenges',
            'issues': [
                'Lack of professional digital presence',
                'Difficulty capturing clients online',
            ],
            'opportunityTitle': '<strong>Opportunity</strong>',
            'opportunity': (
                'Create a digital platform that builds trust and converts visitors into clients.'
            ),
        },
    },
    {
        'section_type': 'conversion_strategy',
        'title': '🚀 Proposed Approach & Conversion Strategy',
        'order': 3,
        'is_wide_panel': False,
        'content_json': {
            'index': '3',
            'title': 'Proposed Approach & Conversion Strategy',
            'intro': (
                'The page will be built as a tool to generate trust '
                'and convert visits into conversations.'
            ),
            'steps': [
                {
                    'title': '👀 Capture attention in the first seconds',
                    'bullets': [
                        'Clear main message: what the client does and who they help',
                        'Professional hero section with call to action',
                    ],
                },
                {
                    'title': '🤝 Build trust and credibility',
                    'bullets': [
                        'Testimonials and success stories',
                        'Credentials and experience',
                    ],
                },
                {
                    'title': '📲 Facilitate immediate contact',
                    'bullets': [
                        'WhatsApp and contact form always visible',
                        'Clear and direct calls to action',
                    ],
                },
            ],
            'resultTitle': '🎯 Expected Result',
            'result': (
                'A page that not only "looks nice" but generates contacts, '
                'conveys professionalism and makes it easy for people to say: "Let me reach out".'
            ),
        },
    },
    {
        'section_type': 'roi_projection',
        'title': '📈 ROI projection & business outcomes',
        'order': 4,
        'is_wide_panel': False,
        'content_json': {
            'index': '4',
            'title': 'ROI projection & business outcomes',
            'subtitle': (
                'What this investment can generate for your business — '
                'key metrics from the financial model.'
            ),
            'kpis': [],
            'methodology': '',
            'scenariosTitle': 'Year-one projected scenarios',
            'scenarios': [],
            'ctaNote': '',
        },
    },
    {
        'section_type': 'investment',
        'title': '💰 Investment & Payment Options',
        'order': 5,
        'is_wide_panel': False,
        'content_json': {
            'index': '4',
            'title': 'Investment & Payment Options',
            'introText': 'The total investment for this project is:',
            'totalInvestment': '',
            'currency': 'USD',
            'whatsIncluded': [
                {'icon': '🎨', 'title': 'Design', 'description': 'UX/UI focused on conversion'},
                {'icon': '⚙️', 'title': 'Development', 'description': 'Full project implementation'},
                {'icon': '🚀', 'title': 'Deployment & Delivery', 'description': 'Production deployment and launch'},
            ],
            'paymentOptions': [
                {'label': '40% upon signing the contract ✍️', 'description': ''},
                {'label': '30% upon final design approval ✅', 'description': ''},
                {'label': '30% upon site deployment 🚀', 'description': ''},
            ],
            'hostingPlan': {
                'title': 'Included Hosting – Cloud 1',
                'description': 'Optimized infrastructure for high-performance and availability:',
                'specs': [
                    {'icon': '🧠', 'label': 'vCPU', 'value': '4 vCPU cores'},
                    {'icon': '🧮', 'label': 'RAM', 'value': '8 GB dedicated RAM'},
                    {'icon': '💾', 'label': 'Storage', 'value': '100 GB NVMe storage'},
                    {'icon': '🌐', 'label': 'Bandwidth', 'value': '4 TB monthly'},
                    {'icon': '📍', 'label': 'Data centers', 'value': 'US, Brazil, France, Lithuania & India'},
                    {'icon': '🧬', 'label': 'Compatibility', 'value': 'Linux (Ubuntu)'},
                ],
                'hostingPercent': 80,
                'monthlyLabel': 'per month',
                'billingTiers': [
                    {
                        'frequency': 'nine_month',
                        'months': 9,
                        'discountPercent': 40,
                        'label': 'Every 9 months',
                        'badge': 'Best value',
                    },
                    {
                        'frequency': 'semiannual',
                        'months': 6,
                        'discountPercent': 20,
                        'label': 'Semiannual',
                        'badge': '20% off',
                    },
                    {
                        'frequency': 'quarterly',
                        'months': 3,
                        'discountPercent': 10,
                        'label': 'Quarterly',
                        'badge': '10% off',
                    },
                ],
                'renewalNote': (
                    'Renewals for each renewal year (from the second year onward): the cost '
                    'is adjusted once a year based on the percentage by which the SMLMV '
                    "(Colombia's monthly legal minimum wage) increased that year, plus a "
                    "fixed 8%, applied to the previous year's cost:\n\n"
                    'Renewal cost = Previous year cost × (1 + (SMLMV increase % + 8%))\n\n'
                    'For example, if the SMLMV increased 5%, the total increase would be '
                    '5% + 8% = 13%. If you were paying $100,000 COP, the new cost would be '
                    '$113,000 COP (a $13,000 increase).'
                ),
                'coverageNote': (
                    'The hosting cost covers three components: technical maintenance of the '
                    'platform (security updates, patches and database optimization), '
                    'incident/bug support, and the computing resources needed to keep '
                    'everything running (server, storage, bandwidth and SSL certificates).'
                ),
                'freeMonths': 1,
                'freeMonthsVisible': True,
                'freeMonthNote': HOSTING_FREE_MONTH_NOTES['en'],
            },
            'paymentMethods': [
                'Bank transfer',
                'Credit/Debit card',
            ],
            'modules': [],
            'valueReasons': [
                'Custom-made design',
                'Optimized code',
                'Post-launch support',
            ],
        },
    },
    {
        'section_type': 'timeline',
        'title': '⏳ Project Timeline',
        'order': 7,
        'is_wide_panel': True,
        'content_json': {
            'index': '6',
            'title': 'Project Timeline',
            'introText': 'The project will be developed in the following phases:',
            'totalDuration': 'Approximately 1 month',
            'phases': [
                {
                    'title': '🎨 Design',
                    'duration': '1 week',
                    'weeks': 'Week 1',
                    'circleColor': 'bg-purple-600',
                    'statusColor': 'bg-purple-100 text-purple-700',
                    'description': 'Custom visual design in Figma, reviews and adjustments.',
                    'tasks': ['Moodboard and color palette', 'High-fidelity UI design', 'Client reviews'],
                    'milestone': 'Design approved',
                },
                {
                    'title': '💻 Development',
                    'duration': '2 weeks',
                    'weeks': 'Weeks 2-3',
                    'circleColor': 'bg-green-600',
                    'statusColor': 'bg-green-100 text-green-700',
                    'description': 'Native coding, payment gateway and email integration.',
                    'tasks': ['Responsive frontend', 'Backend and database', 'Integrations'],
                    'milestone': 'Functional MVP',
                },
                {
                    'title': '🚀 QA & Launch',
                    'duration': '3 days',
                    'weeks': 'Week 4',
                    'circleColor': 'bg-orange-600',
                    'statusColor': 'bg-orange-100 text-orange-700',
                    'description': 'Final testing, adjustments, and publication.',
                    'tasks': ['Cross-browser testing', 'Final adjustments', 'Production deploy'],
                    'milestone': 'Site in production',
                },
                {
                    'title': '📦 Delivery & Deployment',
                    'duration': '3 days',
                    'weeks': 'Week 4',
                    'circleColor': 'bg-pink-600',
                    'statusColor': 'bg-pink-100 text-pink-700',
                    'description': 'Domain setup, documentation delivery, and closure.',
                    'tasks': ['Domain and SSL setup', 'Documentation delivery', 'Client training'],
                    'milestone': 'Final delivery 💫',
                },
            ],
        },
    },
    {
        'section_type': 'design_ux',
        'title': '🎨 Visual Design & User Experience',
        'order': 8,
        'is_wide_panel': False,
        'content_json': {
            'index': '7',
            'title': 'Visual Design & User Experience',
            'paragraphs': [
                'The web development will be conceived as a professional digital experience.',
                'Each section will be carefully created to generate a fluid journey.',
            ],
            'focusTitle': 'Structure Highlights',
            'focusItems': [
                'Clear service presentation',
                'Social media integration',
                'Space for booking appointments or consultations',
            ],
            'objectiveTitle': 'Visual <strong>Objective</strong>',
            'objective': (
                'Inspire trust from the first moment, reflecting authenticity '
                'and depth of message.'
            ),
        },
    },
    {
        'section_type': 'creative_support',
        'title': '🤝 Personalized Creative Support',
        'order': 9,
        'is_wide_panel': False,
        'content_json': {
            'index': '8',
            'title': 'Personalized Creative Support',
            'paragraphs': [
                'Throughout the process, the client will have close support from our team.',
                'The process will be collaborative, warm, and empathetic.',
            ],
            'includesTitle': 'Includes',
            'includes': [
                '💡 Design and structure review and feedback sessions.',
                '🎨 Support in selecting color palette, typography, and visual style.',
                '🕊 Adaptations as ideas evolve.',
                '🔗 Ensuring coherence between aesthetics, content, and purpose.',
            ],
            'closing': (
                'Every decision will be a co-creation, where the client can actively participate '
                'so the final result faithfully reflects their message.'
            ),
        },
    },
    {
        'section_type': 'value_added_modules',
        'title': '🎁 Included at no extra cost',
        'order': 11,
        'is_wide_panel': False,
        'content_json': {
            'index': '11',
            'title': 'What we add to your project at no extra cost',
            'intro': (
                'These modules are not billed separately. They are included because we believe '
                'every deliverable should ship with the minimum tools to operate, measure and '
                'understand it from day one.'
            ),
            'module_ids': ['admin_module', 'manual_module', 'kpi_dashboard_module', 'analytics_dashboard', 'ai_automation_module'],
            'justifications': {
                'admin_module': 'So you don\'t depend on a developer every time you need to change content.',
                'analytics_dashboard': 'So you know how your audience behaves without paying for external tools.',
                'kpi_dashboard_module': 'To make decisions with real-time data, not intuition.',
                'manual_module': 'So anyone on your team can understand the system without training sessions.',
                'ai_automation_module': 'So a task you do by hand today can be driven from an AI assistant chat and run on its own via scheduled tasks.',
            },
            # Legal wording lives in the _*_CLAUSES_EN catalog above; must stay
            # in parity with the ES section.
            'conditions': {
                'kpi_dashboard_module': _module_condition(
                    _KPI_CLAUSES_EN,
                    min_price_usd=1500,
                    min_price_cop=6000000,
                    discretionary_note='Implemented if the business logic allows and it makes sense to define and measure KPIs.',
                ),
                'analytics_dashboard': _module_condition(
                    _ANALYTICS_CLAUSES_EN,
                    min_price_usd=1800,
                    min_price_cop=7200000,
                    discretionary_note='Implemented if the business logic allows and it makes sense to collect and analyze usage data.',
                ),
                'admin_module': _module_condition(
                    _ADMIN_CLAUSES_EN,
                    discretionary_note='Implemented if the business logic allows managing content or operations autonomously.',
                ),
                'manual_module': _module_condition(
                    _MANUAL_CLAUSES_EN,
                    discretionary_note='Implemented over the processes and roles defined within the proposal scope.',
                ),
                'ai_automation_module': _module_condition(
                    _AI_CLAUSES_EN,
                    min_price_usd=2900,
                    min_price_cop=10400000,
                    duration_months=6,
                    discretionary_note='Implemented if the business logic allows and it makes sense to automate the process by connecting it to an AI assistant.',
                ),
            },
            'general_terms': deepcopy(_VALUE_ADDED_GENERAL_TERMS_EN),
            'footer_note': 'Additional total: $0. Already priced inside the project budget.',
        },
    },
    {
        'section_type': 'functional_requirements',
        'title': '🧩 Functional Requirements',
        'order': 10,
        'is_wide_panel': True,
        'content_json': {
            'index': '10',
            'title': 'Functional Requirements',
            'intro': 'Below are the functional requirements for the project.',
            'groups': [
                {
                    'id': 'views',
                    'icon': '🖥️',
                    'title': 'Views',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Each view is a screen or section of the website. Its purpose is to guide the visitor '
                        'to understand the value proposition and facilitate contact or the desired action.'
                    ),
                    'items': [
                        {'icon': '🏠', 'name': 'Home (Landing Page)', 'description': 'The first impression of the site. Clearly presents the brand identity with an attractive message, call to action, and quick access to main sections.'},
                        {'icon': 'ℹ️', 'name': 'About Us', 'description': 'Page dedicated to sharing the history, mission, vision, and values of the company or project. Ideal for building trust with visitors.'},
                        {'icon': '📞', 'name': 'Contact', 'description': 'Section with a form for users to send messages, along with contact information (phone, email, address) and an optional map.'},
                        {'icon': '📜', 'name': 'Terms & Conditions', 'description': 'Page informing users about site policies, personal data handling, and terms of use. Includes an acceptance checkbox ensuring compliance with regulations.'},
                        {'icon': '🛒', 'name': 'Categories', 'description': 'Section to display available product categories, allowing users to explore the different types of products offered on the site.'},
                        {'icon': '🗂️', 'name': 'Catalog by Category', 'description': 'Allows users to explore products within a specific category, facilitating navigation and selection of related products.'},
                        {'icon': '📦', 'name': 'Product View', 'description': 'Shows details of a selected product, including images, price, features, descriptions, and options to add to cart.'},
                        {'icon': '🛒', 'name': 'Shopping Cart', 'description': 'Allows users to view added products, adjust quantities, remove items, and proceed to checkout.'},
                        {'icon': '📜', 'name': 'Purchase History', 'description': 'Allows users to review past purchases, including details such as date, amount, and products acquired.'},
                        {'icon': '👤', 'name': 'User Registration', 'description': 'Allows users to create an account to access personalized features like purchase history and favorite products.'},
                        {'icon': '🔐', 'name': 'Login', 'description': 'Provides access for registered users to manage their purchases and preferences.'},
                        {'icon': '❤️', 'name': 'Wishlist / Favorites', 'description': 'Allows users to save products for quick reference in future visits.'},
                        {'icon': '📝', 'name': 'User Profile', 'description': 'Section where users can view and update their personal information, purchase history, and account settings.'},
                    ],
                },
                {
                    'id': 'components',
                    'icon': '🧩',
                    'title': 'Components',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Components are visual or functional elements reused across multiple sections '
                        'of the site. This ensures a coherent experience and optimizes development.'
                    ),
                    'items': [
                        {'icon': '🔝', 'name': 'Header', 'description': 'Includes logo, navigation menu, and quick access to social media or key site sections.'},
                        {'icon': '🔚', 'name': 'Footer', 'description': 'Contains additional information such as copyright, policies, social media links, and other useful resources.'},
                        {'icon': '🎯', 'name': 'Featured Products Carousel', 'description': 'Highlights selected products such as promotions, special offers, or seasonal products to improve visibility and customer interest.'},
                        {'icon': '🎁', 'name': 'Featured Wishlists Carousel', 'description': 'Highlights selected wishlists such as promotions, special offers, or seasonal products to improve visibility and customer interest.'},
                        {'icon': '❓', 'name': 'FAQ (Frequently Asked Questions)', 'description': 'Section to answer the most common customer questions and resolve doubts quickly and efficiently.'},
                    ],
                },
                {
                    'id': 'features',
                    'icon': '⚙️',
                    'title': 'Specific Features',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Features are interactive actions or behaviors of the website. '
                        'They bring life and dynamism, making the page practical and useful.'
                    ),
                    'items': [
                        {'icon': '🔑', 'name': 'Google Registration', 'description': 'One-click account creation with the user\'s Google account (OAuth). Captures a verified name and email without long forms — key for knowing real data of interested customers from the first contact. 🔐📧'},
                        {'icon': '🔓', 'name': 'Google Sign-In', 'description': 'Instant access for returning users with their Google account, with no extra passwords to remember or recover. Less friction on every repeat visit. ⚡'},
                        {'icon': '🔎', 'name': 'Advanced Search with Dynamic Filters', 'description': 'Users can filter properties by zones, price range, square meters, and specific features. Intuitive navigation saves time and better qualifies interest. 🔍📍'},
                        {'icon': '💬', 'name': 'Direct WhatsApp per Property', 'description': 'Each property listing includes an instant contact button. One click sends a predefined message indicating exactly which property the client is inquiring about. 📲⚡'},
                        {'icon': '🖼️', 'name': 'Rich Visualization & Galleries', 'description': 'High-quality visualization system with interactive zoom and optimized loading so property images look impeccable without affecting site speed. 📸✨'},
                        {'icon': '📩', 'name': 'Automatic Notifications', 'description': 'The system sends automatic confirmation emails when a user registers or submits an information request, keeping contact active from the first second. 📩✅'},
                    ],
                },
                {
                    'id': 'cross_cutting_features',
                    'icon': '🔗',
                    'title': 'Cross-cutting Features',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Quality capabilities that span multiple views, components, and flows. '
                        'This catalog is a starting point and must be adapted to the business, '
                        'product stage, and actual scope of each proposal.'
                    ),
                    'items': [
                        {'icon': '📱', 'name': 'Responsive Design', 'description': 'The experience adapts to the screen sizes and interaction modes defined for the project, prioritizing the devices relevant to its users.'},
                        {'icon': '♿', 'name': 'Accessibility', 'description': 'The interface considers navigation, contrast, labels, and understandable states according to the audience and agreed accessibility level.'},
                        {'icon': '🧭', 'name': 'Consistent Usability', 'description': 'Interaction and feedback patterns remain coherent across the views and flows included in scope.'},
                        {'icon': '⚡', 'name': 'Performance', 'description': 'Screens and resources are optimized for response times appropriate to the expected content, traffic, and devices.'},
                        {'icon': '🛡️', 'name': 'Security', 'description': 'Access, forms, and sensitive operations apply controls proportional to the risks and roles defined for the project.'},
                        {'icon': '🔒', 'name': 'Data Privacy', 'description': 'Data collection, use, and retention are limited to what is necessary and aligned with the obligations applicable to the business.'},
                        {'icon': '🌐', 'name': 'Cross-browser Compatibility', 'description': 'The experience is validated in the browsers and versions agreed according to the audience and real usage conditions.'},
                    ],
                },
                {
                    'id': 'admin_module',
                    'icon': '🛠️',
                    'title': 'Admin Module',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'The admin module allows managing the site content and operations '
                        'without depending on technical development. The scope covers only the '
                        'managers listed in this proposal; additional managers are quoted as an extension.'
                    ),
                    'items': [
                        {'icon': '📂', 'name': 'Product Manager', 'description': 'Create, edit, and delete main products or content.'},
                        {'icon': '🗂️', 'name': 'Category Manager', 'description': 'Catalog organization by categories or collections.'},
                        {'icon': '👥', 'name': 'User Manager', 'description': 'User account administration.'},
                        {'icon': '📝', 'name': 'Blog Manager', 'description': 'Article and editorial content publishing.'},
                        {'icon': '❤️', 'name': 'Favorites Manager', 'description': 'User wishlists and favorites management.'},
                    ],
                },
                {
                    'id': 'analytics_dashboard',
                    'icon': '📊',
                    'title': 'Analytics Module',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Smart reporting dashboard with real-time metrics to understand '
                        'visitor behavior and make data-driven decisions. Includes up to '
                        '6 standard reports (the ones listed here) with data from the last '
                        '12 months; additional custom reports are quoted separately.'
                    ),
                    'items': [
                        {
                            'icon': '🔥',
                            'name': 'Most Visited Pages & Products',
                            'description': (
                                'Identify which sections and products generate the most interest. '
                                'Prioritize content, reorganize your catalog, and boost '
                                'what truly attracts your visitors.'
                            ),
                        },
                        {
                            'icon': '🔄',
                            'name': 'New vs Returning Visitors',
                            'description': (
                                'Distinguish between first-time visitors and returning ones. '
                                'Helps measure loyalty and evaluate whether your retention '
                                'strategies are working.'
                            ),
                        },
                        {
                            'icon': '📱',
                            'name': 'Audience Devices',
                            'description': (
                                'Know which devices your users browse from: mobile, tablet, or desktop. '
                                'Optimize the experience for the device most used by your audience.'
                            ),
                        },
                        {
                            'icon': '🌍',
                            'name': 'Geographic Origin',
                            'description': (
                                'See which cities or countries your visitors come from. '
                                'Ideal for focusing ad campaigns and understanding where '
                                'your real market is.'
                            ),
                        },
                        {
                            'icon': '🔗',
                            'name': 'Traffic Sources',
                            'description': (
                                'Discover how users reach your site: organic search, '
                                'social media, direct links, or paid campaigns. Invest '
                                'your marketing budget more wisely.'
                            ),
                        },
                        {
                            'icon': '📈',
                            'name': 'Visit Trends',
                            'description': (
                                'Visit evolution chart over time. Detect peaks, '
                                'measure campaign impact, and understand seasonal patterns '
                                'in your audience.'
                            ),
                        },
                    ],
                },
                {
                    'id': 'kpi_dashboard_module',
                    'icon': '📊',
                    'title': 'KPI Dashboard & Metrics',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'Control panel complementary to the analytics module, with real-time '
                        'key performance indicators to monitor the health of your business '
                        'and make data-driven decisions. Includes up to 8 KPIs and 4 charts, '
                        'defined with the client at project kickoff.'
                    ),
                    'items': [
                        {'icon': '📈', 'name': 'Real-time KPIs', 'description': 'Visualize the most important indicators of your business updated instantly: sales, conversions, traffic and more. Up to 8 indicators defined with the client.'},
                        {'icon': '📊', 'name': 'Interactive Charts', 'description': 'Visual dashboards with line, bar and pie charts that allow filtering by period, category or segment. Up to 4 charts included.'},
                        {'icon': '🔔', 'name': 'Performance Alerts', 'description': 'Automatic notifications when a KPI falls below the defined threshold or exceeds a set goal. Up to 5 alerts configured within scope.'},
                        {'icon': '📥', 'name': 'Report Export', 'description': 'Download reports in CSV to share with your team or stakeholders without needing to access the system.'},
                    ],
                },
                {
                    'id': 'manual_module',
                    'icon': '📘',
                    'title': 'Interactive User Manual',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'A non-technical interactive manual/wiki, with a navigable index and search, '
                        'that describes the processes, flows, dependencies, roles and responsibilities '
                        'of your application. Designed so anyone on the team can understand the '
                        'system without asking the developer for help. It covers the processes and '
                        'roles of the approved scope, with up to 15 documentation articles and one '
                        '(1) content update included at delivery.'
                    ),
                    'items': [
                        {'icon': '🔎', 'name': 'Search and index navigation', 'description': 'Find any process, view or role in seconds.'},
                        {'icon': '🧭', 'name': 'Step-by-step processes and flows', 'description': 'Every system flow documented in plain language, no jargon.'},
                        {'icon': '👥', 'name': 'Roles and responsibilities', 'description': 'Who does what inside the application and what permissions each role has.'},
                        {'icon': '🔗', 'name': 'Dependencies and business rules', 'description': 'How modules relate to each other and which rules apply.'},
                    ],
                },
                {
                    'id': 'ai_automation_module',
                    'icon': '🤖',
                    'title': 'AI Assistant Automation',
                    'is_visible': True,
                    'selected': True,
                    'price_percent': 0,
                    'description': (
                        'We take one (1) process you do manually today and automate it by connecting it to '
                        'an AI assistant (Claude or ChatGPT). From the chat you can control the process '
                        'and, via scheduled tasks inside the assistant itself, let it run on its own.'
                    ),
                    'items': [
                        {'icon': '💬', 'name': 'Control from the chat', 'description': 'Run and monitor the process by talking to the AI assistant, without opening the system.'},
                        {'icon': '⏰', 'name': 'Scheduled tasks', 'description': 'The assistant itself runs the process automatically on the schedule you define.'},
                        {'icon': '🔗', 'name': 'Integration with your current process', 'description': 'We connect the automation directly onto the manual flow you use today.'},
                    ],
                },
            ],
            'additionalModules': [
                {
                    'id': 'integration_electronic_invoicing',
                    'icon': '🧾',
                    'title': 'Electronic Invoicing & DIAN Integration (API Integration)',
                    'is_visible': True,
                    'description': (
                        'Platform connection with the client\'s invoicing system to generate, '
                        'send, query, and reconcile electronic receipts from business operational flows. '
                        'Includes synchronization of clients, products, taxes, invoices, '
                        'credit/debit notes and support documents, with fiscal status traceability '
                        'and support for API automations.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 60,
                    'is_invite': False,
                    'items': [
                        {'icon': '📄', 'name': 'Electronic Receipt Generation', 'description': 'Automatic creation of invoices, credit/debit notes, and support documents from business operational flows.'},
                        {'icon': '🔄', 'name': 'Fiscal Data Synchronization', 'description': 'Bidirectional synchronization of clients, products, taxes, and receipts with the invoicing system.'},
                        {'icon': '📊', 'name': 'Fiscal Status Traceability', 'description': 'Query and track the status of each receipt: issued, accepted, rejected, or in process with DIAN.'},
                        {'icon': '🔗', 'name': 'Colombian Provider Integration', 'description': 'Connection with Siigo, Alegra, or other providers with presence and documented API in Colombia.'},
                        {'icon': '⚙️', 'name': 'API Automations', 'description': 'Automatic flows for payment reconciliation, invoice issuance upon order completion, and fiscal status notifications.'},
                    ],
                },
                {
                    'id': 'integration_regional_payments',
                    'icon': '🇨🇴',
                    'title': 'Regional Payment Gateway (Colombia) (API Integration)',
                    'is_visible': True,
                    'description': (
                        'Integration with payment gateways present in the Colombian market '
                        'to facilitate local transactions with multiple payment methods.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'is_invite': False,
                    'items': [
                        {'icon': '💳', 'name': 'PayU', 'description': 'One of the most used in Colombia, supports card, PSE, Efecty, Baloto, Nequi, Daviplata.'},
                        {'icon': '🏦', 'name': 'Wompi (Bancolombia)', 'description': 'Excellent local option with PSE, cards, Nequi, and Bancolombia button support.'},
                        {'icon': '💰', 'name': 'ePayco', 'description': 'Easy-to-integrate Colombian alternative supporting PSE, cards, and physical collections.'},
                    ],
                },
                {
                    'id': 'integration_international_payments',
                    'icon': '🌎',
                    'title': 'International Payment Gateway (API Integration)',
                    'is_visible': True,
                    'description': (
                        'Integration with international payment gateways to facilitate '
                        'global transactions with credit/debit cards and international accounts.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'is_invite': False,
                    'items': [
                        {'icon': '💳', 'name': 'Stripe', 'description': 'Ideal for credit/debit card payments, widely used worldwide. Supports subscriptions, one-time payments, and multiple currencies.'},
                        {'icon': '🅿️', 'name': 'PayPal', 'description': 'Globally recognized platform, allows payments with PayPal balance, cards, and international accounts.'},
                    ],
                },
                {
                    'id': 'pwa_module',
                    'icon': '📱',
                    'title': 'Installable Mobile App (PWA)',
                    'is_visible': True,
                    'description': (
                        'Turn your website into an installable application that works '
                        'even without an internet connection. Deliver a native-like experience '
                        'directly from the browser, no app stores required.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 40,
                    'items': [
                        {'icon': '📲', 'name': 'Device Installation', 'description': 'Users can install your site as an app on their phone or computer, with direct access from the home screen.'},
                        {'icon': '📡', 'name': 'Offline Functionality', 'description': 'The site remains accessible without an internet connection, showing previously loaded content and syncing data upon reconnection.'},
                        {'icon': '🔔', 'name': 'Push Notifications', 'description': 'Send direct notifications to user devices to keep them informed about news, promotions, or updates.'},
                        {'icon': '🎨', 'name': 'Custom Splash Screen', 'description': 'Branded splash screen with your visual identity when opening the app, creating a professional experience from the first moment.'},
                        {'icon': '🔄', 'name': 'Background Sync', 'description': 'Data syncs automatically when the device reconnects, ensuring up-to-date information without user intervention.'},
                        {'icon': '⬆️', 'name': 'Automatic Updates', 'description': 'The application updates transparently without requiring any user action, always running the latest version.'},
                    ],
                },
                {
                    'id': 'corporate_branding_module',
                    'icon': '🎨',
                    'title': 'Visual Identity & Corporate Branding',
                    'is_visible': True,
                    'description': (
                        'We apply your visual identity consistently across every system touchpoint — emails, '
                        'documents, social previews and internal screens — so your brand feels professional and '
                        'coherent everywhere your customers interact with it.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': True,
                    'selected': True,
                    'price_percent': 35,
                    'items': [
                        {'icon': '✉️', 'name': 'Branded Transactional Emails', 'description': 'HTML templates with logo, colors, typography and brand signature applied across all system emails — welcome, confirmations, alerts, password recovery and notifications — instead of plain-text or generic messages.'},
                        {'icon': '📄', 'name': 'PDFs & Exports with Branding', 'description': 'Invoices, reports, certificates, receipts and Excel/CSV downloads generated from the system with branded headers, corporate color palette and brand footers. Every document that leaves the platform reinforces the business\'s professional image.'},
                        {'icon': '🔗', 'name': 'Social Link Preview Cards (Open Graph)', 'description': 'When someone shares a link to the site or a proposal on WhatsApp, Facebook, LinkedIn or X, a card with logo, image and brand colors appears — not a plain link. Direct impact on perception and CTR.'},
                        {'icon': '🖥️', 'name': 'System Screens with Brand Identity', 'description': 'Error pages (404, 500), maintenance, login and loading states (skeletons, spinners) with visual identity and messaging in the brand\'s voice, instead of the framework\'s generic screens.'},
                        {'icon': '🔎', 'name': 'Structured Metadata for Search & AI', 'description': 'JSON-LD Organization with logo, colors, social profiles and contact data — so Google, Bing and assistants like ChatGPT or Perplexity correctly display the brand in knowledge panels, enriched results and citations.'},
                    ],
                },
                {
                    'id': 'ai_module',
                    'icon': '🤖',
                    'title': 'AI Integration & Automation',
                    'is_visible': True,
                    'description': (
                        'Supercharge your project with artificial intelligence. '
                        'We explore together how to tailor AI solutions to your specific business needs.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 0,
                    'is_invite': True,
                    'invite_note': (
                        '🤝 We invite you to a personalized call where we\'ll explore together '
                        'how artificial intelligence can transform your business. You\'ll learn '
                        'about our solutions, how we tailor them to your specific case, '
                        'and associated costs \u2014 no commitment required.'
                    ),
                    'items': [
                        {'icon': '⚡', 'name': 'Automations', 'description': 'Intelligent workflows that execute repetitive tasks autonomously, freeing up time for what truly matters.'},
                        {'icon': '📊', 'name': 'Natural Language Data Analysis', 'description': 'Query your data using plain language questions and get clear answers, charts, and reports without technical expertise.'},
                        {'icon': '✍️', 'name': 'Content Generation', 'description': 'AI-assisted creation of texts, product descriptions, blog articles, and communications, maintaining your brand tone and style.'},
                        {'icon': '💬', 'name': 'Intelligent Communication', 'description': 'Chatbots and virtual assistants that serve your customers 24/7, answer FAQs, and escalate conversations when needed.'},
                        {'icon': '📄', 'name': 'Document Processing', 'description': 'Automatic extraction and classification of information from invoices, contracts, and forms, reducing manual work and errors.'},
                        {'icon': '🔍', 'name': 'Search & Research', 'description': 'Semantic search engine that understands user intent and returns relevant results, not just text matches.'},
                        {'icon': '🛡️', 'name': 'Security & Moderation', 'description': 'Automatic detection of inappropriate content, spam, and suspicious activity to keep your platform safe and trustworthy.'},
                        {'icon': '⚙️', 'name': 'Process Optimization', 'description': 'Intelligent analysis of your operations to identify bottlenecks, suggest improvements, and automate routine decisions.'},
                        {'icon': '🎓', 'name': 'Learning & Training', 'description': 'Adaptive systems that personalize the learning experience according to each user\'s pace and level.'},
                        {'icon': '🔮', 'name': 'Prediction & Forecasting', 'description': 'Predictive models that anticipate trends, demand, and customer behavior for more informed decision-making.'},
                        {'icon': '🔗', 'name': 'Integration & Orchestration', 'description': 'Intelligent connection between your existing tools and services, coordinating data flows and actions across multiple platforms.'},
                    ],
                },
                {
                    'id': 'integration_conversion_tracking',
                    'icon': '📡',
                    'title': 'Smart Conversions (Meta & Google Ads) (API Integration)',
                    'is_visible': True,
                    'description': (
                        'Maximize your advertising ROI with server-side conversion tracking. '
                        'Your website reports every valuable action directly to Meta and Google, '
                        'without relying on cookies or the visitor\'s browser.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 0,
                    'is_invite': True,
                    'invite_note': (
                        '🤝 We invite you to a call where we\'ll analyze your current '
                        'advertising strategy and design together the server-side integration '
                        'with Meta and Google Ads. See how to maximize your ROAS with '
                        'accurate conversion data \u2014 no commitment required.'
                    ),
                    'items': [
                        {'icon': '🔗', 'name': 'Direct Meta Conversions API Connection', 'description': 'Every conversion is sent from your server directly to Meta, allowing Facebook and Instagram to identify which ads generated real results, even with ad blockers.'},
                        {'icon': '📊', 'name': 'Direct Google Enhanced Conversions Connection', 'description': 'Conversions are reported from the server with encrypted client data. Google matches each conversion to the original ad click and optimizes automated bids with real information.'},
                        {'icon': '🛡️', 'name': 'Immune to Blockers & Cookie Restrictions', 'description': 'Unlike traditional tracking, this module works from your server. It is not affected by ad blockers, iOS 14+ restrictions, or third-party cookie deprecation.'},
                        {'icon': '🔄', 'name': 'Automatic Event Deduplication', 'description': 'The system keeps browser tracking as a backup and syncs both sources with a unique identifier. Meta and Google automatically remove duplicates.'},
                        {'icon': '🎯', 'name': 'Custom Conversion Events', 'description': 'Configure the events that matter to your business: form submitted, WhatsApp click, call booked, proposal viewed, proposal accepted. Each with its monetary value to calculate real ROAS.'},
                        {'icon': '📈', 'name': 'Conversion Status Panel', 'description': 'View from your admin panel the status of each event sent: confirmed, pending, or failed. Includes matching quality diagnostics.'},
                    ],
                },
                {
                    'id': 'biometric_verification_module',
                    'icon': '🪪',
                    'title': 'Biometric Verification & Validation (API Integration)',
                    'is_visible': True,
                    'description': (
                        'Confirms that the person behind the screen is really who they claim to be, '
                        'combining ID document reading, facial recognition, and liveness detection. '
                        'Reduces fraud, meets KYC requirements, and streamlines digital onboarding '
                        'for your customers and/or internal users.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 0,
                    'is_invite': True,
                    'invite_note': (
                        '🤝 We invite you to a call where we\'ll define together the scope of '
                        'biometric verification and identity validation for your business. '
                        'A specialized provider runs the integration and bills the service '
                        'directly to the end client — we connect the solution to your platform, '
                        'no commitment required.'
                    ),
                    'items': [
                        {'icon': '🪪', 'name': 'ID Document Reading & Validation', 'description': 'Captures the identity document (front and back) with OCR and validates fields, formats, and authenticity.'},
                        {'icon': '👤', 'name': 'Facial Recognition', 'description': 'Biometric comparison between the document photo and a live selfie of the user to confirm identity match.'},
                        {'icon': '🎬', 'name': 'Liveness Detection', 'description': 'Active or passive detection that the person is physically present, preventing spoofing with photos, videos, or masks.'},
                        {'icon': '🛡️', 'name': 'Antifraud & KYC', 'description': 'Acceptance rules, watchlists, and per-attempt traceability — aligned with KYC best practices and compliance.'},
                        {'icon': '⚡', 'name': 'Frictionless Digital Onboarding', 'description': 'End-to-end flow embedded in your platform: the user validates in minutes from their phone or computer, without in-person paperwork.'},
                        {'icon': '📊', 'name': 'Verifications Panel', 'description': 'Admin view with the status of each verification (approved, rejected, pending), evidence, and reason — ready for audit.'},
                    ],
                },
                {
                    'id': 'behavior_tracking_module',
                    'icon': '👣',
                    'title': 'User Behavior Tracking',
                    'is_visible': True,
                    'description': (
                        'Discover how people actually use your platform: when your users come in, '
                        'which views they open and how long they spend on each one. It is the same '
                        'capability we use to understand interest in our own proposals, installed '
                        'in your product with data that is 100% yours. Included scope: tracking for '
                        'up to 15 views, a panel with up to 8 KPIs and 4 charts, and 12-month data '
                        'retention.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 30,
                    'items': [
                        {'icon': '📍', 'name': 'Session & Open Tracking', 'description': 'Captures every usage session: when the user enters, from which device, and whether it is a first visit or a return. Fully first-party — no third-party cookies or external tools.'},
                        {'icon': '🖥️', 'name': 'Views Opened & Time per View', 'description': 'Records which views or sections each user opens and how many seconds they stay on each one. Covers up to 15 system views, defined with the client at project kickoff.'},
                        {'icon': '🔥', 'name': 'Interest Map per View', 'description': 'Ranking of the views with the most and least attention based on accumulated time and visit counts — so you know what works and what goes unnoticed, with nothing extra to install.'},
                        {'icon': '🚪', 'name': 'Journey Funnel with Drop-off', 'description': 'Visualize how users move across the tracked views and detect at which step they leave. Includes one (1) main funnel defined with the client over the tracked views.'},
                        {'icon': '📊', 'name': 'Built-in Behavior Panel', 'description': 'A dashboard inside your own admin panel with up to 8 KPIs and 4 charts: sessions, average time, most-opened views and device breakdown. No external licenses or subscriptions.'},
                        {'icon': '📱', 'name': 'Device Breakdown', 'description': 'Identify which device your users prefer — mobile, tablet or desktop — to prioritize improvements where your users actually are.'},
                        {'icon': '🗄️', 'name': 'Own Data with 12-Month Retention', 'description': 'Events are stored in your own database and kept for the last 12 months. Does not include screen recording, click heatmaps or third-party cross-site tracking.'},
                    ],
                },
                {
                    'id': 'reports_alerts_module',
                    'icon': '📬',
                    'title': 'Reports & Alerts via Email or WhatsApp',
                    'is_visible': True,
                    'description': (
                        'Stay informed at all times with automated reports and customized alerts '
                        'delivered directly to your email or WhatsApp.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'items': [
                        {'icon': '📧', 'name': 'Automated Email Reports', 'description': 'Receive periodic summaries with key business metrics directly in your inbox, without having to log into the system.'},
                        {'icon': '🔔', 'name': 'Custom Alerts', 'description': 'Set up notifications for important events: new sales, user registrations, low stock, or any metric you define.'},
                        {'icon': '💚', 'name': 'WhatsApp Integration', 'description': 'Receive instant alerts and reports on your WhatsApp number through the official API, perfect for staying informed from the same channel where you serve your customers.'},
                        {'icon': '⏰', 'name': 'Scheduled Delivery', 'description': 'Define the frequency and timing of your reports: daily, weekly, monthly, or real-time based on your needs.'},
                        {'icon': '📋', 'name': 'Periodic Executive Summary', 'description': 'Consolidated report with the most relevant metrics of your project, designed for quick reading and agile decision-making.'},
                    ],
                },
                {
                    'id': 'email_marketing_module',
                    'icon': '📧',
                    'title': 'Email Marketing Integration',
                    'is_visible': True,
                    'description': (
                        'Connect your website with email marketing platforms to '
                        'automate campaigns, segment audiences and increase '
                        'visitor-to-customer conversion.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 10,
                    'items': [
                        {'icon': '📬', 'name': 'Lead Capture', 'description': 'Optimized forms and smart pop-ups to capture emails from visitors interested in your content or products.'},
                        {'icon': '🔄', 'name': 'Email Automations', 'description': 'Automatic welcome sequences, abandoned carts, post-purchase follow-up and re-engagement of inactive users.'},
                        {'icon': '🎯', 'name': 'Audience Segmentation', 'description': 'Classify your subscribers by behavior, interests and demographics to send relevant, personalized messages.'},
                        {'icon': '📊', 'name': 'Campaign Analytics', 'description': 'Detailed metrics on opens, clicks, conversions and ROI of each campaign to optimize your communication strategy.'},
                        {'icon': '🔗', 'name': 'Platform Integration', 'description': 'Native connection with Mailchimp, SendGrid, Brevo or other leading email marketing platforms based on your needs.'},
                    ],
                },
                {
                    'id': 'qr_generator_module',
                    'icon': '🔳',
                    'title': 'QR Code Generator',
                    'is_visible': True,
                    'description': (
                        'Turn any link, text, or action into a QR code ready to print, share, or '
                        'paste wherever your business needs it. Built to bridge the physical world '
                        'and your digital platform without friction — from a restaurant table to '
                        'your product packaging.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 25,
                    'items': [
                        {'icon': '⚡', 'name': 'Instant Generation', 'description': 'Create QR codes from URLs, text, vCard contacts, WiFi networks, WhatsApp numbers, or any internal platform flow — in seconds.'},
                        {'icon': '🎨', 'name': 'Branded Customization', 'description': 'Apply your corporate colors, place your logo at the center, and pick formats (PNG, SVG, PDF) ready for high-resolution printing without quality loss.'},
                        {'icon': '🔄', 'name': 'Editable Dynamic Codes', 'description': 'Change where an already-printed QR points to without reprinting it. Ideal for seasonal menus, promos, events, and campaigns that evolve.'},
                        {'icon': '📊', 'name': 'Scan Tracking', 'description': 'Measure how often each code is scanned, from which device, and at what time — perfect for evaluating the performance of physical campaigns, billboards, flyers, and packaging.'},
                        {'icon': '🗂️', 'name': 'Code Library', 'description': 'Every QR generated is organized in a panel, grouped by campaign or purpose, ready to reuse, download, or deactivate once no longer needed.'},
                        {'icon': '🚀', 'name': 'Ready-to-Use Cases', 'description': 'Digital menu, WhatsApp link, event check-in, catalog download, quick login, surveys, tipping, or reviews — preconfigured to launch the same day.'},
                    ],
                },
                {
                    'id': 'content_generator_module',
                    'icon': '✍️',
                    'title': 'AI Content Generator with Editorial Calendar',
                    'is_visible': True,
                    'description': (
                        'Keep your brand active and consistent without relying on daily '
                        'inspiration. AI drafts blog posts, emails, and social content in your '
                        'business voice, and an editorial calendar lets you plan, schedule, and '
                        'auto-publish — all from a single panel, with monthly or weekly views '
                        'of what\'s coming up.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 30,
                    'items': [
                        {'icon': '🤖', 'name': 'AI-Assisted Writing', 'description': 'Draft blog posts, newsletters, emails, and social posts from a simple brief. Tweak tone, length, and format with a couple of clicks.'},
                        {'icon': '🎙️', 'name': 'Brand Voice & Templates', 'description': 'Define your editorial identity once (tone, style, banned words, calls to action) and the AI honors that voice in every piece it generates.'},
                        {'icon': '🌐', 'name': 'Multichannel: Blog, Email & Social', 'description': 'A single idea automatically adapts to each channel\'s format: long post for the blog, subject and body for email, short copy for Instagram, LinkedIn, or X.'},
                        {'icon': '📅', 'name': 'Visual Editorial Calendar', 'description': 'Monthly and weekly views with every piece planned, in draft, scheduled, and published. Drag and drop to rearrange dates in seconds.'},
                        {'icon': '⏰', 'name': 'Scheduling & Auto-Publishing', 'description': 'Schedule each piece for a specific date and time. The system publishes to the blog, sends the email, or posts to connected social networks — without manual intervention.'},
                        {'icon': '📊', 'name': 'Tracking Panel', 'description': 'Status of every publication (draft, scheduled, published, failed), basic performance metrics, and the option to reschedule or duplicate pieces with one click.'},
                        {'icon': '🔗', 'name': 'Channel Integrations', 'description': 'Connection to your blog, email provider, and social networks so everything planned on the calendar is published on the channels your audience already follows.'},
                    ],
                },
                {
                    'id': 'i18n_module',
                    'icon': '🌍',
                    'title': 'Multi-language & Regional Localization',
                    'is_visible': True,
                    'description': (
                        'Native internationalization system that serves your site '
                        'in multiple languages with an integrated translation workflow, '
                        'regional currency and date formats, and the ability to display '
                        'different catalogs or prices by country.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 15,
                    'items': [
                        {'icon': '🌐', 'name': 'Native Multi-language Support', 'description': 'Structure ready to serve all site content in two or more languages, with a visible language selector and user preference persistence.'},
                        {'icon': '💱', 'name': 'Regional Currency & Date Formats', 'description': 'Automatic adaptation of numeric formats, currencies, and dates based on the visitor\'s region or selected language.'},
                        {'icon': '🛒', 'name': 'Catalogs & Pricing by Country', 'description': 'Ability to display products, prices, and availability differentiated by geographic region or target market.'},
                        {'icon': '📝', 'name': 'Integrated Translation Workflow', 'description': 'Admin panel to manage translations for each section without technical intervention, with an indicator for content pending translation.'},
                        {'icon': '🔍', 'name': 'Automatic Language Detection', 'description': 'The site detects the visitor\'s preferred browser language and automatically redirects to the corresponding version, improving the experience from the first moment.'},
                    ],
                },
                {
                    'id': 'live_chat_module',
                    'icon': '💬',
                    'title': 'First-Party Live Chat',
                    'is_visible': True,
                    'description': (
                        'Real-time chat system fully hosted on the client\'s infrastructure '
                        '— no Intercom, Drift, or LiveChat — where agents respond '
                        'from the same admin panel. Data is 100% owned, with no growing '
                        'subscription costs or risk of the tool displaying competitor ads.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 40,
                    'items': [
                        {'icon': '🔌', 'name': 'Embedded Chat Widget', 'description': 'Floating component integrated into the website that allows the visitor to start a real-time conversation without leaving the page they are browsing.'},
                        {'icon': '🖥️', 'name': 'Agent Panel in Admin', 'description': 'Agents handle conversations directly from the site\'s admin panel, without needing external applications or additional accounts.'},
                        {'icon': '📡', 'name': 'Real-time Communication (WebSocket)', 'description': 'Instant bidirectional messages between visitor and agent via persistent connection, with no delays or page reloads needed.'},
                        {'icon': '🗄️', 'name': 'Owned Conversation History', 'description': 'All conversations are stored in the client\'s database, with search, date filters, and export. Data is 100% client-owned.'},
                        {'icon': '🤖', 'name': 'Configurable Auto-responses', 'description': 'Welcome messages, after-hours responses, and automated FAQs that keep support active even when no agents are available.'},
                        {'icon': '🔔', 'name': 'New Chat Notifications', 'description': 'Real-time alerts to the agent when a visitor starts a conversation or sends a new message, ensuring minimal response times.'},
                    ],
                },                {
                    'id': 'dark_mode_module',
                    'icon': '🌙',
                    'title': 'Dark & Light Mode',
                    'is_visible': True,
                    'description': (
                        'The system automatically switches between light and dark mode based on the '
                        'user\'s device preference, and remembers their choice. It reduces eye strain '
                        'and gives the platform a modern finish.'
                    ),
                    'is_calculator_module': True,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'items': [
                        {'icon': '🎨', 'name': 'Dual Color Palette', 'description': 'Design of two complete color systems (light and dark) with CSS variables that switch instantly, maintaining visual coherence in both modes.'},
                        {'icon': '⚙️', 'name': 'Automatic System Preference Detection', 'description': 'The site detects the user\'s OS theme preference (prefers-color-scheme) and applies the corresponding mode from the first visit.'},
                        {'icon': '💾', 'name': 'User Choice Persistence', 'description': 'The user\'s manual preference is stored and respected on future visits, taking precedence over the operating system configuration.'},
                        {'icon': '🔄', 'name': 'Smooth Mode Transition', 'description': 'Elegant and smooth animation when switching between light and dark mode, without flashes or visual jumps that interrupt the browsing experience.'},
                        {'icon': '🖼️', 'name': 'Image & Media Adaptation', 'description': 'Images, icons, and graphic elements automatically adjust to the active mode, optimizing contrast and readability in each context.'},
                    ],
                },
                {
                    'id': 'gift_cards_module',
                    'icon': '🎁',
                    'title': 'Gift Cards & Digital Vouchers',
                    'is_visible': False,
                    'description': (
                        'Create, sell, and redeem digital gift cards with configurable balance, '
                        'branded design, and a unique verifiable code at checkout. '
                        'Generate upfront revenue and capture new customers through '
                        'existing buyers.'
                    ),
                    'is_calculator_module': False,
                    'default_selected': False,
                    'selected': False,
                    'price_percent': 20,
                    'items': [
                        {'icon': '💳', 'name': 'Gift Card Creation & Sales', 'description': 'Customers can purchase digital gift cards with configurable balance directly from your website, with an integrated payment process.'},
                        {'icon': '✅', 'name': 'Checkout Redemption with Unique Code', 'description': 'Each gift card generates a unique verifiable code that the recipient can apply during checkout as a partial or full payment method.'},
                        {'icon': '📊', 'name': 'Balance & Transaction History', 'description': 'Both the buyer and recipient can check the available balance, transactions made, and expiration date for each card.'},
                        {'icon': '🎨', 'name': 'Custom Branded Design', 'description': 'Gift cards are generated with your brand\'s visual identity, including logo, colors, and a customizable message from the buyer to the recipient.'},
                        {'icon': '⏰', 'name': 'Configurable Expiration', 'description': 'Define expiration policies per card type: no expiration, 6 months, 1 year, or custom. Includes automatic notifications before expiration.'},
                    ],
                },

            ],
        },
    },
    {
        'section_type': 'development_stages',
        'title': '📌 Contracting & Development Stages',
        'order': 12,
        'is_wide_panel': True,
        'content_json': {
            'index': '11',
            'title': 'Contracting & Development Stages',
            'intro': 'Our process is designed to offer clarity, trust, and support at every stage 🧭:',
            'currentLabel': 'Current',
            'stages': [
                {
                    'icon': '✉️',
                    'title': 'Commercial Proposal',
                    'description': 'Formal presentation of the technical and economic proposal (current stage).',
                    'current': True,
                },
                {
                    'icon': '✍️',
                    'title': 'Contract Signing',
                    'description': 'Agreement on scope, timeline, and conditions.',
                },
                {
                    'icon': '🎨',
                    'title': 'Design & Creative Review',
                    'description': 'Custom visual design in Figma with reviews and adjustments.',
                },
                {
                    'icon': '📱',
                    'title': 'Native Development',
                    'description': 'Custom coding, payment gateway and email integration.',
                },
                {
                    'icon': '🚀',
                    'title': 'Launch & Deployment',
                    'description': 'QA, production deployment, and domain setup.',
                },
                {
                    'icon': '📦',
                    'title': 'Final Delivery',
                    'description': 'Site online and validated, closing the digital transformation cycle.',
                },
            ],
        },
    },
    {
        'section_type': 'process_methodology',
        'title': '⚙️ Process & Methodology',
        'order': 6,
        'is_wide_panel': False,
        'content_json': {
            'index': '5',
            'title': 'Process & Methodology',
            'intro': 'We work with a structured process that ensures transparency, quality, and on-time delivery at every stage.',
            'activeStep': 0,
            'steps': [
                {
                    'icon': '🔍',
                    'title': 'Discovery',
                    'description': 'We research your business, competitors, and users to define the ideal strategy.',
                    'clientAction': 'Your input: initial briefing',
                },
                {
                    'icon': '🎨',
                    'title': 'UX/UI Design',
                    'description': 'We create interactive prototypes in Figma with iterations until visual approval.',
                    'clientAction': 'Your input: design feedback',
                },
                {
                    'icon': '💻',
                    'title': 'Development',
                    'description': 'We implement with clean code, scalable architecture, and best practices.',
                    'clientAction': '',
                },
                {
                    'icon': '🧪',
                    'title': 'QA & Testing',
                    'description': 'Thorough testing of functionality, performance, security, and compatibility.',
                    'clientAction': 'Your input: acceptance testing',
                },
                {
                    'icon': '🚀',
                    'title': 'Launch',
                    'description': 'Production deployment, post-launch monitoring, and team training.',
                    'clientAction': '',
                },
            ],
        },
    },
    {
        'section_type': 'proposal_summary',
        'title': '📋 Proposal Summary',
        'order': 13,
        'is_wide_panel': False,
        'content_json': {
            'index': '12',
            'title': 'Proposal Summary',
            'subtitle': 'Key details of this proposal at a glance:',
            'kpis': [
                {'value': '+40%', 'label': 'Expected increase in web conversion', 'source': 'HubSpot 2024'},
                {'value': '3x', 'label': 'Estimated ROI within 12 months', 'source': 'Internal analysis'},
                {'value': '-60%', 'label': 'Reduction in manual management time', 'source': 'McKinsey Digital 2023'},
            ],
            '_kpi_note': (
                'KPIs are customizable per client. Include metrics relevant '
                'to the client\'s industry with verifiable sources. These will appear '
                'as highlighted cards at the top of the summary.'
            ),
            'cards': [
                {
                    'icon': '💰',
                    'title': 'Investment',
                    'description': 'Total project amount as per the economic proposal.',
                    'source': 'total_investment',
                },
                {
                    'icon': '⏱️',
                    'title': 'Estimated Time',
                    'description': 'Approximate project duration from kickoff to delivery.',
                    'source': 'timeline_duration',
                },
                {
                    'icon': '🛡️',
                    'title': 'Warranty',
                    'description': '1-year warranty included on the delivered development.',
                    'source': 'static',
                },
                {
                    'icon': '🧑‍💻',
                    'title': 'Support',
                    'description': 'Dedicated team for design, development, and post-launch support.',
                    'source': 'static',
                },
                {
                    # Mirrors CLAUSE 22 of the contract. The closing sentence is
                    # not optional: the contract ties these times to an active
                    # hosting and support subscription.
                    'icon': '🚨',
                    'title': 'Incident response',
                    'description': (
                        'Critical incident: 4 business-hour response, restored '
                        'within 1 business day. Medium: 1 and 5 business days. '
                        'Low: 3 and 9 business days. Includes continuous '
                        'monitoring, backups and a closure report. Applies while '
                        'the hosting and support service is active.'
                    ),
                    'source': 'static',
                },
                {
                    'icon': '📅',
                    'title': 'Validity',
                    'description': 'Proposal validity from the date it was sent.',
                    'source': 'expires_at',
                },
            ],
        },
    },
    {
        'section_type': 'final_note',
        'title': '📝 Final Note & Next Steps',
        'order': 14,
        'is_wide_panel': False,
        'content_json': {
            'index': '13',
            'title': 'Final Note & Next Steps',
            'message': (
                'We firmly believe this proposal represents an exceptional opportunity '
                'to transform your digital presence and achieve your business goals.'
            ),
            'personalNote': (
                'We are excited about the possibility of working with you and helping you '
                'take your business to the next level.'
            ),
            'teamName': 'The Project App Team',
            'teamRole': 'Your partner in digital transformation',
            'contactEmail': 'team@projectapp.co',
            'commitmentBadges': [
                {
                    'icon': '🤝',
                    'title': 'Total Commitment',
                    'description': 'Complete dedication to your project until exceptional results',
                },
                {
                    'icon': '💯',
                    'title': 'Quality Guarantee',
                    'description': 'Unlimited revisions until your complete satisfaction',
                },
                {
                    'icon': '🎯',
                    'title': 'Results-Focused',
                    'description': 'We measure our success by the impact on your business',
                },
            ],
            'validityMessage': (
                'This proposal is valid for a limited period from its send date. '
                'Prices and conditions may be subject to changes after this period.'
            ),
            'thankYouMessage': (
                'We sincerely appreciate the opportunity to present this proposal. '
                'We look forward to the possibility of working with you.'
            ),
        },
    },
    {
        'section_type': 'next_steps',
        'title': '✅ Closing & Next Steps',
        'order': 15,
        'is_wide_panel': False,
        'content_json': {
            'index': '14',
            'title': 'Closing & Next Steps',
            'introMessage': (
                'We are ready to start this journey together. '
                'Here is how to take the next step:'
            ),
            'steps': [
                {
                    'title': 'Review & Questions',
                    'description': 'Review the proposal and send us any questions or adjustments you need.',
                },
                {
                    'title': 'Confirmation Meeting',
                    'description': 'We schedule a call to align final details and sign the contract.',
                },
                {
                    'title': "Let's Begin!",
                    'description': 'We start the project with the kickoff meeting and begin the Discovery phase.',
                },
            ],
            'ctaMessage': (
                'Contact us today and let us start working on your project. '
                'We are just a message away.'
            ),
            'primaryCTA': {
                'text': 'Contact via WhatsApp',
                'link': 'https://wa.me/1234567890',
            },
            'secondaryCTA': {
                'text': 'Schedule Meeting',
                'link': 'https://calendly.com/projectapp',
            },
            'contactMethods': [
                {
                    'icon': '📧',
                    'title': 'Email',
                    'value': 'team@projectapp.co',
                    'link': 'mailto:team@projectapp.co',
                },
                {
                    'icon': '📱',
                    'title': 'WhatsApp',
                    'value': '+57 123 456 7890',
                    'link': 'https://wa.me/571234567890',
                },
                {
                    'icon': '🌐',
                    'title': 'Website',
                    'value': 'www.projectapp.co',
                    'link': 'https://projectapp.co',
                },
            ],
            'validityMessage': (
                'This proposal is valid for 30 days from the date of issue. '
                'Prices and conditions may be subject to change after this period.'
            ),
            'thankYouMessage': (
                'We sincerely appreciate the opportunity to present this proposal. '
                'We look forward to the possibility of working with you.'
            ),
        },
    },
    {
        'section_type': 'technical_document',
        'title': '🔧 Technical document',
        'order': 16,
        'is_wide_panel': True,
        'content_json': deepcopy(EMPTY_TECHNICAL_DOCUMENT_JSON),
    },
    {
        # PDF-only appendix: hour packages + scope-exclusion clause.
        'section_type': 'commercial_conditions',
        'title': '📑 Commercial conditions',
        'order': 17,
        'is_wide_panel': False,
        'content_json': {
            'index': '17',
            'title': 'Commercial conditions',
            'packagesTitle': 'Hour packages for follow-up requirements',
            'packagesIntro': (
                'For low or medium-low effort requirements after delivery, we offer hour '
                'banks at a preferential rate. The larger the package, the lower the cost per hour.'
            ),
            'hourlyRate': 30000,
            'currency': 'COP',
            'packages': [
                {'name': 'Single Hour', 'hours': 1, 'discountPercent': 0, 'note': 'For a quick one-off tweak.'},
                {'name': 'Agile Pack', 'hours': 20, 'discountPercent': 10, 'note': 'For short iterations.'},
                {'name': 'Pro Pack', 'hours': 60, 'discountPercent': 20, 'note': 'For continuous improvements.'},
                {'name': 'Premium Pack', 'hours': 180, 'discountPercent': 30, 'note': 'For sustained product evolution.'},
            ],
            'effortBadge': (
                'Any requirement of medium or higher effort is quoted as an independent requirement, '
                'outside these packages.'
            ),
            'scopeTitle': 'Scope of the approved work',
            'scopeParagraphs': [
                'The approved and quoted work corresponds solely to what is described within the scope '
                'of this commercial proposal and its technical detail. Any conversation, message, '
                'email, meeting, idea, resource, file, reference or request that arises **before or '
                'during** the project and is not explicitly described within that scope does not, by '
                'itself, constitute a commitment to implement it, nor is it part of the contracted work.',
                'This does not limit communication: we can talk and explore ideas freely. However, for '
                'a feature, change or deliverable to become part of the approved work, it must be '
                'documented and quoted as part of the scope, and formalized through an amendment to the '
                'contract or through an independent contract. This protects both parties: it avoids '
                'misunderstandings about what is included, keeps the '
                'project focused, and ensures every additional effort is planned and fairly paid.',
                'Consequently, the timelines, costs and warranties of this proposal apply only to the '
                'described scope. Anything beyond it will be handled via the hour packages above (for '
                'low or medium-low efforts) or as an independent quote (for medium or higher efforts).',
                'Carrying out any activity outside the scope does not modify it, does not create a right '
                'to demand similar work in the future, and does not waive anything stated here.',
            ],
        },
    },
]


CURRENT_HOSTING_TERM_STATUSES = frozenset({
    'draft', 'sent', 'viewed', 'negotiating', 'expired',
})


def proposal_uses_current_hosting_terms(proposal):
    """Whether a proposal must show the currently offered hosting terms."""
    return bool(
        getattr(proposal, 'is_active', False)
        and getattr(proposal, 'status', None) in CURRENT_HOSTING_TERM_STATUSES
    )


def normalize_hosting_plan(
    proposal, hosting_plan_json, *, force_current_terms=False,
):
    """Merge BusinessProposal model fields with content_json.hostingPlan.

    Model fields are the pricing source of truth for active proposals. Closed
    or inactive proposals keep their stored tier snapshot so historical terms
    remain unchanged in the public view and PDF. Operational consumers can
    request the currently offered terms when creating a new platform record.

    Pure function: no ORM queries, no side effects.
    """
    # Deferred import — avoids coupling content package load order to
    # accounts during app initialization.
    from accounts.models import HostingSubscription

    base = dict(hosting_plan_json or {})

    model_percent = getattr(proposal, 'hosting_percent', None)
    base['hostingPercent'] = (
        model_percent if model_percent else base.get('hostingPercent', 80)
    )

    lang = getattr(proposal, 'language', 'es') or 'es'

    # Free-month gift block. Resolved here — the one read-time hook shared by
    # the panel form, the public view and the PDF — so all three agree.
    #
    # ``freeMonthsVisible`` is the explicit gate. Content written before the
    # flag existed has no key, so it falls back to the old rule (a non-zero
    # count meant visible) and those proposals keep their current appearance.
    if 'freeMonthsVisible' not in base:
        base['freeMonthsVisible'] = _coerce_free_months(base.get('freeMonths')) > 0
    else:
        base['freeMonthsVisible'] = bool(base['freeMonthsVisible'])
    if not str(base.get('freeMonthNote') or '').strip():
        base['freeMonthNote'] = default_free_month_note(lang)

    if (not force_current_terms
            and not proposal_uses_current_hosting_terms(proposal)):
        if not base.get('billingTiers'):
            base['billingTiers'] = [
                {
                    'frequency': 'annual',
                    'months': 12,
                    'discountPercent': getattr(
                        proposal, 'hosting_discount_nine_month', 40,
                    ),
                    'label': 'Annual' if lang == 'en' else 'Anual',
                    'badge': 'Best value' if lang == 'en' else 'Máximo descuento',
                },
                {
                    'frequency': 'semiannual',
                    'months': 6,
                    'discountPercent': getattr(
                        proposal, 'hosting_discount_semiannual', 20,
                    ),
                    'label': 'Semiannual' if lang == 'en' else 'Semestral',
                    'badge': '20% off' if lang == 'en' else '20% dcto',
                },
                {
                    'frequency': 'quarterly',
                    'months': 3,
                    'discountPercent': getattr(
                        proposal, 'hosting_discount_quarterly', 10,
                    ),
                    'label': 'Quarterly' if lang == 'en' else 'Trimestral',
                    'badge': '10% off' if lang == 'en' else '10% dcto',
                },
            ]
        return base

    discount_overrides = {
        HostingSubscription.PLAN_NINE_MONTH:
            getattr(proposal, 'hosting_discount_nine_month', None),
        HostingSubscription.PLAN_SEMIANNUAL:
            getattr(proposal, 'hosting_discount_semiannual', None),
        HostingSubscription.PLAN_QUARTERLY:
            getattr(proposal, 'hosting_discount_quarterly', None),
    }

    # Enforce the canonical offered set, best discount first. An annual tier in
    # stale JSON is treated as presentation data for the new nine-month tier.
    stored_by_freq = {
        t.get('frequency'): t
        for t in (base.get('billingTiers') or [])
        if isinstance(t, dict)
    }
    if ('annual' in stored_by_freq
            and HostingSubscription.PLAN_NINE_MONTH not in stored_by_freq):
        stored_by_freq[HostingSubscription.PLAN_NINE_MONTH] = stored_by_freq['annual']
    tier_defaults = {
        HostingSubscription.PLAN_NINE_MONTH: {
            'months': 9,
            'label': 'Every 9 months' if lang == 'en' else 'Cada 9 meses',
            'badge': 'Best value' if lang == 'en' else 'Máximo descuento',
            'discount': 40,
        },
        HostingSubscription.PLAN_SEMIANNUAL: {
            'months': 6,
            'label': 'Semiannual' if lang == 'en' else 'Semestral',
            'badge': '20% off' if lang == 'en' else '20% dcto',
            'discount': 20,
        },
        HostingSubscription.PLAN_QUARTERLY: {
            'months': 3,
            'label': 'Quarterly' if lang == 'en' else 'Trimestral',
            'badge': '10% off' if lang == 'en' else '10% dcto',
            'discount': 10,
        },
    }
    normalized_tiers = []
    for freq in (HostingSubscription.PLAN_NINE_MONTH,
                 HostingSubscription.PLAN_SEMIANNUAL,
                 HostingSubscription.PLAN_QUARTERLY):
        defaults = tier_defaults[freq]
        stored = stored_by_freq.get(freq) or {}
        override = discount_overrides.get(freq)
        if override is not None:
            discount = override
        elif stored.get('discountPercent') is not None:
            discount = stored.get('discountPercent')
        else:
            discount = defaults['discount']
        normalized_tiers.append({
            'frequency': freq,
            'months': defaults['months'],
            'label': defaults['label'],
            'badge': stored.get('badge', defaults['badge']),
            'discountPercent': discount,
        })
    base['billingTiers'] = normalized_tiers
    return base


CALC_MODULE_PREFIX = 'module-'
REGULAR_GROUP_PREFIX = 'group-'


def normalize_selected_module_ids(selected, fr_content_json):
    """Return *selected* with canonical prefixed ids.

    Calculator modules round-trip through the frontend as ``module-<id>``
    and regular groups as ``group-<id>``. Older payloads, template copies,
    or manual JSON edits can ship bare group ids, which break equality
    checks in the PDF renderer and in the frontend calculator. Using the
    functional_requirements content as the source of truth for which
    groups are calculator modules, rebuild each id into its canonical
    prefixed form.

    Pure function: no ORM queries, no side effects.
    """
    if not isinstance(selected, list):
        return []

    calc_group_ids = set()
    regular_group_ids = set()
    if isinstance(fr_content_json, dict):
        for arr_key in ('groups', 'additionalModules'):
            for grp in (fr_content_json.get(arr_key) or []):
                if not isinstance(grp, dict):
                    continue
                gid = str(grp.get('id') or '').strip()
                if not gid:
                    continue
                if grp.get('is_calculator_module'):
                    calc_group_ids.add(gid)
                else:
                    regular_group_ids.add(gid)

    normalized = []
    seen = set()
    for raw in selected:
        if raw in (None, ''):
            continue
        mod_id = str(raw).strip()
        if not mod_id:
            continue
        if mod_id.startswith((CALC_MODULE_PREFIX, REGULAR_GROUP_PREFIX)):
            canonical = mod_id
        elif mod_id in calc_group_ids:
            canonical = f'{CALC_MODULE_PREFIX}{mod_id}'
        elif mod_id in regular_group_ids:
            canonical = f'{REGULAR_GROUP_PREFIX}{mod_id}'
        else:
            # Unknown bare id — keep as-is rather than dropping, so the
            # admin does not silently lose data they may recognize.
            canonical = mod_id
        if canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


def admin_default_calculator_group_ids(fr_content_json):
    """Return the bare ids of the visible calculator modules the admin marked
    as selected in the FR content JSON.

    ``selected`` is the source of truth (the "Seleccionado" checkbox in the
    admin panel): a calculator module (``is_calculator_module=True``) counts
    as an admin default when ``selected`` is truthy. ``default_selected`` only
    acts as a fallback when the module carries no explicit ``selected`` value
    (legacy data / old JSON imports) — an explicit ``selected=False`` wins
    over ``default_selected=True``. Hidden modules (``is_visible=False``) are
    excluded. Returns a set of bare ids (no ``module-`` prefix).

    Pure function: no ORM queries, no side effects.
    """
    ids = set()
    if not isinstance(fr_content_json, dict):
        return ids
    for arr_key in ('groups', 'additionalModules'):
        for group in (fr_content_json.get(arr_key) or []):
            if not isinstance(group, dict):
                continue
            if not group.get('is_calculator_module'):
                continue
            if group.get('is_visible') is False:
                continue
            sel = group.get('selected')
            if sel is None:
                sel = group.get('default_selected')
            if not sel:
                continue
            gid = str(group.get('id') or '').strip()
            if gid:
                ids.add(gid)
    return ids


def admin_pinned_calculator_group_ids(fr_content_json):
    """Bare ids of visible calculator modules the admin pinned explicitly
    (``selected is True``).

    Unlike :func:`admin_default_calculator_group_ids` (which also counts
    ``default_selected``), pinned modules are forced into a client's selection
    even when the client already confirmed a different one — "I checked it in
    the panel, so the client sees it selected". Hidden modules
    (``is_visible=False``) are excluded.

    Pure function: no ORM queries, no side effects.
    """
    ids = set()
    if not isinstance(fr_content_json, dict):
        return ids
    for arr_key in ('groups', 'additionalModules'):
        for group in (fr_content_json.get(arr_key) or []):
            if not isinstance(group, dict):
                continue
            if not group.get('is_calculator_module'):
                continue
            if group.get('is_visible') is False:
                continue
            if group.get('selected') is not True:
                continue
            gid = str(group.get('id') or '').strip()
            if gid:
                ids.add(gid)
    return ids


class ProposalService:
    """
    Business logic for proposal lifecycle management.
    """
    DEFAULT_EXPIRATION_DAYS = 21

    @staticmethod
    def open_notifications_suppressed(proposal):
        """Whether "client opened the proposal" notifications should be skipped.

        We don't notify on opens once the proposal is in a closed/won state:
        accepted or finished. At that point the open-tracking signal no longer
        helps the sales team and only produces noise (e.g. the owner revisiting
        an old, already-accepted proposal).
        """
        from content.models import BusinessProposal
        return proposal.status in (
            BusinessProposal.Status.ACCEPTED,
            BusinessProposal.Status.FINISHED,
        )

    @staticmethod
    def _require_valid_client_email(proposal):
        """Raise ProposalActionError if proposal lacks a deliverable client_email."""
        from content.api_errors import ProposalActionError
        if not proposal.client_email:
            raise ProposalActionError(
                'Falta el correo del cliente.',
                code='missing_client_email',
                hint='Agrega el correo del cliente en la propuesta y vuelve a intentar.',
            )
        from content.utils import validate_email_domain_mx
        if not validate_email_domain_mx(proposal.client_email):
            raise ProposalActionError(
                'El dominio del correo del cliente no puede recibir emails.',
                code='invalid_client_email_domain',
                hint='Verifica que el correo del cliente esté bien escrito.',
            )

    @staticmethod
    def _normalize_required_email_intro(value):
        """Return normalized proposal-specific copy or raise an actionable error."""
        from content.api_errors import ProposalActionError

        if not isinstance(value, str) or not value.strip():
            raise ProposalActionError(
                'Falta el mensaje personalizado del correo.',
                code='missing_email_intro',
                hint=(
                    'Escribe en la pestaña Correos qué resuelve esta propuesta '
                    'para el cliente y vuelve a intentar.'
                ),
            )
        return value.strip()

    @staticmethod
    def _require_email_intro(proposal):
        """Require the proposal-specific message used by the initial email."""
        return ProposalService._normalize_required_email_intro(
            getattr(proposal, 'email_intro', ''),
        )

    @staticmethod
    def get_default_expiration_days(language='es'):
        """
        Return the configured default expiration period (in days) for a language.

        Falls back to 21 days when no DB config exists.
        """
        from content.models import ProposalDefaultConfig

        config = ProposalDefaultConfig.objects.filter(language=language).first()
        if config and config.expiration_days:
            return int(config.expiration_days)
        return ProposalService.DEFAULT_EXPIRATION_DAYS

    @staticmethod
    def compute_default_expires_at(language='es'):
        """Return a timezone-aware datetime for the default expiration."""
        from django.utils import timezone
        from datetime import timedelta

        return timezone.now() + timedelta(
            days=ProposalService.get_default_expiration_days(language),
        )

    _MONTHS_ES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre',
                  'diciembre')

    @staticmethod
    def compute_validity_text(proposal):
        """Return the client-facing validity sentence for *proposal*.

        Single source of truth shared by the PDF (_render_final_note) and
        the proposal serializer (public web view), so the two surfaces can
        never drift. States the total window from the send date (or issue
        date for unsent drafts) to ``expires_at`` plus the absolute
        deadline — never a countdown. Returns None without an expiry date.
        """
        from django.utils import timezone

        expires_at = getattr(proposal, 'expires_at', None)
        if not expires_at:
            return None
        lang = 'en' if getattr(proposal, 'language', 'es') == 'en' else 'es'
        expiry_local = timezone.localtime(expires_at)
        sent_at = getattr(proposal, 'sent_at', None)
        ref = sent_at or getattr(proposal, 'created_at', None)
        n_days = ((expiry_local.date() - timezone.localtime(ref).date()).days
                  if ref else 0)
        if lang == 'en':
            expiry_txt = (f'{expiry_local.strftime("%B")} '
                          f'{expiry_local.day}, {expiry_local.year}')
            if n_days <= 0:
                return f'This proposal is valid until {expiry_txt}.'
            unit = 'calendar day' if n_days == 1 else 'calendar days'
            since = 'its send date' if sent_at else 'its issue date'
            return (f'This proposal is valid for {n_days} {unit} '
                    f'from {since} (valid until {expiry_txt}).')
        month = ProposalService._MONTHS_ES[expiry_local.month - 1]
        expiry_txt = f'{expiry_local.day} de {month} de {expiry_local.year}'
        if n_days <= 0:
            return f'Esta propuesta es válida hasta el {expiry_txt}.'
        unit = 'día calendario' if n_days == 1 else 'días calendario'
        since = 'su fecha de envío' if sent_at else 'su fecha de emisión'
        return (f'Esta propuesta tiene una vigencia de {n_days} {unit} '
                f'a partir de {since} (válida hasta el {expiry_txt}).')

    # Hosting fields whose creation defaults are admin-editable in
    # ProposalDefaultConfig. Shared by the panel form and the JSON/MCP
    # creation paths so a payload that omits them gets the configured
    # value instead of the model default.
    HOSTING_CONFIG_FIELDS = (
        'hosting_percent',
        'hosting_discount_nine_month',
        'hosting_discount_semiannual',
        'hosting_discount_quarterly',
    )

    @staticmethod
    def apply_hosting_defaults(proposal, provided_fields):
        """Fill hosting fields from ProposalDefaultConfig when not provided.

        ``provided_fields`` is the set of keys present in the creation
        payload; only absent fields are overwritten. No-op when no config
        row exists for the proposal's language.
        """
        from content.models import ProposalDefaultConfig

        config = ProposalDefaultConfig.objects.filter(
            language=proposal.language,
        ).first()
        if not config:
            return
        updates = [
            field for field in ProposalService.HOSTING_CONFIG_FIELDS
            if field not in provided_fields
            and getattr(config, field, None) is not None
        ]
        if not updates:
            return
        for field in updates:
            setattr(proposal, field, getattr(config, field))
        proposal.save(update_fields=updates)

    @staticmethod
    def send_proposal(proposal, *, acting_user=None):
        """
        Mark proposal as sent and schedule the Huey reminder tasks.

        Sets status=SENT, sent_at=now(), auto-sets expires_at using the
        configured default expiration days (21 by default) if not already
        set, and schedules reminder (day 10) and urgency
        (day 15) emails.

        Args:
            proposal: BusinessProposal instance.

        Returns:
            dict: Email delivery result from ``_send_initial_email``.

        Raises:
            ValueError: If client_email or the personalized message is not set.
        """
        ProposalService._require_valid_client_email(proposal)
        ProposalService._require_email_intro(proposal)

        from content.services.proposal_snapshot_service import (
            finalize_proposal_snapshots,
            prepare_proposal_snapshots,
        )

        prepared = prepare_proposal_snapshots(
            [proposal], acting_user=acting_user,
        )

        now = timezone.now()
        proposal.status = 'sent'
        proposal.sent_at = now
        update_fields = ['status', 'sent_at']

        if not proposal.expires_at:
            proposal.expires_at = now + timedelta(
                days=ProposalService.get_default_expiration_days(proposal.language),
            )
            update_fields.append('expires_at')

        proposal.save(update_fields=update_fields)

        delivery = ProposalService._send_initial_email(
            proposal, snapshot=prepared[0],
        )
        finalize_proposal_snapshots(
            prepared, delivery, acting_user=acting_user,
        )
        ProposalService._schedule_email_tasks(proposal)
        return delivery

    @staticmethod
    def resend_proposal(proposal, *, acting_user=None, email_intro=None):
        """
        Re-send a proposal keeping the existing expires_at.

        Resets sent_at, status, reminder_sent_at, urgency_email_sent_at
        and re-schedules email tasks based on remaining time.

        Args:
            proposal: BusinessProposal instance.

        Returns:
            dict: Email delivery result from ``_send_initial_email``.

        Raises:
            ValueError: If client_email or the personalized message is not set.
        """
        ProposalService._require_valid_client_email(proposal)

        if email_intro is not None:
            # A resend must never erase the last usable message merely because
            # the submitted replacement is blank. Draft editing may persist an
            # empty value through the regular update API, but this action is
            # all-or-nothing: validate before writing.
            normalized_intro = ProposalService._normalize_required_email_intro(
                email_intro,
            )
            if normalized_intro != proposal.email_intro:
                from content.services.proposal_audit import log_proposal_change

                old_intro = proposal.email_intro
                proposal.email_intro = normalized_intro
                proposal.save(update_fields=['email_intro'])
                log_proposal_change(
                    proposal,
                    change_type='updated',
                    field_name='email_intro',
                    old_value=old_intro,
                    new_value=normalized_intro,
                    actor_type='seller',
                    description='Mensaje personalizado actualizado antes del reenvío.',
                )

        ProposalService._require_email_intro(proposal)

        from content.services.proposal_snapshot_service import (
            finalize_proposal_snapshots,
            prepare_proposal_snapshots,
        )

        prepared = prepare_proposal_snapshots(
            [proposal], acting_user=acting_user,
        )

        now = timezone.now()
        proposal.status = 'sent'
        proposal.sent_at = now
        proposal.reminder_sent_at = None
        proposal.urgency_email_sent_at = None
        proposal.save(update_fields=[
            'status', 'sent_at', 'reminder_sent_at', 'urgency_email_sent_at',
        ])

        delivery = ProposalService._send_initial_email(
            proposal, snapshot=prepared[0],
        )
        finalize_proposal_snapshots(
            prepared, delivery, acting_user=acting_user,
        )
        ProposalService._schedule_email_tasks(proposal)
        return delivery

    @staticmethod
    def _send_initial_email(proposal, snapshot=None):
        """
        Send the proposal link email to the client.

        Unexpected errors are swallowed (logged + reported as
        ``unexpected_error``) so the status change is not rolled back.
        """
        from content.services.proposal_email_service import (
            ProposalEmailService,
            _delivery,
            GENERIC_SEND_FAILURE_DETAIL,
        )
        try:
            return ProposalEmailService.send_proposal_to_client(
                proposal, snapshot=snapshot,
            )
        except Exception as exc:
            logger.exception(
                'Failed to send initial email for proposal %s',
                proposal.uuid,
            )
            return _delivery(False, 'unexpected_error', GENERIC_SEND_FAILURE_DETAIL)

    @staticmethod
    def _schedule_email_tasks(proposal):
        """
        Schedule reminder (day N) and urgency (day M) Huey tasks.

        Skips scheduling if the target day has already passed or if
        it would fire after the proposal's expiration date.
        """
        try:
            from content.tasks import send_proposal_reminder, send_urgency_reminder

            now = timezone.now()
            expires = proposal.expires_at

            # Schedule reminder at reminder_days (default 10)
            reminder_target = proposal.sent_at + timedelta(days=proposal.reminder_days)
            if reminder_target > now and (not expires or reminder_target < expires):
                delay_seconds = int((reminder_target - now).total_seconds())
                send_proposal_reminder.schedule(
                    args=(proposal.id,), delay=delay_seconds
                )
                logger.info(
                    'Scheduled reminder for proposal %s in %d days',
                    proposal.uuid, proposal.reminder_days,
                )

            # Schedule urgency at urgency_reminder_days (default 15)
            urgency_target = proposal.sent_at + timedelta(
                days=proposal.urgency_reminder_days
            )
            if urgency_target > now and (not expires or urgency_target < expires):
                delay_seconds = int((urgency_target - now).total_seconds())
                send_urgency_reminder.schedule(
                    args=(proposal.id,), delay=delay_seconds
                )
                logger.info(
                    'Scheduled urgency reminder for proposal %s in %d days',
                    proposal.uuid, proposal.urgency_reminder_days,
                )
        except Exception:
            logger.exception(
                'Failed to schedule email tasks for proposal %s', proposal.uuid
            )

    @staticmethod
    def record_view(proposal):
        """
        Record a client viewing the proposal.

        Increments view_count, sets first_viewed_at on first visit,
        updates status to VIEWED if currently SENT.
        """
        proposal.view_count += 1
        update_fields = ['view_count']

        if proposal.first_viewed_at is None:
            proposal.first_viewed_at = timezone.now()
            update_fields.append('first_viewed_at')

        if proposal.status == 'sent':
            proposal.status = 'viewed'
            update_fields.append('status')

        proposal.save(update_fields=update_fields)

    @staticmethod
    def check_expiration(proposal):
        """
        Check if a proposal is expired.

        Returns:
            bool: True if expired.
        """
        return proposal.is_expired

    @staticmethod
    def send_multi_proposals(proposals, *, acting_user=None):
        """Send a single email referencing several proposals from the same client.

        Side effects per proposal (mirrors send/resend single):
        - draft → sent + sent_at=now + expires_at if missing + schedule reminders
        - status='expired' OR expires_at past → bumps expires_at to now+default,
          status reverts to sent (or viewed if view_count > 0), reschedules.
        - sent / viewed / negotiating → re-send (resets reminder/urgency timestamps,
          reschedules) without changing status.

        Args:
            proposals: ordered list of ``BusinessProposal`` from the same client.

        Returns:
            dict: Email delivery result merged with ``transitions`` map
                  ``{proposal_id: 'sent' | 'resent' | 'reopened'}``.

        Raises:
            ValueError: If client_email is not set on the primary proposal,
                        proposals span multiple clients, or any personalized
                        message is blank.
        """
        from content.models import BusinessProposal
        from content.api_errors import ProposalActionError

        if not proposals:
            raise ProposalActionError(
                'No se proporcionaron propuestas para el envío conjunto.',
                code='no_proposals',
            )

        primary = proposals[0]
        ProposalService._require_valid_client_email(primary)

        client_id = primary.client_id
        if any(p.client_id != client_id for p in proposals):
            raise ProposalActionError(
                'Todas las propuestas deben pertenecer al mismo cliente.',
                code='multiple_clients',
            )

        for proposal in proposals:
            ProposalService._require_email_intro(proposal)

        from content.services.proposal_snapshot_service import (
            finalize_proposal_snapshots,
            prepare_proposal_snapshots,
        )

        prepared = prepare_proposal_snapshots(
            proposals, acting_user=acting_user,
        )

        Status = BusinessProposal.Status
        now = timezone.now()
        transitions = {}

        for proposal in proposals:
            old_status = proposal.status
            update_fields = []

            expires_past = (
                proposal.expires_at is not None and proposal.expires_at <= now
            )
            if old_status == Status.DRAFT:
                proposal.status = Status.SENT
                proposal.sent_at = now
                update_fields += ['status', 'sent_at']
                if not proposal.expires_at:
                    proposal.expires_at = now + timedelta(
                        days=ProposalService.get_default_expiration_days(proposal.language),
                    )
                    update_fields.append('expires_at')
                transitions[proposal.id] = 'sent'

            elif old_status == Status.EXPIRED or expires_past:
                proposal.expires_at = now + timedelta(
                    days=ProposalService.get_default_expiration_days(proposal.language),
                )
                proposal.status = (
                    Status.VIEWED if proposal.view_count > 0 else Status.SENT
                )
                proposal.sent_at = now
                proposal.reminder_sent_at = None
                proposal.urgency_email_sent_at = None
                update_fields += [
                    'status', 'sent_at', 'expires_at',
                    'reminder_sent_at', 'urgency_email_sent_at',
                ]
                transitions[proposal.id] = 'reopened'

            else:
                proposal.sent_at = now
                proposal.reminder_sent_at = None
                proposal.urgency_email_sent_at = None
                update_fields += [
                    'sent_at', 'reminder_sent_at', 'urgency_email_sent_at',
                ]
                transitions[proposal.id] = 'resent'

            if update_fields:
                proposal.save(update_fields=update_fields)

        from content.services.proposal_email_service import (
            ProposalEmailService,
            _delivery,
        )

        try:
            delivery = ProposalEmailService.send_multi_proposal_to_client(
                proposals, snapshots=prepared,
            )
        except Exception as exc:
            logger.exception(
                'Failed to send multi-proposal email for client %s', client_id,
            )
            delivery = _delivery(False, 'unexpected_error', str(exc)[:500])

        finalize_proposal_snapshots(
            prepared, delivery, acting_user=acting_user,
        )

        for proposal in proposals:
            ProposalService._schedule_email_tasks(proposal)

        return {**delivery, 'transitions': transitions}

    @staticmethod
    def reopen_if_unexpired(proposal, *, old_status):
        """
        Revert ``status`` from ``expired`` when ``expires_at`` is now in the future.

        Mirrors the system rule that only ``sent`` / ``viewed`` proposals get
        marked ``expired`` (see ``expire_stale_proposals`` task). When un-expiring,
        we revert to ``viewed`` if the client has visited the proposal at least
        once (``view_count > 0``), otherwise to ``sent``.

        Mutates ``proposal.status`` in memory only; the caller persists and logs.

        Args:
            proposal: BusinessProposal instance with the new expires_at already applied.
            old_status: Status before the update.

        Returns:
            str | None: The new status if changed, else None.
        """
        from content.models import BusinessProposal

        if old_status != BusinessProposal.Status.EXPIRED:
            return None
        if not proposal.expires_at or proposal.expires_at <= timezone.now():
            return None

        new_status = (
            BusinessProposal.Status.VIEWED
            if proposal.view_count > 0
            else BusinessProposal.Status.SENT
        )
        proposal.status = new_status
        return new_status

    @staticmethod
    def get_hardcoded_defaults(language='es'):
        """
        Return a deep copy of the hardcoded default sections (no DB lookup).

        Args:
            language: 'es' for Spanish (default), 'en' for English.

        Returns:
            list[dict]: Deep copy of DEFAULT_SECTIONS or DEFAULT_SECTIONS_EN.
        """
        return ProposalService._hardcoded_with_item_ids(language)

    # Hardcoded defaults are module constants — annotate their item ids once
    # per language instead of re-slugging on every call.
    _HARDCODED_WITH_IDS_CACHE = {}

    @staticmethod
    def _hardcoded_with_item_ids(language):
        import copy
        cache = ProposalService._HARDCODED_WITH_IDS_CACHE
        if language not in cache:
            source = DEFAULT_SECTIONS_EN if language == 'en' else DEFAULT_SECTIONS
            cache[language] = ProposalService._with_item_ids(copy.deepcopy(source))
        return copy.deepcopy(cache[language])

    @staticmethod
    def _with_item_ids(sections):
        """Assign stable item ids to the functional_requirements section in place."""
        from content.services.proposal_module_links import (
            ensure_functional_requirements_item_ids,
        )
        for section in sections:
            if section.get('section_type') == 'functional_requirements':
                section['content_json'] = ensure_functional_requirements_item_ids(
                    section.get('content_json')
                )
        return sections

    @staticmethod
    def get_default_sections(language='es'):
        """
        Return the default section configurations for a new proposal.

        Checks the DB-backed ProposalDefaultConfig first; falls back to
        the hardcoded DEFAULT_SECTIONS / DEFAULT_SECTIONS_EN.

        Args:
            language: 'es' for Spanish (default), 'en' for English.

        Returns:
            list[dict]: List of section configs with section_type, title, order,
                        is_wide_panel, and content_json.
        """
        import copy
        from content.models import ProposalDefaultConfig

        config = ProposalDefaultConfig.objects.filter(language=language).first()
        if config and config.sections_json:
            return ProposalService._with_item_ids(copy.deepcopy(config.sections_json))

        return ProposalService._hardcoded_with_item_ids(language)

    @staticmethod
    def get_default_section(language, section_type):
        """Return the default config for a single section_type, or None."""
        for cfg in ProposalService.get_default_sections(language=language):
            if cfg['section_type'] == section_type:
                return cfg
        return None


# ---------------------------------------------------------------------------
# From-JSON create/update (shared by the panel views and the MCP connector)
#
# These hold the section-merge logic that protects default functional-
# requirements groups/modules, stamps item ids and normalizes technical-doc
# links — behavior that is load-bearing for the PDF pipeline. Both the panel
# `*_from_json` views and the proposals MCP call these so the rules never drift.
# They operate purely on validated data (no request); callers serialize the
# result themselves.
# ---------------------------------------------------------------------------

@transaction.atomic
def build_proposal_from_json(validated_data):
    """Create a BusinessProposal + its sections from validated from-JSON data.

    Runs atomically: the proposal, its client profile snapshot and all
    sections are committed together or not at all (no email/side effects
    happen inside this function).

    ``validated_data`` is the output of ProposalFromJSONSerializer (it still
    contains ``sections`` and, optionally, a resolved ``client``). Returns
    ``(proposal, unmapped_keys)``.
    """
    import copy

    from accounts.services import proposal_client_service
    from content.models import BusinessProposal, ProposalSection
    from content.serializers.proposal import SECTION_KEY_MAP, SECTION_TYPE_TO_KEY
    from content.services.module_requirements_catalog import (
        seed_module_technical_requirements,
    )
    from content.services.proposal_module_links import (
        ensure_functional_requirements_item_ids,
        normalize_technical_document_module_links,
    )

    data = dict(validated_data)
    sections_data = data.pop('sections')
    explicit_client = data.pop('client', None)

    expires_at = data.get('expires_at')
    if not expires_at:
        expires_at = ProposalService.compute_default_expires_at(
            data.get('language', 'es'),
        )

    if explicit_client is not None:
        client_profile = explicit_client
    else:
        client_profile = proposal_client_service.get_or_create_client_for_proposal(
            name=data.get('client_name', ''),
            email=data.get('client_email', ''),
            phone=data.get('client_phone', ''),
            company=data.get('client_company', ''),
        )

    proposal = BusinessProposal.objects.create(
        title=data['title'],
        client_name=data['client_name'],
        client_email=data.get('client_email', ''),
        client_phone=data.get('client_phone', ''),
        project_type=data.get('project_type', ''),
        project_type_custom=data.get('project_type_custom', ''),
        market_type=data.get('market_type', ''),
        market_type_custom=data.get('market_type_custom', ''),
        language=data.get('language', 'es'),
        total_investment=data.get('total_investment', 0),
        currency=data.get('currency', 'COP'),
        nationality=data.get('nationality', 'COL'),
        expires_at=expires_at,
        reminder_days=data.get('reminder_days', 10),
        urgency_reminder_days=data.get('urgency_reminder_days', 15),
        discount_percent=data.get('discount_percent', 0),
        show_contract_terms=data.get('show_contract_terms', True),
        email_intro=data.get('email_intro', ''),
        client=client_profile,
    )
    proposal_client_service.sync_snapshot(proposal)
    # Hosting defaults are admin-editable; explicit payload values win.
    ProposalService.apply_hosting_defaults(proposal, set(data))

    default_sections = ProposalService.get_default_sections(proposal.language)
    resolved_sections = []

    for section_cfg in default_sections:
        section_type = section_cfg['section_type']
        json_key = SECTION_TYPE_TO_KEY.get(section_type)

        if json_key and json_key in sections_data:
            content_json = copy.deepcopy(sections_data[json_key])
        else:
            content_json = copy.deepcopy(section_cfg['content_json'])
            if section_type == 'commercial_conditions':
                # No explicit payload for this section: seed it from the
                # hour-package catalog (falls back to defaults when empty).
                from content.services.hour_package_service import (
                    seed_commercial_conditions_from_catalog,
                )
                content_json = seed_commercial_conditions_from_catalog(
                    content_json,
                    nationality=proposal.nationality,
                    language=proposal.language,
                )

        if section_type == 'greeting':
            general = sections_data.get('general', {})
            content_json.setdefault('proposalTitle', proposal.title)
            content_json.setdefault('clientName', proposal.client_name)
            if general.get('inspirationalQuote'):
                content_json['inspirationalQuote'] = general['inspirationalQuote']

        if section_type == 'value_added_modules' and json_key in sections_data:
            # The payload replaces content_json wholesale; without this the
            # legal terms would be dropped on every JSON/MCP import.
            content_json = merge_value_added_legal_terms(
                content_json, section_cfg['content_json'],
            )

        if section_type == 'commercial_conditions' and json_key in sections_data:
            # Same hazard, opposite direction: the payload does carry the scope
            # clause, and a stale snapshot would reinject an outdated one.
            content_json = enforce_scope_clause(
                content_json, section_cfg['content_json'],
            )

        if section_type == 'functional_requirements' and json_key in sections_data:
            default_cj = copy.deepcopy(section_cfg['content_json'])
            default_groups = default_cj.get('groups', [])
            default_modules = default_cj.get('additionalModules', [])
            json_groups = content_json.get('groups', [])
            json_modules = content_json.get('additionalModules', [])

            json_groups_by_id = {
                g['id']: g for g in json_groups if isinstance(g, dict) and g.get('id')
            }
            json_modules_by_id = {
                m['id']: m for m in json_modules if isinstance(m, dict) and m.get('id')
            }

            merged_groups = []
            for dg in default_groups:
                gid = dg.get('id')
                if gid and gid in json_groups_by_id:
                    merged = json_groups_by_id.pop(gid)
                    merged['id'] = gid
                    merged.setdefault('is_visible', dg.get('is_visible', True))
                    merged_groups.append(merged)
                else:
                    merged_groups.append(dg)
            for gid, g in json_groups_by_id.items():
                merged_groups.append(g)

            merged_modules = []
            for dm in default_modules:
                mid = dm.get('id')
                if mid and mid in json_modules_by_id:
                    merged = json_modules_by_id.pop(mid)
                    merged['id'] = mid
                    merged.setdefault('is_visible', dm.get('is_visible', True))
                    merged_modules.append(merged)
                else:
                    merged_modules.append(dm)
            for mid, m in json_modules_by_id.items():
                merged_modules.append(m)

            content_json['groups'] = merged_groups
            content_json['additionalModules'] = merged_modules

            final_groups = []
            existing_mod_ids = {m.get('id') for m in content_json['additionalModules']}
            for g in content_json['groups']:
                if g.get('is_calculator_module'):
                    if g.get('id') not in existing_mod_ids:
                        content_json['additionalModules'].append(g)
                else:
                    final_groups.append(g)
            content_json['groups'] = final_groups

        if section_type == 'functional_requirements':
            content_json = ensure_functional_requirements_item_ids(content_json)

        resolved_sections.append({
            'section_type': section_type,
            'title': section_cfg['title'],
            'order': section_cfg['order'],
            'is_wide_panel': section_cfg.get('is_wide_panel', False),
            'content_json': content_json,
        })

    technical_section = next(
        (
            section
            for section in resolved_sections
            if section['section_type'] == ProposalSection.SectionType.TECHNICAL_DOCUMENT
        ),
        None,
    )
    if technical_section:
        technical_section['content_json'] = seed_module_technical_requirements(
            technical_section['content_json'],
            resolved_sections,
            language=proposal.language,
        )
        technical_section['content_json'] = normalize_technical_document_module_links(
            technical_section['content_json'],
            resolved_sections,
        )
        # Creation is deliberately NOT gated for item coverage: the functional
        # requirements resolved above are the payload MERGED with the language
        # template, so the required set includes items the caller never
        # authored and could not link. The technical document is authored
        # through updates, and apply_proposal_json_update gates those.

    for section in resolved_sections:
        ProposalSection.objects.create(proposal=proposal, **section)

    known_keys = set(SECTION_KEY_MAP.keys()) | {'_meta', '_seller_prompt'}
    provided_keys = set(sections_data.keys())
    unmapped_keys = sorted(provided_keys - known_keys)
    return proposal, unmapped_keys


@transaction.atomic
def _default_commercial_conditions(language):
    """Resolve the commercial_conditions defaults for a language.

    Reads through ``get_default_sections`` so an admin-edited clause stored in
    ``ProposalDefaultConfig`` wins over the hardcoded constants.
    """
    for section_cfg in ProposalService.get_default_sections(language):
        if section_cfg.get('section_type') == 'commercial_conditions':
            return section_cfg.get('content_json') or {}
    return {}


@transaction.atomic
def apply_proposal_json_update(proposal, validated_data):
    """Update an existing proposal + its sections from validated from-JSON data.

    Runs atomically: metadata, change logs and section updates are committed
    together or not at all (no email/side effects happen inside this function).
    The decorator is what makes that sentence true — without it a failure
    part-way through left the proposal half-updated, which the coverage gate
    below turns from a latent risk into a reachable one.

    Returns ``(proposal, updated_sections, unmapped_keys)``.
    """
    from accounts.services import proposal_client_service
    from content.models import ProposalChangeLog, ProposalSection
    from content.serializers.proposal import SECTION_KEY_MAP, SECTION_TYPE_TO_KEY
    from content.services.module_requirements_catalog import (
        seed_module_technical_requirements,
    )
    from content.services.proposal_module_links import (
        ensure_functional_requirements_item_ids,
        normalize_technical_document_module_links,
    )

    data = dict(validated_data)
    sections_data = data.pop('sections')
    explicit_client = data.pop('client', None)
    old_status = proposal.status

    metadata_fields = [
        'title', 'client_name', 'client_email', 'client_phone',
        'project_type', 'market_type', 'project_type_custom',
        'market_type_custom', 'language', 'total_investment', 'currency',
        'nationality',
        'reminder_days', 'urgency_reminder_days', 'discount_percent',
        'show_contract_terms', 'email_intro',
    ]
    tracked_old = {}
    for field in metadata_fields:
        tracked_old[field] = str(getattr(proposal, field, ''))
        if field in data:
            setattr(proposal, field, data[field])

    if 'expires_at' in data:
        tracked_old['expires_at'] = str(proposal.expires_at or '')
        proposal.expires_at = data['expires_at']

    if explicit_client is not None:
        proposal.client = explicit_client
    elif data.get('client_name') or data.get('client_email'):
        client_profile = proposal_client_service.get_or_create_client_for_proposal(
            name=data.get('client_name', '') or proposal.client_name,
            email=data.get('client_email', ''),
            phone=data.get('client_phone', ''),
            company=data.get('client_company', ''),
        )
        proposal.client = client_profile

    reopened_status = ProposalService.reopen_if_unexpired(
        proposal, old_status=old_status,
    )

    proposal.save()
    if proposal.client_id:
        proposal_client_service.sync_snapshot(proposal)

    if reopened_status:
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='updated',
            field_name='status',
            old_value=old_status,
            new_value=reopened_status,
            actor_type='seller',
            description=(
                f'Auto-reopened from expired after expires_at moved to the future '
                f'({old_status} → {reopened_status}).'
            ),
        )

    for field in list(metadata_fields) + ['expires_at']:
        new_val = str(getattr(proposal, field, ''))
        old_val = tracked_old.get(field, '')
        if old_val != new_val:
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type='updated',
                field_name=field,
                old_value=old_val,
                new_value=new_val,
                actor_type='seller',
                description=f'JSON import — {field}: {old_val} → {new_val}',
            )

    updated_sections = []
    all_sections = list(proposal.sections.all())
    for section in all_sections:
        json_key = SECTION_TYPE_TO_KEY.get(section.section_type)
        if json_key and json_key in sections_data:
            new_content = sections_data[json_key]

            if section.section_type == 'greeting':
                general = sections_data.get('general', {})
                new_content.setdefault('proposalTitle', proposal.title)
                new_content.setdefault('clientName', proposal.client_name)
                if general.get('inspirationalQuote'):
                    new_content['inspirationalQuote'] = general['inspirationalQuote']

            if section.section_type == 'value_added_modules':
                # Preserve the legal terms already stored on the proposal — the
                # payload never carries them.
                new_content = merge_value_added_legal_terms(
                    new_content, section.content_json,
                )

            if section.section_type == 'commercial_conditions':
                # Only reached when the payload rewrites this section: a stale
                # snapshot must not be able to downgrade the scope clause. A
                # payload that omits the section leaves it untouched, so already
                # delivered proposals keep the wording they were sent with.
                new_content = enforce_scope_clause(
                    new_content, _default_commercial_conditions(proposal.language),
                )
                # The manual hour-rate settings live only in the panel tab and
                # are absent from every JSON payload, so a wholesale replace
                # would silently reset the proposal to catalog pricing. Carry
                # them over unless the payload states them explicitly.
                new_content = preserve_manual_hour_rate_keys(
                    new_content, section.content_json,
                )

            if section.section_type == 'functional_requirements':
                final_groups = []
                new_content.setdefault('additionalModules', [])
                existing_mod_ids = {m.get('id') for m in new_content['additionalModules']}
                for g in new_content.get('groups', []):
                    if g.get('is_calculator_module'):
                        if g.get('id') not in existing_mod_ids:
                            new_content['additionalModules'].append(g)
                    else:
                        final_groups.append(g)
                new_content['groups'] = final_groups
                new_content = ensure_functional_requirements_item_ids(new_content)

            section.content_json = new_content
            section.save(update_fields=['content_json'])
            updated_sections.append(json_key)

    if {'technicalDocument', 'functionalRequirements'} & set(updated_sections):
        technical_section = next(
            (s for s in all_sections
             if s.section_type == ProposalSection.SectionType.TECHNICAL_DOCUMENT),
            None,
        )
        if technical_section and isinstance(technical_section.content_json, dict):
            section_payloads = [
                {'section_type': s.section_type, 'content_json': s.content_json}
                for s in all_sections
            ]
            seeded = seed_module_technical_requirements(
                technical_section.content_json,
                section_payloads,
                language=proposal.language,
            )
            normalized = normalize_technical_document_module_links(
                seeded,
                section_payloads,
            )
            if normalized != technical_section.content_json:
                technical_section.content_json = normalized
                technical_section.save(update_fields=['content_json'])
            # Gate only a technical document the caller actually authored —
            # its own payload must carry epics. An update that omits the
            # section, or sends an empty one and lets the seeder fill it, is
            # asserting nothing about the detail, so it must not be rejected
            # for what the system generated on its behalf. Mirrors the admin
            # editor, which gates the technical-document save.
            # Validates the NORMALIZED result so seeded links count, and
            # raising rolls the whole update back (@transaction.atomic).
            payload_technical = sections_data.get('technicalDocument')
            if isinstance(payload_technical, dict) and payload_technical.get('epics'):
                enforce_technical_item_coverage(section_payloads, normalized)

    ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type='updated',
        actor_type='seller',
        description=(
            f'Proposal updated from JSON import. '
            f'Sections updated: {", ".join(updated_sections) if updated_sections else "none"}.'
        ),
    )

    known_keys = set(SECTION_KEY_MAP.keys()) | {'_meta', '_seller_prompt'}
    provided_keys = set(sections_data.keys())
    unmapped_keys = sorted(provided_keys - known_keys)
    return proposal, updated_sections, unmapped_keys


# ---------------------------------------------------------------------------
# Panel section management (add/delete a single section from the editor)
# ---------------------------------------------------------------------------

def _personalize_seeded_section(proposal, section_cfg):
    """Stamp proposal-specific values into a seeded default section config.

    Shared by proposal creation (all default sections) and
    :func:`create_section_for_proposal` so both paths personalize the
    greeting and investment content the same way.
    """
    if section_cfg['section_type'] == 'greeting':
        section_cfg['content_json']['proposalTitle'] = proposal.title
        section_cfg['content_json']['clientName'] = proposal.client_name
    if section_cfg['section_type'] == 'commercial_conditions':
        from content.services.hour_package_service import (
            seed_commercial_conditions_from_catalog,
        )
        section_cfg['content_json'] = seed_commercial_conditions_from_catalog(
            section_cfg['content_json'],
            nationality=proposal.nationality,
            language=proposal.language,
        )
    if section_cfg['section_type'] == 'investment' and proposal.total_investment:
        total = float(proposal.total_investment)
        cur = proposal.currency or 'COP'
        fmt = '${:,.0f}'.format
        section_cfg['content_json']['totalInvestment'] = fmt(total)
        section_cfg['content_json']['currency'] = cur
        section_cfg['content_json']['paymentOptions'] = [
            {
                'label': '40% al firmar el contrato ✍️',
                'description': f'{fmt(total * 0.4)} {cur}',
            },
            {
                'label': '30% al aprobar el diseño final ✅',
                'description': f'{fmt(total * 0.3)} {cur}',
            },
            {
                'label': '30% al desplegar el sitio web 🚀',
                'description': f'{fmt(total * 0.3)} {cur}',
            },
        ]
    return section_cfg


def create_section_for_proposal(proposal, section_type, *, title=None):
    """Create one section on ``proposal`` seeded from the language defaults.

    Raises ProposalActionError with code ``invalid_section_type`` or
    ``section_already_exists`` (proposal+section_type is unique).
    """
    from django.db import IntegrityError
    from django.db.models import Max

    from content.api_errors import ProposalActionError
    from content.models import ProposalSection

    if section_type not in ProposalSection.SectionType.values:
        raise ProposalActionError('Tipo de sección inválido.', code='invalid_section_type')

    duplicate_error = ProposalActionError(
        'La propuesta ya tiene una sección de este tipo.',
        code='section_already_exists',
        hint='Edita la sección existente o elimínala primero.',
    )
    if proposal.sections.filter(section_type=section_type).exists():
        raise duplicate_error

    section_cfg = ProposalService.get_default_section(proposal.language, section_type)
    if section_cfg is None:
        section_cfg = {
            'section_type': section_type,
            'title': ProposalSection.SectionType(section_type).label,
            'content_json': {},
            'is_wide_panel': False,
        }
    section_cfg = _personalize_seeded_section(proposal, section_cfg)
    if title:
        section_cfg['title'] = title

    max_order = proposal.sections.aggregate(m=Max('order'))['m']
    section_cfg['order'] = (max_order if max_order is not None else 0) + 1

    try:
        return ProposalSection.objects.create(proposal=proposal, **section_cfg)
    except IntegrityError:
        # Lost a race with a concurrent create of the same type.
        raise duplicate_error from None


def delete_section_from_proposal(section):
    """Delete a section, guarding calculator-confirmed functional requirements.

    Returns ``{'section_type', 'title'}`` for the audit log. Raises
    ProposalActionError with code ``fr_has_confirmed_selection`` when the
    client already confirmed calculator modules (deleting the section would
    silently drop their pricing from effective totals and the PDF).
    """
    from content.api_errors import ProposalActionError
    from content.models import ProposalSection

    proposal = section.proposal
    is_fr = section.section_type == ProposalSection.SectionType.FUNCTIONAL_REQUIREMENTS
    if is_fr and (proposal.selected_modules or proposal.has_confirmed_module_selection):
        raise ProposalActionError(
            'No se puede eliminar: el cliente ya confirmó módulos en la calculadora.',
            code='fr_has_confirmed_selection',
            hint='Desactiva la sección en lugar de eliminarla.',
        )

    info = {'section_type': section.section_type, 'title': section.title}
    section.delete()

    if is_fr:
        # Payment options were scaled on calculator modules that no longer
        # exist; rebuild them on the base total.
        from content.services.proposal_totals_service import (
            resync_investment_from_modules,
        )
        resync_investment_from_modules(proposal, None)

    return info
