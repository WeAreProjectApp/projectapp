"""Validation shared by the panel API and the Documents MCP connector."""


MAX_CUSTOM_NOTE_TITLE_LENGTH = 255


class DocumentNotesValidationError(ValueError):
    """Raised when the private custom-notes payload has an invalid shape."""


def normalize_client_custom_notes(value):
    """Return an ordered, trimmed list of private document notes."""
    if not isinstance(value, list):
        raise DocumentNotesValidationError('Debe ser una lista de notas.')

    normalized = []
    for index, note in enumerate(value, start=1):
        if not isinstance(note, dict):
            raise DocumentNotesValidationError(
                f'La nota {index} debe contener title y content.',
            )

        title = note.get('title')
        content = note.get('content')
        if not isinstance(title, str) or not title.strip():
            raise DocumentNotesValidationError(
                f'El título de la nota {index} es obligatorio.',
            )
        if len(title.strip()) > MAX_CUSTOM_NOTE_TITLE_LENGTH:
            raise DocumentNotesValidationError(
                f'El título de la nota {index} no puede superar '
                f'{MAX_CUSTOM_NOTE_TITLE_LENGTH} caracteres.',
            )
        if not isinstance(content, str) or not content.strip():
            raise DocumentNotesValidationError(
                f'El contenido de la nota {index} es obligatorio.',
            )

        item = {
            'title': title.strip(),
            'content': content.strip(),
        }
        if note.get('text_formats'):
            from content.services.editorial_format import validate_formats
            item['text_formats'] = validate_formats('documentnote', item, note['text_formats'])
        normalized.append(item)

    return normalized
