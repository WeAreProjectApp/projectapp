import copy
import logging
import re
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from content.api_errors import (
    ProposalActionError,
    error_response,
    error_response_from_exc,
)
from content.services import contract_variants, proposal_status_service
from content.services.proposal_audit import log_proposal_change
from content.services.proposal_status_service import (
    enqueue_onboarding_on_accept as _enqueue_onboarding_on_accept,
)
from content.services.proposal_analytics_service import (
    COMPUTED_ALERT_DISMISS_PREFIX as _COMPUTED_ALERT_DISMISS_PREFIX,
    COMPUTED_ALERT_TYPES as _COMPUTED_ALERT_TYPES,
    KEY_PROPOSAL_SECTIONS as _KEY_PROPOSAL_SECTIONS,
    TECHNICAL_DOCUMENT_TRACKING_TYPES,
    TECHNICAL_FRAGMENT_ORDER as _TECHNICAL_FRAGMENT_ORDER,
    TECHNICAL_FRAGMENT_TITLES as _TECHNICAL_FRAGMENT_TITLES,
    build_dashboard,
    build_proposal_alerts,
    build_proposal_analytics,
    compute_engagement_score as _compute_engagement_score,
    compute_heat_score_with_summary as _compute_heat_score_with_summary,
    computed_alert_key as _computed_alert_key,
    csv_analytics_section_group as _csv_analytics_section_group,
    dashboard_top_dropoff_allowlist as _dashboard_top_dropoff_allowlist,
    technical_fragment_has_content as _technical_fragment_has_content,
)
from content.services.proposal_totals_service import (
    build_effective_totals_map as _build_effective_totals_map,
    effective_total_for_proposal as _effective_total_for_proposal,
    sync_manual_investment,
)
from content.throttles import (
    MagicLinkRequestThrottle,
    ProposalPdfThrottle,
    PublicProposalActionThrottle,
    TrackingAnonThrottle,
)
from content.utils import get_client_ip, is_staff_session

from content.models import (
    BusinessProposal, ProposalAlert, ProposalSection,
    ProposalViewEvent, ProposalSectionView,
    ProposalChangeLog, ProposalShareLink,
    ProposalDefaultConfig,
)
from content.serializers.proposal import (
    ContractParamsSerializer,
    ProposalAlertSerializer,
    ProposalCreateUpdateSerializer,
    ProposalDefaultConfigSerializer,
    ProposalDetailSerializer,
    ProposalFromJSONSerializer,
    ProposalListSerializer,
    ProposalProjectStageSerializer,
    ProposalResendSerializer,
    ProposalSectionUpdateSerializer,
    ProposalShareLinkSerializer,
    SECTION_KEY_MAP,
    SECTION_TYPE_TO_KEY,
    serialize_proposal_document,
)
from content.views._email_attachment import render_markdown_pdf_response

logger = logging.getLogger(__name__)


def _proposal_admin_response(request, proposal, delivery=None):
    """Serialize a proposal for the admin panel, optionally with delivery info."""
    payload = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': True}
    ).data
    if delivery is not None:
        payload['email_delivery'] = delivery
    return Response(payload, status=status.HTTP_200_OK)


def _normalize_selected_module_ids(selected, fr_content_json):
    """Thin wrapper around the shared normalizer in ``proposal_service``."""
    from content.services.proposal_service import normalize_selected_module_ids
    return normalize_selected_module_ids(selected, fr_content_json)


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------

def _serve_public_proposal(request, proposal):
    """Shared handler for the public proposal endpoint.

    This GET is intentionally read-only for engagement metrics. A browser is
    counted only after the public page remains visible long enough to POST a
    validated heartbeat to ``track_proposal_engagement``.
    """
    if not proposal.is_active:
        return Response(
            {'error': 'This proposal is not available.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    is_expired = proposal.is_expired
    expired_meta = None

    if is_expired:
        if proposal.status != BusinessProposal.Status.EXPIRED:
            proposal.status = BusinessProposal.Status.EXPIRED
            proposal.save(update_fields=['status'])

        # Build WhatsApp link for recovery CTA
        from urllib.parse import quote as _url_quote
        wa_number = getattr(settings, 'WHATSAPP_CONTACT_NUMBER', '')
        wa_msg = _url_quote(
            f'Hola, me interesa retomar la propuesta "{proposal.title}". '
            f'Link: {proposal.public_url}'
        )
        wa_url = f'https://wa.me/{wa_number}?text={wa_msg}' if wa_number else ''
        seller_name = getattr(settings, 'SELLER_DISPLAY_NAME', 'nuestro equipo')

        expired_meta = {
            'expired_at': (
                proposal.expires_at.isoformat()
                if proposal.expires_at else None
            ),
            'seller_name': seller_name,
            'whatsapp_url': wa_url,
        }

    # Admin preview detection — skip all analytics when staff views
    # Detects by Django session cookie (automatic, no query param needed)
    is_preview = is_staff_session(request)

    serializer = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': False}
    )
    response_data = serializer.data
    if is_preview:
        response_data['is_admin_preview'] = True
    if expired_meta:
        response_data['expired_meta'] = expired_meta
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def retrieve_public_proposal(request, proposal_uuid):
    """Retrieve a proposal by UUID for client viewing."""
    proposal = get_object_or_404(
        BusinessProposal.objects
        .select_related('client__user', 'deliverable__project__client__profile')
        .prefetch_related('sections'),
        uuid=proposal_uuid,
    )
    return _serve_public_proposal(request, proposal)


@api_view(['GET'])
@permission_classes([AllowAny])
def retrieve_public_proposal_by_slug(request, proposal_slug):
    """Retrieve a proposal by its editable slug for client viewing."""
    proposal = get_object_or_404(
        BusinessProposal.objects
        .select_related('client__user', 'deliverable__project__client__profile')
        .prefetch_related('sections'),
        slug=proposal_slug,
    )
    return _serve_public_proposal(request, proposal)


def _public_contract_terms_proposal(proposal_uuid):
    """Resolve a proposal only when its generic legal module is available."""
    proposal = get_object_or_404(BusinessProposal, uuid=proposal_uuid)
    if not (
        proposal.is_active
        and proposal.language == BusinessProposal.Language.ES
        and proposal.show_contract_terms
    ):
        return None
    return proposal


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([ProposalPdfThrottle])
def retrieve_public_contract_terms(request, proposal_uuid):
    """Return the current global contract as a masked, linkable preview."""
    proposal = _public_contract_terms_proposal(proposal_uuid)
    if proposal is None:
        return Response(
            {'error': 'Este contenido no está disponible.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    from content.services.contract_terms_service import (
        build_contract_terms_payload,
    )

    payload = build_contract_terms_payload()
    if payload is None:
        return Response(
            {'error': 'El borrador del contrato no está disponible temporalmente.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    response = Response(payload, status=status.HTTP_200_OK)
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([ProposalPdfThrottle])
def download_public_draft_contract_pdf(request, proposal_uuid):
    """Download the masked global contract with a BORRADOR watermark."""
    proposal = _public_contract_terms_proposal(proposal_uuid)
    if proposal is None:
        return Response(
            {'error': 'Este contenido no está disponible.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    from content.models import ContractTemplate
    from content.services.contract_pdf_service import generate_contract_pdf
    from content.services.pdf_utils import add_watermark_to_pdf

    if not ContractTemplate.get_default():
        return Response(
            {'error': 'El borrador del contrato no está disponible temporalmente.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    pdf_bytes = generate_contract_pdf(
        proposal,
        draft=True,
        force_default=True,
    )
    if not pdf_bytes:
        return Response(
            {'error': 'No fue posible generar el borrador del contrato.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    response = _contract_pdf_response(
        add_watermark_to_pdf(pdf_bytes),
        proposal,
        'Borrador_Contrato',
    )
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([ProposalPdfThrottle])
def download_proposal_pdf(request, proposal_uuid):
    """
    Generate and download a PDF of the proposal using ReportLab.
    """
    proposal = get_object_or_404(BusinessProposal, uuid=proposal_uuid)

    if proposal.is_expired:
        return Response(
            {
                'error': 'This proposal has expired.',
                'code': 'proposal_expired',
            },
            status=status.HTTP_410_GONE,
        )

    return _proposal_pdf_response(request, proposal)


@api_view(['GET'])
@permission_classes([IsAdminUser])
@throttle_classes([ProposalPdfThrottle])
def download_admin_proposal_pdf(request, proposal_id):
    """Allow staff to download the original proposal even after expiry."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    response = _proposal_pdf_response(request, proposal)
    response['Cache-Control'] = 'private, no-store'
    return response


def _proposal_pdf_response(request, proposal):
    """Render the same commercial/technical content for both access policies."""
    from content.services.proposal_pdf_service import (
        ProposalPdfService,
        default_selected_modules_from_content,
    )

    doc_variant = (request.query_params.get('doc') or '').strip().lower()
    # Selection is persisted administrative scope, never a public query override.
    if 'selected_modules' in request.query_params:
        return Response({'error': 'Module selection is managed by the proposal owner.'}, status=400)
    selected_modules = default_selected_modules_from_content(proposal)

    if doc_variant == 'technical':
        from content.services.technical_document_pdf import generate_technical_document_pdf

        pdf_bytes = generate_technical_document_pdf(
            proposal, selected_modules=selected_modules
        )
        if not pdf_bytes:
            return Response(
                {'error': 'Technical document is not available for this proposal.'},
                status=status.HTTP_404_NOT_FOUND,
            )
    else:
        pdf_bytes = ProposalPdfService.generate(
            proposal, selected_modules=selected_modules
        )

        if not pdf_bytes:
            return Response(
                {'error': 'PDF generation failed. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    from django.http import HttpResponse
    from content.services.pdf_utils import safe_pdf_filename
    _created = proposal.created_at or timezone.now()
    date_suffix = _created.strftime('%d-%m-%y')
    prefix = 'Detalle_Tecnico' if doc_variant == 'technical' else 'Propuesta_Comercial'
    filename = safe_pdf_filename(prefix, proposal.title or proposal.client_name, date_suffix)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Admin endpoints (staff only)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_proposals(request):
    """
    List all proposals with lightweight serializer.
    Supports ?status= and ?client_id= query parameters for filtering.
    Includes heat_score (1-10) for active non-draft proposals.
    """
    qs = BusinessProposal.objects.select_related('client__user', 'deliverable__project__client__profile').all()
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    client_id = request.query_params.get('client_id')
    if client_id:
        qs = qs.filter(client_id=client_id)

    proposals = list(qs)
    effective_totals = _build_effective_totals_map(proposals)

    serializer = ProposalListSerializer(proposals, many=True)
    data = serializer.data

    # Use pre-computed cached_heat_score from the model instead of
    # computing on-the-fly (avoids N+1 queries on every list load).
    for item in data:
        eff_total = effective_totals.get(item['id'])
        item['effective_total_investment'] = (
            str(eff_total) if eff_total is not None else item['total_investment']
        )
        if item['status'] in ('accepted', 'finished'):
            item['heat_score'] = 10
        elif item['status'] in ('sent', 'viewed') and item['is_active']:
            item['heat_score'] = item.get('cached_heat_score', 0) or 0
        else:
            item['heat_score'] = 0
        item['engagement_summary'] = None

    # Batch-compute engagement summaries for active sent/viewed proposals
    # using 3 aggregated queries instead of N*5 individual queries.
    active_ids = [
        item['id'] for item in data
        if item['status'] in ('sent', 'viewed') and item['is_active'] and item.get('heat_score', 0) > 0
    ]
    if active_ids:
        from django.db.models import Count, Q, Sum
        now = timezone.now()

        # Single query: investment + technical time aggregated together via conditional Sum.
        section_agg = {
            pid: (inv_t or 0, tech_t or 0)
            for pid, inv_t, tech_t in ProposalSectionView.objects
            .filter(view_event__proposal_id__in=active_ids)
            .values('view_event__proposal_id')
            .annotate(
                inv_t=Sum('time_spent_seconds', filter=Q(section_type='investment')),
                tech_t=Sum(
                    'time_spent_seconds',
                    filter=Q(section_type__in=TECHNICAL_DOCUMENT_TRACKING_TYPES),
                ),
            )
            .values_list('view_event__proposal_id', 'inv_t', 'tech_t')
        }
        unique_ips_map = dict(
            ProposalViewEvent.objects
            .filter(proposal_id__in=active_ids)
            .exclude(ip_address__isnull=True).exclude(ip_address='')
            .values('proposal_id')
            .annotate(cnt=Count('ip_address', distinct=True))
            .values_list('proposal_id', 'cnt')
        )
        # Only fetch rows for key sections — avoids loading unrelated section data.
        viewed_sections: dict[int, set] = {}
        for pid, stype in ProposalSectionView.objects.filter(
            view_event__proposal_id__in=active_ids,
            section_type__in=_KEY_PROPOSAL_SECTIONS,
        ).values_list('view_event__proposal_id', 'section_type').distinct():
            viewed_sections.setdefault(pid, set()).add(stype)

        summaries_map = {}
        for pid in active_ids:
            inv_t, tech_t = section_agg.get(pid, (0, 0))
            uniq = unique_ips_map.get(pid, 0)
            skipped = [s for s in _KEY_PROPOSAL_SECTIONS if s not in viewed_sections.get(pid, set())]
            summaries_map[pid] = {
                'investment_time_sec': round(inv_t),
                'technical_time_sec': round(tech_t),
                'technical_viewed': tech_t >= 5,
                'unique_devices': uniq,
                'skipped_sections': skipped,
            }

        for item in data:
            pid = item['id']
            if pid not in summaries_map:
                continue
            s = summaries_map[pid]
            last_activity = item.get('last_activity_at')
            last_activity_str = None
            if last_activity:
                try:
                    la_dt = (
                        last_activity if hasattr(last_activity, 'tzinfo')
                        else parse_datetime(last_activity)
                    )
                    if la_dt:
                        delta = now - la_dt
                        if delta.days == 0:
                            hours = delta.seconds // 3600
                            last_activity_str = f"hace {hours}h" if hours > 0 else "hace menos de 1h"
                        else:
                            last_activity_str = f"hace {delta.days}d"
                except Exception:
                    pass
            item['engagement_summary'] = {
                'views': item.get('view_count', 0),
                'last_activity': last_activity_str,
                **s,
            }

    return Response(data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def retrieve_proposal(request, proposal_id):
    """
    Retrieve full proposal detail for admin editing.
    Returns all sections (including disabled ones).
    """
    proposal = get_object_or_404(
        BusinessProposal.objects
        .select_related('client__user', 'deliverable__project__client__profile')
        .prefetch_related(
            'project_stages',
            'sections',
            # change_logs intentionally not prefetched: the serializer slices
            # to 50, so a LIMIT query beats loading the unbounded log table.
            'proposal_documents',
        ),
        pk=proposal_id,
    )
    serializer = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': True}
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_proposal(request):
    """
    Create a new proposal.
    Auto-generates 12 default sections with content_json populated
    from the existing component defaults.
    """
    serializer = ProposalCreateUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    from content.services.proposal_service import ProposalService

    with transaction.atomic():
        proposal = serializer.save()

        if not proposal.expires_at:
            proposal.expires_at = ProposalService.compute_default_expires_at(proposal.language)
            proposal.save(update_fields=['expires_at'])

        # Hosting defaults are admin-editable; payload values win.
        ProposalService.apply_hosting_defaults(proposal, set(request.data))

        # Log creation
        log_proposal_change(
            proposal,
            'created',
            actor_type='seller',
            description=(
                f'Proposal created: "{proposal.title}" for {proposal.client_name}. '
                f'Investment: ${proposal.total_investment} {proposal.currency}.'
            ),
        )

        # Auto-create default sections, personalized like single-section adds
        from content.services.proposal_service import _personalize_seeded_section
        default_sections = ProposalService.get_default_sections(proposal.language)
        for section_cfg in default_sections:
            _personalize_seeded_section(proposal, section_cfg)
            ProposalSection.objects.create(proposal=proposal, **section_cfg)

    # Return the full detail
    detail = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': True}
    )
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_proposal_from_json(request):
    """
    Create a proposal from a complete JSON payload.

    The payload includes metadata (title, client_name, etc.) and a
    ``sections`` dict whose keys are camelCase section names with their
    full content_json.  Missing sections fall back to DEFAULT_SECTIONS.
    """
    serializer = ProposalFromJSONSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    from content.services.proposal_service import build_proposal_from_json

    proposal, unmapped_keys = build_proposal_from_json(serializer.validated_data)

    detail = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': True}
    )
    response_data = detail.data
    if unmapped_keys:
        response_data['warnings'] = [
            f'Unknown section keys ignored: {", ".join(unmapped_keys)}. '
            f'Valid keys: {", ".join(sorted(SECTION_KEY_MAP.keys()))}.'
        ]
    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_proposal_json_template(request):
    """
    Return a downloadable JSON template with all default sections
    (commercial + technicalDocument) pre-populated with placeholder content.

    Query params:
        lang: 'es' (default) or 'en'
    """
    lang = request.query_params.get('lang', 'es')

    from content.services.proposal_service import ProposalService
    default_sections = ProposalService.get_default_sections(lang)

    template = {}
    for section_cfg in default_sections:
        section_type = section_cfg['section_type']
        json_key = SECTION_TYPE_TO_KEY.get(section_type, section_type)
        template[json_key] = copy.deepcopy(section_cfg['content_json'])

    template['_meta'] = {
        'description': 'Proposal JSON template — fill in each section and import via the panel',
        'required_fields': ['general.clientName'],
        'optional_metadata': {
            'title': 'Propuesta de ... — Client Name',
            'client_email': 'client@example.com',
            'email_intro': (
                'Mensaje breve y específico: problema del cliente, solución '
                'propuesta y resultado de negocio esperado.'
            ),
            'language': 'es | en',
            'total_investment': 0,
            'currency': 'COP | USD',
            'nationality': 'COL | EXT | USA',
        },
    }

    # Add _do_not_remove annotations to functionalRequirements groups
    fr_key = SECTION_TYPE_TO_KEY.get('functional_requirements', 'functionalRequirements')
    if fr_key in template:
        fr = template[fr_key]
        for group in fr.get('groups', []):
            group['_do_not_remove'] = True
        for mod in fr.get('additionalModules', []):
            mod['_do_not_remove'] = True

    template['_seller_prompt'] = {
        'role': (
            'You are an expert sales consultant crafting a business proposal. '
            'Your goal is to persuade the client by demonstrating deep understanding '
            'of their industry, challenges, and opportunities.'
        ),
        'tone': (
            'Business-oriented but approachable. Avoid overly technical jargon. '
            'Write as if speaking directly to the decision-maker. Use confident, '
            'results-focused language.'
        ),
        'personalization': [
            'Always mention the client name and company name.',
            'Reference the client\'s specific industry, sector, and market.',
            'Include at least 2-3 metrics or statistics relevant to their sector (cite reliable sources).',
            'Tailor examples and case studies to their business type.',
            (
                'Write _meta.optional_metadata.email_intro as a concise, '
                'client-specific plain-text message that connects the confirmed '
                'problem, this proposal\'s solution, and the expected business outcome.'
            ),
        ],
        'investment_anchoring': [
            'Present ROI and value BEFORE mentioning price.',
            'Frame the investment as a business decision, not a cost.',
            'Compare the investment to the cost of inaction or lost opportunity.',
            'If applicable, show projected revenue impact or efficiency gains.',
        ],
        'structure_tips': [
            'Greeting: warm, personal, mention how/why you connected.',
            'Executive Summary: 3-4 sentences max, outcome-focused.',
            'Context/Diagnostic: show you understand their current situation.',
            'Strategy: actionable and specific to their goals.',
            'Investment: lead with value, break down modules clearly.',
            'Timeline: realistic milestones tied to business outcomes.',
        ],
        'bold_formatting': (
            'Use only <b>…</b> for inline emphasis. Every non-empty section lead '
            'listed below MUST contain one or two short bold fragments that '
            'highlight a business outcome, verifiable scope, or decisive '
            'condition: executiveSummary.paragraphs[], '
            'contextDiagnostic.paragraphs[], conversionStrategy.intro, '
            'roiProjection.subtitle, designUX.paragraphs[], '
            'creativeSupport.paragraphs[], developmentStages.intro, '
            'processMethodology.intro, functionalRequirements.intro, '
            'valueAddedModules.intro, investment.introText, timeline.introText, '
            'proposalSummary.subtitle, and finalNote.message. Do NOT bold an '
            'entire sentence or paragraph, do NOT use Markdown ** markers, and '
            'do not invent copy for an intentionally empty field. Existing '
            'nested emphasis rules still apply to highlights, issues, bullets, '
            'results, focus items, objectives, includes, closing copy, and '
            'functional requirement item descriptions.'
        ),
        'CRITICAL_metadata': (
            'Do NOT add any keys to "_meta.optional_metadata" beyond the ones already '
            'listed in the template. Populate email_intro for every generated proposal; '
            'email_intro is required before sending and must be plain text, without '
            'HTML or Markdown. '
            'In particular, NEVER add an "expires_at" field: the proposal expiration date '
            'is set automatically from the admin-configured default when the proposal is '
            'created, not from this JSON.'
        ),
        'CRITICAL_functionalRequirements': (
            'Do NOT remove any groups or modules from the functionalRequirements section. '
            'All base groups in "groups" and all optional modules in "additionalModules" '
            'MUST remain in their respective arrays, in their original order. '
            'Do NOT move modules between arrays. '
            'You may modify content (title, description, items) and add new entries, '
            'but NEVER delete or relocate existing ones. The seller will remove them manually '
            'after the proposal is created if needed. '
            'Every item MUST carry a stable "id" — see '
            'CRITICAL_functionalRequirements_itemIds.'
        ),
        'CRITICAL_crossCuttingFeatures': (
            'The required group with id "cross_cutting_features" belongs immediately after '
            '"features". It is a CONTEXTUAL STARTER CATALOG, not fixed boilerplate: review '
            'responsive design, accessibility, consistent usability, performance, security, '
            'data privacy, and browser compatibility against the business, product stage, '
            'audience, and actual proposal scope. Keep, rewrite, remove, or add individual '
            'items as justified, but keep the group non-empty and preserve its id. Put '
            'single-screen or business-specific behaviors in "features"; put qualities that '
            'apply across multiple views, components, or flows here, with no duplication '
            'between the two groups. Never promise a compliance level, certification, '
            'browser/version matrix, security control, or performance target unless the '
            'proposal context supports it.'
        ),
        'CRITICAL_functionalRequirements_itemIds': (
            'EVERY item in every functionalRequirements group AND in every additional '
            'module must have a stable "id" with the exact format '
            '"item-<group_id>-<slug-of-name>". Slug algorithm (apply EXACTLY): lowercase '
            'the full item name; strip accents/diacritics (a-acute -> a, n-tilde -> n); '
            'replace every run of characters outside [a-z0-9] (spaces, "&", "/", commas, '
            'parentheses, emojis) with a SINGLE hyphen; trim leading/trailing hyphens. '
            'Example: "Registro de usuario" in group "views" -> '
            '"item-views-registro-de-usuario". Ids must be UNIQUE across the whole '
            'section (groups + additionalModules): on collision, walk the document in '
            'order (groups top-to-bottom, then additionalModules top-to-bottom); the '
            'FIRST occurrence keeps the base slug and later ones get "-2", "-3" '
            'suffixes in order of appearance. STABILITY: when EDITING an existing '
            'proposal, NEVER change an already-assigned id, even if the item name '
            'changes — the id is decoupled from the name after creation. These ids are '
            'the contract with the technical document (step 2): technical requirements '
            'reference them via "linked_item_ids", powering the client-facing '
            '"View requirements" modal and the PDF; a changed or missing id silently '
            'breaks that traceability. Ids derive from the name in the proposal '
            'language — never reuse ids or technical documents across ES/EN versions.'
        ),
        'CRITICAL_functionalRequirements_atomicItems': (
            'Every item must be ATOMIC: exactly ONE screen, ONE component or ONE '
            'capability per item. NEVER join two distinct screens or capabilities in '
            'a single item name with " y ", " e ", " o ", "/" or "&": '
            '"Registro e Inicio de Sesion" is WRONG — produce TWO items ("Registro de '
            'Usuario" and "Inicio de Sesion"), each with its own id and its own '
            'description. The rule applies to views, components, features, cross-cutting '
            'features and module items alike. Only exception: names denoting a single indivisible '
            'capability or an idiomatic proper name (e.g. "Terminos y Condiciones" is '
            'one legal page; "Registro con Google" and "Inicio de Sesion con Google" '
            'are still two items even though both use the same Google account). When '
            'in doubt, split: atomic items produce clearer scope and precise '
            'per-item technical traceability in step 2, where each item is broken '
            'down into as many linked technical requirements as its real '
            'complexity demands (transactional items 4-6, typical 3-5, trivial '
            'static ones 1-2 - never a uniform count nor a repeated title '
            'pattern across items).'
        ),
        'CRITICAL_functionalRequirements_itemDetail': (
            'Each item in every functionalRequirements group (and in every SELECTED additional '
            'module) must have a RICH "description" written as TWO paragraphs separated by '
            '"<br><br>": '
            '(1) the first paragraph DESCRIBES the element in detail (what it is, what it shows, '
            'what it is for) — not telegraphic; '
            '(2) the second paragraph STARTS with "El usuario podrá …" (or "The user will be able '
            'to …" in EN) and lists what the user can do there, WITHOUT repeating verbatim what the '
            'first paragraph already said (add, do not duplicate). '
            'Highlight 1-3 key words/phrases per paragraph with <b>…</b> (never whole paragraphs). '
            'Keep "name" as plain text (no HTML). Use <b> and <br><br> only — do NOT use markdown '
            '("**") or <p> tags (they are not rendered). '
            'Where it applies, write a narrative that helps the client imagine the product is '
            'SCALABLE and what they will be able to do with it — but anchor everything to the real '
            'scope: never invent features, metrics, integrations or case studies; if something is '
            'future work, say so explicitly.'
        ),
        'CRITICAL_roiProjection': (
            'The roiProjection section anchors the investment in business value '
            'and MUST be populated before the investment section in the narrative. '
            'Provide EXACTLY 3 KPIs in "kpis" — no more, no less. The UI '
            'renders 3 cards under the subtitle and the layout assumes that '
            'fixed count; with fewer it looks empty and with more the grid '
            'breaks. SELECTION CRITERION: first brainstorm all verifiable '
            'KPIs you could cite for this sector and project (each with real '
            'source + year), then pick the 3 that most push the client to '
            'feel the investment is worth it. Mix three angles when possible: '
            '(1) urgency / market context — a stat that proves NOT digitizing '
            'costs (sector growth, legal mandate, target audience digital '
            'adoption); (2) magnitude of the opportunity or pain — sector '
            'size, number of clients / processes / households affected; '
            '(3) direct client pain this investment solves — hours lost, '
            'no-show rate, response time, ROI of a specific channel. Discard '
            'true-but-neutral KPIs that do not move the buying decision. '
            'Apply this HARD RULE on sourcing: '
            'every KPI requires a "source" naming a real report / study / law + '
            'organization + year, written IN SPANISH whenever a natural Spanish '
            'rendering exists. Source ORIGIN MUST PRIORITIZE Colombia / Latin '
            'America: clients are Colombian or LATAM and ProjectApp builds '
            'custom software for ANY sector (commerce, health, education, '
            'construction, banking, agribusiness, transport, tourism, '
            'manufacturing, professional services, sports, legal, etc.). The '
            'categories below are SUGGESTIONS — NOT a closed list. The AI is '
            'free to cite any other source that fits the client sector better, '
            'as long as it is real, named, has a year, and a seller could '
            'verify it with a single Google search. Suggested buckets: '
            '(a) Colombian state — DANE, Banco de la República, Mintic, DNP, '
            'Confecámaras, Procolombia; (b) Colombian superintendencias / '
            'reguladores by sector — Financiera, Industria y Comercio (SIC), '
            'Salud, Sociedades, Servicios Públicos, Transporte, Educación, '
            'Notariado y Registro, etc.; (c) Sector-specific Colombian '
            'ministries — MinSalud, MinEducación, MinTransporte, '
            'MinAgricultura, MinComercio Industria y Turismo, MinJusticia, '
            'MinTrabajo, MinVivienda, MinDeporte, etc.; (d) Colombian sector '
            'guilds / associations — Fenalco, ANDI, ANIF, Acopi, Camacol, '
            'Asobancaria, Anato, Cotelco, Andesco, FedeArroz, Fedegan, '
            'Asocolflores, etc.; (e) Regional Chambers of Commerce '
            '(Bogotá, Medellín, Cali, Barranquilla, etc.) and their economic '
            'observatories; (f) Colombian universities with sector observatories '
            '(Andes/CEDE, Rosario, Javeriana, EAFIT, Externado, Nacional, EIA); '
            '(g) Recognized economic / business news media — when they cite a '
            'study or interview a sector authority — Portafolio, La República, '
            'El Tiempo (sección Economía), Semana / Dinero, Valora Analitik, '
            'BloombergLínea, BNamericas, América Economía, Forbes Colombia / '
            'Forbes LATAM, Reuters; cite the outlet name + year + ideally the '
            'underlying report the article references; (h) LATAM regional '
            'bodies — CEPAL, BID, Felaban, AMVO, IAB Colombia/LATAM, CCCE, '
            'plus LATAM cuts of global guild reports; (i) Colombian laws / '
            'decrees / resolutions relevant to the sector; (j) Other '
            'verifiable sources — local consultancies, think tanks, private '
            'observatorios, LATAM academic papers, etc. — fully valid as long '
            'as they are named with year and traceable. International (US / '
            'Europe / global) sources are accepted only when no local '
            'equivalent exists for that specific data point, and then AT MOST '
            'ONCE per KPI block, marking sublabel as "referente internacional '
            'aplicable". Verifiability test: if the seller pastes the source '
            'string into Google and finds nothing that backs the figure, it '
            'is not valid. If a KPI lacks a real named source with year, IT '
            'IS NOT A KPI — IT IS A PROMISE. Drop it. Generic strings like '
            '"Benchmark sectorial", "Estudio interno", "Datos del mercado" are '
            'NOT acceptable. Prefer 3 well-sourced LOCAL KPIs over 4 with '
            'vague provenance or first-world data. KPI labels MUST be '
            'readable by a '
            'non-financial person — no MRR, LTV, CAC, churn, conv. rate jargon. '
            'Use plain language: "Out of every 100 visits, 3 book a class" '
            'instead of "3% conversion". Provide EXACTLY 3 scenarios in '
            '"scenarios" with names "conservative", "realistic", "optimistic" '
            '(labels: Conservador/Realista/Optimista in ES, '
            'Conservative/Realistic/Optimistic in EN). Each scenario MUST have '
            '3-5 metrics with parallel labels across scenarios so the client can '
            'compare row by row. Mark exactly ONE metric per scenario with '
            'emphasis=true (the most impactful one, typically projected annual '
            'revenue). Scenario metric labels follow the same plain-language '
            'rule. Tailor KPIs and metrics to the client sector and the '
            'total_investment provided (which already includes selected '
            'additionalModules). Keep ctaNote consultative and honest — '
            'projections grounded in real reports, not promises. '
            'SHOW YOUR WORK so the client understands HOW the numbers were '
            'obtained — these three fields are mandatory: '
            '(1) "methodology" (section level): 2-3 plain-language sentences '
            'naming the verifiable BASE you start from for this sector '
            '(e.g. expected local-market traffic / number of potential clients '
            '/ size of the target audience), the KEY ASSUMPTION you apply '
            '("out of every 100 visits, X book") and that you project it over '
            '12 months — then state that each scenario simply moves that '
            'assumption up or down. Same anti-jargon rule as the labels. '
            '(2) "assumptions" (array on EACH scenario): 2-4 short phrases '
            'with the concrete levers that define THAT scenario (adoption pace, '
            'share of the reachable market, active channels, conversion, etc.), '
            'kept parallel across the three scenarios so the client sees why '
            'conservative < realistic < optimistic. '
            '(3) "basis" (string on metrics): the arithmetic behind the number '
            '(e.g. "≈ 6,500 clients × $43,000 average ticket"). REQUIRED on '
            'every metric flagged emphasis=true; strongly recommended on the '
            'other numeric metrics. Everything must reconcile: the basis and '
            'assumptions have to add up to the values shown — never invent a '
            'formula, anchor every projection to the verifiable base.'
        ),
        'CRITICAL_additionalModules_autoselect': (
            'Scan the project requirements, brief, and notes provided by the seller. '
            'For EACH module in functionalRequirements.additionalModules, decide whether '
            'the requirements explicitly or implicitly describe that capability. '
            'Detection hints: DIAN, electronic invoicing or e-invoicing, Siigo, Alegra -> '
            '"integration_electronic_invoicing". PSE, Wompi, PayU, ePayco, Nequi, Daviplata, '
            'Bancolombia or Colombian payments -> "integration_regional_payments". Stripe, '
            'PayPal, cross-border or international payments -> '
            '"integration_international_payments". Installable app, PWA, offline mode, push '
            'notifications -> "pwa_module". AI, intelligent automation, chatbot, assistants '
            '-> "ai_module". Meta Ads, Facebook Ads, Google Ads, Conversions API, CAPI, ROAS, '
            'Enhanced Conversions -> "integration_conversion_tracking". Reports, notifications '
            'or alerts via email/WhatsApp, sales/stock alerts -> '
            '"reports_alerts_module". Email marketing, Mailchimp, Brevo, SendGrid, lead '
            'capture -> "email_marketing_module". Multi-language, i18n, multiple countries, '
            'translations, per-country pricing -> "i18n_module". Live chat, real-time '
            'support, in-house chat widget -> "live_chat_module". Dark mode, theme '
            'switching -> "dark_mode_module". '
            'Biometric verification, biometric validation, KYC, e-KYC, identity '
            'verification, facial recognition, liveness, ID document validation, '
            'antifraud onboarding, verificación biométrica, validación de identidad, '
            'reconocimiento facial, prueba de vida, validación de cédula, '
            'onboarding digital, antifraude -> "biometric_verification_module". '
            'QR, código QR, qr code, dynamic qr, menú digital, código de mesa, '
            'link tree, physical-to-digital, scan to action -> "qr_generator_module". '
            'AI content, content generation, generación de contenido, blog AI, '
            'copy AI, calendario editorial, content calendar, social media scheduling, '
            'programación de publicaciones, scheduled posts, auto-publishing, '
            'editorial planning -> "content_generator_module". '
            'In-product user behavior tracking, product analytics, time per view or '
            'screen, usage sessions, usage funnels, first-party user tracking, rastreo '
            'de comportamiento, tiempo por vista, embudos de uso -> '
            '"behavior_tracking_module" (do not confuse with '
            '"integration_conversion_tracking", which reports AD conversions to '
            'Meta/Google, nor with the free analytics_dashboard basic web analytics). '
            'When a module matches the brief, set BOTH "default_selected": true AND '
            '"selected": true on that module object, and ADAPT its "description" and reorder '
            'or rewrite its "items" so the wording reflects the exact terminology, providers '
            'and nuances mentioned in the requirements (e.g. if the brief says "I want to '
            'receive reports via WhatsApp", make sure the WhatsApp item in '
            'reports_alerts_module leads the list and the description names WhatsApp as the '
            'primary channel). '
            'Never invent a match that is not supported by the requirements. When in doubt, '
            'leave default_selected as false. Do NOT change the module id, icon, '
            'is_invite, or its position in the array.'
        ),
    }

    return Response(template, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_proposal_json(request, proposal_id):
    """
    Export an existing proposal as a JSON object compatible with
    the ``create-from-json`` / ``update-from-json`` import format.

    Returns a dict with camelCase section keys and a ``_meta`` block
    containing proposal metadata.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    result = {}
    for section in proposal.sections.all().order_by('order'):
        json_key = SECTION_TYPE_TO_KEY.get(section.section_type)
        if json_key:
            result[json_key] = copy.deepcopy(section.content_json or {})

    result['_meta'] = {
        'title': proposal.title,
        'client_name': proposal.client_name,
        'client_email': proposal.client_email or '',
        'email_intro': proposal.email_intro or '',
        'client_phone': proposal.client_phone or '',
        'project_type': proposal.project_type or '',
        'market_type': proposal.market_type or '',
        'project_type_custom': proposal.project_type_custom or '',
        'market_type_custom': proposal.market_type_custom or '',
        'language': proposal.language or 'es',
        'total_investment': str(proposal.total_investment),
        'currency': proposal.currency or 'COP',
        'hosting_percent': proposal.hosting_percent,
        'hosting_discount_nine_month': proposal.hosting_discount_nine_month,
        'hosting_discount_semiannual': proposal.hosting_discount_semiannual,
        'hosting_discount_quarterly': proposal.hosting_discount_quarterly,
        'expires_at': (
            proposal.expires_at.isoformat() if proposal.expires_at else None
        ),
        'reminder_days': proposal.reminder_days,
        'urgency_reminder_days': proposal.urgency_reminder_days,
        'discount_percent': proposal.discount_percent,
    }

    return Response(result, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAdminUser])
def update_proposal_from_json(request, proposal_id):
    """
    Update an existing proposal from a complete JSON payload.

    Accepts the same structure as ``create-from-json``: metadata fields
    at the top level and a ``sections`` dict whose keys are camelCase
    section names mapped to content_json dicts.

    Metadata fields are updated on the proposal, and each section's
    content_json is replaced by the matching key from the payload.
    Sections not present in the payload are left unchanged.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    serializer = ProposalFromJSONSerializer(
        data=request.data, context={'proposal': proposal}
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    from content.services.proposal_service import apply_proposal_json_update

    try:
        proposal, updated_sections, unmapped_keys = apply_proposal_json_update(
            proposal, serializer.validated_data,
        )
    except ValueError as e:  # includes ProposalActionError
        return error_response_from_exc(e)

    detail = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': True}
    )
    response_data = detail.data
    if unmapped_keys:
        response_data['warnings'] = [
            f'Unknown section keys ignored: {", ".join(unmapped_keys)}. '
            f'Valid keys: {", ".join(sorted(SECTION_KEY_MAP.keys()))}.'
        ]
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_proposal(request, proposal_id):
    """
    Update proposal metadata (title, client_name, etc.).
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    # Snapshot tracked fields before update
    tracked_fields = [
        'title', 'total_investment', 'currency', 'client_name',
        'client_email', 'client_phone', 'discount_percent', 'status',
        'language', 'project_type', 'market_type', 'slug',
        'expires_at', 'reminder_days', 'urgency_reminder_days',
        'show_contract_terms', 'email_intro',
    ]
    old_values = {f: str(getattr(proposal, f, '')) for f in tracked_fields}

    serializer = ProposalCreateUpdateSerializer(
        proposal, data=request.data, partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            serializer.save()

            from content.services.proposal_service import ProposalService
            reopened_status = ProposalService.reopen_if_unexpired(
                proposal, old_status=old_values['status'],
            )
            if reopened_status:
                proposal.save(update_fields=['status'])

            # Log field-level changes
            for field in tracked_fields:
                new_val = str(getattr(proposal, field, ''))
                if old_values[field] != new_val:
                    description = f'{field}: {old_values[field]} → {new_val}'
                    if field == 'status' and reopened_status:
                        description = (
                            f'Auto-reopened from expired after expires_at moved to the future '
                            f'({old_values[field]} → {new_val}).'
                        )
                    log_proposal_change(
                        proposal,
                        'updated',
                        field_name=field,
                        old_value=old_values[field],
                        new_value=new_val,
                        actor_type='seller',
                        description=description,
                    )

            # Sync total_investment / currency into the investment section's content_json
            investment_changed = (
                old_values.get('total_investment') != str(proposal.total_investment)
                or old_values.get('currency') != str(proposal.currency)
            )
            if investment_changed:
                sync_manual_investment(proposal)
    except ValueError as exc:
        return Response(
            {'client_email': [str(exc)]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    detail = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': True}
    )
    return Response(detail.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_proposal(request, proposal_id):
    """
    Delete a proposal and all related sections/groups (CASCADE).

    Proposals that were launched to the platform are referenced by
    ``ProjectPhase`` rows via ``on_delete=PROTECT`` (see accounts.models).
    Deleting such a proposal raises ProtectedError; we surface a clear
    409 instead of a 500 so the admin understands the link must be
    removed first.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    try:
        proposal.delete()
    except ProtectedError:
        if proposal.contract_snapshots.exists():
            return Response(
                {'error': 'No se puede eliminar esta propuesta porque conserva instantáneas permanentes de sus contratos.',
                 'code': 'contract_history_protected'},
                status=status.HTTP_409_CONFLICT,
            )
        phases = proposal.project_phases.select_related('project').all()
        phase_labels = [
            f'{ph.project.name} (fase {ph.order})'
            if getattr(ph, 'project', None) else f'fase {ph.order}'
            for ph in phases
        ]
        detail = (
            'No se puede eliminar esta propuesta porque está vinculada a un '
            'proyecto lanzado a la plataforma'
        )
        if phase_labels:
            detail += ': ' + ', '.join(phase_labels)
        detail += '. Desvincula el proyecto antes de eliminarla.'
        return Response(
            {'error': detail},
            status=status.HTTP_409_CONFLICT,
        )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_action(request):
    """
    Perform a batch action on multiple proposals.

    Payload: { "ids": [1, 2, 3], "action": "delete"|"expire"|"resend" }
    """
    ids = request.data.get('ids', [])
    action_type = request.data.get('action', '')

    if not ids or not isinstance(ids, list):
        return Response(
            {'detail': 'ids must be a non-empty list.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if action_type not in ('delete', 'expire', 'resend'):
        return Response(
            {'detail': 'action must be one of: delete, expire, resend.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    proposals = BusinessProposal.objects.filter(pk__in=ids)
    affected = 0

    if action_type == 'delete':
        affected = proposals.count()
        proposals.delete()

    elif action_type == 'expire':
        affected = proposals.exclude(status='expired').update(
            status='expired',
            expires_at=timezone.now(),
        )

    elif action_type == 'resend':
        from content.services.proposal_service import ProposalService
        resendable = list(
            proposals.filter(status__in=['sent', 'viewed'], client_email__gt='')
        )
        missing_message = [
            p for p in resendable if not (p.email_intro or '').strip()
        ]
        if missing_message:
            titles = ', '.join(p.title for p in missing_message[:3])
            if len(missing_message) > 3:
                titles += f' y {len(missing_message) - 3} más'
            return error_response(
                'Hay propuestas sin mensaje personalizado para el correo.',
                code='missing_email_intro',
                hint=f'Completa el mensaje en la pestaña Correos: {titles}.',
            )
        for p in resendable:
            try:
                ProposalService.resend_proposal(p, acting_user=request.user)
                affected += 1
            except Exception:
                logger.exception('Bulk resend failed for proposal %s', p.id)

    return Response({'affected': affected, 'action': action_type})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def duplicate_proposal(request, proposal_id):
    """
    Duplicate a proposal: creates a deep copy with all its sections.
    The copy is reset to draft status with a clean lifecycle.
    """
    from content.services.proposal_service import (
        duplicate_proposal as duplicate_proposal_service,
    )

    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    new_proposal = duplicate_proposal_service(proposal)

    detail = ProposalDetailSerializer(
        new_proposal, context={'request': request, 'is_admin': True}
    )
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_proposal(request, proposal_id):
    """
    Mark proposal as SENT, set sent_at, schedule Huey reminder task.
    Requires client_email and the personalized email message to be set.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    from content.services.proposal_service import ProposalService
    try:
        delivery = ProposalService.send_proposal(
            proposal, acting_user=request.user,
        )
    except ValueError as e:
        return error_response_from_exc(e)

    ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type='sent',
        actor_type='seller',
        description=f'Proposal sent to {proposal.client_email}.',
    )

    return _proposal_admin_response(request, proposal, delivery)


# Templates exposed to the panel preview UI (client-facing only).
PREVIEWABLE_TEMPLATE_KEYS = frozenset({
    'proposal_sent_client',
    'proposal_multi_sent_client',
    'proposal_documents_sent',
    'branded_email',
    'proposal_accepted_client',
    'proposal_finished_client',
    'proposal_rejected_client',
    'proposal_negotiation_confirmation',
    'proposal_reminder',
    'proposal_urgency',
    'proposal_urgency_no_discount',
    'proposal_reengagement',
    'proposal_abandonment_followup',
    'proposal_investment_interest_followup',
    'proposal_scheduled_followup',
})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def preview_proposal_email(request, proposal_id):
    """Render an email template against this proposal's context.

    Body (all optional, overrides the saved proposal data for the preview only):
        {
            "template_key": "proposal_sent_client",
            "email_intro": "Qué resuelve esta propuesta para el cliente.",
            "email_features": ["...", ...],
            "email_method_phases": [{...}, ...],
            "email_signed_by": "gustavo" | "carlos"
        }

    Returns ``text/html`` with the fully rendered email so it can be iframe'd.
    """
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from content.services.proposal_email_service import (
        ProposalEmailService,
        _build_design_context,
    )
    from content.utils import format_cop_email

    template_key = request.data.get('template_key') or 'proposal_sent_client'
    if template_key not in PREVIEWABLE_TEMPLATE_KEYS:
        return Response(
            {'error': f'template_key inválido: {template_key}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    # Apply unsaved overrides in-memory so the preview matches the current panel state.
    overrides = {}
    if 'email_features' in request.data:
        overrides['email_features'] = request.data.get('email_features') or []
    if 'email_method_phases' in request.data:
        overrides['email_method_phases'] = request.data.get('email_method_phases') or []
    if 'email_signed_by' in request.data:
        overrides['email_signed_by'] = request.data.get('email_signed_by') or 'gustavo'
    if 'email_intro' in request.data:
        overrides['email_intro'] = request.data.get('email_intro') or ''
    for k, v in overrides.items():
        setattr(proposal, k, v)

    # Build a context dict that mirrors what each send_* method produces.
    base_context = {
        'client_name': proposal.client_name,
        'proposal_url': proposal.public_url,
        'days_remaining': proposal.days_remaining,
        'expires_at': proposal.expires_at,
        'total_investment': format_cop_email(proposal.total_investment),
        'currency': proposal.currency,
        'title': proposal.title,
        'discount_percent': proposal.discount_percent,
        'discounted_investment': format_cop_email(
            proposal.total_investment * (Decimal(100 - proposal.discount_percent) / Decimal(100))
        ) if proposal.discount_percent else '',
    }
    # Initial-email helpers (payment_options, total_duration, payment_summary, email_intro).
    base_context.update(ProposalEmailService._build_initial_email_context(proposal))
    # Design helpers (signature, features, phases, reference).
    base_context.update(_build_design_context(proposal))
    # EmailTemplateConfig overrides (greeting, body, cta_text, etc.).
    resolved = ProposalEmailService._resolve_content(template_key, base_context)
    base_context.update(resolved)

    # Branded email expects sections/footer/attachment_names; supply placeholders so the
    # preview shows the layout even if those weren't passed by the panel.
    base_context.setdefault('greeting', f'Hola {proposal.client_name},')
    base_context.setdefault('sections', ['Cuerpo de ejemplo para preview del correo libre.'])
    base_context.setdefault('footer', '')
    base_context.setdefault('attachment_names', [])
    # Multi-proposal expects a list of "phases" with per-proposal urls.
    base_context.setdefault('phases', [])
    base_context.setdefault('phases_count', 0)
    base_context.setdefault('document_descriptions', [])
    # Acceptance/finished use these for the project card.
    base_context.update(ProposalEmailService._build_platform_context(proposal))

    html = render_to_string(f'emails/{template_key}.html', base_context)
    return HttpResponse(html, content_type='text/html; charset=utf-8')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_multi_proposal(request, proposal_id):
    """
    Send a single email referencing 2+ proposals from the same client.

    Body:
        { "proposal_ids": [12, 15, 18] }

    The path proposal is implicitly added if missing. All proposals must
    belong to the same client.
    """
    primary = get_object_or_404(BusinessProposal, pk=proposal_id)

    raw_ids = request.data.get('proposal_ids') or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return error_response(
            'Selecciona al menos una propuesta para el envío conjunto.',
            code='invalid_proposal_ids',
        )

    try:
        ids = list(dict.fromkeys(int(x) for x in raw_ids))
    except (TypeError, ValueError):
        return error_response(
            'La lista de propuestas contiene valores no válidos.',
            code='invalid_proposal_ids',
        )

    MAX_PROPOSALS_PER_EMAIL = 10
    if len(ids) > MAX_PROPOSALS_PER_EMAIL:
        return error_response(
            f'No se pueden enviar más de {MAX_PROPOSALS_PER_EMAIL} propuestas en un solo correo.',
            code='too_many_proposals',
        )

    if primary.client_id is None:
        return error_response(
            'La propuesta principal no tiene cliente asociado.',
            code='missing_client',
            hint='Asocia un cliente a la propuesta antes de enviarla.',
        )

    selected = list(
        BusinessProposal.objects
        .filter(pk__in=ids, client_id=primary.client_id)
        .prefetch_related('sections')
    )
    if len(selected) != len(ids):
        return error_response(
            'Algunas propuestas no existen o no pertenecen al mismo cliente.',
            code='invalid_proposal_selection',
        )

    by_id = {p.id: p for p in selected}
    seen = set()
    ordered = []
    if primary.id not in by_id:
        ordered.append(primary)
        seen.add(primary.id)
    for pid in ids:
        if pid in by_id and pid not in seen:
            ordered.append(by_id[pid])
            seen.add(pid)

    if len(ordered) < 2:
        return error_response(
            'Se requieren al menos 2 propuestas para un envío conjunto.',
            code='not_enough_proposals',
        )

    from content.services.proposal_service import ProposalService
    try:
        result = ProposalService.send_multi_proposals(
            ordered, acting_user=request.user,
        )
    except ValueError as e:
        return error_response_from_exc(e)

    transitions = result.get('transitions', {})
    titles = ', '.join(p.title for p in ordered)
    for proposal in ordered:
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='sent',
            actor_type='seller',
            description=(
                f'Multi-envío a {primary.client_email}: {len(ordered)} '
                f'propuestas ({titles}). Acción: {transitions.get(proposal.id, "")}.'
            ),
        )

    return _proposal_admin_response(request, primary, result)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def toggle_proposal_active(request, proposal_id):
    """
    Toggle a proposal's is_active flag.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    proposal.is_active = not proposal.is_active
    proposal.save(update_fields=['is_active'])

    detail = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': True}
    )
    return Response(detail.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_proposal_status(request, proposal_id):
    """
    Inline status change from the panel (admin mode).
    Body: { "status": "expired" }

    Any known status is accepted; side effects (client email on
    draft→sent, finished confirmation, onboarding on accept) fire only on
    natural transitions per ``ALLOWED_TRANSITIONS`` — forced jumps just
    save + log. Error codes: ``invalid_status`` / ``same_status``.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    try:
        delivery, _forced = proposal_status_service.change_status(
            proposal,
            request.data.get('status'),
            source='inline',
            acting_user_id=request.user.id,
        )
    except ValueError as e:  # includes ProposalActionError
        return error_response_from_exc(e)

    return _proposal_admin_response(request, proposal, delivery)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def launch_to_platform(request, proposal_id):
    """Compatibility route; an explicit review replaces automatic provisioning."""
    from content.views.proposal_approval import decode_payload
    from content.services.proposal_approval_service import review_proposal
    get_object_or_404(BusinessProposal, pk=proposal_id)
    payload = decode_payload(request)
    payload.setdefault('action', 'confirm')
    if payload['action'] != 'retry':
        payload.setdefault('accept_proposal', False)
    files = request.FILES.getlist('custom_files[]') or request.FILES.getlist('custom_files')
    return Response(review_proposal(proposal_id, payload, actor=request.user, files=files))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def proposal_scorecard(request, proposal_id):
    """
    Pre-send scorecard: returns a 1-10 completeness score with
    individual checks and blockers for a proposal.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    checks = []

    # 1. Client email
    has_email = bool(proposal.client_email)
    checks.append({
        'key': 'client_email',
        'label': 'Email del cliente',
        'passed': has_email,
        'blocker': True,
    })

    # 2. Client name
    has_name = bool(proposal.client_name)
    checks.append({
        'key': 'client_name',
        'label': 'Nombre del cliente',
        'passed': has_name,
        'blocker': True,
    })

    # 3. Personalized message for the initial/resend email
    has_email_intro = bool((proposal.email_intro or '').strip())
    checks.append({
        'key': 'email_intro',
        'label': 'Mensaje personalizado del correo',
        'passed': has_email_intro,
        'blocker': True,
    })

    # 4. Investment > 0
    has_investment = bool(proposal.total_investment and proposal.total_investment > 0)
    checks.append({
        'key': 'total_investment',
        'label': 'Inversión total > $0',
        'passed': has_investment,
        'blocker': True,
    })

    # 5. Expiration date in the future
    has_expiration = bool(
        proposal.expires_at and proposal.expires_at > timezone.now()
    )
    checks.append({
        'key': 'expires_at',
        'label': 'Fecha de expiración futura',
        'passed': has_expiration,
        'blocker': True,
    })

    # 6. At least 1 enabled section
    enabled_sections = proposal.sections.filter(is_enabled=True).count()
    has_sections = enabled_sections >= 1
    checks.append({
        'key': 'enabled_sections',
        'label': 'Al menos 1 sección habilitada',
        'passed': has_sections,
        'blocker': True,
    })

    # 7. Title set
    has_title = bool(proposal.title and proposal.title.strip())
    checks.append({
        'key': 'title',
        'label': 'Título de la propuesta',
        'passed': has_title,
        'blocker': False,
    })

    # 7. Sections with content (non-empty content_json)
    import json as _json
    sections_with_content = 0
    for sec in proposal.sections.filter(is_enabled=True):
        cj = sec.content_json
        if isinstance(cj, str):
            try:
                cj = _json.loads(cj)
            except (ValueError, TypeError):
                cj = {}
        if cj and cj != {}:
            sections_with_content += 1
    content_ratio = (
        sections_with_content / enabled_sections if enabled_sections > 0 else 0
    )
    checks.append({
        'key': 'sections_content',
        'label': f'Secciones con contenido ({sections_with_content}/{enabled_sections})',
        'passed': content_ratio >= 0.5,
        'blocker': False,
    })

    # 8. Client phone (useful for WhatsApp follow-ups)
    has_phone = bool(proposal.client_phone and proposal.client_phone.strip())
    checks.append({
        'key': 'client_phone',
        'label': 'Teléfono del cliente (para WhatsApp)',
        'passed': has_phone,
        'blocker': False,
    })

    # 9. Language configured
    has_language = bool(proposal.language)
    checks.append({
        'key': 'language',
        'label': 'Idioma configurado',
        'passed': has_language,
        'blocker': False,
    })

    # 10. Discount configured (optional quality check)
    has_discount_or_na = True  # Not a blocker
    checks.append({
        'key': 'discount_review',
        'label': 'Descuento revisado',
        'passed': has_discount_or_na,
        'blocker': False,
    })

    # 11. Payment options set (read from investment section content_json)
    investment_section = proposal.sections.filter(
        section_type='investment', is_enabled=True
    ).first()
    inv_cj = {}
    if investment_section:
        inv_cj = investment_section.content_json or {}
        if isinstance(inv_cj, str):
            try:
                inv_cj = _json.loads(inv_cj)
            except (ValueError, TypeError):
                inv_cj = {}
    has_payment = bool(inv_cj.get('paymentOptions'))
    checks.append({
        'key': 'payment_options',
        'label': 'Opciones de pago definidas',
        'passed': has_payment,
        'blocker': False,
    })

    # 10. Timeline / estimated weeks (read from investment section content_json)
    estimated_weeks = inv_cj.get('estimatedWeeks', 0)
    try:
        estimated_weeks = int(estimated_weeks)
    except (ValueError, TypeError):
        estimated_weeks = 0
    has_timeline = estimated_weeks > 0
    checks.append({
        'key': 'estimated_weeks',
        'label': 'Tiempo estimado definido',
        'passed': has_timeline,
        'blocker': False,
    })

    # Compute score (1-10)
    passed_count = sum(1 for c in checks if c['passed'])
    score = max(1, round(passed_count / len(checks) * 10))
    blockers = [c for c in checks if c['blocker'] and not c['passed']]

    return Response({
        'score': score,
        'checks': checks,
        'blockers': blockers,
        'can_send': len(blockers) == 0,
        'total_checks': len(checks),
        'passed_checks': passed_count,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def resend_proposal(request, proposal_id):
    """
    Re-send a proposal: reset lifecycle timers, keep existing expires_at,
    and re-schedule reminder emails.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    serializer = ProposalResendSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            'No se pudo validar el mensaje del reenvío.',
            code='invalid_resend_payload',
            errors=serializer.errors,
        )

    from content.services.proposal_service import ProposalService
    try:
        delivery = ProposalService.resend_proposal(
            proposal,
            acting_user=request.user,
            email_intro=serializer.validated_data.get('email_intro'),
        )
    except ValueError as e:
        return error_response_from_exc(e)

    ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type='resent',
        actor_type='seller',
        description=f'Proposal re-sent to {proposal.client_email}.',
    )

    return _proposal_admin_response(request, proposal, delivery)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_proposal_section(request, section_id):
    """
    Update a section's content_json, title, order, is_enabled, etc.

    Response shape (admin panel only):
        {
          "section": <ProposalSectionDetailSerializer>,
          "proposal_totals": {
              "total_investment": "...",
              "effective_total_investment": "..."
          },
          "investment_section": <ProposalSectionDetailSerializer>  # only when
              # the saved section is functional_requirements and the auto
              # resync mutated the investment section's content_json
        }

    The proposal-level totals are recomputed here so the admin's General tab
    badge "Cliente ve: $X" stays in sync without an extra refetch round-trip.
    """
    section = get_object_or_404(ProposalSection.objects.select_related('proposal'), pk=section_id)
    serializer = ProposalSectionUpdateSerializer(
        section, data=request.data, partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()

    investment_section = None
    if section.section_type == ProposalSection.SectionType.FUNCTIONAL_REQUIREMENTS:
        sync_manual_investment(section.proposal)
        investment_section = section.proposal.sections.filter(
            section_type=ProposalSection.SectionType.INVESTMENT,
        ).first()

    section.proposal.refresh_from_db()

    from content.serializers.proposal import ProposalSectionDetailSerializer
    payload = {
        'section': ProposalSectionDetailSerializer(section).data,
        'proposal_totals': {
            'total_investment': str(section.proposal.total_investment),
            'effective_total_investment': str(_effective_total_for_proposal(section.proposal)),
        },
    }
    if investment_section is not None:
        payload['investment_section'] = ProposalSectionDetailSerializer(investment_section).data
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def preview_sync_section(request, section_id):
    """
    Compute a read-only diff between the submitted content_json and the current
    project state. Does not save anything.

    Returns has_project=False if the proposal has no linked project yet.
    """
    from django.db import transaction as _tx
    from accounts.models import Project
    from accounts.services.technical_resources_sync import (
        compute_sync_diff,
        filtered_technical_doc_for_sync,
    )

    section = get_object_or_404(ProposalSection, pk=section_id)
    if section.section_type != ProposalSection.SectionType.TECHNICAL_DOCUMENT:
        return Response({'detail': 'Not a technical_document section.'}, status=status.HTTP_400_BAD_REQUEST)

    content_json = request.data.get('content_json')
    if not isinstance(content_json, dict):
        return Response({'detail': 'content_json must be a dict.'}, status=status.HTTP_400_BAD_REQUEST)

    proposal = section.proposal
    if not proposal.platform_onboarding_completed_at or not proposal.deliverable_id:
        return Response({'ok': True, 'has_project': False})

    deliverable = proposal.deliverable
    project = Project.objects.select_related('client').get(pk=deliverable.project_id)

    diff = compute_sync_diff(
        project, filtered_technical_doc_for_sync(proposal, content_json), proposal=proposal,
    )

    return Response({
        'ok': True,
        'has_project': True,
        'project': {
            'id': project.id,
            'name': project.name,
            'client_email': project.client.email,
        },
        'deliverable': {
            'id': deliverable.id,
            'title': deliverable.title,
        },
        'diff': diff,
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def apply_sync_section(request, section_id):
    """
    Save the submitted content_json to the section and sync project resources
    (with soft-deletion of records removed from the JSON). Transactional.
    """
    from django.db import transaction as _tx
    from accounts.services.technical_resources_sync import sync_technical_resources_for_deliverable

    section = get_object_or_404(ProposalSection, pk=section_id)
    if section.section_type != ProposalSection.SectionType.TECHNICAL_DOCUMENT:
        return Response({'detail': 'Not a technical_document section.'}, status=status.HTTP_400_BAD_REQUEST)

    content_json = request.data.get('content_json')
    if not isinstance(content_json, dict):
        return Response({'detail': 'content_json must be a dict.'}, status=status.HTTP_400_BAD_REQUEST)

    proposal = section.proposal
    if not proposal.platform_onboarding_completed_at or not proposal.deliverable_id:
        return Response(
            {'detail': 'Esta propuesta no tiene proyecto asociado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from content.serializers.proposal import ProposalSectionDetailSerializer

    with _tx.atomic():
        serializer = ProposalSectionUpdateSerializer(
            section, data={'content_json': content_json}, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        deliverable = proposal.deliverable
        sync_result = sync_technical_resources_for_deliverable(
            deliverable, request.user, delete_removed=True,
        )

    return Response({
        **sync_result,
        'section': ProposalSectionDetailSerializer(section).data,
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_reorder_sections(request, proposal_id):
    """
    Reorder sections for a proposal.
    Body: { "sections": [{"id": 1, "order": 0}, {"id": 2, "order": 1}, ...] }
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    sections_data = request.data.get('sections', [])

    if not isinstance(sections_data, list):
        return error_response(
            'El campo "sections" debe ser una lista de objetos {id, order}.',
            code='invalid_sections_payload',
        )

    section_ids = {s['id'] for s in sections_data if 'id' in s}
    sections_qs = proposal.sections.filter(id__in=section_ids)
    sections_map = {s.id: s for s in sections_qs}

    updated = []
    for item in sections_data:
        section = sections_map.get(item.get('id'))
        if section and 'order' in item:
            section.order = item['order']
            updated.append(section)

    if updated:
        ProposalSection.objects.bulk_update(updated, ['order'])

    return Response({'reordered': len(updated)}, status=status.HTTP_200_OK)


def _proposal_totals_payload(proposal):
    """Totals block returned by every section-mutation endpoint."""
    return {
        'total_investment': str(proposal.total_investment),
        'effective_total_investment': str(_effective_total_for_proposal(proposal)),
    }


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_proposal_section(request, proposal_id):
    """Add a section of a given type to a proposal, seeded from defaults.

    Body: {"section_type": str, "title"?: str}
    → 201 {"section": <ProposalSectionDetailSerializer>, "proposal_totals": {...}}
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    section_type = request.data.get('section_type')
    if not section_type or not isinstance(section_type, str):
        return error_response('Debes indicar el tipo de sección.', code='missing_section_type')
    title = request.data.get('title') or None

    from content.services.proposal_service import create_section_for_proposal
    try:
        with transaction.atomic():
            section = create_section_for_proposal(proposal, section_type, title=title)
            log_proposal_change(
                proposal,
                'updated',
                actor_type='seller',
                field_name='sections',
                description=f'Sección «{section.title}» agregada desde el editor.',
            )
    except ProposalActionError as exc:
        return error_response_from_exc(exc)

    from content.serializers.proposal import ProposalSectionDetailSerializer
    return Response(
        {
            'section': ProposalSectionDetailSerializer(section).data,
            'proposal_totals': _proposal_totals_payload(proposal),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_proposal_section(request, section_id):
    """Delete a proposal section from the editor.

    → 200 {"deleted": true, "section_type": str, "proposal_totals": {...}}
    """
    section = get_object_or_404(
        ProposalSection.objects.select_related('proposal'), pk=section_id,
    )
    proposal = section.proposal

    from content.services.proposal_service import delete_section_from_proposal
    try:
        with transaction.atomic():
            info = delete_section_from_proposal(section)
            log_proposal_change(
                proposal,
                'updated',
                actor_type='seller',
                field_name='sections',
                description=f'Sección «{info["title"]}» eliminada desde el editor.',
            )
    except ProposalActionError as exc:
        return error_response_from_exc(exc)

    return Response(
        {
            'deleted': True,
            'section_type': info['section_type'],
            'proposal_totals': _proposal_totals_payload(proposal),
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Auth check endpoint (for Nuxt admin middleware)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicProposalActionThrottle])
def respond_to_proposal(request, proposal_uuid):
    """
    Client accepts, rejects, or negotiates a proposal.
    Body: { "action": "accepted" | "rejected" | "negotiating", "reason": "...", "comment": "..." }

    Updates proposal status, stores rejection feedback, and sends emails:
    - Acceptance: confirmation to client + notification to team
    - Rejection: thank-you to client + notification with reason to team
    - Negotiating: confirmation to client + notification to team with comment
    """
    proposal = get_object_or_404(BusinessProposal, uuid=proposal_uuid)

    if proposal.status not in ('sent', 'viewed'):
        return error_response(
            'Esta propuesta no puede recibir respuestas en su estado actual.',
            code='invalid_status',
        )

    action = request.data.get('action')
    if action not in ('accepted', 'rejected', 'negotiating'):
        return error_response(
            'Acción inválida. Debe ser "accepted", "rejected" o "negotiating".',
            code='invalid_action',
        )

    comment = request.data.get('comment', '')
    condition = request.data.get('condition', '').strip()

    # Status mutation + audit trail commit or roll back together. Email
    # sends and onboarding enqueue stay outside so the transaction is
    # never held open through SMTP.
    with transaction.atomic():
        proposal.status = action
        proposal.responded_at = timezone.now()
        update_fields = ['status', 'responded_at']

        if action == 'rejected':
            proposal.rejection_reason = request.data.get('reason', '')
            proposal.rejection_comment = request.data.get('comment', '')
            update_fields.extend(['rejection_reason', 'rejection_comment'])

        # 3.6 — Auto-pause follow-ups on client response
        if not proposal.automations_paused:
            proposal.automations_paused = True
            update_fields.append('automations_paused')

        proposal.save(update_fields=update_fields)

        # Log the response event
        description = f'Client {action} the proposal.'
        if action == 'rejected' and proposal.rejection_reason:
            description += f' Reason: {proposal.rejection_reason}'
        if action == 'negotiating' and comment:
            description += f' Comment: {comment[:500]}'
        if action == 'accepted' and condition:
            description += f' Condition: {condition[:500]}'
        log_proposal_change(
            proposal,
            action,
            actor_type='client',
            description=description,
        )

        # Log conditional acceptance separately for easy querying
        if action == 'accepted' and condition:
            log_proposal_change(
                proposal,
                'cond_accepted',
                actor_type='client',
                description=f'Conditional acceptance: {condition[:500]}',
            )

        # Log automation pause
        log_proposal_change(
            proposal,
            'note',
            actor_type='system',
            description=f'Automations paused: client responded with "{action}".',
        )

    from content.services.proposal_email_service import ProposalEmailService
    ProposalEmailService.send_response_notification(proposal, action)

    if action == 'rejected':
        ProposalEmailService.send_rejection_thank_you(proposal)
        # Schedule re-engagement email 48h later if rejection is budget-related
        _schedule_reengagement_if_budget(proposal)
    elif action == 'negotiating':
        ProposalEmailService.send_negotiation_notification(proposal, comment)
        ProposalEmailService.send_negotiation_confirmation(proposal)
    elif action == 'accepted':
        ProposalEmailService.send_acceptance_confirmation(proposal)
        # Acceptance waits for explicit internal project review.

    return Response(
        {'status': action, 'message': f'Proposal {action} successfully.'},
        status=status.HTTP_200_OK,
    )


def _schedule_reengagement_if_budget(proposal):
    """
    Schedule a re-engagement email 48h after rejection when the reason
    is budget-related. Uses Huey's delay scheduling via the tasks module.
    """
    budget_keywords = (
        'presupuesto', 'budget', 'alto', 'precio', 'price', 'costo', 'cost',
    )
    reason = (proposal.rejection_reason or '').lower()
    if not any(kw in reason for kw in budget_keywords):
        return
    try:
        from content.tasks import send_rejection_reengagement
        send_rejection_reengagement.schedule(args=[proposal.id], delay=172800)
        logger.info(
            'Scheduled re-engagement email for proposal %s in 48h',
            proposal.uuid,
        )
    except Exception:
        logger.exception(
            'Failed to schedule re-engagement for proposal %s',
            proposal.uuid,
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicProposalActionThrottle])
def comment_on_proposal(request, proposal_uuid):
    """
    Client submits a negotiation comment before deciding.
    Body: { "comment": "..." }

    Logs the comment in ProposalChangeLog and notifies the sales team.
    Does not change proposal status — client is in negotiation, not rejecting.
    """
    proposal = get_object_or_404(BusinessProposal, uuid=proposal_uuid)

    if proposal.status not in ('sent', 'viewed', 'rejected'):
        return error_response(
            'Esta propuesta no puede recibir comentarios en su estado actual.',
            code='invalid_status',
        )

    comment = (request.data.get('comment') or '').strip()
    if not comment:
        return error_response(
            'El comentario no puede estar vacío.',
            code='empty_comment',
        )

    log_proposal_change(
        proposal,
        'commented',
        actor_type='client',
        description=f'Client left a comment: {comment[:500]}',
    )

    from content.services.proposal_email_service import ProposalEmailService
    ProposalEmailService.send_comment_notification(proposal, comment)

    return Response(
        {'message': 'Comment received. We will be in touch soon.'},
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_admin_auth(request):
    """
    Returns 200 if user is authenticated staff, 403 otherwise.
    Used by the Nuxt admin middleware to verify session auth.
    """
    if not request.user.is_staff:
        return Response(
            {'error': 'Not authorized'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return Response(
        {
            'user': {
                'username': request.user.username,
                'is_staff': True,
                'is_superuser': request.user.is_superuser,
            }
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Section engagement tracking (public)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TrackingAnonThrottle])
def track_proposal_engagement(request, proposal_uuid):
    """
    Validate and persist one visible-browser engagement heartbeat.

    The first accepted heartbeat is the canonical commercial "view". GET of
    the public document never mutates view counters or notification state.
    """
    proposal = get_object_or_404(
        BusinessProposal, uuid=proposal_uuid, is_active=True
    )

    # Don't track engagement for draft proposals
    if proposal.status == BusinessProposal.Status.DRAFT:
        return Response({'status': 'skipped'}, status=status.HTTP_200_OK)

    # Skip tracking for admin staff (detect via Django session cookie)
    if is_staff_session(request):
        return Response({'status': 'skipped'}, status=status.HTTP_200_OK)

    from content.serializers.proposal_tracking import ProposalEngagementSerializer
    from content.services.proposal_tracking_service import ProposalTrackingService

    serializer = ProposalEngagementSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    result = ProposalTrackingService.record(
        proposal_id=proposal.id,
        payload=serializer.validated_data,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        referrer=request.query_params.get('ref', ''),
    )
    if result['first_view_confirmed']:
        # Queueing is deliberately outside the DB transaction. A broker outage
        # leaves the durable state as pending for the periodic reconciler.
        try:
            from content.tasks import notify_first_view

            notify_first_view(proposal.id)
        except Exception:
            logger.exception(
                'Failed to queue first-view notification for proposal %s',
                proposal.uuid,
            )

    return Response(
        {
            'status': 'ok',
            'view_event_id': result['view_event_id'],
            'is_final': result['finalized'],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TrackingAnonThrottle])
def track_calculator_interaction(request, proposal_uuid):
    """Retired: client interests cannot mutate contracted scope or pricing."""
    return Response({'error': 'The investment calculator has been retired.',
                     'code': 'calculator_retired'}, status=status.HTTP_410_GONE)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TrackingAnonThrottle])
def track_requirement_click(request, proposal_uuid):
    """
    Track when a client clicks on a functional requirements group card.

    Payload: { "group_id": "...", "group_title": "..." }
    """
    import json as _json
    from datetime import timedelta

    proposal = get_object_or_404(
        BusinessProposal, uuid=proposal_uuid, is_active=True,
    )

    # Skip tracking for admin staff
    if is_staff_session(request):
        return Response({'status': 'skipped'}, status=status.HTTP_200_OK)

    group_id = request.data.get('group_id', '')
    group_title = request.data.get('group_title', '')

    if not group_id and not group_title:
        return Response(
            {'error': 'group_id or group_title is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Deduplicate: skip if same group clicked in last 60 seconds
    recent = ProposalChangeLog.objects.filter(
        proposal=proposal,
        change_type='req_clicked',
        created_at__gte=timezone.now() - timedelta(seconds=60),
        description__contains=str(group_id),
    ).exists()

    if not recent:
        ProposalChangeLog.objects.create(
            proposal=proposal,
            change_type='req_clicked',
            actor_type='client',
            description=_json.dumps({
                'group_id': group_id,
                'group_title': group_title,
            }),
        )

    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([MagicLinkRequestThrottle])
def request_magic_link(request):
    """
    Magic link re-access: client provides their email and receives
    a link to their most recent active proposal.

    Rate-limited: 1 request per email per 5 minutes (via simple DB check).
    Body: { "email": "client@example.com" }
    """
    from datetime import timedelta

    email = (request.data.get('email') or '').strip().lower()
    if not email:
        return Response(
            {'error': 'Email is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Rate limiting: check EmailLog for recent magic_link sends to this email
    five_min_ago = timezone.now() - timedelta(minutes=5)
    try:
        from content.models import EmailLog
        recent = EmailLog.objects.filter(
            template_key='magic_link',
            recipient=email,
            delivery_role=EmailLog.DeliveryRole.PRIMARY,
            sent_at__gte=five_min_ago,
        ).exists()
        if recent:
            # Still return 200 to avoid email enumeration
            return Response({'status': 'ok'}, status=status.HTTP_200_OK)
    except Exception:
        pass

    # Find proposals for this email
    proposals = BusinessProposal.objects.filter(
        client_email__iexact=email,
        is_active=True,
    ).order_by('-created_at')[:5]

    if proposals.exists():
        try:
            from content.services.proposal_email_service import (
                ProposalEmailService,
            )
            ProposalEmailService.send_magic_link_email(email, list(proposals))
        except Exception:
            logger.exception(
                'Failed to send magic link email to %s', email,
            )

    # Always return 200 to prevent email enumeration
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Proposal sharing (public)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicProposalActionThrottle])
def create_share_link(request, proposal_uuid):
    """
    Create a tracked share link for a proposal.
    Body: { "name": "...", "email": "..." }

    Returns the share link UUID for constructing the shared URL.
    Notifies the sales team about the sharing event.
    """
    proposal = get_object_or_404(
        BusinessProposal, uuid=proposal_uuid, is_active=True
    )

    name = request.data.get('name', '').strip()
    email = request.data.get('email', '').strip()

    if not name:
        return Response(
            {'error': 'Name is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    share_link = ProposalShareLink.objects.create(
        proposal=proposal,
        shared_by_name=name,
        shared_by_email=email,
    )

    try:
        from content.services.proposal_email_service import ProposalEmailService
        ProposalEmailService.send_share_notification(proposal, share_link)
    except Exception:
        logger.exception(
            'Failed to send share notification for proposal %s',
            proposal.uuid,
        )

    serializer = ProposalShareLinkSerializer(share_link)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def retrieve_shared_proposal(request, share_uuid):
    """
    Retrieve a proposal via a share link UUID.
    Optionally records viewer info from query params: ?name=&email=

    Increments the share link's view_count and sets first_viewed_at.
    Returns the full proposal detail (same as public view).
    """
    share_link = get_object_or_404(
        ProposalShareLink.objects
        .select_related('proposal__client__user')
        .prefetch_related('proposal__sections'),
        uuid=share_uuid,
    )
    proposal = share_link.proposal

    if not proposal.is_active:
        return error_response(
            'Esta propuesta no está disponible.',
            code='proposal_unavailable',
            status=status.HTTP_404_NOT_FOUND,
        )

    if proposal.is_expired:
        return error_response(
            'Esta propuesta ha expirado.',
            code='proposal_expired',
            status=status.HTTP_410_GONE,
        )

    # Internal previews return the public payload without mutating commercial
    # engagement or filling recipient details from an operator's query string.
    if not is_staff_session(request):
        viewer_name = request.query_params.get('name', '').strip()
        viewer_email = request.query_params.get('email', '').strip()
        update_fields = ['view_count']

        share_link.view_count += 1
        if not share_link.first_viewed_at:
            share_link.first_viewed_at = timezone.now()
            update_fields.append('first_viewed_at')
        if viewer_name and not share_link.recipient_name:
            share_link.recipient_name = viewer_name
            update_fields.append('recipient_name')
        if viewer_email and not share_link.recipient_email:
            share_link.recipient_email = viewer_email
            update_fields.append('recipient_email')

        share_link.save(update_fields=update_fields)

    serializer = ProposalDetailSerializer(
        proposal, context={'request': request, 'is_admin': False}
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Schedule follow-up (public — for rejected proposals)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicProposalActionThrottle])
def schedule_followup(request, proposal_uuid):
    """
    Schedule a follow-up reminder for a rejected proposal.
    Body: { "months": 3 }

    The client requests to be contacted again after N months.
    Schedules a Huey task for the follow-up email.
    """
    proposal = get_object_or_404(BusinessProposal, uuid=proposal_uuid)

    if proposal.status != 'rejected':
        return Response(
            {'error': 'Follow-up can only be scheduled for rejected proposals.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if proposal.followup_scheduled_at:
        return Response(
            {'error': 'A follow-up is already scheduled for this proposal.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    months = request.data.get('months', 3)
    try:
        months = int(months)
        if months < 1 or months > 12:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {'error': 'months must be an integer between 1 and 12.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from datetime import timedelta
    followup_at = timezone.now() + timedelta(days=months * 30)
    proposal.followup_scheduled_at = followup_at
    proposal.save(update_fields=['followup_scheduled_at'])

    # Schedule the Huey task
    try:
        from content.tasks import send_scheduled_followup
        delay_seconds = int((followup_at - timezone.now()).total_seconds())
        send_scheduled_followup.schedule(
            args=(proposal.id,), delay=delay_seconds
        )
        logger.info(
            'Scheduled followup for proposal %s in %d months',
            proposal.uuid, months,
        )
    except Exception:
        logger.exception(
            'Failed to schedule followup task for proposal %s',
            proposal.uuid,
        )

    ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type='updated',
        field_name='followup_scheduled_at',
        new_value=followup_at.isoformat(),
        actor_type='client',
        description=f'Client requested follow-up in {months} months.',
    )

    return Response(
        {'status': 'scheduled', 'followup_at': followup_at.isoformat()},
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Proposal analytics (admin only)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAdminUser])
def retry_first_view_notification(request, proposal_id):
    """Retry a failed first-view email without fabricating another view."""
    with transaction.atomic():
        proposal = get_object_or_404(
            BusinessProposal.objects.select_for_update(),
            pk=proposal_id,
        )
        state = BusinessProposal.FirstViewNotificationStatus
        if proposal.first_view_notification_status != state.FAILED:
            return Response(
                {'error': 'Only failed first-view notifications can be retried.'},
                status=status.HTTP_409_CONFLICT,
            )
        proposal.first_view_notification_status = state.PENDING
        proposal.first_view_notification_attempts = 0
        proposal.first_view_notification_attempted_at = None
        proposal.first_view_notification_last_error = ''
        proposal.save(update_fields=[
            'first_view_notification_status',
            'first_view_notification_attempts',
            'first_view_notification_attempted_at',
            'first_view_notification_last_error',
        ])

    try:
        from content.tasks import notify_first_view

        notify_first_view(proposal.id)
    except Exception:
        logger.exception(
            'Failed to queue manual first-view retry for proposal %s',
            proposal.uuid,
        )
    proposal.refresh_from_db()
    payload = ProposalDetailSerializer(
        proposal,
        context={'request': request, 'is_admin': True},
    ).data['first_view_notification']
    return Response(payload, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def retrieve_proposal_analytics(request, proposal_id):
    """
    Return aggregated section engagement analytics for a proposal.

    Includes: time-to-first-view, time-to-response, skipped sections,
    device breakdown, per-section engagement, session history, and
    change log timeline.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    return Response(build_proposal_analytics(proposal), status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Global KPI Dashboard (admin only)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def proposal_dashboard(request):
    """
    Return aggregated KPIs across all proposals for the admin dashboard.

    Includes: total counts by status, conversion rate, avg time metrics,
    avg proposal value by status, top rejection reasons, monthly trend.
    """
    return Response(build_dashboard(), status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# CSV Export (admin only)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_proposal_analytics_csv(request, proposal_id):
    """
    Export proposal analytics as a CSV file.

    Includes two sheets combined:
    1. Section engagement summary
    2. Session history
    """
    import csv
    from django.http import HttpResponse as DjangoHttpResponse
    from django.db.models import Sum, Count, Avg

    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    response = DjangoHttpResponse(content_type='text/csv')
    filename = f'analytics_{proposal.client_name}_{proposal.id}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Header
    writer.writerow([f'Analytics Report: {proposal.title}'])
    writer.writerow([f'Client: {proposal.client_name}'])
    writer.writerow([f'Status: {proposal.status}'])
    writer.writerow([f'Total Views: {proposal.view_count}'])
    writer.writerow([])

    # Section engagement
    writer.writerow(['--- SECTION ENGAGEMENT ---'])
    writer.writerow([
        'Note: technical_document + technical_document_public both belong to '
        '”detalle técnico” (vista panel vs vista pública).',
    ])
    writer.writerow([
        'Section Type', 'Metric group', 'Section Title', 'Visit Count',
        'Total Time (s)', 'Avg Time (s)',
    ])

    section_stats = (
        ProposalSectionView.objects
        .filter(view_event__proposal=proposal)
        .values('section_type')
        .annotate(
            visit_count=Count('id'),
            total_time=Sum('time_spent_seconds'),
            avg_time=Avg('time_spent_seconds'),
        )
        .order_by('section_type')
    )
    for stat in section_stats:
        latest_title = (
            ProposalSectionView.objects
            .filter(view_event__proposal=proposal, section_type=stat['section_type'])
            .order_by('-entered_at')
            .values_list('section_title', flat=True)
            .first()
        ) or stat['section_type']
        stype = stat['section_type']
        writer.writerow([
            stype,
            _csv_analytics_section_group(stype),
            latest_title,
            stat['visit_count'],
            round(stat['total_time'] or 0, 1),
            round(stat['avg_time'] or 0, 1),
        ])

    writer.writerow([])

    # Session history
    writer.writerow(['--- SESSION HISTORY ---'])
    writer.writerow(['Session ID', 'IP Address', 'Viewed At', 'Sections Viewed', 'Total Time (s)'])

    for event in proposal.view_events.order_by('-viewed_at')[:100]:
        sv = event.section_views.all()
        writer.writerow([
            event.session_id,
            event.ip_address or '',
            event.viewed_at.isoformat(),
            sv.count(),
            round(sum(s.time_spent_seconds for s in sv), 1),
        ])

    writer.writerow([])

    # Change log
    writer.writerow(['--- CHANGE LOG ---'])
    writer.writerow(['Date', 'Type', 'Field', 'Old Value', 'New Value', 'Description'])
    for log in proposal.change_logs.order_by('-created_at')[:100]:
        writer.writerow([
            log.created_at.isoformat(),
            log.change_type,
            log.field_name,
            log.old_value,
            log.new_value,
            log.description,
        ])

    return response


# ---------------------------------------------------------------------------
# Mini-CRM: client history (admin only)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_clients(request):
    """
    Return a list of unique clients with their full proposal history.

    Groups by a compound (resolved_email, client_name) key so that two
    different clients sharing the same contact email stay separated, while
    proposals with a blank email still merge into the email group of the
    same client_name.  When no email exists anywhere for a name, the email
    component of the key is empty and grouping falls back to name alone.
    Each client entry contains:
    - client_name, client_email
    - total_proposals, accepted, rejected, pending counts
    - last_status, last_sent_at
    - proposals: list of lightweight proposal summaries
    """
    proposals_qs = (
        BusinessProposal.objects
        .order_by('client_email', '-created_at')
        .values(
            'id', 'uuid', 'title', 'client_name', 'client_email',
            'status', 'total_investment', 'currency',
            'project_type', 'market_type',
            'sent_at', 'created_at', 'responded_at',
            'rejection_reason', 'rejection_comment',
            'view_count', 'expires_at',
        )
    )

    proposals_list = list(proposals_qs)

    # Pass 1: map each client name to its primary (first non-blank) email
    name_to_email: dict[str, str] = {}
    for p in proposals_list:
        email = (p['client_email'] or '').strip().lower()
        name = p['client_name'].strip().lower()
        if email and name not in name_to_email:
            name_to_email[name] = email

    # Pass 2: group by (resolved_email, name) — see docstring for rationale.
    clients: dict = {}
    for p in proposals_list:
        email = (p['client_email'] or '').strip().lower()
        name = p['client_name'].strip().lower()
        resolved_email = email if email else name_to_email.get(name, '')
        key = (resolved_email, name)

        if key not in clients:
            clients[key] = {
                'client_name': p['client_name'],
                'client_email': p['client_email'] or '',
                'proposals': [],
            }
        if email and not clients[key]['client_email']:
            clients[key]['client_email'] = p['client_email']
        clients[key]['proposals'].append(p)

    result = []
    for key, client in clients.items():
        props = client['proposals']
        statuses = [p['status'] for p in props]
        last = props[0]
        result.append({
            'client_key': f"{key[0]}|{key[1]}",
            'client_name': client['client_name'],
            'client_email': client['client_email'],
            'total_proposals': len(props),
            'accepted': statuses.count('accepted') + statuses.count('finished'),
            'rejected': statuses.count('rejected'),
            'pending': sum(1 for s in statuses if s in ('draft', 'sent', 'viewed')),
            'last_status': last['status'],
            'last_sent_at': last['sent_at'].isoformat() if last['sent_at'] else None,
            'proposals': [
                {
                    'id': p['id'],
                    'uuid': str(p['uuid']),
                    'title': p['title'],
                    'status': p['status'],
                    'project_type': p['project_type'] or '',
                    'market_type': p['market_type'] or '',
                    'total_investment': str(p['total_investment']),
                    'currency': p['currency'],
                    'view_count': p['view_count'],
                    'sent_at': p['sent_at'].isoformat() if p['sent_at'] else None,
                    'created_at': p['created_at'].isoformat() if p['created_at'] else None,
                    'responded_at': p['responded_at'].isoformat() if p['responded_at'] else None,
                    'rejection_reason': p['rejection_reason'] or '',
                    'rejection_comment': p['rejection_comment'] or '',
                    'expires_at': p['expires_at'].isoformat() if p['expires_at'] else None,
                }
                for p in props
            ],
        })

    # Sort by most recent activity first
    result.sort(key=lambda c: c['last_sent_at'] or '', reverse=True)

    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def log_activity(request, proposal_id):
    """
    Manually log a seller activity (call, meeting, follow-up, note) on a proposal.

    Body:
        change_type: one of 'call', 'meeting', 'followup', 'note'
        description: free-text description of the activity
    """
    proposal = get_object_or_404(BusinessProposal, id=proposal_id)
    change_type = request.data.get('change_type', '')
    description = request.data.get('description', '')

    allowed_types = ['call', 'meeting', 'followup', 'note']
    if change_type not in allowed_types:
        return Response(
            {'error': f'change_type must be one of: {", ".join(allowed_types)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not description.strip():
        return Response(
            {'error': 'description is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    log = ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type=change_type,
        actor_type='seller',
        description=description.strip(),
    )
    proposal.last_activity_at = timezone.now()
    proposal.save(update_fields=['last_activity_at'])

    return Response({
        'id': log.id,
        'change_type': log.change_type,
        'description': log.description,
        'created_at': log.created_at.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def proposal_alerts(request):
    """
    Return proposals that need attention:
    - Sent but not viewed after reminder_days
    - Viewed but not responded after urgency_reminder_days
    - Expiring within 3 days
    """
    return Response(build_proposal_alerts(), status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_proposal_alert(request):
    """
    Create a manual alert/reminder for a proposal.

    Payload: { proposal, alert_type, message, alert_date }
    """
    serializer = ProposalAlertSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def dismiss_proposal_alert(request, alert_id):
    """
    Dismiss an alert.

    - Manual alert: pass only path param `alert_id` (ProposalAlert ID).
    - Computed alert: pass payload
      { computed_alert_type, ref_date } and path param `alert_id` as proposal ID.
    """
    computed_alert_type = request.data.get('computed_alert_type')
    if computed_alert_type:
        if computed_alert_type not in _COMPUTED_ALERT_TYPES:
            return Response(
                {'error': 'Invalid computed_alert_type.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        proposal = get_object_or_404(BusinessProposal, pk=alert_id)
        ref_date = request.data.get('ref_date', '')
        marker_key = _computed_alert_key(proposal.id, computed_alert_type, ref_date)
        marker_message = f'{_COMPUTED_ALERT_DISMISS_PREFIX}{marker_key}'
        if not ProposalAlert.objects.filter(
            proposal=proposal,
            is_dismissed=True,
            message=marker_message,
        ).exists():
            ProposalAlert.objects.create(
                proposal=proposal,
                alert_type='custom',
                message=marker_message,
                alert_date=timezone.now(),
                is_dismissed=True,
            )
        return Response(
            {'status': 'dismissed', 'computed_alert_key': marker_key},
            status=status.HTTP_200_OK,
        )

    alert = get_object_or_404(ProposalAlert, pk=alert_id)
    alert.is_dismissed = True
    alert.save(update_fields=['is_dismissed'])
    return Response({'status': 'dismissed'}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Proposal Default Config
# ---------------------------------------------------------------------------

def _stale_defaults_response(config, base_updated_at):
    """Reject a defaults write based on a version that is no longer current.

    ``sections_json`` is saved wholesale from the snapshot the panel loaded when
    the page opened. A tab left open across a migration — or another admin's
    save — would otherwise rewind the stored defaults without a trace, and every
    proposal created afterwards would inherit the rewound content.

    The comparison is exact: the value travels back untouched from the one this
    endpoint serialised, so anything older than the stored ``updated_at`` means
    the caller never saw the current version.

    Returns a ``Response`` when the write must be refused, ``None`` when it may
    proceed.
    """
    parsed = parse_datetime(base_updated_at) if base_updated_at else None
    if parsed is None:
        return error_response(
            'La versión de referencia enviada no es una fecha válida.',
            code='invalid_base_updated_at',
            hint='Recarga la página de valores por defecto e intenta de nuevo.',
        )
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)

    if config.updated_at <= parsed:
        return None

    return error_response(
        'Los valores por defecto cambiaron desde que abriste esta página.',
        code='stale_defaults',
        hint=(
            'Recarga para ver la versión actual; si guardas ahora perderías '
            'esos cambios.'
        ),
        status=status.HTTP_409_CONFLICT,
    )


@api_view(['GET', 'PUT'])
@permission_classes([IsAdminUser])
def proposal_defaults(request):
    """
    GET  — Retrieve the default section config for a language.
           Falls back to the hardcoded defaults when no DB config exists.
    PUT  — Save (create or update) the default section config for a language.
           Callers that rewrite ``sections_json`` may send ``base_updated_at``
           (the ``updated_at`` they loaded) to get a 409 instead of silently
           overwriting a newer version.
    """
    from content.services.proposal_service import ProposalService

    lang = request.query_params.get('lang', request.data.get('language', 'es'))
    if lang not in ('es', 'en'):
        return Response(
            {'detail': 'lang must be "es" or "en".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == 'GET':
        config = ProposalDefaultConfig.objects.filter(language=lang).first()
        if config:
            serializer = ProposalDefaultConfigSerializer(config)
            return Response(serializer.data)
        # Return hardcoded defaults wrapped in the same shape. Hosting
        # values come from the model field defaults so they cannot drift
        # from what a freshly created config row would hold.
        hardcoded = ProposalService.get_hardcoded_defaults(lang)
        blank = ProposalDefaultConfig(language=lang)
        return Response({
            'id': None,
            'language': lang,
            'sections_json': hardcoded,
            'default_currency': ProposalDefaultConfig.Currency.COP,
            'default_total_investment': '0.00',
            'hosting_percent': blank.hosting_percent,
            'hosting_discount_nine_month': blank.hosting_discount_nine_month,
            'hosting_discount_semiannual': blank.hosting_discount_semiannual,
            'hosting_discount_quarterly': blank.hosting_discount_quarterly,
            'expiration_days': ProposalService.DEFAULT_EXPIRATION_DAYS,
            'reminder_days': 3,
            'urgency_reminder_days': 7,
            'default_discount_percent': 0,
            'default_slug_pattern': '{client_name}',
            'created_at': None,
            'updated_at': None,
        })

    # PUT
    config = ProposalDefaultConfig.objects.filter(language=lang).first()
    payload = dict(request.data)
    base_updated_at = payload.pop('base_updated_at', None)
    if config and base_updated_at and 'sections_json' in payload:
        stale = _stale_defaults_response(config, base_updated_at)
        if stale is not None:
            return stale
    payload['language'] = lang
    if 'sections_json' not in payload:
        if config:
            payload['sections_json'] = config.sections_json
        else:
            payload['sections_json'] = ProposalService.get_hardcoded_defaults(lang)
    if 'default_slug_pattern' not in payload and config:
        # Preserve the previously saved pattern when caller only updates
        # other fields (e.g. general form submits without touching the pattern).
        payload['default_slug_pattern'] = config.default_slug_pattern

    if config:
        serializer = ProposalDefaultConfigSerializer(config, data=payload)
    else:
        serializer = ProposalDefaultConfigSerializer(data=payload)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_proposal_defaults(request):
    """
    Delete the DB-backed default config for a language, reverting to hardcoded defaults.
    """
    lang = request.data.get('language', 'es')
    if lang not in ('es', 'en'):
        return Response(
            {'detail': 'language must be "es" or "en".'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    deleted_count, _ = ProposalDefaultConfig.objects.filter(language=lang).delete()
    return Response(
        {'status': 'reset', 'deleted': deleted_count > 0},
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# F11: Email Deliverability Dashboard
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def email_deliverability_dashboard(request):
    """
    Return aggregated email deliverability stats for the admin dashboard.

    Includes: total sent, success rate, per-template breakdown,
    daily trend (last 30 days), and recent failures.
    """
    from datetime import timedelta
    from django.db.models import Count, Q
    from django.db.models.functions import TruncDate
    from content.models import EmailLog

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    from content.services.email_log_service import representative_delivery_queryset

    all_logs = representative_delivery_queryset(EmailLog.objects.filter(
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    ))
    recent_logs = all_logs.filter(sent_at__gte=thirty_days_ago)

    # Overall counts
    total = recent_logs.count()
    by_status = dict(
        recent_logs.values('status')
        .annotate(count=Count('id'))
        .values_list('status', 'count')
    )
    sent_count = by_status.get('sent', 0) + by_status.get('delivered', 0)
    failed_count = by_status.get('failed', 0) + by_status.get('bounced', 0)
    success_rate = round((sent_count / total) * 100, 1) if total > 0 else 0

    # Per-template breakdown
    template_stats = list(
        recent_logs
        .values('template_key')
        .annotate(
            total=Count('id'),
            sent=Count('id', filter=Q(status__in=['sent', 'delivered'])),
            failed=Count('id', filter=Q(status__in=['failed', 'bounced'])),
        )
        .order_by('-total')
    )
    for stat in template_stats:
        stat['success_rate'] = (
            round((stat['sent'] / stat['total']) * 100, 1)
            if stat['total'] > 0 else 0
        )

    # Daily trend (last 30 days)
    daily_trend = list(
        recent_logs
        .annotate(date=TruncDate('sent_at'))
        .values('date')
        .annotate(
            total=Count('id'),
            sent=Count('id', filter=Q(status__in=['sent', 'delivered'])),
            failed=Count('id', filter=Q(status__in=['failed', 'bounced'])),
        )
        .order_by('date')
    )
    for entry in daily_trend:
        entry['date'] = entry['date'].isoformat()

    # Recent failures
    recent_failures = list(
        recent_logs.filter(status__in=['failed', 'bounced'])
        .order_by('-sent_at')[:20]
        .values(
            'template_key', 'recipient', 'status',
            'error_message', 'sent_at',
        )
    )
    for f in recent_failures:
        f['sent_at'] = f['sent_at'].isoformat()

    return Response({
        'total_emails_30d': total,
        'success_rate': success_rate,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'by_template': template_stats,
        'daily_trend': daily_trend,
        'recent_failures': recent_failures,
    }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Contract & document management endpoints
# ---------------------------------------------------------------------------

def _generate_and_save_contract_pdf(proposal, variant=contract_variants.COMBINED):
    """Generate one contract PDF of *variant* from contract_params and store it."""
    from content.services.contract_pdf_service import generate_contract_pdf, resolve_contract_content

    spec = contract_variants.VARIANTS[variant]
    content = resolve_contract_content(proposal, variant=variant)
    pdf_bytes = generate_contract_pdf(proposal, resolved_content=content)
    if not pdf_bytes:
        return
    from django.core.files.base import ContentFile
    from content.models import ProposalDocument
    from content.services.pdf_utils import safe_pdf_filename

    filename = safe_pdf_filename(
        spec.file_prefix,
        proposal.title or proposal.client_name,
        (proposal.created_at or timezone.now()).strftime('%Y-%m-%d'),
    )
    # No unique constraint backs "one document per variant", so reuse the newest.
    doc = contract_variants.contract_document(proposal, variant) or ProposalDocument(
        proposal=proposal, document_type=spec.doc_type,
        title=spec.document_title, is_generated=True,
    )
    doc.content_markdown = content['snapshot']
    doc.file.save(filename, ContentFile(pdf_bytes), save=True)


def _sync_active_contracts(proposal):
    """(Re)generate every contract of the active modality that has what it needs.

    Documents of the inactive modality are neither regenerated nor served, so
    they can never be sent stale; switching back regenerates them.
    """
    params = proposal.contract_params or {}
    for variant in contract_variants.active_variants(proposal):
        if contract_variants.can_generate(params, variant):
            _generate_and_save_contract_pdf(proposal, variant)


def _merged_contract_params(proposal, incoming):
    """Saved parameters overlaid with the request, so no edit drops another document's data."""
    saved = {
        key: value for key, value in (proposal.contract_params or {}).items()
        if value not in ('', None)
    }
    return {**saved, **(incoming if isinstance(incoming, dict) else {})}


def _service_conditions_error(proposal, params, variants):
    from content.services.proposal_hosting_terms import ServiceConditionsError, service_conditions_markdown

    if contract_variants.SERVICE in variants and contract_variants.can_generate(params, contract_variants.SERVICE):
        try:
            service_conditions_markdown(proposal)
        except ServiceConditionsError as exc:
            return Response({'error': str(exc), 'code': 'service_conditions_missing'}, status=422)
    return None


@api_view(['POST'])
@permission_classes([IsAdminUser])
def save_contract_and_negotiate(request, proposal_id):
    """Save contract params, generate contract PDF, and move status to negotiating."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    allowed = BusinessProposal.ALLOWED_TRANSITIONS.get(proposal.status, frozenset())
    if 'negotiating' not in allowed:
        return Response(
            {'error': f'Cannot transition from {proposal.status} to negotiating.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ContractParamsSerializer(
        data=_merged_contract_params(proposal, request.data.get('contract_params', {})),
        context={'modality': contract_variants.modality(proposal)},
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    error = _service_conditions_error(proposal, serializer.validated_data, contract_variants.active_variants(proposal))
    if error is not None:
        return error
    old_status = proposal.status
    proposal.contract_params = serializer.validated_data
    proposal.status = BusinessProposal.Status.NEGOTIATING
    proposal.save(update_fields=['contract_params', 'status', 'updated_at'])

    _sync_active_contracts(proposal)

    ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type='negotiating',
        field_name='status',
        old_value=old_status,
        new_value='negotiating',
        actor_type='seller',
        description='Status changed to negotiating with contract generation.',
    )

    detail = ProposalDetailSerializer(proposal, context={'request': request, 'is_admin': True})
    return Response(detail.data, status=status.HTTP_200_OK)


def _requested_variant(proposal, requested):
    """Resolve which contract a request is about: ``(variant, None)`` or ``(None, error)``.

    Without a name the single contract is implied; a split closing has two
    documents, so the caller must say which one. A document of the modality
    that was not chosen is never served, because it is not kept up to date.
    """
    active = contract_variants.active_variants(proposal)
    if not requested:
        if len(active) == 1:
            return active[0], None
        return None, Response(
            {'error': 'Indica qué contrato quieres: producto o servicio.', 'code': 'variant_required'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if requested not in contract_variants.VARIANTS:
        return None, Response(
            {'error': f'Contrato desconocido: {requested}.', 'code': 'invalid_variant'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if requested not in active:
        return None, Response(
            {
                'error': 'Ese contrato no corresponde a la modalidad de cierre elegida.',
                'code': 'inactive_variant',
            },
            status=status.HTTP_409_CONFLICT,
        )
    return requested, None


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_contract_params(request, proposal_id):
    """Update contract params and regenerate the contracts of the active modality.

    ``variant`` optionally names the document being generated or edited. It must
    belong to the chosen modality and adds its own rules: the service contract
    needs its three terms unless it uses a custom text.
    """
    with transaction.atomic():
        proposal = get_object_or_404(BusinessProposal.objects.select_for_update(), pk=proposal_id)
        requested = request.data.get('variant') or None
        if requested:
            _variant, error = _requested_variant(proposal, requested)
            if error:
                return error

        serializer = ContractParamsSerializer(
            data=_merged_contract_params(proposal, request.data.get('contract_params', {})),
            context={'modality': contract_variants.modality(proposal), 'variant': requested},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        error = _service_conditions_error(proposal, serializer.validated_data, contract_variants.active_variants(proposal))
        if error is not None:
            return error
        proposal.contract_params = serializer.validated_data
        proposal.save(update_fields=['contract_params', 'updated_at'])

        _sync_active_contracts(proposal)

    detail = ProposalDetailSerializer(proposal, context={'request': request, 'is_admin': True})
    return Response(detail.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_contract_modality(request, proposal_id):
    """During negotiation apply directly; every other state needs a preview."""
    from content.services import proposal_contract_modality as service
    from content.views.proposal_contract_modality import error_response, proposal_response

    get_object_or_404(BusinessProposal, pk=proposal_id)
    try:
        proposal, result = service.apply(proposal_id, request.data, actor=request.user)
    except service.ContractModalityError as exc:
        return error_response(exc)
    return Response(proposal_response(proposal, result, request))


def _get_contract_doc(proposal, variant=contract_variants.COMBINED):
    """Return the stored contract of *variant* for *proposal*, or None."""
    return contract_variants.contract_document(proposal, variant)


def _contract_pdf_response(pdf_bytes, proposal, prefix):
    """Build an HttpResponse with a branded PDF filename."""
    from django.http import HttpResponse
    from content.services.pdf_utils import safe_pdf_filename

    filename = safe_pdf_filename(
        prefix,
        proposal.title or proposal.client_name,
        (proposal.created_at or timezone.now()).strftime('%Y-%m-%d'),
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@api_view(['GET'])
@permission_classes([IsAdminUser])
def download_contract_pdf(request, proposal_id):
    """Download a generated contract PDF (``?variant=`` for a split closing)."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    variant, error = _requested_variant(proposal, request.query_params.get('variant'))
    if error:
        return error
    doc = _get_contract_doc(proposal, variant)
    if not doc or not doc.file:
        return Response(
            {'error': 'Contract PDF not found. Generate it first.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    return _contract_pdf_response(
        doc.file.read(), proposal, contract_variants.VARIANTS[variant].file_prefix,
    )


def _draft_prefix(variant):
    if variant == contract_variants.COMBINED:
        return 'Borrador_Contrato'
    return f'Borrador_{contract_variants.VARIANTS[variant].file_prefix}'


@api_view(['GET'])
@permission_classes([IsAdminUser])
def download_draft_contract_pdf(request, proposal_id):
    """Download the contract PDF with a diagonal BORRADOR watermark and no signature."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    variant, error = _requested_variant(proposal, request.query_params.get('variant'))
    if error:
        return error
    if variant == contract_variants.SERVICE:
        from content.services.proposal_hosting_terms import ServiceConditionsError, service_conditions_markdown
        try:
            service_conditions_markdown(proposal)
        except ServiceConditionsError as exc:
            return Response({'error': str(exc), 'code': 'service_conditions_missing'}, status=422)
    from content.services.contract_pdf_service import generate_contract_pdf
    from content.services.pdf_utils import add_watermark_to_pdf

    pdf_bytes = generate_contract_pdf(proposal, draft=True, variant=variant)
    if not pdf_bytes:
        return Response(
            {'error': 'Could not generate draft contract PDF.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    draft_bytes = add_watermark_to_pdf(pdf_bytes)
    return _contract_pdf_response(draft_bytes, proposal, _draft_prefix(variant))


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser])
def get_company_settings(request):
    """Read contract defaults or update the service-term catalogs as an admin."""
    from content.models import CompanySettings
    from content.serializers.service_contract_settings import CompanyServiceSettingsSerializer

    settings = CompanySettings.load()
    if request.method == 'PATCH':
        serializer = CompanyServiceSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        settings.service_contract_settings = serializer.validated_data['service_contract_settings']
        settings.save(update_fields=['service_contract_settings', 'updated_at'])
    return Response(settings.to_dict(), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_default_contract_template(request):
    """Return the default contract template markdown for preview/editing."""
    from content.services.contract_template_service import read_template
    from content.services.contract_template_validation import ContractTemplateError
    try:
        return Response(read_template(request.query_params.get('variant', 'combined')))
    except ContractTemplateError as exc:
        return Response({'detail': str(exc), 'code': exc.code, **exc.details}, status=404 if exc.code == 'NOT_FOUND' else 400)



@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_proposal_documents(request, proposal_id):
    """List all documents attached to a proposal."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    docs = list(proposal.proposal_documents.all().order_by('-created_at'))
    from content.services.service_contract_freshness import current_service_snapshot
    snapshot = current_service_snapshot(proposal) if any(d.document_type == 'contract_service' for d in docs) else None
    return Response([serialize_proposal_document(d, proposal=proposal, service_snapshot=snapshot) for d in docs], status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def upload_proposal_document(request, proposal_id):
    """Upload an additional document to a proposal (annexes, client docs, etc.)."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    from content.models import ProposalDocument

    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate file type and size
    from pathlib import Path
    ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg'}
    MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB
    ext = Path(file.name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return Response(
            {'error': f'File type {ext} not allowed. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if file.size > MAX_FILE_SIZE:
        return Response(
            {'error': 'File too large. Maximum size is 15 MB.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    title = request.data.get('title', file.name)
    document_type = request.data.get('document_type', ProposalDocument.DOC_TYPE_OTHER)

    valid_types = {c[0] for c in ProposalDocument.DOC_TYPE_CHOICES}
    if document_type not in valid_types or document_type in ProposalDocument.CONTRACT_DOC_TYPES:
        return Response(
            {'error': f'Invalid document_type: {document_type}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    custom_type_label = (request.data.get('custom_type_label') or '').strip()[:100]

    doc = ProposalDocument.objects.create(
        proposal=proposal,
        document_type=document_type,
        custom_type_label=custom_type_label if document_type == ProposalDocument.DOC_TYPE_OTHER else '',
        title=title,
        file=file,
        is_generated=False,
    )
    return Response(serialize_proposal_document(doc), status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_proposal_document(request, proposal_id, doc_id):
    """Delete a user-uploaded proposal document. Generated docs cannot be deleted."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    from content.models import ProposalDocument

    doc = get_object_or_404(ProposalDocument, pk=doc_id, proposal=proposal)
    if doc.is_generated:
        return Response(
            {'error': 'Cannot delete system-generated documents.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        doc.delete()
    except ProtectedError:
        return error_response(
            'Este documento forma parte de una fuente o evidencia contractual '
            'retenida y no se puede eliminar.',
            code='document_used_in_delivery',
            hint='Conserva el original: las capturas de guías y respuestas son inmutables.',
            status=status.HTTP_409_CONFLICT,
        )
    # Resolve all protected database references before removing the original.
    doc.file.delete(save=False)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_documents_to_client(request, proposal_id):
    """Send selected proposal documents to the client via email.

    Expects JSON body::

        {
            "documents": ["draft_contract", "commercial", "technical"],
            "additional_doc_ids": [12, 15],
            "subject": "...",
            "greeting": "...",
            "body": "...",
            "footer": "...",
            "document_descriptions": [
                {"name": "Contrato", "description": "..."},
            ]
        }
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    if not proposal.client_email:
        return Response(
            {'error': 'No hay email del cliente configurado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ALLOWED_DOC_KEYS = {'draft_contract', 'commercial', 'technical'}
    doc_keys = request.data.get('documents', [])
    additional_ids = request.data.get('additional_doc_ids', [])
    invalid_keys = set(doc_keys) - ALLOWED_DOC_KEYS
    if invalid_keys:
        return Response(
            {'error': f'Claves de documento no reconocidas: {invalid_keys}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not doc_keys and not additional_ids:
        return Response(
            {'error': 'Debes seleccionar al menos un documento.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from content.models import ProposalDocument
    from content.services.pdf_utils import add_watermark_to_pdf, safe_pdf_filename

    date_str = (proposal.created_at or timezone.now()).strftime('%Y-%m-%d')
    client_title = proposal.client_name or proposal.title

    attachments = []

    if 'draft_contract' in doc_keys:
        from content.services.contract_pdf_service import generate_contract_pdf
        # One draft per document of the chosen closing modality.
        for variant in contract_variants.active_variants(proposal):
            contract_bytes = generate_contract_pdf(proposal, draft=True, variant=variant)
            if contract_bytes:
                draft_bytes = add_watermark_to_pdf(contract_bytes)
                attachments.append((
                    safe_pdf_filename(_draft_prefix(variant), client_title, date_str),
                    draft_bytes,
                    'application/pdf',
                ))

    if 'commercial' in doc_keys:
        from content.services.proposal_pdf_service import ProposalPdfService
        pdf_bytes = ProposalPdfService.generate(proposal)
        if pdf_bytes:
            attachments.append((
                safe_pdf_filename('Propuesta_Comercial', client_title, date_str),
                pdf_bytes,
                'application/pdf',
            ))

    if 'technical' in doc_keys:
        from content.services.technical_document_pdf import (
            generate_technical_document_pdf,
        )
        tech_bytes = generate_technical_document_pdf(proposal)
        if tech_bytes:
            attachments.append((
                safe_pdf_filename('Detalle_Tecnico', client_title, date_str),
                tech_bytes,
                'application/pdf',
            ))

    if additional_ids:
        import mimetypes
        extra_docs = ProposalDocument.objects.filter(
            proposal=proposal, pk__in=additional_ids,
        )
        for doc in extra_docs:
            if doc.file:
                ext = doc.file.name.rsplit('.', 1)[-1] if '.' in doc.file.name else 'pdf'
                mime = mimetypes.guess_type(doc.file.name)[0] or 'application/octet-stream'
                safe_title = safe_pdf_filename(
                    'Documento', doc.title or 'documento', date_str,
                ).rsplit('.', 1)[0]  # strip the .pdf suffix
                with doc.file.open('rb') as f:
                    file_data = f.read()
                attachments.append((
                    f'{safe_title}.{ext}',
                    file_data,
                    mime,
                ))

    if not attachments:
        return Response(
            {'error': 'No se pudieron generar los documentos seleccionados.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Email content from the compose modal
    email_subject = request.data.get('subject', '') or None
    email_greeting = request.data.get('greeting', '') or None
    email_body = request.data.get('body', '') or None
    email_footer = request.data.get('footer', '') or None
    document_descriptions = request.data.get('document_descriptions', [])

    from content.services.proposal_email_service import ProposalEmailService
    sent = ProposalEmailService.send_documents_to_client(
        proposal, attachments,
        subject=email_subject,
        greeting=email_greeting,
        body=email_body,
        footer=email_footer,
        document_descriptions=document_descriptions,
    )

    if sent:
        return Response(
            {'message': f'Documentos enviados a {proposal.client_email}.'},
            status=status.HTTP_200_OK,
        )
    return Response(
        {'error': 'Error al enviar el correo. Intenta de nuevo.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_discount_offer(request, proposal_id):
    """Manually send the discount-offer email (proposal_urgency) to the client.

    Discount emails are never auto-sent; the seller triggers this action after
    reviewing the preview. Requires a configured discount and client email.
    """
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    if not proposal.client_email:
        return Response(
            {'error': 'No hay email del cliente configurado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not (proposal.discount_percent and proposal.discount_percent > 0):
        return Response(
            {'error': 'La propuesta no tiene descuento configurado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from content.services.proposal_email_service import ProposalEmailService
    sent = ProposalEmailService.send_urgency_email(proposal, force=True)

    if sent:
        return Response(
            {'message': f'Oferta de descuento enviada a {proposal.client_email}.'},
            status=status.HTTP_200_OK,
        )
    return Response(
        {'error': 'Error al enviar el correo. Intenta de nuevo.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# ── User-composed emails (branded & proposal) ────────────────────

_COMPOSED_EMAIL_ALLOWED_EXT = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg'}
_COMPOSED_EMAIL_MAX_FILE = 15 * 1024 * 1024  # 15 MB


def _doc_ref_variant(proposal, ref):
    """The contract a doc_ref points at; the single contract when none is named."""
    from content.views._doc_refs import DocRefError

    requested = ref.get('variant')
    active = contract_variants.active_variants(proposal)
    if not requested:
        if len(active) == 1:
            return active[0]
        raise DocRefError('Indica qué contrato adjuntar: producto o servicio.')
    if requested not in active:
        raise DocRefError('Ese contrato no corresponde a la modalidad de cierre elegida.')
    return requested


def _resolve_proposal_doc_refs(proposal, doc_refs):
    """
    Resolve a list of doc_refs into email attachment tuples.

    Each ref is ``{'source': str, 'id'?: int, 'variant'?: str}``. Supported sources:
      - ``contract_pdf``    → generated contract (final PDF); ``variant``
        names the product or service document of a split closing
      - ``contract_draft``  → freshly generated draft with watermark (same ``variant``)
      - ``commercial_pdf``  → commercial proposal PDF (ProposalPdfService)
      - ``technical_pdf``   → technical document PDF
      - ``proposal_document`` (with ``id``) → uploaded ProposalDocument file
    """
    import mimetypes

    from content.models import ProposalDocument
    from content.services.contract_pdf_service import generate_contract_pdf
    from content.services.pdf_utils import add_watermark_to_pdf, safe_pdf_filename
    from content.services.proposal_pdf_service import ProposalPdfService
    from content.services.technical_document_pdf import generate_technical_document_pdf
    from content.views._doc_refs import DocRefError

    doc_ids = [r.get('id') for r in doc_refs
               if isinstance(r, dict) and r.get('source') == 'proposal_document']
    docs_by_id = {
        doc.pk: doc
        for doc in ProposalDocument.objects.filter(proposal=proposal, pk__in=doc_ids)
    } if doc_ids else {}

    out = []
    date_str = (proposal.created_at or timezone.now()).strftime('%Y-%m-%d')
    client_title = proposal.client_name or proposal.title or 'cliente'

    for ref in doc_refs:
        if not isinstance(ref, dict):
            raise DocRefError('Cada doc_ref debe ser un objeto.')
        source = ref.get('source')

        if source in ('contract_pdf', 'contract_draft'):
            variant = _doc_ref_variant(proposal, ref)
            draft = source == 'contract_draft'
            pdf_bytes = generate_contract_pdf(proposal, draft=draft, variant=variant)
            if not pdf_bytes:
                raise DocRefError(
                    'No se pudo generar el borrador del contrato.' if draft
                    else 'El contrato aún no ha sido generado.'
                )
            if draft:
                name, pdf_bytes = _draft_prefix(variant), add_watermark_to_pdf(pdf_bytes)
            else:
                name = 'Contrato' if variant == contract_variants.COMBINED else (
                    contract_variants.VARIANTS[variant].file_prefix
                )
            out.append((
                safe_pdf_filename(name, client_title, date_str),
                pdf_bytes,
                'application/pdf',
            ))
        elif source == 'commercial_pdf':
            pdf_bytes = ProposalPdfService.generate(proposal)
            if not pdf_bytes:
                raise DocRefError('No se pudo generar la propuesta comercial.')
            out.append((
                safe_pdf_filename('Propuesta_Comercial', client_title, date_str),
                pdf_bytes,
                'application/pdf',
            ))
        elif source == 'technical_pdf':
            pdf_bytes = generate_technical_document_pdf(proposal)
            if not pdf_bytes:
                raise DocRefError('No se pudo generar el detalle técnico.')
            out.append((
                safe_pdf_filename('Detalle_Tecnico', client_title, date_str),
                pdf_bytes,
                'application/pdf',
            ))
        elif source == 'proposal_document':
            doc_id = ref.get('id')
            doc = docs_by_id.get(doc_id)
            if doc is None:
                raise DocRefError(f'Documento {doc_id} no existe.')
            if not doc.file:
                raise DocRefError(f'Documento "{doc.title}" no tiene archivo.')
            with doc.file.open('rb') as fh:
                data = fh.read()
            name = doc.file.name.rsplit('/', 1)[-1]
            mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            out.append((name, data, mime))
        else:
            raise DocRefError(f'Fuente de documento desconocida: {source!r}.')

    return out


def _parse_composed_email(request, proposal, template_key):
    """
    Validate and parse a composed-email request.

    Returns ``(parsed_data, None)`` on success or ``(None, Response)`` on error.
    """
    import json
    import mimetypes
    from datetime import timedelta
    from pathlib import Path

    from content.models import EmailLog

    # ── Rate limit: 1 email per minute per proposal per type ──
    one_min_ago = timezone.now() - timedelta(minutes=1)
    if EmailLog.objects.filter(
        proposal=proposal, template_key=template_key,
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
        sent_at__gte=one_min_ago,
    ).exists():
        return None, Response(
            {'error': 'Espera al menos 1 minuto entre envíos.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # ── Required text fields ──
    from content.services.email_recipient_service import (
        EmailRecipientValidationError,
        parse_email_recipients,
    )

    try:
        recipient_emails, cc_emails = parse_email_recipients(request.data)
    except EmailRecipientValidationError as exc:
        return None, Response(
            {'error': str(exc), 'code': exc.code, 'field': exc.field},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subject = (request.data.get('subject') or '').strip()
    if not subject:
        return None, Response(
            {'error': 'El asunto es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    greeting = (request.data.get('greeting') or '').strip()
    footer = (request.data.get('footer') or '').strip()

    # ── Sections (JSON-encoded string in multipart) ──
    from content.views.standalone_email import _parse_sections_field
    sections, sections_error = _parse_sections_field(request.data.get('sections', '[]'))
    if sections_error:
        return None, Response(
            {'error': sections_error},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not sections:
        return None, Response(
            {'error': 'Debe incluir al menos una sección con contenido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── File attachments ──
    attachments = []
    for f in request.FILES.getlist('attachments'):
        ext = Path(f.name).suffix.lower()
        if ext not in _COMPOSED_EMAIL_ALLOWED_EXT:
            return None, Response(
                {'error': f'Tipo de archivo {ext} no permitido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if f.size > _COMPOSED_EMAIL_MAX_FILE:
            return None, Response(
                {'error': f'El archivo "{f.name}" excede el límite de 15 MB.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mime_type = mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        attachments.append((f.name, f.read(), mime_type))

    # ── References to existing documents (contract, PDFs, templates, uploads) ──
    from content.views._doc_refs import DocRefError, parse_doc_refs_field

    doc_refs, error_response = parse_doc_refs_field(request)
    if error_response:
        return None, error_response
    try:
        attachments.extend(_resolve_proposal_doc_refs(proposal, doc_refs))
    except DocRefError as err:
        return None, Response(
            {'error': str(err)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return {
        'recipient_emails': recipient_emails,
        'cc_emails': cc_emails,
        'subject': subject,
        'greeting': greeting,
        'sections': sections,
        'footer': footer,
        'attachments': attachments or None,
    }, None


def _send_composed_email_view(request, proposal_id, send_method, template_key):
    """Shared handler for branded-email and proposal-email send views."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    parsed, error_response = _parse_composed_email(request, proposal, template_key)
    if error_response:
        return error_response

    sent = send_method(
        proposal=proposal,
        recipient_emails=parsed['recipient_emails'],
        cc_emails=parsed['cc_emails'],
        subject=parsed['subject'],
        greeting=parsed['greeting'],
        sections=parsed['sections'],
        footer=parsed['footer'],
        attachments=parsed['attachments'],
    )

    if sent:
        return Response(
            {
                'message': (
                    f'Correo enviado a {", ".join(parsed["recipient_emails"])} '
                    f'({len(parsed["recipient_emails"])} destinatario(s), '
                    f'{len(parsed["cc_emails"])} CC).'
                ),
                'recipient_emails': parsed['recipient_emails'],
                'cc_emails': parsed['cc_emails'],
            },
            status=status.HTTP_200_OK,
        )
    return Response(
        {'error': 'Error al enviar el correo. Intenta de nuevo.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _get_email_defaults_view(request, proposal_id, template_key):
    """Shared handler for branded-email and proposal-email defaults views."""
    from content.services.proposal_email_service import ProposalEmailService

    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)

    context = {
        'client_name': proposal.client_name or '',
        'title': proposal.title or '',
    }
    field_values = ProposalEmailService._resolve_content(template_key, context)

    return Response(field_values, status=status.HTTP_200_OK)


def _list_emails_view(request, proposal_id, template_key):
    """Shared handler for branded-email and proposal-email history views."""
    from content.models import EmailLog

    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    logs = EmailLog.objects.filter(
        proposal=proposal,
        template_key=template_key,
        delivery_role=EmailLog.DeliveryRole.PRIMARY,
    ).order_by('-sent_at')

    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    page_size = 20
    offset = (page - 1) * page_size

    from content.services.email_log_service import (
        attach_delivery_copies,
        attach_delivery_recipients,
        delivery_copy_payloads,
        delivery_recipient_payloads,
        representative_delivery_queryset,
    )

    logs = representative_delivery_queryset(logs)
    total = logs.count()
    page_logs = attach_delivery_recipients(
        attach_delivery_copies(logs[offset:offset + page_size]),
    )
    data = [
        {
            'id': log.pk,
            'delivery_id': str(log.delivery_id) if log.delivery_id else None,
            'recipient': log.recipient,
            'subject': log.subject,
            'status': log.status,
            'sent_at': log.sent_at.isoformat(),
            'metadata': log.metadata,
            'copies': delivery_copy_payloads(log),
            **delivery_recipient_payloads(log),
        }
        for log in page_logs
    ]
    return Response({
        'results': data,
        'total': total,
        'page': page,
        'page_size': page_size,
        'has_next': offset + page_size < total,
    }, status=status.HTTP_200_OK)


# ── Branded email endpoints ──

@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_branded_email(request, proposal_id):
    """Send a user-composed branded email with dynamic body sections."""
    from content.services.proposal_email_service import ProposalEmailService
    return _send_composed_email_view(request, proposal_id, ProposalEmailService.send_branded_email, 'branded_email')


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_branded_email_defaults(request, proposal_id):
    """Return admin-configurable defaults for the branded email composer."""
    return _get_email_defaults_view(request, proposal_id, 'branded_email')


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_branded_emails(request, proposal_id):
    """List branded emails sent for a proposal (paginated, 20 per page)."""
    return _list_emails_view(request, proposal_id, 'branded_email')


# ── Proposal email endpoints (logged as activity) ──

@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_proposal_email(request, proposal_id):
    """Send a user-composed proposal email and log it as proposal activity."""
    from content.services.proposal_email_service import ProposalEmailService
    return _send_composed_email_view(request, proposal_id, ProposalEmailService.send_proposal_email, 'proposal_email')


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_proposal_email_defaults(request, proposal_id):
    """Return admin-configurable defaults for the proposal email composer."""
    return _get_email_defaults_view(request, proposal_id, 'proposal_email')


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_proposal_emails(request, proposal_id):
    """List proposal emails sent for a proposal (paginated, 20 per page)."""
    return _list_emails_view(request, proposal_id, 'proposal_email')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def generate_email_markdown_attachment(request, proposal_id):
    """Generate a transient PDF from markdown for email attachment (not persisted)."""
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    return render_markdown_pdf_response(request, client_name=proposal.client_name or '')


# ── Project schedule endpoints (Cronograma admin tab) ──
#
# Two endpoints power the admin "Cronograma" tab:
#  - update_project_stage: PUT to set/update start_date + end_date for a stage
#  - complete_project_stage: POST to mark a stage as completed (silences alerts)


@api_view(['PUT'])
@permission_classes([IsAdminUser])
def update_project_stage(request, proposal_id, stage_key):
    """
    Set or update start_date / end_date for a project stage.

    The row is created lazily if it doesn't exist (first time the admin
    schedules this stage). Date validation enforces start_date <= end_date.
    """
    from content.services.proposal_stage_tracker import ProposalStageTracker

    if stage_key not in dict(ProposalStageTracker.STAGE_DEFINITIONS):
        return Response(
            {'detail': f'Etapa desconocida: {stage_key}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    stage = ProposalStageTracker.get_or_create_stage(proposal, stage_key)

    serializer = ProposalProjectStageSerializer(
        stage,
        data=request.data,
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    ProposalStageTracker.maybe_reset_warning_on_date_change(stage)

    ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type=ProposalChangeLog.ChangeType.UPDATED,
        actor_type=ProposalChangeLog.ActorType.SELLER,
        description=(
            f'Cronograma — etapa "{stage.get_stage_key_display()}" '
            f'actualizada (inicio={stage.start_date}, fin={stage.end_date}).'
        ),
    )

    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def complete_project_stage(request, proposal_id, stage_key):
    """
    Mark a project stage as completed.

    Sets `completed_at = now()` and clears the alert timestamps so future
    runs of the daily Huey task skip this stage entirely.
    """
    from content.services.proposal_stage_tracker import ProposalStageTracker

    if stage_key not in dict(ProposalStageTracker.STAGE_DEFINITIONS):
        return Response(
            {'detail': f'Etapa desconocida: {stage_key}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    stage = ProposalStageTracker.get_or_create_stage(proposal, stage_key)

    stage.completed_at = timezone.now()
    stage.warning_sent_at = None
    stage.last_overdue_reminder_at = None
    stage.save(update_fields=[
        'completed_at', 'warning_sent_at', 'last_overdue_reminder_at',
        'updated_at',
    ])

    ProposalChangeLog.objects.create(
        proposal=proposal,
        change_type=ProposalChangeLog.ChangeType.STAGE_COMPLETED,
        actor_type=ProposalChangeLog.ActorType.SELLER,
        description=(
            f'Cronograma — etapa "{stage.get_stage_key_display()}" '
            f'marcada como completada.'
        ),
    )

    return Response(
        ProposalProjectStageSerializer(stage).data,
        status=status.HTTP_200_OK,
    )
