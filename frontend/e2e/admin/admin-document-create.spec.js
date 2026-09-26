/**
 * E2E tests for admin document create flow.
 *
 * @flow:admin-document-create
 * Covers: page renders with mode tabs, paste Markdown mode with its
 *         Editar/Vista previa switch, file upload mode, private fixed/custom
 *         notes, form submission, and error handling.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_CREATE } from '../helpers/flow-tags.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const createdDocument = {
  id: 10, title: 'Nuevo Doc', status: 'draft', client_name: null, created_at: '2026-03-30T10:00:00Z',
};

const PORTRAIT_VIEWPORT = { width: 835, height: 1195 };

async function expectInlineControlError(page, control, message) {
  await expect(control).toHaveAttribute('aria-invalid', 'true');
  const errorId = await control.getAttribute('aria-describedby');
  expect(errorId).toBeTruthy();
  await expect(page.locator(`[id="${errorId}"]`)).toHaveText(message);
}

// Cancelar antes que Crear Documento, centrados en la misma línea, pegados al
// borde derecho y sin avisos en la fila: lo que falta se dice bajo cada campo.
async function expectActionRowAligned(actions) {
  await expect(actions.getByRole('alert')).toHaveCount(0);
  const row = await actions.boundingBox();
  const cancel = await actions.getByRole('link', { name: 'Cancelar' }).boundingBox();
  const create = await actions.getByRole('button', { name: /Crear Documento/i }).boundingBox();
  expect(cancel.x + cancel.width).toBeLessThan(create.x);
  expect(Math.abs((cancel.y + cancel.height / 2) - (create.y + create.height / 2)))
    .toBeLessThanOrEqual(1);
  expect(Math.abs((row.x + row.width) - (create.x + create.width))).toBeLessThanOrEqual(1);
}

test.describe('Admin Document Create', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test('renders create page with Pegar Markdown and Cargar Archivo tabs', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });
    await page.goto('/panel/documents/create');

    await expect(page.getByRole('button', { name: /Pegar Markdown/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Cargar Archivo/i })).toBeVisible();
    await expect(page.getByText(/Nuevo Documento/i)).toBeVisible();
  });

  test('back link navigates to documents list', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });
    await page.goto('/panel/documents/create');

    const backLink = page.getByRole('link', { name: /Volver a documentos/i });
    await expect(backLink).toBeVisible();
    await expect(backLink).toHaveAttribute('href', /\/panel\/documents/);
  });

  test('submitting paste mode form creates document and redirects to list', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let postBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        postBody = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(createdDocument) };
      }
      if (apiPath === 'documents/') return { status: 200, contentType: 'application/json', body: JSON.stringify([createdDocument]) };
      return null;
    });
    await page.goto('/panel/documents/create');

    await page.getByLabel(/T[ií]tulo/i).fill('Nuevo Doc');
    await page.getByRole('button', { name: /Pegar Markdown/i }).click();
    const textarea = page.getByPlaceholder(/Escribe o pega tu contenido en formato Markdown/i);
    await textarea.fill('# Contenido de prueba\n\nEste es el cuerpo del documento.');

    await page.getByRole('button', { name: /Crear|Guardar/i }).click();
    await page.waitForURL(/\/panel\/documents/, { timeout: 15000 });
    expect(postBody.markdown).toContain('Contenido de prueba');
  });

  test('paste mode shows the preview in place of the editor', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the create form is the surface under test; its entry from the list is covered by the canvas catalog spec)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      return null;
    });
    await page.goto('/panel/documents/create');
    const markdown = page.getByPlaceholder(/Escribe o pega tu contenido en formato Markdown/i);
    await markdown.fill('# Propuesta de servicios\n\nAlcance y entregables.');

    await page.getByRole('tab', { name: 'Vista previa', exact: true }).click();

    await expect(page.getByRole('heading', { name: 'Propuesta de servicios', level: 1 }))
      .toHaveText('Propuesta de servicios');
    await expect(markdown).toBeHidden();
    await page.getByRole('tab', { name: 'Editar', exact: true }).click();
    await expect(markdown).toHaveValue('# Propuesta de servicios\n\nAlcance y entregables.');
  });

  test('stores the client messages in the create payload', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let postBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        postBody = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(createdDocument) };
      }
      if (apiPath === 'documents/') return { status: 200, contentType: 'application/json', body: JSON.stringify([createdDocument]) };
      return null;
    });
    await page.goto('/panel/documents/create');

    const noteButton = page.getByTestId('doc-client-note-open');
    await expect(noteButton).toHaveAttribute('data-panel-action', 'notes');
    await expect(noteButton).toHaveAccessibleName('Agregar notas');
    await noteButton.click();
    await page.getByTestId('client-note-subject').fill('Caso resuelto');
    await page.getByTestId('client-note-email').fill('Hola Ana,\n\nEl caso fue resuelto.');
    await page.getByTestId('client-note-whatsapp').fill('Hola Ana, el caso ya fue resuelto.');
    await expect(page.getByTestId('client-note-submit')).toHaveText('Aplicar al borrador');
    await expect(page.getByTestId('client-note-draft-hint'))
      .toContainText('Quedarán guardadas cuando crees el documento');
    await page.getByTestId('client-note-submit').click();
    expect(postBody).toBeNull();
    await expect(page.getByText('Notas aplicadas al borrador', { exact: true })).toBeVisible();
    await expect(page.getByText('Todavía falta crear el documento para guardarlas.')).toBeVisible();
    await expect(noteButton).toHaveAccessibleName('Editar notas');

    // Opening the modal proves Nuxt hydration completed before we edit the
    // underlying form; filling SSR inputs earlier can be replaced by hydration.
    await page.locator('#doc-title').fill('Informe de soporte');
    await page.getByPlaceholder(/Escribe o pega tu contenido en formato Markdown/i)
      .fill('# Informe\n\nCaso resuelto.');

    await page.getByRole('button', { name: /Crear Documento/i }).click();
    await page.waitForURL(/\/panel\/documents/, { timeout: 15000 });

    expect(postBody.client_email_subject).toBe('Caso resuelto');
    expect(postBody.client_email_body).toBe('Hola Ana,\n\nEl caso fue resuelto.');
    expect(postBody.client_whatsapp_message).toBe('Hola Ana, el caso ya fue resuelto.');
  });

  test('stores a custom note in the create payload', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let postBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        postBody = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(createdDocument) };
      }
      return null;
    });
    await page.goto('/panel/documents/create');
    await page.getByTestId('doc-client-note-open').click();
    await page.getByTestId('client-note-add-custom').click();
    await page.getByTestId('client-note-custom-title-0').fill('Próximo paso');
    await page.getByTestId('client-note-custom-content-0').fill('Confirmar la fecha de entrega.');
    await page.getByTestId('client-note-submit').click();

    await page.locator('#doc-title').fill('Informe con contexto');
    await page.getByPlaceholder(/Escribe o pega tu contenido en formato Markdown/i)
      .fill('# Informe');

    await page.getByRole('button', { name: /Crear Documento/i }).click();
    await page.waitForURL(/\/panel\/documents/, { timeout: 15000 });

    expect(postBody.client_custom_notes).toEqual([
      { title: 'Próximo paso', content: 'Confirmar la fecha de entrega.' },
    ]);
  });

  test('rejected notes remain on the create page', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ client_email_subject: ['Revisa el asunto.'] }),
        };
      }
      return null;
    });
    await page.goto('/panel/documents/create');
    await page.getByTestId('doc-client-note-open').click();
    await page.getByTestId('client-note-subject').fill('Asunto por revisar');
    await page.getByTestId('client-note-submit').click();

    await page.locator('#doc-title').fill('Informe rechazado');
    await page.getByPlaceholder(/Escribe o pega tu contenido en formato Markdown/i)
      .fill('# Informe');

    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/documents/create-from-markdown/'),
    );
    await page.getByRole('button', { name: /Crear Documento/i }).click();
    await responsePromise;

    await expect(page.getByText('client_email_subject: Revisa el asunto.')).toBeVisible();
    await expect(page).toHaveURL(/\/panel\/documents\/create$/);
  });

  test('a server failure preserves the notes draft', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        return {
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Servicio temporalmente no disponible.' }),
        };
      }
      return null;
    });
    await page.goto('/panel/documents/create');
    await page.getByTestId('doc-client-note-open').click();
    await page.getByTestId('client-note-subject').fill('Borrador preservado');
    await page.getByTestId('client-note-submit').click();

    await page.locator('#doc-title').fill('Informe pendiente');
    await page.getByPlaceholder(/Escribe o pega tu contenido en formato Markdown/i)
      .fill('# Informe');

    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/documents/create-from-markdown/'),
    );
    await page.getByRole('button', { name: /Crear Documento/i }).click();
    await responsePromise;
    await page.getByTestId('doc-client-note-open').click();

    await expect(page.getByTestId('client-note-subject')).toHaveValue('Borrador preservado');
  });

  test('upload mode loads the file content into the readonly preview', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
      return null;
    });
    await page.goto('/panel/documents/create');

    await page.getByRole('button', { name: /Cargar Archivo/i }).click();
    await page.locator('input[type="file"]').setInputFiles({
      name: 'contrato.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# Contrato\n\nCuerpo del contrato.'),
    });

    await expect(page.getByText('contrato.md')).toBeVisible();
    await expect(page.getByPlaceholder('El contenido del archivo aparecerá aquí...'))
      .toHaveValue(/Cuerpo del contrato/);
  });

  test('upload mode submits the loaded markdown and redirects to the list', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let postBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        postBody = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(createdDocument) };
      }
      if (apiPath === 'documents/') return { status: 200, contentType: 'application/json', body: JSON.stringify([createdDocument]) };
      return null;
    });
    await page.goto('/panel/documents/create');

    await page.getByLabel(/T[ií]tulo/i).fill('Doc desde archivo');
    await page.getByRole('button', { name: /Cargar Archivo/i }).click();
    await page.locator('input[type="file"]').setInputFiles({
      name: 'anexo.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# Anexo\n\nContenido del anexo.'),
    });
    await expect(page.getByText('anexo.md')).toBeVisible();

    await page.getByRole('button', { name: /Crear|Guardar/i }).click();
    await page.waitForURL(/\/panel\/documents/, { timeout: 15000 });
    expect(postBody.markdown).toContain('Contenido del anexo.');
  });

  test('picking a project first autofills its client into the payload', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let postBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'accounting/projects/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: [{
              id: 11, name: 'Kore - Diseño', status: 'active',
              status_label: 'Activo', client_profile_id: 7,
              client_display_name: 'Kore SAS',
            }],
          }),
        };
      }
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        postBody = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify(createdDocument) };
      }
      if (apiPath === 'documents/') return { status: 200, contentType: 'application/json', body: JSON.stringify([createdDocument]) };
      if (apiPath === 'document-folders/' || apiPath === 'document-tags/') {
        return { status: 200, contentType: 'application/json', body: '[]' };
      }
      return null;
    });
    await page.goto('/panel/documents/create');

    // Proyecto PRIMERO: el selector lista todos con su dueño y elegir uno
    // completa el cliente solo (cascada inversa).
    await page.getByTestId('doc-project-select').click();
    await page.getByTestId('doc-project-select-option-11').click();
    await expect(page.getByTestId('doc-client-autocomplete')).toHaveValue('Kore SAS');

    await page.getByLabel(/T[ií]tulo/i).fill('Entregable Kore');
    const textarea = page.getByPlaceholder(/Escribe o pega tu contenido en formato Markdown/i);
    await textarea.fill('# Entregable');
    await page.getByRole('button', { name: /Crear|Guardar/i }).click();
    await page.waitForURL(/\/panel\/documents/, { timeout: 15000 });

    expect(postBody.project).toBe(11);
    expect(postBody.client).toBe(7);
  });

  test('creating inside a client folder proposes that client by default', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (?folder= is the create page's own contract —
    // the subject is the suggestion that folder context triggers)
    // quality: allow-no-interaction (the trigger IS the folder context carried
    // by the navigation; the assertions pin the concrete suggested client)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'document-folders/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([{
            id: 9, name: 'Kore - Diseño', parent: null, order: 0,
            is_archived: false, document_count: 4, children_count: 0,
          }]),
        };
      }
      if (apiPath === 'documents/folder-client-suggestion/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            client: 7, client_display_name: 'Kore SAS',
            linked_documents: 3, folder_documents: 4,
          }),
        };
      }
      if (apiPath === 'document-tags/') return { status: 200, contentType: 'application/json', body: '[]' };
      if (apiPath === 'accounting/projects/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [] }) };
      return null;
    });
    await page.goto('/panel/documents/create?folder=9');

    // Sólo prellenado, nunca lock: el hint lo dice y el selector queda vivo.
    await expect(page.getByTestId('doc-client-suggested-hint')).toBeVisible();
    await expect(page.getByTestId('doc-client-autocomplete')).toHaveValue('Kore SAS');
  });

  test('a folder that states its client is inherited, without asking the heuristic', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let suggestionCalled = false;
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
      }
      if (apiPath === 'document-folders/') {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([{
            id: 9, name: 'Kore - Diseño', parent: null, order: 0,
            is_archived: false, document_count: 4, children_count: 0,
            client: 7, client_display_name: 'Kore SAS', project: null,
          }]),
        };
      }
      if (apiPath === 'documents/folder-client-suggestion/') {
        suggestionCalled = true;
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ client: null }) };
      }
      if (apiPath === 'document-tags/') return { status: 200, contentType: 'application/json', body: '[]' };
      if (apiPath === 'accounting/projects/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [] }) };
      return null;
    });
    await page.goto('/panel/documents/create?folder=9');

    // La carpeta lo dice: es un dato, no una conjetura por mayoría.
    await expect(page.getByTestId('doc-client-autocomplete')).toHaveValue('Kore SAS');
    await expect(page.getByTestId('doc-client-suggested-hint'))
      .toContainText('Heredado de la carpeta');
    expect(suggestionCalled).toBe(false);

    // Y es un default, no una atadura: sacar el documento de la carpeta retira
    // lo heredado en vez de dejarlo pegado.
    await page.getByTestId('doc-folder-select').selectOption({ label: 'Sin carpeta' });

    await expect(page.getByTestId('doc-client-autocomplete')).toHaveValue('');
    await expect(page.getByTestId('doc-client-suggested-hint')).toHaveCount(0);
  });

  test('keeps create validation beside the incomplete fields', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const posts = [];
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        posts.push(apiPath);
        return { status: 201, contentType: 'application/json', body: JSON.stringify(createdDocument) };
      }
      return null;
    });
    await page.goto('/panel/documents/create');

    await page.getByRole('button', { name: /Crear Documento/i }).click();

    const title = page.locator('#doc-title');
    await expectInlineControlError(page, title, 'Escribe el título del documento.');
    await expectInlineControlError(
      page,
      page.locator('#doc-markdown'),
      'Pega, escribe o carga el contenido Markdown.',
    );
    expect(posts).toHaveLength(0);

    // Completar un campo retira sólo su aviso; el del contenido acompaña al
    // modo de carga porque sigue faltando.
    await title.fill('Informe mensual');
    await expect(title).not.toHaveAttribute('aria-invalid', 'true');
    await page.getByRole('button', { name: /Cargar Archivo/i }).click();
    await expect(page.getByText('Pega, escribe o carga el contenido Markdown.', { exact: true }))
      .toBeVisible();
  });

  test('keeps Cancelar and Crear Documento aligned after a failed attempt', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => (apiPath === 'auth/check/' ? authCheck : null));
    await page.goto('/panel/documents/create');

    const actions = page.getByTestId('doc-create-actions');
    await actions.getByRole('button', { name: /Crear Documento/i }).click();
    await expect(page.locator('#doc-title')).toHaveAttribute('aria-invalid', 'true');
    await expectActionRowAligned(actions);

    // Por debajo de landscape las acciones bajan al pie con el mismo orden.
    await page.setViewportSize(PORTRAIT_VIEWPORT);
    await expectActionRowAligned(page.getByTestId('doc-create-actions-compact'));
  });

  test('a rejected title stays under its field instead of a notification', {
    tag: [...ADMIN_DOCUMENT_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const rejection = 'Asegúrate de que este campo no tenga más de 255 caracteres.';
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ title: [rejection] }),
        };
      }
      return null;
    });
    await page.goto('/panel/documents/create');

    const title = page.locator('#doc-title');
    await title.fill('Informe con un título demasiado largo');
    await page.getByPlaceholder(/Escribe o pega tu contenido en formato Markdown/i).fill('# Informe');
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/documents/create-from-markdown/'),
    );
    await page.getByRole('button', { name: /Crear Documento/i }).click();
    await responsePromise;

    await expectInlineControlError(page, title, rejection);
    await expect(title).toBeFocused();
    await expect(page.getByText(/^title:/)).toHaveCount(0);
    await expect(page).toHaveURL(/\/panel\/documents\/create$/);
  });
});
