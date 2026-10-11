"""Only transactional writer of the private cell rental contract and its mirror."""
import hashlib
import logging
import re

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from content.models import (
    BuildingOnDemandContract, BuildingOnDemandContractMirror, BuildingOnDemandContractRevision,
    ContractTemplate, Document, DocumentFolder,
)
from content.services.building_on_demand_content import BuildingOnDemandError
from content.services.contract_mirror_service import pinned_mirror_folder
from content.services.contract_template_service import _diff_summary
from content.services.contract_template_validation import ContractTemplateError, apply_patches, markdown_diff
from content.services.document_note_service import create_note
from content.services.document_pdf_service import DocumentPdfService
from content.services.document_type_utils import get_markdown_document_type
from content.services.document_write_service import document_etag
from content.services.entity_history import history_operation
from content.services.pdf_utils import add_watermark_to_pdf

logger = logging.getLogger(__name__)
CONTRACT_TITLE = 'Contrato de alquiler de célula — Building on Demand'
MIRROR_POINTER = (
    f'# {CONTRACT_TITLE}\n\nEste documento muestra en vivo el contrato vigente de Building on Demand. '
    'Se edita desde el MCP «Building on Demand».'
)
INITIALIZATION_NOTE = 'Inicialización del espejo contractual de sólo lectura.'
PENDING_DECISIONS_V1 = """Inventario de preguntas abiertas de las fichas y respuestas de la versión inicial.
«Decidido» identifica lo aprobado por el operador el 2026-10-10; las demás respuestas son supuestos v1 para revisión.

PA-177 — Módulo de alquiler de célula Scrum:
1. ¿Nombre del módulo? Decidido: «Building on Demand» de cara al cliente y «Células» en el panel (cláusula 1).
2. ¿Tiempo completo o contratación? Decidido: no; es una bolsa de horas disponibles consumida según la estimación de la calculadora (cláusulas 1 y 4).
3. ¿Consumo promedio esperado por nivel? Sin dato aún; Economía muestra el equilibrio de 32 / 74 / 171 horas mensuales y 27 / 59 / 127 a nueve meses para contrastarlo con consumo real. Es una referencia interna, no una garantía contractual (cláusulas 2 y 6).
4. ¿Subir de plan por roles, servidor y soporte, no por valor de la hora? Sí; las tarjetas no muestran valor por hora (cláusulas 2 y 12).
5. ¿Costo interno por hora? Referencia de 55.000 pesos por hora estimada, interna y editable por MCP; no es la tarifa del cliente (cláusula 2).
6. ¿Célula compartida o dedicada? Compartida (cláusula 1).
7. ¿Horas por rol o de célula? Horas de célula, sin distinguir el rol que ejecuta (cláusulas 1 y 4).
8. ¿Propiedad intelectual? Lo entregado y pagado es del cliente; PROJECTAPP conserva herramientas y componentes previos con licencia de uso para el cliente (cláusula 13).
9. ¿Sin alcance fijo ni fecha comprometida? Sí, en la vista pública y en el contrato (cláusula 6).
10. ¿Salida antes de terminar un plazo? Devuelve meses no iniciados, menos el descuento recibido en los meses usados; el plan mensual termina con aviso de 30 días (cláusula 11).
11. ¿Subir y bajar de nivel? Subir desde el ciclo siguiente; bajar con aviso de 30 días y, dentro de un plazo, al terminarlo (cláusula 10).
12. ¿Exceso sobre la bolsa del mes? Sin horas extra automáticas: dividir la tarea, esperar al siguiente mes o subir de nivel (cláusula 7).
13. ¿Precios en la vista pública? Sí: precio mensual y por plazo, nunca valor por hora; el contrato usa referencias y fija el precio efectivo en Condiciones particulares (cláusula 2).
14. ¿Contrato del proyecto o aparte? Contrato propio, no anexo, que puede coexistir con un contrato de proyecto (cláusula 16).
15. ¿Qué significa no transferir? Ni a otra empresa o persona ni a otro proyecto del mismo cliente (cláusula 3).
16. ¿Horas no usadas? Vencen al cierre del mes; se informa en tarjetas y preguntas frecuentes y se acepta antes de iniciar (cláusula 3).
17. ¿Tope de ritmo? Una / dos / tres tareas en curso por nivel (cláusula 5).
18. ¿Mantenimiento y soporte por plan? Actualizaciones, copias y monitoreo preventivos del servidor e incidentes, con respuesta objetivo de 48 horas hábiles / 24 horas hábiles / 4 horas con prioridad; sin SLA con penalidades (cláusula 12).
19. ¿Consumen bolsa el mantenimiento y soporte? Mantenimiento preventivo e incidentes del servidor no; cambios, ajustes y nuevas funcionalidades sí (cláusulas 4 y 12).
20. ¿Cuenta del VPS y salida? Cuenta de PROJECTAPP; copia completa de código y datos y 30 días de transición. Hosting propio se acuerda en Condiciones particulares (cláusulas 12 y 14).
21. ¿VPS de un cliente mensual que sale al primer mes? Decisión interna de PROJECTAPP: reasignar o asumir; no se incorpora al contrato. Los plazos de 3, 6 y 9 meses reducen ese riesgo (referencia de plazos: cláusula 8).
22. ¿Detección propia de malware incluida? No se promete en v1 (cláusula 12).
23. ¿Business a seis meses: 15 o 20 por ciento? Decidido: 15 por ciento (cláusula 2).
24. ¿Plazo completo o cuotas? Completo y por adelantado (cláusula 8).
25. ¿Renovación con descuento al terminar? Continúa mensual al precio base hasta elegir otro plazo (cláusula 8).
26. ¿Reajuste anual? Adicional v1: variación del salario mínimo más 12 puntos, nunca sobre un plazo ya pagado (cláusula 9).

PA-179 — Contrato que rige el alquiler de la célula Scrum:
1. ¿Propiedad intelectual? Igual que PA-177 punto 8: lo entregado y pagado del cliente, con licencia de componentes previos (cláusula 13).
2. ¿Sin alcance fijo ni fecha de entrega comprometida? Sí (cláusula 6).
3. ¿Salida antes de terminar un plazo? Igual que PA-177 punto 10: meses no iniciados menos descuento recibido; modalidad mensual con aviso de 30 días (cláusula 11).
4. ¿Exceso de horas? Igual que PA-177 punto 12: dividir, esperar o subir, sin extras automáticas (cláusula 7).
5. ¿Subir o bajar de plan? Igual que PA-177 punto 11: siguiente ciclo para subir, aviso de 30 días y fin del plazo para bajar (cláusula 10).
6. ¿Cuenta del VPS y código/datos al terminar? Igual que PA-177 punto 20: cuenta de PROJECTAPP, copia completa y transición de 30 días; hosting propio por acuerdo (cláusulas 12 y 14).
7. ¿Registro y aceptación de estimación? PROJECTAPP envía la estimación por escrito; el cliente la aprueba por correo, WhatsApp o canal escrito acordado antes de empezar; sólo esa estimación descuenta horas (cláusula 4).
8. ¿Contrato aparte o anexo? Contrato propio (cláusula 16).
9. ¿Confidencialidad y datos personales? Sí, conforme a la Ley 1581 de 2012 (cláusula 15).
10. ¿Plantilla existente o documento nuevo? Documento nuevo con la estructura de Building with Us: partes, antecedentes, cláusulas, Condiciones particulares, Anexo A y firmas (cláusula 20).
11. ¿Firma? Fuera del sistema, con el PDF del panel firmado por las partes; sin flujo de formalización de propuestas (cláusula 20).

Borrador para revisión del operador y de un asesor jurídico antes de usarlo con un cliente."""


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _load(*, lock=False):
    try:
        return BuildingOnDemandContract.load(lock=lock)
    except BuildingOnDemandContract.DoesNotExist as exc:
        raise BuildingOnDemandError('El contrato no está configurado.', code='NOT_FOUND') from exc


def contract_etag(revision):
    return _hash(f'bod:contract:{revision.pk}:{revision.version}:{_hash(revision.markdown)}')


def _mirror(contract, *, lock=False):
    queryset = BuildingOnDemandContractMirror.objects.filter(contract=contract)
    if lock:
        return queryset.select_for_update().first()
    return queryset.select_related('document__folder', 'revision').first()


def _folder(folder_id, *, lock=False):
    if type(folder_id) is not int or folder_id < 1:
        raise BuildingOnDemandError('folder_id debe ser un entero positivo.', code='FOLDER_NOT_ALLOWED')
    queryset = DocumentFolder.objects.select_for_update() if lock else DocumentFolder.objects
    return queryset.filter(pk=folder_id).first()


def _folder_etag(folder):
    if folder is None:
        return 'none'
    return _hash(
        f'{folder.pk}:{folder.name}:{folder.parent_id}:{folder.is_archived}:{folder.system_key}:'
        f'{folder.client_user_id}:{folder.project_id}:{folder.updated_at.isoformat()}'
    )


def resource_etags(arguments=None):
    contract = _load()
    mirror = _mirror(contract)
    pinned, source = pinned_mirror_folder()
    resources = {
        'contract': contract_etag(contract.current_revision), 'mirror': 'none',
        'folder_pin': _hash(f'{source}:{_folder_etag(pinned)}'),
    }
    if mirror:
        document = mirror.document
        identity = (
            f'{mirror.pk}:{mirror.document_id}:{document.folder_id}:{mirror.revision_id}:'
            f'{mirror.synced_at.isoformat()}:{document_etag(document)}:'
            f'{document.title}:{document.language}:{document.is_archived}:{document.is_client_visible}:'
            f'{document.client_user_id}:{document.project_id}:{_hash(document.content_markdown)}:'
            f'{_folder_etag(document.folder)}:'
            f'{hashlib.sha256(bytes(mirror.pdf_content)).hexdigest()}'
        )
        resources['mirror'] = _hash(identity)
    if isinstance(arguments, dict) and 'folder_id' in arguments:
        resources['folder'] = _folder_etag(_folder(arguments['folder_id']))
    return resources


def validate_markdown(markdown):
    if not isinstance(markdown, str) or not markdown.strip() or len(markdown) > 250000:
        raise BuildingOnDemandError('markdown debe ser texto no vacío de hasta 250000 caracteres.')
    first = next(line for line in markdown.splitlines() if line.strip())
    if not first.startswith('# '):
        raise BuildingOnDemandError('La primera línea no vacía debe ser un título de nivel uno (# ).')
    if re.search(r'\{[a-z_][a-z0-9_]*\}', markdown):
        raise BuildingOnDemandError('Usa XXX-XXX-XXX para los espacios por completar; no se admiten placeholders.',
                                    code='PLACEHOLDER_NOT_SUPPORTED')
    return markdown


def _allowed_folder(folder):
    if not folder or folder.is_archived or folder.client_user_id or folder.project_id or folder.system_key:
        return False
    pinned, _source = pinned_mirror_folder()
    return folder.pk == pinned.pk if pinned else folder.name == 'Contratos'


def _resolve_folder(folder_id=None, *, lock=False):
    pinned, _source = pinned_mirror_folder()
    if folder_id is not None:
        folder = _folder(folder_id, lock=lock)
        if not _allowed_folder(folder):
            raise BuildingOnDemandError('Elige la carpeta fijada o una carpeta interna, activa y manual llamada Contratos.',
                                        code='FOLDER_NOT_ALLOWED')
        return folder
    if pinned is not None:
        folder = _folder(pinned.pk, lock=lock)
        if _allowed_folder(folder):
            return folder
    hint = 'Ejecuta sync_building_on_demand_contract_mirror --apply --folder-id N con una carpeta interna Contratos válida.'
    raise BuildingOnDemandError(
        f'No hay una carpeta contractual fijada y válida; no se aplicó ningún cambio. {hint}',
        code='MIRROR_SYNC_FAILED', details={'stage': 'folder_pin', 'applied': False, 'hint': hint},
    )


def _mirror_status(contract, mirror):
    document = mirror.document if mirror else None
    folder = document.folder if document and document.folder_id else None
    synchronized = bool(
        mirror and mirror.revision_id == contract.current_revision_id
        and mirror.pdf_content and bytes(mirror.pdf_content).startswith(b'%PDF-')
        and not document.is_archived and not document.is_client_visible
        and not document.client_user_id and not document.project_id
        and document.title == CONTRACT_TITLE and document.language == 'es'
        and document.content_markdown == MIRROR_POINTER and _allowed_folder(folder)
    )
    return {
        'status': 'synchronized' if synchronized else 'out_of_sync' if mirror else 'not_initialized',
        'document_id': document.pk if document else None,
        'title': document.title if document else CONTRACT_TITLE,
        'folder_id': folder.pk if folder else None,
        'folder_path': ' › '.join([*[row.name for row in folder.get_ancestors()], folder.name]) if folder else None,
        'version': mirror.revision.version if mirror else None,
        'last_synced_at': mirror.synced_at.isoformat() if mirror else None,
    }


def mirror_status():
    contract = _load()
    return _mirror_status(contract, _mirror(contract))


def read_contract():
    contract = _load()
    revision = contract.current_revision
    return {
        'markdown': revision.markdown, 'version': revision.version, 'version_id': revision.pk,
        'updated_at': contract.updated_at.isoformat(), 'author': revision.author_label,
        'change_note': revision.change_note, 'etag': contract_etag(revision),
        'mirror': _mirror_status(contract, _mirror(contract)),
    }


def list_versions(*, offset=0, limit=20, include_content=False):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50 or type(include_content) is not bool:
        raise BuildingOnDemandError('Usa offset >= 0, limit entre 1 y 50 e include_content booleano.')
    queryset = BuildingOnDemandContractRevision.objects.select_related('restored_from')
    versions = []
    for row in queryset[offset:offset + limit]:
        item = {
            'version_id': row.pk, 'version': row.version, 'author': row.author_label,
            'created_at': row.created_at.isoformat(), 'change_note': row.change_note,
            'restored_from_version_id': row.restored_from_id,
            'restored_from_version': row.restored_from.version if row.restored_from_id else None,
        }
        if include_content:
            item['markdown'] = row.markdown
        versions.append(item)
    return {'total': queryset.count(), 'versions': versions}


def prepare_update(arguments, *, restore=False, require_match=False):
    allowed = {'version_id' if restore else 'markdown', 'if_match', 'change_note'}
    if not restore:
        allowed.add('patches')
    if not isinstance(arguments, dict) or set(arguments) - allowed:
        raise BuildingOnDemandError('Hay argumentos desconocidos.')
    sources = [key for key in ('markdown', 'patches', 'version_id') if key in arguments]
    if len(sources) != 1 or (restore and sources != ['version_id']):
        raise BuildingOnDemandError('Indica exactamente markdown o patches; para restaurar usa version_id.')
    contract = _load()
    current = contract.current_revision
    etag = contract_etag(current)
    if require_match and not arguments.get('if_match'):
        raise BuildingOnDemandError('if_match es obligatorio.', code='PRECONDITION_REQUIRED')
    if 'if_match' in arguments and arguments['if_match'] != etag:
        raise BuildingOnDemandError('El contrato cambió; vuelve a leerlo.', code='STALE_VERSION', details={'current_etag': etag})
    note = arguments.get('change_note', '')
    if not isinstance(note, str) or len(note.strip()) > 4000 or (require_match and not note.strip()):
        raise BuildingOnDemandError('change_note debe explicar el cambio (entre 1 y 4000 caracteres).')
    if restore:
        version_id = arguments['version_id']
        if type(version_id) is not int or version_id < 1:
            raise BuildingOnDemandError('version_id debe ser un entero positivo.')
        revision = BuildingOnDemandContractRevision.objects.filter(pk=version_id).first()
        if revision is None:
            raise BuildingOnDemandError('La versión no existe.', code='NOT_FOUND')
        markdown = revision.markdown
    elif 'markdown' in arguments:
        markdown = arguments['markdown']
    else:
        try:
            markdown = apply_patches(current.markdown, arguments['patches'])
        except ContractTemplateError as exc:
            raise BuildingOnDemandError(str(exc), code=exc.code, details=exc.details) from exc
    validate_markdown(markdown)
    mirror = _mirror(contract)
    return {
        'changed': markdown != current.markdown, 'markdown': markdown,
        'diff': markdown_diff(current.markdown, markdown, 'building-on-demand'), 'placeholders': [],
        'document_to_sync': {'document_id': mirror.document_id if mirror else None, 'status': 'ready' if mirror else 'missing'},
        'resource_etags': resource_etags(),
    }


def render_pdf(markdown, document=None):
    """Use the Gestor's markdown renderer and saved cover/style choices."""
    options = {key: getattr(document, key) for key in (
        'include_portada', 'include_subportada', 'include_contraportada', 'template_style',
    )} if document else {}
    pdf = DocumentPdfService.generate_from_markdown(title=CONTRACT_TITLE, markdown_text=markdown, language='es', **options)
    if not pdf or not pdf.startswith(b'%PDF-'):
        raise ValueError('El renderizador no produjo un PDF.')
    pdf = add_watermark_to_pdf(pdf)
    if not pdf or not pdf.startswith(b'%PDF-'):
        raise ValueError('El PDF con marca de agua no es válido.')
    return pdf


def _sync_error(*, stage):
    return BuildingOnDemandError('No se sincronizó el espejo; no se aplicó ningún cambio.', code='MIRROR_SYNC_FAILED',
                                details={'stage': stage, 'applied': False})


def _synchronize(contract, revision, mirror, *, actor, note, diff):
    stage = 'pdf'
    try:
        pdf = render_pdf(revision.markdown, mirror.document)
        stage = 'mirror'
        mirror.revision = revision
        mirror.pdf_content = pdf
        mirror.synced_at = timezone.now()
        mirror.save()
        mirror.document.save(update_fields=['updated_at'])
        stage = 'private_note'
        create_note(mirror.document, actor=actor, title=f'Contrato Building on Demand — versión {revision.version}',
                    content=f'Versión {revision.version}\nFecha: {mirror.synced_at.isoformat()}\n{note}\n\n{_diff_summary(diff)}')
    except Exception as exc:
        raise _sync_error(stage=stage) from exc


def _sync_outcome(contract, mirror, folder):
    if mirror is None:
        return 'create'
    return 'noop' if mirror.document.folder_id == folder.pk and _mirror_status(contract, mirror)['status'] == 'synchronized' else 'resync'


def _sync_locked(contract, mirror, folder, *, actor, note, diff=''):
    outcome = _sync_outcome(contract, mirror, folder)
    if outcome == 'noop':
        return outcome, mirror
    try:
        if mirror is None:
            document = Document.objects.create(
                document_type=get_markdown_document_type(), title=CONTRACT_TITLE, folder=folder,
                language='es', is_client_visible=False, content_markdown=MIRROR_POINTER, created_by=actor,
            )
            mirror = BuildingOnDemandContractMirror(contract=contract, document=document,
                                                    revision=contract.current_revision, synced_at=timezone.now())
        else:
            document = mirror.document
            document.folder = folder
            document.title = CONTRACT_TITLE
            document.content_markdown = MIRROR_POINTER
            document.language = 'es'
            document.client_user = None
            document.project = None
            document.is_client_visible = False
            document.is_archived = False
            document.archived_at = None
            document.archived_via_folder = None
            document.save(update_fields=[
                'folder', 'title', 'content_markdown', 'language', 'client_user', 'project',
                'is_client_visible', 'is_archived', 'archived_at', 'archived_via_folder', 'updated_at',
            ])
    except Exception as exc:
        raise _sync_error(stage='document') from exc
    _synchronize(contract, contract.current_revision, mirror, actor=actor, note=note, diff=diff)
    if outcome == 'create':
        try:
            create_note(mirror.document, actor=actor, title='Inventario de decisiones pendientes (v1)', content=PENDING_DECISIONS_V1)
        except Exception as exc:
            raise _sync_error(stage='private_note') from exc
    return outcome, mirror


def _lock_mirror(contract):
    mirror = _mirror(contract, lock=True)
    if mirror:
        mirror.document = Document.objects.select_for_update().get(pk=mirror.document_id)
    return mirror


def _lock_folder_pin():
    """Keep the shared location stable after contract, mirror and document locks."""
    ContractTemplate.objects.select_for_update().filter(is_default=True).first()


@transaction.atomic
def apply_update(arguments, *, actor, credential=None, restore=False, expected_etags=None):
    contract = _load(lock=True)
    mirror = _lock_mirror(contract)
    _lock_folder_pin()
    if expected_etags is not None and expected_etags != resource_etags():
        raise BuildingOnDemandError('El contrato, su espejo o la carpeta fijada cambió desde la vista previa.', code='STALE_VERSION')
    prepared = prepare_update(arguments, restore=restore, require_match=True)
    folder = _resolve_folder(lock=True)
    if not prepared['changed']:
        _sync_locked(contract, mirror, folder, actor=actor, note=INITIALIZATION_NOTE)
        return {'applied': True, 'changed': False}
    revision = BuildingOnDemandContractRevision.objects.create(
        version=contract.current_revision.version + 1, markdown=prepared['markdown'], author=actor, credential=credential,
        author_label=actor.get_username() if actor else 'Consola', change_note=arguments['change_note'].strip(),
        restored_from_id=arguments['version_id'] if restore else None,
    )
    contract.current_revision = revision
    contract.save(update_fields=['current_revision', 'updated_at'])
    _outcome, mirror = _sync_locked(contract, mirror, folder, actor=actor, note=revision.change_note, diff=prepared['diff'])
    return {'applied': True, 'changed': True, 'version': revision.version, 'version_id': revision.pk,
            'etag': contract_etag(revision), 'mirror': _mirror_status(contract, mirror)}


def prepare_sync(folder_id=None):
    """Describe a pinned or explicitly permitted synchronization without writing."""
    folder = _resolve_folder(folder_id)
    contract = _load()
    mirror = _mirror(contract)
    outcome = _sync_outcome(contract, mirror, folder)
    arguments = {'folder_id': folder_id} if folder_id is not None else None
    return {'outcome': outcome, 'folder_id': folder.pk, 'mirror': _mirror_status(contract, mirror),
            'resource_etags': resource_etags(arguments)}


@transaction.atomic
def sync_mirror(*, actor, folder_id=None, expected_etags=None, note=None):
    contract = _load(lock=True)
    mirror = _lock_mirror(contract)
    _lock_folder_pin()
    arguments = {'folder_id': folder_id} if folder_id is not None else None
    if expected_etags is not None and expected_etags != resource_etags(arguments):
        raise BuildingOnDemandError('El contrato, su espejo o la carpeta cambió desde la vista previa.', code='STALE_VERSION')
    if note is not None and (not isinstance(note, str) or not note.strip() or len(note.strip()) > 4000):
        raise BuildingOnDemandError('note debe ser texto no vacío de hasta 4000 caracteres.')
    folder = _resolve_folder(folder_id, lock=True)
    outcome, mirror = _sync_locked(contract, mirror, folder, actor=actor,
                                   note=note.strip() if note is not None else INITIALIZATION_NOTE)
    return {'outcome': outcome, 'mirror': _mirror_status(contract, mirror)}


def reconcile_mirror():
    """Converge to the shared pin without rendering or writing redundant notes."""
    try:
        status = mirror_status()
        if status['status'] == 'synchronized':
            return {'outcome': 'noop', 'mirror': status}
        actor = get_user_model().objects.filter(is_active=True, is_superuser=True).order_by('pk').first()
        if actor is None:
            logger.warning('Building on Demand contract mirror skipped: no active superuser.')
            return {'outcome': 'skipped'}
        with history_operation(actor=actor, source='task:building-on-demand-contract-mirror'):
            return sync_mirror(actor=actor)
    except Exception:
        logger.warning('Building on Demand contract mirror could not converge; no changes applied.', exc_info=True)
        return {'outcome': 'skipped'}


def current_pdf():
    """Serve a synchronized artifact, or render the current text without writing."""
    contract = _load()
    mirror = _mirror(contract)
    if _mirror_status(contract, mirror)['status'] == 'synchronized':
        return bytes(mirror.pdf_content), contract.current_revision.version
    try:
        return render_pdf(contract.current_revision.markdown, mirror.document if mirror else None), contract.current_revision.version
    except Exception as exc:
        raise BuildingOnDemandError('El PDF vigente no está disponible.', code='PDF_RENDER_FAILED') from exc
