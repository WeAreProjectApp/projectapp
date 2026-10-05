"""Strict placeholders and bounded, literal Markdown patches."""
import difflib
import re
from string import Formatter

CORE_FIELDS = {
    'client_full_name', 'client_cedula', 'client_email', 'contractor_full_name',
    'contractor_id_type', 'contractor_id_number', 'contractor_email',
    'bank_name', 'bank_account_type', 'bank_account_number', 'contract_city',
}
SERVICE_FIELDS = {'service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days'}
KNOWN_FIELDS = CORE_FIELDS | SERVICE_FIELDS | {'contractor_nit', 'contractor_cedula', 'contract_date', 'service_conditions'}
VARIANTS = ('combined', 'product', 'service')
TEXT_FIELDS = {'combined': 'content_markdown', 'product': 'product_content_markdown', 'service': 'service_content_markdown'}
MAX_MARKDOWN = 250_000


class ContractTemplateError(ValueError):
    def __init__(self, message, *, code='VALIDATION_ERROR', details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def variant_key(value):
    if value not in VARIANTS:
        raise ContractTemplateError('variant debe ser combined, product o service.')
    return value


def placeholders(markdown):
    fields = set()
    try:
        for _literal, field, spec, conversion in Formatter().parse(markdown):
            if field is None:
                continue
            if not re.fullmatch(r'[a-z][a-z_0-9]*', field) or spec or conversion:
                raise ContractTemplateError('Usa únicamente campos {placeholder} sin formatos ni atributos.')
            fields.add(field)
    except ValueError as exc:
        raise ContractTemplateError('La plantilla contiene llaves o campos mal formados.') from exc
    return fields


def validate_markdown(markdown, variant):
    variant_key(variant)
    if not isinstance(markdown, str) or not markdown.strip() or len(markdown) > MAX_MARKDOWN:
        raise ContractTemplateError('markdown debe ser texto no vacío de hasta 250000 caracteres.')
    fields = placeholders(markdown)
    required = CORE_FIELDS | (SERVICE_FIELDS if variant in {'combined', 'service'} else set())
    if variant == 'service':
        required |= {'service_conditions'}
    unknown, missing = fields - KNOWN_FIELDS, required - fields
    if unknown or missing:
        raise ContractTemplateError('Revisa los campos de la plantilla.', details={
            'variant': variant, 'unknown_placeholders': sorted(unknown), 'missing_placeholders': sorted(missing),
        })
    return sorted(fields)


def heading_span(markdown, heading, *, clause=None):
    """One complete section, ending before the next equal/higher heading."""
    if not isinstance(heading, str) or not heading.strip():
        raise ContractTemplateError('El encabezado debe ser texto no vacío.')
    start, end = 0, len(markdown)
    if clause:
        start, end = heading_span(markdown, clause)
    matches = list(re.finditer(r'^(#{1,6})[ \t]+(.+?)[ \t]*$', markdown[start:end], re.M))
    wanted = heading.lstrip('#').strip()
    selected = [(i, match) for i, match in enumerate(matches) if match.group(2) == wanted]
    if len(selected) != 1:
        raise ContractTemplateError('El encabezado no existe o es ambiguo.', code='PATCH_TARGET_ERROR', details={'heading': heading, 'matches': len(selected)})
    index, match = selected[0]
    boundary = next((item.start() for item in matches[index + 1:] if len(item.group(1)) <= len(match.group(1))), end - start)
    return start + match.start(), start + boundary


def apply_patches(markdown, patches):
    if not isinstance(patches, list) or not patches or len(patches) > 50:
        raise ContractTemplateError('patches debe contener entre 1 y 50 operaciones.')
    for patch in patches:
        if not isinstance(patch, dict) or set(patch) - {'operation', 'heading', 'clause_heading', 'text', 'markdown'}:
            raise ContractTemplateError('Parche inválido.')
        operation = patch.get('operation')
        replacement = patch.get('markdown')
        if operation not in {'replace', 'insert_before', 'insert_after'} or not isinstance(replacement, str):
            raise ContractTemplateError('Usa replace, insert_before o insert_after con markdown.')
        if ('heading' in patch) == ('text' in patch) or ('clause_heading' in patch and 'heading' not in patch):
            raise ContractTemplateError('Selecciona un encabezado o un texto exacto.')
        if 'heading' in patch:
            start, end = heading_span(markdown, patch['heading'], clause=patch.get('clause_heading'))
        else:
            target = patch['text']
            if not isinstance(target, str) or not target or markdown.count(target) != 1:
                raise ContractTemplateError('El texto exacto no existe o es ambiguo.', code='PATCH_TARGET_ERROR')
            start = markdown.index(target)
            end = start + len(target)
        if operation == 'insert_before':
            end = start
        elif operation == 'insert_after':
            start = end
        markdown = markdown[:start] + replacement + markdown[end:]
        if len(markdown) > MAX_MARKDOWN:
            raise ContractTemplateError('El resultado excede el tamaño permitido.')
    return markdown


def markdown_diff(before, after, variant):
    return ''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f'{variant}:vigente', tofile=f'{variant}:propuesta'))
