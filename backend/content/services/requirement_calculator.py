"""One transactional writer for calculator rules, documents and project versions."""
import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from accounts.models import Project
from content.models import (
    CalculatorRevision,
    Document,
    DocumentFolder,
    HourPackageSettings,
    ProjectCalculatorChange,
    ProjectCalculatorVersion,
    RequirementCalculator,
)
from content.serializers.requirement_calculator import DefinitionSerializer
from content.services.calculator_documents import (
    calculator_document_write,
    render_definition,
    update_document,
)
from content.services.document_type_utils import get_markdown_document_type
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError


class CalculatorConflict(APIException):
    status_code = 409
    default_detail = 'La calculadora cambió. Consulta de nuevo antes de guardar.'
    default_code = 'calculator_version_conflict'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def normalized(definition):
    serializer = DefinitionSerializer(data=definition)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.data)


def seed_definition():
    definition = json.loads((Path(__file__).resolve().parents[1] / 'data/requirement_calculator.json').read_text())
    settings = HourPackageSettings.objects.filter(pk=1).first()
    for row in definition['sizes'][:3]:
        row['standard_value_cop'] = str(getattr(settings, row['id'].lower() + '_price_cop',
                                               {'XS': 50000, 'S': 125000, 'M': 360000}[row['id']]))
    return normalized(definition)


def general_etag(calculator):
    return f'general:{calculator.current_revision_id}:{calculator.current_revision.digest}' if calculator else 'uninitialized'


def version_etag(version):
    return f'project:{version.pk}:{version.status}:{version.digest}:{version.updated_at.isoformat()}'


def revision_payload(revision, *, include_definition=False):
    result = {'id': revision.pk, 'digest': revision.digest, 'note': revision.note,
              'author_id': revision.author_id, 'created_at': revision.created_at.isoformat()}
    if include_definition:
        result['definition'] = revision.definition
    return result


def project_version_payload(version, *, include_definition=True):
    result = {'id': version.pk, 'project_id': version.project_id, 'base_revision_id': version.base_revision_id,
            'document_id': version.document_id, 'document_url': f'/panel/documents/{version.document_id}/edit',
            'status': version.status, 'digest': version.digest, 'if_match': version_etag(version),
            'note': version.note,
            'approved_by_id': version.approved_by_id,
            'approved_at': version.approved_at.isoformat() if version.approved_at else None,
            'pdf_digest': version.pdf_digest, 'created_at': version.created_at.isoformat(),
            'updated_at': version.updated_at.isoformat()}
    if include_definition:
        result['definition'] = version.definition
        result['changes'] = list(version.changes.values('id', 'digest', 'status', 'note', 'author_id', 'created_at')[:20])
    return result


def _record_project_change(version, *, actor):
    ProjectCalculatorChange.objects.create(version=version, definition=version.definition, digest=version.digest,
                                           status=version.status, note=version.note, author=actor)


def overview():
    calculator = RequirementCalculator.objects.select_related('current_revision').first()
    if calculator is None:
        candidates = Document.objects.filter(title='Skill: requirement-calculator — Calculadora de Requerimientos',
                                              is_archived=False, content_format='markdown')
        return {'initialized': False, 'if_match': 'uninitialized', 'definition': seed_definition(),
                'document_candidates': list(candidates.values('id', 'title'))[:10]}
    return {'initialized': True, 'if_match': general_etag(calculator),
            'revision_id': calculator.current_revision_id, 'definition': calculator.current_revision.definition,
            'document_id': calculator.document_id, 'document_url': f'/panel/documents/{calculator.document_id}/edit',
            'revision': revision_payload(calculator.current_revision)}


def list_revisions(*, limit=20, offset=0):
    if not 1 <= limit <= 50 or offset < 0:
        raise ValidationError('Usa limit entre 1 y 50 y offset no negativo.')
    rows = CalculatorRevision.objects.all()
    return {'count': rows.count(), 'results': [revision_payload(row) for row in rows[offset:offset + limit]]}


def revision_detail(revision_id):
    return revision_payload(get_object_or_404(CalculatorRevision, pk=revision_id), include_definition=True)


def preview(definition):
    config = normalized(definition)
    return {'definition': config, 'digest': digest(config),
            'markdown': render_definition(config, version='Vista previa')}


@transaction.atomic
def publish(definition, *, note, if_match, actor, document_id=None):
    config = normalized(definition)
    # Lock the singleton's stable parent even during the first initialization.
    settings = HourPackageSettings.load()
    settings = HourPackageSettings.objects.select_for_update().get(pk=settings.pk)
    calculator = RequirementCalculator.objects.select_for_update().select_related('current_revision', 'document').first()
    if if_match != general_etag(calculator):
        raise CalculatorConflict()
    if calculator and document_id is not None and document_id != calculator.document_id:
        raise ValidationError({'document_id': 'El documento general ya está vinculado.'})
    if not note or not note.strip():
        raise ValidationError({'note': 'Indica el motivo del cambio.'})
    for row in config['sizes'][:3]:
        if row['standard_value_cop'] is None:
            raise ValidationError('XS, S y M necesitan valor estándar para el catálogo de paquetes vigente.')
    revision = CalculatorRevision.objects.create(definition=config, digest=digest(config), note=note, author=actor)
    if calculator:
        document = calculator.document
    elif document_id is not None:
        document = get_object_or_404(Document.objects.select_for_update(), pk=document_id)
        if document.is_archived or document.is_contract_mirror or document.is_generated_snapshot or document.content_format != 'markdown':
            raise ValidationError({'document_id': 'Selecciona un documento Markdown editable y activo.'})
        from content.services.calculator_documents import managed
        if managed(document):
            raise ValidationError({'document_id': 'El documento ya pertenece a una calculadora.'})
    else:
        document = Document.objects.create(document_type=get_markdown_document_type(), title=config['title'],
                                           created_by=actor, updated_by=actor, is_client_visible=False)
    with calculator_document_write():
        document.metadata = {**document.metadata, 'requirement_calculator': {'kind': 'general', 'revision_id': revision.pk}}
        document.is_client_visible = False
        update_document(document, render_definition(config, version=revision.pk), actor=actor)
    RequirementCalculator.objects.update_or_create(pk=1, defaults={'current_revision': revision, 'document': document})
    HourPackageSettings.objects.filter(pk=settings.pk).update(**{
        row['id'].lower() + '_price_cop': Decimal(row['standard_value_cop']) for row in config['sizes'][:3]
    })
    return overview()


def publish_package_prices(changes, *, actor):
    """Compatibility writer: the old Packages screen uses the same calculator revision."""
    current = overview()
    if not current['initialized']:
        return
    config = deepcopy(current['definition'])
    dirty = False
    for row in config['sizes'][:3]:
        field = row['id'].lower() + '_price_cop'
        if field in changes and Decimal(row['standard_value_cop']) != Decimal(changes[field]):
            row['standard_value_cop'] = str(changes[field])
            dirty = True
    if dirty:
        publish(config, note='Valores por talla actualizados desde Paquetes de requerimientos.',
                if_match=current['if_match'], actor=actor)


def _project(project_id, *, lock=False):
    queryset = Project.objects.select_for_update() if lock else Project.objects.all()
    return get_object_or_404(queryset, pk=project_id)


def _project_etag(project):
    drafts = ProjectCalculatorVersion.objects.filter(project=project, status='draft').values_list('pk', 'digest', 'updated_at').first()
    return digest({'active': project.calculator_document_id, 'draft': [str(value) for value in drafts] if drafts else None})


def project_overview(project_id):
    project = _project(project_id)
    rows = ProjectCalculatorVersion.objects.filter(project=project).defer('definition', 'pdf_content')
    return {'project_id': project.pk, 'project_name': project.name, 'if_match': _project_etag(project),
            'calculator_document_id': project.calculator_document_id,
            'versions': [project_version_payload(row, include_definition=False) for row in rows[:50]]}


def project_version_detail(version_id):
    version = get_object_or_404(ProjectCalculatorVersion.objects.defer('pdf_content'), pk=version_id)
    return project_version_payload(version)


def _folder(project):
    from content.models.document_folder import lock_document_folder_mutations
    from content.services.project_document_folder_service import (
        ProjectFolderReconciliationRequired,
        require_project_folder,
    )
    try:
        root = require_project_folder(project)
    except ProjectFolderReconciliationRequired as exc:
        raise ValidationError({'project_id': str(exc)}) from exc
    lock_document_folder_mutations()
    key = f'calculator:project:{project.pk}'
    existing = DocumentFolder.objects.filter(system_key=key).first()
    if existing:
        if existing.is_archived or existing.parent_id != root.pk or existing.project_id != project.pk:
            raise ValidationError('Revisa la carpeta de calculadoras del proyecto.')
        return existing
    if root.children.filter(name__iexact='Calculadora de requerimientos').exists():
        raise ValidationError('La carpeta Calculadora de requerimientos ya existe; concíliala antes de asignar.')
    return DocumentFolder.objects.create(name='Calculadora de requerimientos', parent=root, project=project,
                                         client_user_id=project.client_id, system_key=key,
                                         creation_source='system', creation_operation='calculator_assignment')


@transaction.atomic
def create_project_draft(project_id, *, base_revision_id, note, if_match, actor):
    project = _project(project_id, lock=True)
    if if_match != _project_etag(project):
        raise CalculatorConflict()
    if ProjectCalculatorVersion.objects.filter(project=project, status='draft').exists():
        raise ValidationError('El proyecto ya tiene un borrador; edítalo antes de crear otro.')
    revision = get_object_or_404(CalculatorRevision, pk=base_revision_id)
    document = Document.objects.create(document_type=get_markdown_document_type(),
        title=f'Calculadora de requerimientos — {project.name}'[:255], folder=_folder(project),
        project=project, client_user_id=project.client_id, created_by=actor, updated_by=actor,
        is_client_visible=False, metadata={'requirement_calculator': {'kind': 'project'}})
    version = ProjectCalculatorVersion.objects.create(project=project, base_revision=revision,
        document=document, definition=deepcopy(revision.definition), digest=revision.digest, note=note, author=actor)
    document.metadata = {'requirement_calculator': {'kind': 'project', 'version_id': version.pk, 'status': 'draft'}}
    update_document(document, render_definition(version.definition, version=f'{revision.pk}/{version.pk}',
                    project_name=project.name, status='draft'), actor=actor)
    _record_project_change(version, actor=actor)
    return project_version_payload(version)


def _parameter_skeleton(config):
    result = deepcopy(config)
    for row in result['sizes']:
        for field in ('points', 'hours_min', 'hours_max', 'standard_value_cop'):
            row[field] = None
    for row in result['signals']:
        row['surcharge_percent'] = None
        row['size'] = None
    for row in result['modifiers']:
        row['minimum'] = row['maximum'] = None
    result['calibration'] = None
    return result


@transaction.atomic
def update_project_draft(version_id, *, definition, note, if_match, actor, **kwargs):
    row = get_object_or_404(ProjectCalculatorVersion.objects.select_related('project'), pk=version_id)
    _project(row.project_id, lock=True)
    version = ProjectCalculatorVersion.objects.select_for_update().select_related('document', 'project', 'base_revision').get(pk=version_id)
    if version.status != 'draft':
        raise ValidationError('La versión aprobada está congelada. Crea otro borrador.')
    if if_match != version_etag(version):
        raise CalculatorConflict()
    config = normalized(definition)
    if _parameter_skeleton(config) != _parameter_skeleton(version.base_revision.definition):
        raise ValidationError('En el proyecto sólo se ajustan parámetros existentes; textos, estructura y fórmulas permanecen fijos.')
    version.definition, version.digest, version.note = config, digest(config), note
    version.save()
    update_document(version.document, render_definition(config, version=f'{version.base_revision_id}/{version.pk}',
                    project_name=version.project.name, status='draft'), actor=actor)
    _record_project_change(version, actor=actor)
    return project_version_payload(version)


@transaction.atomic
def approve_project_version(version_id, *, note, if_match, actor):
    row = get_object_or_404(ProjectCalculatorVersion, pk=version_id)
    project = _project(row.project_id, lock=True)
    version = ProjectCalculatorVersion.objects.select_for_update().select_related('document').get(pk=version_id)
    if version.status != 'draft' or if_match != version_etag(version):
        raise CalculatorConflict()
    from content.services.document_pdf_service import DocumentPdfService
    document = version.document
    document.metadata = {'requirement_calculator': {'kind': 'project', 'version_id': version.pk, 'status': 'approved'}}
    update_document(document, render_definition(version.definition, version=f'{version.base_revision_id}/{version.pk}',
                    project_name=project.name, status='approved'), actor=actor)
    pdf = DocumentPdfService.generate(document)
    if not pdf:
        raise ValidationError('No se pudo generar el PDF. La versión sigue en borrador.')
    version.status, version.approved_by, version.approved_at = 'approved', actor, timezone.now()
    version.note, version.pdf_content, version.pdf_digest = note, pdf, hashlib.sha256(pdf).hexdigest()
    version.save()
    project.calculator_document = document
    project.save(update_fields=['calculator_document', 'updated_at'])
    _record_project_change(version, actor=actor)
    return project_version_payload(version)


def calculator_context(*, project_id=None, project_version_id=None, requirement=''):
    warning = ''
    project_version = None
    if project_id is not None:
        project = _project(project_id)
        if project_version_id is not None:
            project_version = get_object_or_404(ProjectCalculatorVersion, pk=project_version_id, project=project)
        elif project.calculator_document_id:
            project_version = get_object_or_404(ProjectCalculatorVersion, document_id=project.calculator_document_id,
                                                 project=project, status='approved')
        else:
            warning = 'El proyecto no tiene calculadora aprobada: se utiliza la definición general vigente.'
    elif project_version_id is not None:
        raise ValidationError('Indica el proyecto al consultar una versión particular.')
    if project_version:
        config, revision_id = project_version.definition, project_version.base_revision_id
        warning = 'Borrador explícito: sus condiciones todavía no están aprobadas.' if project_version.status == 'draft' else warning
    else:
        current = RequirementCalculator.objects.select_related('current_revision').first()
        if current is None:
            raise ValidationError('Inicializa primero la calculadora desde el panel.')
        config, revision_id = current.current_revision.definition, current.current_revision_id
    return {'revision_id': revision_id, 'project_id': project_id,
            'project_version_id': project_version.pk if project_version else None,
            'definition_digest': digest(config), 'definition': config, 'requirement': requirement,
            'warning': warning,
            'instructions': 'Aplica esta definición en el chat. Devuelve talla y explicación sin horas, costos ni precios unitarios. Registra la estimación con su revisión y huella exactas; no confundas registrar con aprobar condiciones ni descontar cupos.'}
