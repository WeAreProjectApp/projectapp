"""Parse untrusted PDFs in a bounded child process, without Django setup."""
import io
import json
import resource
import sys


def inspect_pdf(data, *, extract=False):
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            return {'error': 'No se admiten PDF cifrados o protegidos por contraseña.'}
        if not len(reader.pages):
            return {'error': 'El PDF debe contener al menos una página.'}
    except Exception:
        return {'error': 'El archivo no es un PDF válido o está dañado.'}
    if not extract:
        return {'valid': True}
    parts, remaining, status = [], 500_000, 'indexed'
    try:
        for index, page in enumerate(reader.pages):
            if index >= 200 or remaining <= 0:
                status = 'partial'
                break
            # Memory/CPU limits apply before any decompression happens. A huge
            # stream can terminate extraction without invalidating the PDF.
            text = page.extract_text() or ''
            if len(text) > remaining:
                status = 'partial'
            parts.append(text[:remaining].replace('\x00', ''))
            remaining -= len(text)
    except Exception:
        status = 'partial' if parts else 'unavailable'
    text = '\n'.join(parts)
    if not text.strip() and status == 'indexed':
        status = 'empty'
    return {'text': text, 'status': status}


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))
    print(json.dumps(inspect_pdf(sys.stdin.buffer.read(25 * 1024 * 1024 + 1), extract='--extract' in sys.argv)))
