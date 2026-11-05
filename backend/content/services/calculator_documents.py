"""Rendered calculator definitions and protected, project-specific documents."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy, deepcopy

from content.services.document_content import build_content_json
from rest_framework.exceptions import ValidationError

_writing = ContextVar('calculator_document_writer', default=False)
MESSAGE = 'Este documento se administra desde Calculadora de requerimientos; modifica sus parámetros allí o mediante su MCP.'


@contextmanager
def calculator_document_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


def managed(document):
    return bool((document.metadata or {}).get('requirement_calculator'))


def protect_save(document):
    """Protect generic writers, history restoration and direct model saves alike."""
    if _writing.get() or not document.pk:
        return
    if getattr(document, '_calculator_managed_at_load', None) is False and not managed(document):
        return
    from content.models import Document
    previous = Document.objects.filter(pk=document.pk).first()
    if previous is None or not managed(previous):
        return
    if previous.metadata['requirement_calculator'].get('kind') == 'general' and document.is_client_visible:
        raise ValidationError('La definición general contiene parámetros internos y no se publica al cliente.')
    # Project client-transfer services may update ownership without changing agreed content.
    owner_matches_project = False
    if document.project_id and document.project_id == previous.project_id:
        from accounts.models import Project
        owner_matches_project = Project.objects.filter(pk=document.project_id, client_id=document.client_user_id).exists()
    # Publication, notes and workflow state remain separate from calculator approval.
    protected = ('content_markdown', 'content_json', 'text_formats', 'metadata', 'title',
                 'project_id', 'client_user_id', 'folder_id', 'content_format',
                 'uploaded_pdf', 'generated_file', 'pdf_version', 'pdf_sha256',
                 'cover_type', 'template_style', 'language', 'include_portada',
                 'include_subportada', 'include_contraportada', 'document_type_id',
                 'issuer_id', 'notes', 'terms_and_conditions', 'client_name',
                 'public_number', 'issue_date', 'due_date', 'city', 'currency',
                 'subtotal', 'discount_total', 'tax_total', 'total', 'template_version',
                 'requires_signature', 'deliverable_id', 'source_proposal_id', 'source_version',
                 'pdf_filename', 'pdf_size')
    if any(getattr(previous, field) != getattr(document, field) for field in protected
           if field != 'client_user_id' or not owner_matches_project):
        raise ValidationError(MESSAGE)


def protect_delete(document):
    if managed(document):
        raise ValidationError(MESSAGE)


def public_definition(config):
    """Explicit projection: no economic fields, effort bands or internal adjustments."""
    return {
        'title': config['title'],
        'sizes': [{key: row[key] for key in ('id', 'label', 'definition', 'examples')}
                  for row in config['sizes']],
        'project_rules': deepcopy(config['project_rules']),
    }


def _definition_digest(config):
    from content.services.requirement_calculator import digest
    return digest(config)


def render_definition(config, *, version, project_name=None, status=None):
    lines = [f'# {config["title"]}', '', f'**Versión:** {version}', f'**Huella de definición:** {_definition_digest(config)}', '']
    if project_name is not None:
        lines += [f'**Proyecto:** {project_name}', f'**Estado:** {"Aprobada" if status == "approved" else "Borrador"}', '']
    lines += ['## Cómo se clasifica', '',
              ('Se acuerdan el resultado y los criterios de aceptación. La talla se explica por '
               'las capacidades involucradas, lo que ya existe y las dependencias. Cada '
               'requerimiento utiliza un cupo de su propia talla cuando el paquete lo incluye. '
               'La fecha de entrega se acuerda por separado.'), '']
    for row in config['sizes']:
        lines += [f'## {row["id"]} — {row["label"]}', '', row['definition'], '']
        lines += [f'- {example}' for example in row['examples']] + ['', f'Puntos de referencia: {row["points"]}.', '']
    lines += ['## Cuándo corresponde un proyecto', ''] + [f'- {rule}' for rule in config['project_rules']]
    if project_name is not None:
        lines += ['', '## Señales de clasificación', '', 'La señal aplicable de mayor talla fija la base. Se distingue lo nuevo de lo que extiende una capacidad existente; cada clasificación cita y explica la señal aplicable.', '']
        for row in config['signals']:
            lines += [f'- **{row["size"]} · {row["label"]}:** {row["description"]}']
        lines += ['', '## Familias espejo', '']
        for row in config['families']:
            lines += [f'- **{row["label"]}:** XS/S: {row["small"]}; M: {row["medium"]}; L: {row["large"]}; XL: {row["extra_large"]}.']
    if project_name is None:
        lines += ['', '## Instrucciones para el chat', '', config['methodology'], '', '## Parámetros internos', '']
        lines += ['| Talla | Puntos | Banda interna de horas | Valor estándar COP |', '|---|---:|---|---:|']
        for row in config['sizes']:
            lines += [f'| {row["id"]} | {row["points"]} | {row["hours_min"]}–{row["hours_max"]} | {row["standard_value_cop"] or "Pendiente"} |']
        lines += ['', '## Señales', '']
        for row in config['signals']:
            lines += [f'- **{row["id"]} · {row["size"]} · {row["label"]}:** {row["description"]} (ajuste interno: {row["surcharge_percent"]} %)']
        lines += ['', '## Modificadores internos', '']
        for row in config['modifiers']:
            lines += [f'- **{row["id"]} · {row["label"]}:** {row["kind"]}, {row["minimum"]}–{row["maximum"]}; tallas {", ".join(row["applies_to"])}; grupo {row["exclusive_group"] or "ninguno"}.']
        lines += ['', '## Familias espejo', '']
        for row in config['families']:
            lines += [f'- **{row["label"]}:** XS/S: {row["small"]}; M: {row["medium"]}; L: {row["large"]}; XL: {row["extra_large"]}.']
        rule = config['calibration']
        lines += ['', '## Calibración interna', '',
                  f'Mínimo de cierres: {rule["minimum_samples"]}. Desvío para proponer revisión: {rule["deviation_percent"]} %. Costo interno por hora COP: {rule["hourly_cost_cop"] or "Pendiente"}.',
                  'Los valores son provisionales hasta contrastarlos con ejecución registrada.']
    return '\n'.join(lines) + '\n'


def update_document(document, markdown, *, actor):
    with calculator_document_write():
        document.content_markdown = markdown
        document.content_json = build_content_json(document, markdown)
        document.updated_by = actor
        document.save()


def protect_bulk_write(rows, fields):
    if _writing.get():
        return
    for row in rows:
        if not managed(row):
            continue
        proposed = copy(row)
        for name, value in fields.items():
            if hasattr(value, 'resolve_expression'):
                raise ValidationError(MESSAGE)
            field = row._meta.get_field(name.removesuffix('_id'))
            setattr(proposed, field.attname, getattr(value, 'pk', value))
        protect_save(proposed)
