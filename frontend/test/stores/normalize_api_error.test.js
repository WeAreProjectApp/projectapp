/**
 * Tests for normalizeApiError — turns the various backend error payload shapes
 * into a consistent { message, code, hint, fieldErrors, status }.
 */

import {
  normalizeApiError,
  normalizeBlobApiError,
  numericIdsFromError,
} from '../../stores/services/normalize_api_error';

function axiosError(status, data) {
  return { response: { status, data } };
}

describe('normalizeApiError', () => {
  it('reads { error, code, hint }', () => {
    const r = normalizeApiError(axiosError(400, {
      error: 'Falta el correo del cliente.',
      code: 'missing_client_email',
      hint: 'Agrega el correo del cliente.',
    }));
    expect(r).toEqual({
      message: 'Falta el correo del cliente.',
      code: 'missing_client_email',
      hint: 'Agrega el correo del cliente.',
      fieldErrors: null,
      status: 400,
    });
  });

  it('falls back to DRF { detail }', () => {
    const r = normalizeApiError(axiosError(403, { detail: 'No autorizado.' }));
    expect(r.message).toBe('No autorizado.');
    expect(r.status).toBe(403);
  });

  it('reads { message }', () => {
    const r = normalizeApiError(axiosError(400, { message: 'Algo pasó.' }));
    expect(r.message).toBe('Algo pasó.');
  });

  it('extracts serializer field errors and uses the first as the message', () => {
    const r = normalizeApiError(axiosError(400, {
      email: ['Correo inválido.'],
      name: ['Requerido.'],
    }));
    expect(r.message).toBe('Correo inválido.');
    expect(r.fieldErrors).toEqual({ email: 'Correo inválido.', name: 'Requerido.' });
  });

  it('keeps field errors alongside a direct message', () => {
    const r = normalizeApiError(axiosError(400, {
      error: 'Revisa el formulario.',
      email: ['Correo inválido.'],
    }));
    expect(r.message).toBe('Revisa el formulario.');
    expect(r.fieldErrors).toEqual({ email: 'Correo inválido.' });
  });

  it('handles a bare string payload', () => {
    const r = normalizeApiError(axiosError(500, 'Internal Server Error'));
    expect(r.message).toBe('Internal Server Error');
  });

  it.each([500, 502, 403])('hides HTML bodies for HTTP %s', (status) => {
    const result = normalizeApiError(axiosError(status, '<!doctype html><html>private traceback</html>'), 'Inténtalo de nuevo.');

    expect(result.message).toBe('Inténtalo de nuevo.');
    expect(result.fieldErrors).toBeNull();
  });

  it('hides non-markup text served as HTML', () => {
    const result = normalizeApiError({ response: { status: 500, data: 'private diagnostics', headers: { 'content-type': 'text/html; charset=utf-8' } } }, 'Inténtalo de nuevo.');

    expect(result.message).toBe('Inténtalo de nuevo.');
  });

  it('hides HTML embedded in JSON messages', () => {
    const result = normalizeApiError(axiosError(500, { error: '<h1>traceback</h1>', hint: '<p>private</p>' }), 'Inténtalo de nuevo.');

    expect(result.message).toBe('Inténtalo de nuevo.');
    expect(result.hint).toBeNull();
  });

  it('uses the fallback when there is no response', () => {
    const r = normalizeApiError(new Error('network down'), 'Sin conexión.');
    expect(r.message).toBe('Sin conexión.');
    expect(r.status).toBeNull();
  });

  it('uses the fallback for an empty object payload', () => {
    const r = normalizeApiError(axiosError(400, {}), 'Error genérico.');
    expect(r.message).toBe('Error genérico.');
  });

  // The machine payload must not leak into the human-facing field errors:
  // fieldErrors feeds per-field messages for every store in the app.
  it('keeps a numeric missing_ids array out of fieldErrors', () => {
    const r = normalizeApiError(
      axiosError(409, {
        error: '1 de los ingresos seleccionados ya no existe.',
        code: 'records_not_found',
        missing_ids: [2],
      }),
    );

    expect(r.message).toBe('1 de los ingresos seleccionados ya no existe.');
    expect(r.code).toBe('records_not_found');
    expect(r.fieldErrors).toBeNull();
  });
});

describe('normalizeBlobApiError', () => {
  it('reads the payload hidden inside a blob body', async () => {
    const error = axiosError(400, new Blob([JSON.stringify({ detail: 'Sin contenido.' })]));

    expect(await normalizeBlobApiError(error, 'Falló.')).toMatchObject({
      message: 'Sin contenido.',
      status: 400,
    });
  });

  it('keeps the field-error map from a blob body', async () => {
    const error = axiosError(400, new Blob([JSON.stringify({ folder_id: ['Archivada.'] })]));

    const result = await normalizeBlobApiError(error, 'Falló.');

    expect(result.fieldErrors).toEqual({ folder_id: 'Archivada.' });
  });

  it('falls back when the blob is not json', async () => {
    const error = axiosError(500, new Blob(['<html>502</html>']));

    expect((await normalizeBlobApiError(error, 'Falló.')).message).toBe('Falló.');
  });

  it('delegates plain json errors untouched', async () => {
    const error = axiosError(403, { detail: 'Sin permisos.' });

    expect((await normalizeBlobApiError(error, 'Falló.')).message).toBe('Sin permisos.');
  });
});

describe('numericIdsFromError', () => {
  it('reads the ids the server named', () => {
    expect(numericIdsFromError(axiosError(409, { missing_ids: [2, 7] })))
      .toEqual([2, 7]);
  });

  it('returns nothing when the key is absent', () => {
    expect(numericIdsFromError(axiosError(400, { error: 'Nope' }))).toEqual([]);
  });

  it('returns nothing when the key is not a list', () => {
    expect(numericIdsFromError(axiosError(409, { missing_ids: 'dos' }))).toEqual([]);
  });

  it('drops entries that are not numbers', () => {
    expect(numericIdsFromError(axiosError(409, { missing_ids: [2, null, 'x'] })))
      .toEqual([2]);
  });

  it('survives an error with no response at all', () => {
    expect(numericIdsFromError(new Error('network down'))).toEqual([]);
  });
});
