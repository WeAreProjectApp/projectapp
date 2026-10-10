"""Level 3: Linktree HTML templates authored, validated and published by conversation.

Every handler reuses the panel service pipeline (package reader, snapshot
creation, browser validation and publication guard). A conversation can
describe the design variables of a card, upload a package it wrote, follow the
validation, preview the result and publish it, but it can never skip the
browser validation nor activate an unvalidated snapshot.
"""
import base64
import binascii
import json
import uuid
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import OPEN_REASON_KEY
from content.mcp.upload_tools import consume_upload, store_artifact
from content.models import Linktree, LinktreeTemplateClick, McpUpload
from content.services.linktree_templates import library, service
from content.services.linktree_templates.package import (
    IMAGE_LIMIT,
    PACKAGE_LIMIT,
    SOURCE_LIMIT,
    asset_batch,
)
from content.services.linktree_templates.render import (
    icon_catalog,
    preview_document,
    profile_data,
    profile_digest,
)
from content.services.linktree_templates.syntax import (
    ACTIONS,
    ATTRS,
    KINDS,
    LINK,
    PROFILE,
    TAGS,
    TemplateError,
)
from content.storage import get_private_storage

IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/webp'}

EXAMPLE_MANIFEST = {
    'spec': '1.0',
    'name': 'Editorial',
    'author': 'ProjectApp',
    'min_width': 320,
    'max_width': 480,
    'fonts': ['Oswald:wght@600;700'],
    'slots': {'photo': {'required': False, 'aspect': '1:1', 'min_px': 240, 'format': ['jpg', 'png', 'webp']}},
    'assets': [{'key': 'hero', 'file': 'assets/hero.png', 'alt': '', 'role': 'background'}],
    'editable_assets': ['hero'],
    'motion': False,
}
EXAMPLE_HTML = (
    '<!doctype html><html lang="es"><head><title>{{name}}</title></head><body>\n'
    '<main class="card">\n'
    '  <img data-asset="hero" class="hero">\n'
    '  {{#photo_url}}<img src="{{photo_url}}" alt="{{name}}" class="photo">{{/photo_url}}\n'
    '  {{^photo_url}}<div class="initials">{{initials}}</div>{{/photo_url}}\n'
    '  <h1>{{name}}</h1>\n'
    '  {{#role}}<p class="role">{{role}}</p>{{/role}}\n'
    '  {{#bio}}<p class="bio">{{bio}}</p>{{/bio}}\n'
    '  {{#primary_link}}<a data-link class="primary" href="{{url}}">'
    '<span data-icon="{{icon}}"></span>{{label}}</a>{{/primary_link}}\n'
    '  <nav>{{#links}}<a data-link class="link link-{{kind}}" href="{{url}}">'
    '<span data-icon="{{icon}}"></span>{{label}}</a>{{/links}}</nav>\n'
    '  <button data-action="save-contact"><span data-icon="user-round-plus"></span>Guardar contacto</button>\n'
    '  <button data-action="share"><span data-icon="share-2"></span>Compartir</button>\n'
    '  {{#footer_tagline}}<footer>{{footer_tagline}}</footer>{{/footer_tagline}}\n'
    '</main></body></html>'
)
EXAMPLE_CSS = (
    'body{background:#001713;color:#fff;font-family:Oswald,sans-serif}\n'
    '.card{padding:24px 16px;text-align:center}\n'
    '.hero{width:100%;height:auto}\n'
    '.photo{width:120px;height:120px;border-radius:50%}\n'
    '.link{display:flex;min-height:48px;align-items:center;justify-content:center;gap:8px;margin-top:12px;'
    'border:1px solid #f0ff3d;color:#fff;text-decoration:none}\n'
    '.primary{display:flex;min-height:52px;align-items:center;justify-content:center;gap:8px;'
    'background:#f0ff3d;color:#001713;text-decoration:none}\n'
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _uuid(value, label):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ToolError(f'{label} debe ser un UUID válido.') from exc


def _tree(arguments):
    linktree_id = _uuid(arguments.get('linktree_id'), 'linktree_id')
    tree = (
        Linktree.objects.select_related('project')
        .prefetch_related('buttons')
        .filter(pk=linktree_id)
        .first()
    )
    if tree is None:
        raise ToolError(f'No existe un Linktree con id={linktree_id}.', code='NOT_FOUND')
    return tree


def _version(tree, value):
    version_id = _uuid(value, 'version_id')
    version = tree.template_versions.select_related('template').filter(pk=version_id).first()
    if version is None:
        raise ToolError('No existe esa versión de plantilla para este Linktree.', code='NOT_FOUND')
    return version


def _template(tree, value):
    template_id = _uuid(value, 'template_id')
    template = service.available_templates(tree).filter(pk=template_id).first()
    if template is None:
        raise ToolError('No existe esa plantilla en la biblioteca de este Linktree.', code='NOT_FOUND')
    return template


def _template_error(exc):
    return ToolError(str(exc), code='INVALID_TEMPLATE', details={'issues': [exc.issue]})


def _iso(value):
    return value.isoformat() if value else None


def _profile_current(tree, version):
    try:
        return profile_digest(profile_data(tree)) == version.profile_digest
    except TemplateError:
        return False


def _next_step(version, tree, profile_current):
    if version.status == 'pending':
        return ('Validación en curso: consulta get_linktree_template_version hasta que '
                'status sea valid o invalid.')
    if version.status == 'invalid':
        return 'Corrige los errores del reporte y sube un paquete nuevo con upload_linktree_template.'
    if tree.active_template_version_id == version.pk:
        return 'Esta versión está publicada en la URL pública.'
    if not profile_current:
        return ('Los datos del perfil cambiaron: crea una nueva candidata con '
                'validate_linktree_template antes de publicar.')
    return 'Lista para publicar con publish_linktree_template (requiere confirmación).'


def _summary(version, tree):
    summary = service.version_summary(version, tree)
    summary['created_at'] = _iso(version.created_at)
    summary['published_at'] = _iso(version.published_at)
    summary['warnings'] = list(version.template.warnings)
    summary['profile_current'] = _profile_current(tree, version)
    summary['next_step'] = _next_step(version, tree, summary['profile_current'])
    return summary


def _asset_metadata(template):
    editable = set(template.manifest.get('editable_assets', []))
    declared = {asset['key']: asset for asset in template.manifest.get('assets', [])}
    return [{
        'key': key,
        'alt': asset.get('alt', ''),
        'format': asset.get('format'),
        'width': asset.get('width'),
        'height': asset.get('height'),
        'editable': key in editable,
        'role': declared.get(key, {}).get('role', ''),
    } for key, asset in template.assets.items()]


def _template_row(template, tree):
    return {
        'id': str(template.pk),
        'name': template.name,
        'author': template.manifest.get('author', ''),
        'is_shared': template.is_shared,
        'owned': template.owner_id == tree.pk,
        'can_share': template.owner_id == tree.pk and bool(service.client_id(tree)),
        'fonts': template.manifest.get('fonts', []),
        'editable_assets': template.manifest.get('editable_assets', []),
        'created_at': _iso(template.created_at),
    }


def _decode_base64(value, limit, label):
    if not isinstance(value, str):
        raise ToolError(f'{label}: base64 debe ser texto.')
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ToolError(f'{label}: base64 no contiene datos válidos.') from exc
    if not data or len(data) > limit:
        raise ToolError(f'{label}: el archivo debe medir entre 1 y {limit} bytes.')
    return data


def _consume_asset(asset_id, uploads, *, allowed=None):
    upload = consume_upload(asset_id, allowed_content_types=allowed)
    with upload.file.open('rb') as source:
        content = source.read(PACKAGE_LIMIT + 1)
    uploads.append(upload)
    return upload.filename, content


def _mark_consumed(uploads):
    for upload in uploads:
        upload.status = McpUpload.STATUS_CONSUMED
        upload.consumed_at = upload.consumed_at or timezone.now()
        upload.save(update_fields=['status', 'consumed_at', 'updated_at'])


def _package_files(entries, uploads):
    """Turn the tool's files list into (path, UploadedFile) pairs for the package reader."""
    if not isinstance(entries, list) or not entries:
        raise ToolError('files debe ser una lista con template.html y manifest.json como mínimo.')
    if len(entries) > 15:
        raise ToolError('El paquete admite hasta 15 archivos.')
    files = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ToolError(f'files[{index}] debe ser un objeto con path y content, base64 o asset_id.')
        path = str(entry.get('path') or '').strip()
        if not path:
            raise ToolError(f'files[{index}].path es obligatorio.')
        sources = [key for key in ('content', 'base64', 'asset_id') if entry.get(key) not in (None, '')]
        if len(sources) != 1:
            raise ToolError(f'{path}: indica exactamente uno de content, base64 o asset_id.')
        if sources[0] == 'content':
            content = entry['content']
            if path == 'manifest.json' and isinstance(content, dict):
                content = json.dumps(content, ensure_ascii=False)
            if not isinstance(content, str):
                raise ToolError(f'{path}: content debe ser texto (o un objeto JSON para manifest.json).')
            data = content.encode('utf-8')
            if len(data) > SOURCE_LIMIT:
                raise ToolError(f'{path}: el archivo de texto supera {SOURCE_LIMIT} bytes.')
        elif sources[0] == 'base64':
            data = _decode_base64(entry['base64'], PACKAGE_LIMIT, path)
        else:
            _, data = _consume_asset(entry['asset_id'], uploads)
        files.append((path, SimpleUploadedFile(path.rsplit('/', 1)[-1], data)))
    return files


def _screenshot_artifacts(version, context):
    artifacts = {}
    storage = get_private_storage()
    for width, path in sorted(version.screenshots.items()):
        try:
            with storage.open(path, 'rb') as stream:
                content = stream.read()
        except (FileNotFoundError, OSError):
            continue
        artifacts[str(width)] = store_artifact(
            connector=context.connector,
            credential=context.credential,
            filename=f'linktree-template-{version.pk}-{width}.png',
            content_type='image/png',
            content=content,
            request=context.request,
        )
    return artifacts


def _library_row(asset):
    row = library.asset_row(asset)
    row['created_at'] = _iso(asset.created_at)
    row['updated_at'] = _iso(asset.updated_at)
    return row


def _card_variables(tree):
    """Everything a designer needs about one card, resolved like the renderer does."""
    issues = []
    try:
        profile = profile_data(tree)
    except TemplateError as exc:
        issues.append(exc.issue)
        profile = None
    buttons = list(tree.buttons.all())
    links = profile['buttons'] if profile else []
    primary = next((link for link in links if link['tier'] == 'primary'), None)
    contact = {key: getattr(tree, f'vcard_{key}') for key in ('first_name', 'last_name', 'org', 'email', 'tel', 'url')}
    available_actions = ['save-contact', 'share', 'copy']
    if contact['tel'].strip():
        available_actions.append('whatsapp')
    if contact['email']:
        available_actions.append('email')
    if tree.pwa_enabled:
        available_actions.append('install-pwa')
    name = tree.display_name or tree.name
    pending = service.expire_pending(tree).exists()
    return {
        'id': str(tree.pk),
        'handle': tree.handle,
        'name': tree.name,
        'kind': tree.kind,
        'public_url': profile['profile_url'] if profile else tree.public_path,
        'project_id': tree.project_id,
        'profile': {
            'name': name,
            'role': tree.role,
            'bio': tree.bio,
            'company': tree.vcard_org,
            'badge': tree.badge_text,
            'footer_tagline': tree.footer_tagline,
            'initials': ''.join(part[0] for part in name.split()[:2]).upper(),
            'claim_line_1': tree.claim_line_1,
            'claim_line_2': tree.claim_line_2,
        },
        'photo': {
            'available': bool(tree.avatar),
            'format': tree.avatar.name.rsplit('.', 1)[-1].lower() if tree.avatar else None,
        },
        'logo': {
            'available': bool(tree.logo),
            'format': tree.logo.name.rsplit('.', 1)[-1].lower() if tree.logo else None,
        },
        'primary_link': {k: primary[k] for k in ('label', 'url', 'icon', 'kind')} if primary else None,
        'links': [{k: link[k] for k in ('label', 'url', 'icon', 'kind', 'tier')} for link in links],
        'links_by_kind': {
            kind: [link['label'] for link in links if link['kind'] == kind] for kind in sorted(KINDS)
        },
        'buttons_without_destination': [b.label for b in buttons if b.is_active and b.is_pending],
        'action_buttons': [
            {'label': b.label, 'action': b.action}
            for b in buttons if b.is_active and b.kind in {'download-vcard', 'pwa-install'}
        ],
        'available_actions': available_actions,
        'contact': contact,
        'pwa': {'enabled': tree.pwa_enabled, 'title': tree.pwa_title, 'description': tree.pwa_description},
        'branding': {
            'background_color': tree.background_color,
            'accent_color': tree.accent_color,
            'text_color': tree.text_color,
            'muted_color': tree.muted_color,
            'button_text_color': tree.button_text_color,
            'font_family': tree.font_family,
            'show_brand_header': tree.show_brand_header,
        },
        'assets': [_library_row(asset) for asset in tree.assets.all()],
        'active_version_id': str(tree.active_template_version_id) if tree.active_template_version_id else None,
        'validation_pending': pending,
        'profile_issues': issues,
    }


# ── Handlers ────────────────────────────────────────────────────────────────

def get_linktree_template_contract(arguments):
    icon_query = str(arguments.get('icon_query') or '').strip().lower()
    icons = sorted(icon_catalog())
    matches = [name for name in icons if icon_query and icon_query in name][:50]
    result = {
        'spec': '1.0',
        'package': {
            'required_files': ['template.html', 'manifest.json'],
            'optional_files': ['template.css', 'assets/<archivo>.png|.webp|.jpg|.svg'],
            'limits': {
                'package_bytes': PACKAGE_LIMIT, 'text_file_bytes': SOURCE_LIMIT,
                'image_bytes': IMAGE_LIMIT, 'max_files': 15, 'max_decorative_images': 12,
                'max_fonts': 8, 'widths_px': [320, 2000],
            },
        },
        'manifest': {
            'fields': {
                'spec': 'Obligatorio, siempre "1.0".',
                'name': 'Nombre de la plantilla (hasta 160 caracteres).',
                'author': 'Opcional, hasta 160 caracteres.',
                'min_width': 'Entero >= 320. Por defecto 320.',
                'max_width': 'Entero <= 2000, ancho máximo del body. Por defecto 480.',
                'fonts': 'Lista de familias de Google Fonts, por ejemplo "Oswald:wght@600;700". Máximo 8.',
                'slots': ('Opcional: photo y/o logo con required, aspect ("4:5"), min_px y '
                          'format (["jpg","png","webp","svg"]).'),
                'assets': ('Imágenes decorativas: objetos con key, file (dentro de assets/), alt y role '
                           'opcional "background". alt vacío = decorativa con aria-hidden.'),
                'editable_assets': ('Claves de assets que el operador puede reemplazar desde el panel o '
                                    'con override_linktree_template_asset.'),
                'motion': 'Booleano. true exige @media (prefers-reduced-motion: reduce) en el CSS.',
            },
            'example': EXAMPLE_MANIFEST,
        },
        'variables': {
            'profile': sorted(PROFILE),
            'profile_notes': {
                'name': 'display_name del Linktree o su nombre interno.',
                'company': 'vcard_org.',
                'badge': 'badge_text.',
                'photo_url': 'URL del avatar; vacío si no hay foto. Úsalo con la sección photo_url.',
                'logo_url': 'URL del logo; vacío si no hay logo.',
                'initials': 'Dos iniciales del nombre para el avatar de reserva.',
            },
            'link': sorted(LINK),
            'link_kinds': sorted(KINDS),
            'sections': ['primary_link', 'links'] + [f'links.{kind}' for kind in sorted(KINDS)],
            'section_notes': (
                'Toda variable de enlace va dentro de una sección links, links.<kind> o primary_link. '
                'Si la plantilla usa primary_link, links contiene los enlaces restantes; si no, todos. '
                'Los botones de vCard e instalación no son enlaces: se expresan con data-action. '
                'Las secciones normales e invertidas también sirven para mostrar u ocultar texto '
                'opcional (role, bio, badge, photo_url).'
            ),
            'mustache_rules': [
                ('Sólo variables escapadas y secciones normales/invertidas; sin triple llave, '
                 'parciales, lambdas ni delimitadores personalizados.'),
                'template.html debe incluir la variable name y la sección links.',
                'El CSS no admite variables Mustache; usa variables CSS.',
            ],
        },
        'links': {
            'markup': '<a data-link href="{{url}}"><span data-icon="{{icon}}"></span>{{label}}</a>',
            'rules': [
                'href debe ser la variable url; no se admiten destinos fijos.',
                'data-link es obligatorio en cada enlace del perfil.',
            ],
        },
        'actions': {
            'values': sorted(ACTIONS),
            'markup': ('<button data-action="save-contact">Guardar contacto</button>; '
                       'data-value indica qué copiar en copy.'),
            'notes': ('El runtime de la plataforma conecta las acciones y oculta las no disponibles '
                      '(whatsapp sin teléfono, email sin correo, install-pwa).'),
        },
        'images': {
            'library': (
                'Cada Linktree tiene una biblioteca de imágenes propia: súbelas con upload_linktree_asset '
                '(clave + imagen) y úsalas en el HTML con <img data-asset="clave"> o src="<url devuelta>", '
                'y en CSS con asset(clave) o url(<url devuelta>). Las URL se normalizan a la clave al subir '
                'el paquete y cada versión guarda su propia copia, así reemplazar una imagen no altera lo publicado.'
            ),
            'package': 'Alternativa portable: declarar la imagen en manifest.assets y enviarla en assets/ dentro del paquete.',
            'profile': 'La foto y el logo del perfil se colocan con las variables photo_url y logo_url.',
            'formats': 'PNG, WebP, JPG o SVG de hasta 800 KB; lados limitados a 2000 px; variantes 1x/2x/3x automáticas.',
        },
        'theme': (
            'Colores, tipografía y disposición son propios de cada HTML. Los campos de branding del editor '
            '(background_color, accent_color, text_color, muted_color, button_text_color, font_family) sólo '
            'aplican al tema básico cuando no hay plantilla publicada; no los reproduzcas en la plantilla.'
        ),
        'icons': {
            'markup': '<span data-icon="mail"></span> inserta un SVG Lucide que hereda currentColor.',
            'catalog_size': len(icons),
            'matches': matches,
            'notes': 'Usa icon_query para buscar nombres válidos; los enlaces ya traen su icono en la variable icon.',
        },
        'html': {
            'allowed_tags': sorted(TAGS),
            'allowed_attributes': sorted(ATTRS),
            'rules': [
                'Sin script, iframe, form, object, svg inline, eventos on*, ni atributos fuera de la lista.',
                'Imágenes decorativas: <img data-asset="clave">. Sin src externos.',
                'Objetivos táctiles de al menos 44 px, sin overflow horizontal a 320 px.',
                'Contraste mínimo 4.5:1 (3:1 en encabezados >= 24 px) sobre el fondo real.',
            ],
        },
        'css': {
            'rules': [
                'Sin @import, fuentes externas ni url() externos: usa asset(clave) para imágenes.',
                'Fuentes sólo desde manifest.fonts (Google Fonts).',
                'Animaciones sólo de transform/opacity; motion: true exige prefers-reduced-motion.',
                'Sin propiedades ejecutables (expression, paint, image-set).',
            ],
        },
        'example': {'manifest.json': EXAMPLE_MANIFEST, 'template.html': EXAMPLE_HTML, 'template.css': EXAMPLE_CSS},
        'workflow': [
            'get_linktree_template_contract con linktree_id para leer las variables reales de la tarjeta.',
            'upload_linktree_asset por cada imagen del diseño (fondos, texturas, sellos) para obtener su clave y URL.',
            'upload_linktree_template con files (template.html, manifest.json, template.css, assets/*).',
            ('get_linktree_template_version hasta que status sea valid; preview_linktree_template '
             'para ver HTML y capturas.'),
            'publish_linktree_template (confirmación) o reset_linktree_template para volver al tema básico.',
        ],
    }
    if arguments.get('linktree_id') not in (None, ''):
        result['linktree'] = _card_variables(_tree(arguments))
    return result


def list_linktree_templates(arguments):
    tree = _tree(arguments)
    service.expire_pending(tree)
    try:
        offset = max(0, int(arguments.get('offset', 0) or 0))
    except (TypeError, ValueError) as exc:
        raise ToolError('offset debe ser un entero.') from exc
    versions = list(
        tree.template_versions.select_related('template')
        .defer('document', 'profile', 'template__html', 'template__css')[offset:offset + 21]
    )
    return {
        'linktree_id': str(tree.pk),
        'active_version_id': str(tree.active_template_version_id) if tree.active_template_version_id else None,
        'can_share': bool(service.client_id(tree)),
        'templates': [_template_row(t, tree) for t in service.available_templates(tree)[:100]],
        'versions': [_summary(v, tree) for v in versions[:20]],
        'next_offset': offset + 20 if len(versions) > 20 else None,
    }


def get_linktree_template(arguments):
    tree = _tree(arguments)
    template = _template(tree, arguments.get('template_id'))
    return {
        **_template_row(template, tree),
        'manifest': template.manifest,
        'html': template.html,
        'css': template.css,
        'warnings': list(template.warnings),
        'assets': _asset_metadata(template),
        'library_assets': template.manifest.get('library_assets', []),
        'versions_count': template.versions.filter(linktree=tree).count(),
    }


def get_linktree_template_version(arguments):
    tree = _tree(arguments)
    service.expire_pending(tree)
    version = _version(tree, arguments.get('version_id'))
    summary = _summary(version, tree)
    summary['report'] = version.report
    summary['overrides'] = list(version.overrides)
    summary['profile'] = {k: v for k, v in version.profile.items() if k != 'contact'}
    return summary


def upload_linktree_template(arguments):
    tree = _tree(arguments)
    uploads = []
    try:
        service.check_pending(tree)
        with asset_batch(), transaction.atomic():
            files = _package_files(arguments.get('files'), uploads)
            template = service.upload_package(tree, files)
            version = service.create_version(tree, template)
            _mark_consumed(uploads)
    except TemplateError as exc:
        raise _template_error(exc)
    version.refresh_from_db()
    return {
        'template': _template_row(template, tree),
        'version': _summary(version, tree),
        'warnings': list(template.warnings),
    }


def validate_linktree_template(arguments):
    tree = _tree(arguments)
    template_id, version_id = arguments.get('template_id'), arguments.get('version_id')
    if bool(template_id) == bool(version_id):
        raise ToolError('Indica template_id o version_id, pero no ambos.')
    try:
        service.check_pending(tree)
        with asset_batch(), transaction.atomic():
            previous = _version(tree, version_id) if version_id else None
            template = previous.template if previous else _template(tree, template_id)
            version = service.create_version(tree, template, previous=previous)
    except TemplateError as exc:
        raise _template_error(exc)
    version.refresh_from_db()
    return _summary(version, tree)


def preview_linktree_template(arguments):
    tree = _tree(arguments)
    version = _version(tree, arguments.get('version_id'))
    result = _summary(version, tree)
    result['report'] = version.report
    if arguments.get('include_document', True):
        result['document'] = preview_document(version)
    if arguments.get('include_screenshots', True) and version.screenshots:
        context = current_mcp_context()
        if context is None or context.credential is None:
            result['screenshot_artifacts'] = {}
            result['screenshot_note'] = 'Las capturas requieren una credencial MCP; ábrelas desde el panel.'
        else:
            result['screenshot_artifacts'] = _screenshot_artifacts(version, context)
    return result


def override_linktree_template_asset(arguments):
    tree = _tree(arguments)
    previous = _version(tree, arguments.get('version_id'))
    key = str(arguments.get('key') or '').strip()
    if not key:
        raise ToolError('key es obligatorio.')
    reset = bool(arguments.get('reset'))
    asset_id, raw = arguments.get('asset_id'), arguments.get('base64')
    if reset == bool(asset_id or raw) or (asset_id and raw):
        raise ToolError('Indica asset_id o base64 para reemplazar la imagen, o reset=true para restablecerla.')
    uploads = []
    try:
        with asset_batch(), transaction.atomic():
            replacement = None
            if asset_id:
                filename, data = _consume_asset(asset_id, uploads, allowed=IMAGE_TYPES)
                replacement = (key, SimpleUploadedFile(filename, data))
            elif raw:
                filename = str(arguments.get('filename') or 'replacement.png')
                replacement = (key, SimpleUploadedFile(filename, _decode_base64(raw, IMAGE_LIMIT, key)))
            version = service.create_version(
                tree, previous.template, previous=previous,
                replacement=replacement, reset_key=key if reset else None,
            )
            _mark_consumed(uploads)
    except TemplateError as exc:
        raise _template_error(exc)
    version.refresh_from_db()
    return _summary(version, tree)


def publish_linktree_template(arguments):
    tree = _tree(arguments)
    version = _version(tree, arguments.get('version_id'))
    try:
        service.publish_version(tree, version)
    except TemplateError as exc:
        raise _template_error(exc)
    tree.refresh_from_db()
    return {**_summary(version, tree), 'public_url': version.profile.get('profile_url', tree.public_path)}


def _publish_impact(arguments):
    tree = _tree(arguments)
    version = _version(tree, arguments.get('version_id'))
    return {
        'summary': f'Publicar la plantilla «{version.template.name}» en {tree.public_path}.',
        'operation': 'publish_linktree_template',
        'resources': {'linktree_id': str(tree.pk), 'version_id': str(version.pk)},
        'status': version.status,
        'replaces_version_id': str(tree.active_template_version_id) if tree.active_template_version_id else None,
    }


def reset_linktree_template(arguments):
    tree = _tree(arguments)
    previous = tree.active_template_version_id
    tree.active_template_version = None
    tree.save(update_fields=['active_template_version', 'updated_at'])
    return {
        'linktree_id': str(tree.pk),
        'active_version_id': None,
        'previous_version_id': str(previous) if previous else None,
    }


def share_linktree_template(arguments):
    tree = _tree(arguments)
    template_id = _uuid(arguments.get('template_id'), 'template_id')
    template = tree.owned_templates.filter(pk=template_id).first()
    if template is None:
        raise ToolError('Sólo se comparten plantillas propias de este Linktree.', code='NOT_FOUND')
    value = arguments.get('is_shared')
    if not isinstance(value, bool):
        raise ToolError('is_shared debe ser booleano.')
    if value and not service.client_id(tree):
        raise ToolError('Vincula el Linktree a un proyecto antes de compartir.', code='CONFLICT')
    template.is_shared = value
    template.client_id = service.client_id(tree)
    template.save(update_fields=['is_shared', 'client'])
    return _template_row(template, tree)


def get_linktree_template_clicks(arguments):
    tree = _tree(arguments)
    version_id = arguments.get('version_id') or tree.active_template_version_id
    if not version_id:
        raise ToolError('El Linktree no tiene una plantilla publicada; indica version_id.', code='NOT_FOUND')
    version = _version(tree, version_id)
    try:
        days = max(1, min(int(arguments.get('days', 30) or 30), 365))
    except (TypeError, ValueError) as exc:
        raise ToolError('days debe ser un entero.') from exc
    since = timezone.localdate() - timedelta(days=days - 1)
    labels = {b['key']: b['label'] for b in version.profile.get('buttons', [])}
    rows = (
        LinktreeTemplateClick.objects.filter(version=version, day__gte=since)
        .values('link_key', 'day').annotate(count=Sum('count')).order_by('day', 'link_key')
    )
    totals = {}
    daily = []
    for row in rows:
        totals[row['link_key']] = totals.get(row['link_key'], 0) + row['count']
        daily.append({
            'day': row['day'].isoformat(), 'link_key': row['link_key'],
            'label': labels.get(row['link_key'], ''), 'count': row['count'],
        })
    return {
        'linktree_id': str(tree.pk),
        'version_id': str(version.pk),
        'since': since.isoformat(),
        'days': days,
        'total': sum(totals.values()),
        'links': [
            {'link_key': key, 'label': labels.get(key, ''), 'count': count}
            for key, count in sorted(totals.items(), key=lambda item: -item[1])
        ],
        'daily': daily,
    }


def list_linktree_assets(arguments):
    tree = _tree(arguments)
    return {
        'linktree_id': str(tree.pk),
        'assets': [_library_row(asset) for asset in tree.assets.all()],
        'usage': {
            'html': '<img data-asset="clave"> o <img src="<url>">',
            'css': 'asset(clave) o url(<url>)',
        },
    }


def upload_linktree_asset(arguments):
    tree = _tree(arguments)
    key = str(arguments.get('key') or '').strip()
    alt = arguments.get('alt') or ''
    asset_id, raw = arguments.get('asset_id'), arguments.get('base64')
    if bool(asset_id) == bool(raw):
        raise ToolError('Indica asset_id (upload completado) o base64 con filename, pero no ambos.')
    uploads = []
    try:
        with asset_batch(), transaction.atomic():
            if asset_id:
                filename, data = _consume_asset(asset_id, uploads, allowed=IMAGE_TYPES)
            else:
                filename = str(arguments.get('filename') or f'{key or "image"}.png')
                data = _decode_base64(raw, IMAGE_LIMIT, key or 'base64')
            asset, sanitized = library.upload_asset(tree, key, alt, SimpleUploadedFile(filename, data))
            _mark_consumed(uploads)
    except TemplateError as exc:
        raise _template_error(exc)
    asset.refresh_from_db()
    return {
        **_library_row(asset),
        'sanitized': sanitized,
        'next_step': (
            f'Usa <img data-asset="{asset.key}"> (o src="{asset.url}") en template.html, o asset({asset.key}) '
            'en CSS, y sube el paquete con upload_linktree_template. Las versiones ya publicadas no cambian.'
        ),
    }


def delete_linktree_asset(arguments):
    tree = _tree(arguments)
    key = str(arguments.get('key') or '').strip()
    try:
        library.delete_asset(tree, key)
    except TemplateError as exc:
        raise _template_error(exc)
    return {'linktree_id': str(tree.pk), 'key': key, 'deleted': True}


# ── Registry ────────────────────────────────────────────────────────────────

_LINKTREE_ID ={'linktree_id': {'type': 'string', 'format': 'uuid', 'description': 'ID del Linktree.'}}
_VERSION_ID = {'version_id': {'type': 'string', 'format': 'uuid', 'description': 'ID de la versión de plantilla.'}}
_TEMPLATE_ID = {'template_id': {'type': 'string', 'format': 'uuid', 'description': 'ID de la plantilla en la biblioteca.'}}

LINKTREE_TEMPLATE_TOOLS = [
    {
        'name': 'list_linktree_assets',
        'description': (
            'Lista la biblioteca de imágenes propia de un Linktree: clave, alt, URL, dimensiones y el '
            'marcado para usarlas en template.html o CSS.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _LINKTREE_ID,
            'required': ['linktree_id'],
            'additionalProperties': False,
        },
        'handler': list_linktree_assets,
    },
    {
        'name': 'upload_linktree_asset',
        'description': (
            'Sube o reemplaza una imagen (PNG, WebP, JPG o SVG de hasta 800 KB) en la biblioteca del '
            'Linktree bajo una clave, y devuelve la URL y el marcado para usarla en el diseño HTML. '
            'Hazlo antes de upload_linktree_template. Las versiones publicadas conservan su copia.'
        ),
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {
                **_LINKTREE_ID,
                'key': {'type': 'string', 'description': 'Clave en minúsculas (letras, números, guion, guion bajo), hasta 40 caracteres.'},
                'alt': {'type': 'string', 'description': 'Texto alternativo; vacío = imagen decorativa.'},
                'asset_id': {'type': 'string', 'format': 'uuid', 'description': 'Upload PNG/JPG/WebP completado.'},
                'base64': {'type': 'string', 'description': 'Imagen en base64 (hasta 800 KB).'},
                'filename': {'type': 'string', 'description': 'Nombre con extensión cuando se usa base64 (p. ej. fondo.svg).'},
            },
            'required': ['linktree_id', 'key'],
            'additionalProperties': False,
        },
        'handler': upload_linktree_asset,
    },
    {
        'name': 'delete_linktree_asset',
        'description': (
            'Elimina una imagen de la biblioteca del Linktree. Las plantillas que la usen ya no podrán '
            'validarse de nuevo; las versiones publicadas conservan su copia.'
        ),
        'risk': 'sensitive',
        'requires_confirmation': True,
        'confirmation_message': 'Eliminar la imagen de la biblioteca del Linktree.',
        'input_schema': {
            'type': 'object',
            'properties': {**_LINKTREE_ID, 'key': {'type': 'string'}},
            'required': ['linktree_id', 'key'],
            'additionalProperties': False,
        },
        'handler': delete_linktree_asset,
    },
    {
        'name': 'get_linktree_template_contract',
        'description': (
            'Devuelve el contrato de autoría de plantillas HTML de Linktree (archivos, manifest, '
            'variables Mustache, enlaces, acciones, iconos, reglas HTML/CSS y un ejemplo) y, con '
            'linktree_id, las variables reales de esa tarjeta: nombre, rol, bio, foto/logo, enlaces con '
            'etiqueta, URL, icono y tipo, contacto, colores y fuente. Llámalo antes de diseñar.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_LINKTREE_ID,
                'icon_query': {
                    'type': 'string',
                    'description': 'Texto para buscar nombres de iconos Lucide (hasta 50 coincidencias).',
                },
            },
            'additionalProperties': False,
        },
        'handler': get_linktree_template_contract,
    },
    {
        'name': 'list_linktree_templates',
        'description': (
            'Lista la biblioteca de plantillas disponibles para un Linktree (propias y compartidas por '
            'el cliente) y sus versiones con estado, errores, capturas y versión activa.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_LINKTREE_ID, 'offset': {'type': 'integer', 'minimum': 0, 'default': 0}},
            'required': ['linktree_id'],
            'additionalProperties': False,
        },
        'handler': list_linktree_templates,
    },
    {
        'name': 'get_linktree_template',
        'description': (
            'Abre el paquete fuente de una plantilla de la biblioteca: manifest, template.html, '
            'template.css, avisos y metadatos de sus imágenes. Úsalo para iterar sobre un diseño existente.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_LINKTREE_ID, **_TEMPLATE_ID},
            'required': ['linktree_id', 'template_id'],
            'additionalProperties': False,
        },
        'handler': get_linktree_template,
    },
    {
        'name': 'get_linktree_template_version',
        'description': (
            'Consulta una versión candidata o publicada: estado de validación (pending, valid, invalid), '
            'reporte completo con errores por archivo y línea, capturas disponibles, imágenes reemplazadas '
            'y si el perfil sigue vigente. Úsalo para esperar el resultado de la validación.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_LINKTREE_ID, **_VERSION_ID},
            'required': ['linktree_id', 'version_id'],
            'additionalProperties': False,
        },
        'handler': get_linktree_template_version,
    },
    {
        'name': 'upload_linktree_template',
        'description': (
            'Sube un paquete de plantilla HTML para un Linktree y crea una versión candidata que se valida '
            'en el navegador. files lleva template.html y manifest.json (obligatorios), template.css y '
            'assets/*: cada archivo con content (texto; manifest.json admite objeto JSON), base64 o '
            'asset_id de un upload. La publicación actual no cambia hasta publicar la nueva versión.'
        ),
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {
                **_LINKTREE_ID,
                'files': {
                    'type': 'array',
                    'minItems': 2,
                    'maxItems': 15,
                    'items': {
                        'type': 'object',
                        'properties': {
                            'path': {
                                'type': 'string',
                                'description': 'template.html, manifest.json, template.css o assets/<archivo>.',
                            },
                            'content': {
                                'type': ['string', 'object'],
                                'description': 'Texto UTF-8 del archivo; manifest.json admite un objeto.',
                                OPEN_REASON_KEY: 'El lector del paquete valida manifest.json, cuyas claves incluyen slots y recursos variables.',
                            },
                            'base64': {'type': 'string', 'description': 'Binario en base64 (imágenes de hasta 800 KB).'},
                            'asset_id': {
                                'type': 'string', 'format': 'uuid',
                                'description': 'Upload completado con begin_upload/complete_upload.',
                            },
                        },
                        'required': ['path'],
                        'additionalProperties': False,
                    },
                },
            },
            'required': ['linktree_id', 'files'],
            'additionalProperties': False,
        },
        'handler': upload_linktree_template,
    },
    {
        'name': 'validate_linktree_template',
        'description': (
            'Crea y valida una nueva candidata con los datos actuales del perfil a partir de una '
            'plantilla de la biblioteca (template_id) o restaurando una versión anterior (version_id). '
            'Necesario después de cambiar textos, enlaces o imágenes del Linktree antes de volver a publicar.'
        ),
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {**_LINKTREE_ID, **_TEMPLATE_ID, **_VERSION_ID},
            'required': ['linktree_id'],
            'additionalProperties': False,
        },
        'handler': validate_linktree_template,
    },
    {
        'name': 'preview_linktree_template',
        'description': (
            'Devuelve la vista previa de una versión: el documento HTML renderizado con los datos '
            'reales, el reporte de validación y las capturas a 320, 375 y 430 px como artefactos '
            'temporales descargables.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_LINKTREE_ID, **_VERSION_ID,
                'include_document': {'type': 'boolean', 'default': True},
                'include_screenshots': {'type': 'boolean', 'default': True},
            },
            'required': ['linktree_id', 'version_id'],
            'additionalProperties': False,
        },
        'handler': preview_linktree_template,
    },
    {
        'name': 'override_linktree_template_asset',
        'description': (
            'Reemplaza (asset_id o base64) o restablece (reset=true) una imagen editable del manifest '
            'sobre una versión y crea una nueva candidata validada con ese cambio.'
        ),
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {
                **_LINKTREE_ID, **_VERSION_ID,
                'key': {'type': 'string', 'description': 'Clave declarada en editable_assets.'},
                'asset_id': {'type': 'string', 'format': 'uuid', 'description': 'Upload PNG/JPG/WebP completado.'},
                'base64': {'type': 'string', 'description': 'Imagen en base64 (hasta 800 KB).'},
                'filename': {
                    'type': 'string',
                    'description': 'Nombre con extensión cuando se usa base64 (p. ej. hero.png).',
                },
                'reset': {'type': 'boolean', 'default': False},
            },
            'required': ['linktree_id', 'version_id', 'key'],
            'additionalProperties': False,
        },
        'handler': override_linktree_template_asset,
    },
    {
        'name': 'publish_linktree_template',
        'description': (
            'Publica una versión válida en la URL pública del Linktree. Exige status valid y perfil '
            'vigente; responde primero con una confirmación y se ejecuta con confirm_action.'
        ),
        'risk': 'sensitive',
        'requires_confirmation': True,
        'confirmation_message': 'Publicar la plantilla HTML en la URL pública del Linktree.',
        'impact_builder': _publish_impact,
        'input_schema': {
            'type': 'object',
            'properties': {**_LINKTREE_ID, **_VERSION_ID},
            'required': ['linktree_id', 'version_id'],
            'additionalProperties': False,
        },
        'handler': publish_linktree_template,
    },
    {
        'name': 'reset_linktree_template',
        'description': (
            'Desactiva la plantilla HTML publicada y vuelve al tema básico del editor (colores, logo y '
            'tipografía). Conserva el historial de versiones para volver a publicar.'
        ),
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': _LINKTREE_ID,
            'required': ['linktree_id'],
            'additionalProperties': False,
        },
        'handler': reset_linktree_template,
    },
    {
        'name': 'share_linktree_template',
        'description': (
            'Comparte o deja de compartir una plantilla propia con los demás Linktrees del mismo '
            'cliente. Requiere que el Linktree esté vinculado a un proyecto.'
        ),
        'risk': 'write',
        'input_schema': {
            'type': 'object',
            'properties': {**_LINKTREE_ID, **_TEMPLATE_ID, 'is_shared': {'type': 'boolean'}},
            'required': ['linktree_id', 'template_id', 'is_shared'],
            'additionalProperties': False,
        },
        'handler': share_linktree_template,
    },
    {
        'name': 'get_linktree_template_clicks',
        'description': (
            'Agrega los clics por enlace y por día de una versión publicada (por defecto la activa) '
            'en los últimos days días. Los conteos son anónimos, sin IPs ni visitantes.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_LINKTREE_ID, **_VERSION_ID,
                'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
            },
            'required': ['linktree_id'],
            'additionalProperties': False,
        },
        'handler': get_linktree_template_clicks,
    },
]
