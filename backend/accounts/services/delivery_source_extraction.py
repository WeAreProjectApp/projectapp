"""Bounded source excerpts with locators that can be checked against evidence."""
from io import StringIO
import json
from pathlib import Path
import re

from content.services.attachment_markdown import (
    MAX_FILE_BYTES, MAX_SOURCE_CHARACTERS, SourceFragmentBuffer,
    extract_attachment_source, source_section_title,
)
from content.services.markdown_export import MarkdownExportError

MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 5000
MAX_JSON_LOCATOR_CHARACTERS = 2048
_HEADING = re.compile(r'^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$')
_FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
_EXCLUDED_JSON_KEYS = {
    'internalnotes', 'privatenotes', 'customnotes', 'privatedeliverycopy',
    'internaldeliverycopy', 'filepath', 'filesystempath', 'storagepath',
    'generatedfile', 'signedfile', 'privatefile', 'file', 'path',
    'signatureip', 'signatureuseragent', 'accesstoken',
    'type', 'level', 'style', 'align', 'ordered', 'language',
    'templatestyle', 'covertype', 'includeportada', 'includesubportada',
    'includecontraportada',
}


def _markdown_source(markdown):
    output = SourceFragmentBuffer()
    if len(markdown) > MAX_SOURCE_CHARACTERS:
        output.omit('Se alcanzó el límite de 60.000 caracteres; quedó contenido sin incluir.')
    section = ''
    block = []
    start = 1
    fence = ''
    fence_length = 0

    def flush(end):
        locator = f'Sección «{section}»' if section else 'Documento'
        locator += f' · líneas {start}–{end}'
        return output.append(locator, '\n'.join(block))

    number = 0
    for number, raw_line in enumerate(StringIO(markdown[:MAX_SOURCE_CHARACTERS]), 1):
        line = raw_line.rstrip('\r\n')
        marker = _FENCE.match(line)
        heading = _HEADING.match(line) if not fence else None
        if (not line.strip() or heading) and block and not fence:
            if not flush(number - 1):
                return output.payload()
            block = []
        if heading:
            section = source_section_title(heading.group(1), output)
        if line.strip() or fence:
            if not block:
                start = number
            block.append(line)
        if marker:
            if not fence:
                fence, fence_length = marker.group(1)[0], len(marker.group(1))
            elif marker.group(1)[0] == fence and len(marker.group(1)) >= fence_length and not marker.group(2).strip():
                fence = ''
    if block:
        flush(number)
    if not output.fragments:
        output.warnings.append('La fuente Markdown está vacía; no hay texto para preparar una guía.')
    return output.payload()


def _json_source(content):
    output = SourceFragmentBuffer()
    output.limits.update({
        'max_json_depth': MAX_JSON_DEPTH, 'max_json_nodes': MAX_JSON_NODES,
        'max_json_locator_characters': MAX_JSON_LOCATOR_CHARACTERS,
    })
    visited = 0
    active = True

    def count_node():
        nonlocal visited, active
        if not active:
            return False
        visited += 1
        if visited > MAX_JSON_NODES:
            output.omit('Se alcanzó el límite de 5.000 elementos JSON; quedó contenido sin incluir.')
            active = False
            return False
        return True

    def walk(value, path, depth):
        nonlocal active
        if not count_node():
            return
        if depth > MAX_JSON_DEPTH:
            output.omit('Se alcanzó el límite de 32 niveles JSON; quedó contenido sin incluir.')
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if len(str(key)) + len(path) + 4 > MAX_JSON_LOCATOR_CHARACTERS:
                    if not count_node():
                        break
                    output.omit('Una referencia JSON supera 2.048 caracteres; ese contenido no se incluyó.')
                    continue
                normalized = re.sub(r'[^a-z0-9]', '', str(key).lower())
                if normalized in _EXCLUDED_JSON_KEYS or normalized.startswith(('internal', 'private')):
                    if not count_node():
                        break
                    continue
                child_path = f'{path}.{key}' if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', str(key)) else f'{path}[{json.dumps(str(key), ensure_ascii=False)}]'
                if len(child_path) > MAX_JSON_LOCATOR_CHARACTERS:
                    if not count_node():
                        break
                    output.omit('Una referencia JSON supera 2.048 caracteres; ese contenido no se incluyó.')
                    continue
                walk(child, child_path, depth + 1)
                if not active:
                    break
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f'{path}[{index}]', depth + 1)
                if not active:
                    break
        elif isinstance(value, (str, int, float, bool)):
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            active = output.append(f'Bloque {path}', text)

    if isinstance(content, dict) and 'blocks' in content:
        walk(content['blocks'], '$.blocks', 0)
    else:
        walk(content, '$', 0)
    output.limits['json_nodes_examined'] = min(visited, MAX_JSON_NODES)
    if not output.fragments:
        output.warnings.append('La fuente JSON no contiene texto visible para preparar una guía.')
    return output.payload()


def extract_prompt_source(raw_bytes, filename, markdown='', content_json=None):
    """Prefer supplied file bytes; failed signed files never use live text."""
    output = SourceFragmentBuffer()
    if raw_bytes:
        if not isinstance(raw_bytes, (bytes, bytearray, memoryview)):
            output.warnings.append('No se pudo leer el contenido del archivo.')
            return output.payload()
        if len(raw_bytes) > MAX_FILE_BYTES:
            output.warnings.append('El archivo supera el límite de 15 MB; no se extrajo su contenido.')
            return output.payload()
        data = bytes(raw_bytes)
        suffix = Path(filename or '').suffix.lower()
        if data.startswith(b'%PDF-'):
            suffix = '.pdf'
        try:
            if suffix in ('.pdf', '.docx'):
                return extract_attachment_source(data, suffix)
            if suffix in ('.md', '.markdown', '.txt'):
                return _markdown_source(data.decode('utf-8-sig'))
            if suffix == '.json':
                return _json_source(json.loads(data.decode('utf-8-sig')))
            output.warnings.append('El formato no admite extracción de texto verificable; requiere revisión del original.')
        except MarkdownExportError as exc:
            output.warnings.append(str(exc))
        except (UnicodeError, ValueError, RecursionError):
            output.warnings.append('No se pudo leer la fuente; puede estar dañada o usar una codificación no admitida.')
        return output.payload()
    if isinstance(markdown, str) and markdown.strip():
        return _markdown_source(markdown)
    if content_json is not None:
        return _json_source(content_json)
    if isinstance(markdown, str) and markdown:
        return _markdown_source(markdown)
    if raw_bytes is not None:
        output.warnings.append('El archivo está vacío o no contiene texto disponible para preparar una guía.')
        return output.payload()
    result = output.payload()
    result['status'] = 'missing'
    result['warnings'] = ['La fuente no está disponible; falta su archivo o contenido.']
    return result
