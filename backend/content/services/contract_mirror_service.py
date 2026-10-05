"""Read-only Document-manager windows onto the three current templates."""
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

CONTRACT_MIRROR_BLOCKER = 'contract_mirror'
CONTRACT_MIRROR_CODE = 'contract_mirror_read_only'
CONTRACT_MIRROR_MESSAGE = (
    'Esta plantilla contractual es de solo lectura y permanece en Contratos. '
    'Su contenido se actualiza mediante el MCP de propuestas o la consola del servidor.'
)
MIRROR_TITLE = 'Contrato unificado de producto y servicio'


def mirror_binding(document):
    if document is None or getattr(document, 'pk', None) is None:
        return None
    try:
        mirror = document.contract_mirror
        return mirror.template, mirror.variant, mirror
    except ObjectDoesNotExist:
        pass
    try:
        return document.contract_template, 'combined', None
    except ObjectDoesNotExist:
        return None


def is_contract_mirror(document):
    return mirror_binding(document) is not None


def mirror_documents(queryset):
    return queryset.filter(Q(contract_template__isnull=False) | Q(contract_mirror__isnull=False))


def folder_contains_mirror(folder):
    from content.models import Document
    return mirror_documents(Document.objects.filter(folder_id__in=[folder.pk, *folder.get_descendant_ids()])).exists()


def draft_content(template, variant):
    """No proposal, client, economic amount or company default enters a mirror."""
    from content.services.contract_pdf_service import _build_params, _substitute_placeholders
    from content.services.contract_variants import VARIANTS
    from content.services.contract_template_validation import TEXT_FIELDS
    blank = 'XXX-XXX-XXX'
    params = _build_params({}, draft=True)
    params['service_conditions'] = 'Condiciones particulares del servicio: por completar en la propuesta.'
    markdown = _substitute_placeholders(getattr(template, TEXT_FIELDS[variant]), params)
    spec = VARIANTS[variant]
    snapshot = (
        f'# {spec.heading}\n\nENTRE: {blank} (EL CONTRATANTE)\n\nY: {blank} (EL CONTRATISTA)\n\n'
        + markdown + '\n\n## EN CONSTANCIA DE LO ANTERIOR,\n\n'
        'las partes firman el presente contrato en dos (2) ejemplares del mismo tenor.\n\n'
        f'**EL CONTRATANTE**\n\n{blank}\n\nC.C. {blank}\n\n'
        f'**EL CONTRATISTA**\n\n{blank}\n\n{params["contractor_id_type"]} {blank}\n'
    )
    return {'params': params, 'source': 'default', 'markdown': markdown, 'snapshot': snapshot, 'variant': variant}


def mirror_markdown(document=None):
    from content.models import ContractTemplate
    binding = mirror_binding(document) if document else None
    template, variant = binding[:2] if binding else (ContractTemplate.get_default(), 'combined')
    return draft_content(template, variant)['snapshot'] if template else None


def render_mirror_pdf(template, variant):
    from types import SimpleNamespace
    from content.services.contract_pdf_service import generate_contract_pdf
    from content.services.pdf_utils import add_watermark_to_pdf
    content = draft_content(template, variant)
    pdf = generate_contract_pdf(SimpleNamespace(pk=None), draft=True, resolved_content=content, variant=variant)
    return add_watermark_to_pdf(pdf) if pdf else None


def mirror_pdf(document=None):
    from content.models import ContractTemplate
    from content.services.contract_template_validation import TEXT_FIELDS
    binding = mirror_binding(document) if document else None
    if binding:
        template, variant, mirror = binding
        if mirror:
            if mirror.revision.markdown != getattr(template, TEXT_FIELDS[variant]):
                return None  # An unsupported direct DB write must never serve an old PDF.
            return bytes(mirror.pdf_content) if mirror.pdf_content else None
    else:
        template, variant = ContractTemplate.get_default(), 'combined'
    return render_mirror_pdf(template, variant) if template else None


def mirror_placeholder_markdown(variant='combined'):
    from content.services.contract_template_service import MIRROR_TITLES
    return f'# {MIRROR_TITLES[variant]}\n\nEste documento muestra en vivo la plantilla contractual vigente de ProjectApp.\n'
