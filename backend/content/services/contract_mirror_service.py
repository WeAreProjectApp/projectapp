"""Read-only Document-manager windows onto the three current templates."""
from content.models import Document, DocumentFolder
from content.services.diagnostic_privacy import register_mcp_domain_codes
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

CONTRACT_MIRROR_FOLDER_PINNED = 'contract_mirror_folder_pinned'
CONTRACT_MIRROR_FOLDER_PINNED_MESSAGE = (
    'La carpeta de los espejos contractuales debe permanecer sin cliente ni proyecto.'
)
CONTRACT_MIRROR_FOLDER_ARCHIVE_BLOCKED = 'contract_mirror_folder_archive_blocked'
register_mcp_domain_codes(CONTRACT_MIRROR_FOLDER_PINNED, CONTRACT_MIRROR_FOLDER_ARCHIVE_BLOCKED)

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
    return mirror_documents(Document.objects.filter(folder_id__in=[folder.pk, *folder.get_descendant_ids()])).exists()


def pinned_mirror_folder(template=None) -> tuple[DocumentFolder | None, str]:
    """Resolve the configured location, falling back to unambiguous live bindings."""
    if template is None:
        from content.services.contract_template_service import default_template
        from content.services.contract_template_validation import ContractTemplateError
        try:
            template = default_template()
        except ContractTemplateError as exc:
            if exc.code != 'NOT_FOUND':
                raise
            return None, 'unpinned'
    if template.mirror_folder_id is not None:
        return template.mirror_folder, 'field'
    folder_ids = set(Document.objects.filter(
        Q(contract_mirror__template_id=template.pk) | Q(pk=template.mirror_document_id),
    ).values_list('folder_id', flat=True))
    if len(folder_ids) == 1 and None not in folder_ids:
        return DocumentFolder.objects.get(pk=folder_ids.pop()), 'derived'
    return None, 'unpinned'


def is_pinned_mirror_folder(folder) -> bool:
    pinned, _source = pinned_mirror_folder()
    return bool(folder and pinned and folder.pk == pinned.pk)


def pinned_folder_state() -> dict:
    from content.services.document_folder_paths import folder_path as _folder_path

    folder, source = pinned_mirror_folder()
    blocker = mirror_folder_archive_blocker(folder) if folder else None
    return {
        'pinned_folder_id': folder.pk if folder else None,
        'pin_source': source,
        'folder_path': _folder_path(folder) if folder else None,
        'folder_movable': bool(folder and not folder.is_archived),
        'archive_blocked': blocker is not None,
        'archive_block_reason': blocker['message'] if blocker else None,
    }


def mirror_folder_archive_blocker(folder) -> dict | None:
    """Protect mirror contents while explaining how to release an ancestor."""
    if not folder_contains_mirror(folder):
        return None
    from content.services.document_folder_paths import folder_path as _folder_path

    pinned, _source = pinned_mirror_folder()
    message = (
        'Contratos guarda los espejos contractuales y no se puede archivar.'
        if pinned and folder.pk == pinned.pk else
        f'La carpeta «{folder.name}» contiene Contratos con los espejos contractuales; '
        'mueve Contratos a otra carpeta primero.'
    )
    documents = mirror_documents(Document.objects.filter(
        folder_id__in=[folder.pk, *folder.get_descendant_ids()],
    ))
    return {
        'code': CONTRACT_MIRROR_FOLDER_ARCHIVE_BLOCKED,
        'message': message,
        'details': {
            'contracts_folder_id': pinned.pk if pinned else None,
            'contracts_folder_path': _folder_path(pinned) if pinned else None,
            'mirror_document_ids': list(documents.order_by('pk').values_list('pk', flat=True)),
        },
    }


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
