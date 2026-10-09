"""Transactional presentation writer shared by the dedicated MCP operations."""
import hashlib
import json
from copy import deepcopy
from urllib.parse import quote

from django.db import transaction

from content.models import BuildingWithUsProgram, BuildingWithUsProgramRevision, McpConnector
from content.services.building_with_us_content import BuildingWithUsError, SECTION_KEYS, canonical_hash, validate_content
from content.services.contract_template_validation import markdown_diff
from content.services.financing_program_service import WHATSAPP_NUMBER
from content.services.frontend_build import schedule_rebuild_after_publish

PUBLIC_PATHS = {'es': '/es-co/building-with-us', 'en': '/en-us/building-with-us'}


def _load(*, lock=False):
    try:
        return BuildingWithUsProgram.load(lock=lock)
    except BuildingWithUsProgram.DoesNotExist as exc:
        raise BuildingWithUsError('La presentación no está configurada.', code='NOT_FOUND') from exc


def program_etag(revision):
    identity = f'bwu:program:{revision.pk}:{revision.version}:{canonical_hash(revision.content)}'
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()


def resource_etags(_arguments=None):
    return {'program': program_etag(_load().current_revision)}


def _metadata(program):
    revision = program.current_revision
    return {
        'version': revision.version, 'version_id': revision.pk, 'updated_at': program.updated_at.isoformat(),
        'author': revision.author_label, 'change_note': revision.change_note, 'etag': program_etag(revision),
    }


def read_program():
    program = _load()
    return {**_metadata(program), 'sections': list(SECTION_KEYS), 'content': deepcopy(program.current_revision.content)}


def serialize_public_program(lang):
    if not isinstance(lang, str) or lang not in PUBLIC_PATHS:
        raise BuildingWithUsError('Usa es o en.', code='INVALID_LANGUAGE')
    program = _load()
    content = validate_content(program.current_revision.content)[lang]
    payload = {key: content[key] for key in SECTION_KEYS}
    message = payload['cta'].pop('whatsapp_message')
    payload['cta']['whatsapp_url'] = f'https://wa.me/{WHATSAPP_NUMBER}?text=' + quote(message)
    return {**payload, 'language': lang, 'version': program.current_revision.version,
            'updated_at': program.updated_at.isoformat(), 'canonical_path': PUBLIC_PATHS[lang],
            'alternate_path': PUBLIC_PATHS['en' if lang == 'es' else 'es'],
            'pdf_path': f'/api/building-with-us/public/pdf/?lang={lang}'}


def list_versions(*, offset=0, limit=20, include_content=False):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50 or type(include_content) is not bool:
        raise BuildingWithUsError('Usa offset >= 0, limit entre 1 y 50 e include_content booleano.')
    queryset = BuildingWithUsProgramRevision.objects.all()
    versions = []
    for row in queryset[offset:offset + limit]:
        item = {'version_id': row.pk, 'version': row.version, 'author': row.author_label,
                'created_at': row.created_at.isoformat(), 'change_note': row.change_note,
                'restored_from_version_id': row.restored_from_id}
        if include_content:
            item['content'] = deepcopy(row.content)
        versions.append(item)
    return {'total': queryset.count(), 'versions': versions}


def _prepare_update(arguments, *, program, restore=False, require_match=False):
    allowed = {'version_id' if restore else 'sections', 'if_match', 'change_note'}
    if not isinstance(arguments, dict) or set(arguments) - allowed:
        raise BuildingWithUsError('Hay argumentos desconocidos.')
    current = program.current_revision
    etag = program_etag(current)
    if require_match and not arguments.get('if_match'):
        raise BuildingWithUsError('if_match es obligatorio.', code='PRECONDITION_REQUIRED')
    if 'if_match' in arguments and arguments['if_match'] != etag:
        raise BuildingWithUsError('La presentación cambió; vuelve a leerla.', code='STALE_VERSION', details={'current_etag': etag})
    note = arguments.get('change_note', '')
    if not isinstance(note, str) or len(note.strip()) > 4000 or (require_match and not note.strip()):
        raise BuildingWithUsError('change_note debe explicar el cambio (entre 1 y 4000 caracteres).')
    restored = None
    if restore:
        version_id = arguments.get('version_id')
        if type(version_id) is not int or version_id < 1:
            raise BuildingWithUsError('version_id debe ser un entero positivo.')
        restored = BuildingWithUsProgramRevision.objects.filter(pk=version_id).first()
        if restored is None:
            raise BuildingWithUsError('La versión no existe.', code='NOT_FOUND')
        candidate = deepcopy(restored.content)
    else:
        sections = arguments.get('sections')
        if not isinstance(sections, dict) or not sections or set(sections) - set(SECTION_KEYS):
            raise BuildingWithUsError('Incluye al menos una sección conocida.', details={'path': 'sections'})
        candidate = deepcopy(current.content)
        for key, translations in sections.items():
            if not isinstance(translations, dict) or set(translations) != {'es', 'en'}:
                raise BuildingWithUsError('Cada sección requiere es y en.', details={'path': key})
            for lang in ('es', 'en'):
                candidate[lang][key] = deepcopy(translations[lang])
    candidate = validate_content(candidate)
    changes = []
    for key in SECTION_KEYS:
        diffs = []
        for lang in ('es', 'en'):
            before = json.dumps(current.content[lang][key], indent=2, sort_keys=True, ensure_ascii=False)
            after = json.dumps(candidate[lang][key], indent=2, sort_keys=True, ensure_ascii=False)
            diffs.append(markdown_diff(before, after, f'{key}.{lang}'))
        changes.append({'section': key, 'changed': any(diffs), 'diff': ''.join(diffs)})
    return ({'changes': changes, 'changed': any(row['changed'] for row in changes),
             'change_note': note.strip(), 'if_match': etag, 'resource_etags': {'program': etag}}, candidate, restored)


def prepare_update(arguments, *, restore=False, require_match=False):
    prepared, _, _ = _prepare_update(arguments, program=_load(), restore=restore, require_match=require_match)
    return prepared


@transaction.atomic
def apply_update(arguments, *, actor, credential=None, restore=False, expected_etags=None):
    program = _load(lock=True)
    etag = program_etag(program.current_revision)
    if expected_etags is not None and expected_etags != {'program': etag}:
        raise BuildingWithUsError('La presentación cambió desde la vista previa.', code='STALE_VERSION', details={'current_etag': etag})
    prepared, content, restored = _prepare_update(arguments, program=program, restore=restore, require_match=True)
    if not prepared['changed']:
        return {'applied': True, 'changed': False, 'version': program.current_revision.version}
    revision = BuildingWithUsProgramRevision.objects.create(
        version=program.current_revision.version + 1, content=content, author=actor, credential=credential,
        author_label=actor.get_username() if actor else 'Consola', change_note=prepared['change_note'], restored_from=restored,
    )
    program.current_revision = revision
    program.save(update_fields=['current_revision', 'updated_at'])
    transaction.on_commit(lambda: schedule_rebuild_after_publish(reason='building-with-us'))
    return {'applied': True, 'changed': True, 'version': revision.version, 'version_id': revision.pk, 'etag': program_etag(revision)}


def admin_overview():
    active = McpConnector.objects.filter(slug='building-with-us', is_active=True).exists()
    return {'program': _metadata(_load()), 'contract': None,
            'connector': {'slug': 'building-with-us', 'is_active': active}, 'public_paths': dict(PUBLIC_PATHS)}
