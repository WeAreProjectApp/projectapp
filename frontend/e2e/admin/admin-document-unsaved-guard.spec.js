/**
 * E2E tests for the unsaved-changes guard on the document editor and creator.
 *
 * @flow:admin-document-unsaved-guard
 * Covers: a pristine form showing no warning and a disabled save button, the
 *         warning naming the fields it holds, the three exits offered when
 *         leaving with pending changes (guardar / descartar / seguir
 *         editando), the panel refresh button asking before it overwrites, a
 *         create form arriving from a folder not being born dirty, and the
 *         client and folder pickers not manufacturing a warning while they are
 *         only searching.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_UNSAVED_GUARD } from '../helpers/flow-tags.js';

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

const authCheck = json({ user: { username: 'admin', is_staff: true } });

const mockDocument = {
  id: 1,
  title: 'Contrato de Servicios',
  status: 'draft',
  content_markdown: '# Contrato\n\nEste es el contenido.',
  client: 7,
  client_display_name: 'Kore SAS',
  project: null,
  language: 'es',
  template_style: 'professional',
};

/** El juego de stubs que el editor necesita para montar completo. */
function baseHandler(extra = () => null) {
  return async (ctx) => {
    const { apiPath } = ctx;
    const fromExtra = await extra(ctx);
    if (fromExtra) return fromExtra;
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'documents/1/detail/') return json(mockDocument);
    if (apiPath === 'accounting/projects/') return json({ results: [] });
    if (apiPath === 'document-folders/') return json([{ id: 3, name: 'Contratos', is_archived: false }]);
    if (apiPath === 'document-tags/') return json([]);
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (apiPath === 'proposals/client-profiles/status-counts/') {
      return json({ all: 0, active: 0, orphans: 0, archived: 0 });
    }
    if (apiPath === 'proposals/client-profiles/') return json([]);
    return null;
  };
}

const notice = (page) => page.getByTestId('doc-unsaved-notice');

/**
 * Anclado: el diálogo del guard se titula "Título sin guardar", así que un
 * match laxo por etiqueta alcanza también al role=dialog.
 */
const titleField = (page) => page.getByRole('textbox', { name: /^T[ií]tulo\s*\*?$/i });

test.describe('Admin Document — Unsaved Changes Guard', () => {
  // Salir del editor compila la ruta del listado por primera vez, y ese
  // arranque en frío se come buena parte del presupuesto por defecto.
  test.setTimeout(90_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test.describe('Editar', () => {
    // La red contra falsos positivos: un aviso que aparece solo enseña a
    // ignorarlo, y es exactamente lo que haría un baseline mal tomado.
    test('a form nobody touched shows no warning and cannot be saved', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:display', '@responsive:canvas'],
    }, async ({ page }) => {
      // quality: allow-deep-link (el editor se alcanza por URL en todo el spec)
      await mockApi(page, baseHandler());
      await page.goto('/panel/documents/1/edit');
      await expect(titleField(page)).toHaveValue('Contrato de Servicios');

      // Escribir el MISMO valor es la prueba de que el aviso compara contra lo
      // cargado en vez de marcar "tocado": tipear no es cambiar.
      await titleField(page).fill('Contrato de Servicios');
      await page.getByTestId('doc-client-autocomplete').click();

      await expect(titleField(page)).toHaveValue('Contrato de Servicios');
      await expect(notice(page)).toBeHidden();
      await expect(page.getByTestId('doc-save')).toBeDisabled();
    });

    test('editing the title raises a warning that names that field', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (el editor se alcanza por URL en todo el spec)
      await mockApi(page, baseHandler());
      await page.goto('/panel/documents/1/edit');
      await titleField(page).fill('Contrato Actualizado');

      await expect(notice(page)).toContainText('Título sin guardar');
      await expect(page.getByTestId('doc-save')).toBeEnabled();
    });

    test('leaving with pending changes saves them and then navigates', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      let patchCalled = false;
      // quality: allow-deep-link (el editor se alcanza por URL en todo el spec)
      await mockApi(page, baseHandler(async ({ apiPath, method }) => {
        if (apiPath === 'documents/1/update/' && method === 'PATCH') {
          patchCalled = true;
          return json({ ...mockDocument, title: 'Contrato Actualizado' });
        }
        if (apiPath === 'documents/' || apiPath.startsWith('documents/?')) return json({ results: [] });
        if (apiPath === 'documents/counts/') return json({});
        return null;
      }));
      await page.goto('/panel/documents/1/edit');
      await titleField(page).fill('Contrato Actualizado');
      await expect(notice(page)).toBeVisible();

      await page.getByRole('link', { name: /Volver a documentos/i }).click();
      await page.getByTestId('confirm-modal-confirm').click();

      await expect(page).toHaveURL(/\/panel\/documents(\?|$)/, { timeout: 60_000 });
      expect(patchCalled).toBe(true);
    });

    test('discarding pending changes navigates without saving them', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      let patchCalled = false;
      // quality: allow-deep-link (el editor se alcanza por URL en todo el spec)
      await mockApi(page, baseHandler(async ({ apiPath, method }) => {
        if (apiPath === 'documents/1/update/' && method === 'PATCH') {
          patchCalled = true;
          return json(mockDocument);
        }
        if (apiPath === 'documents/' || apiPath.startsWith('documents/?')) return json({ results: [] });
        if (apiPath === 'documents/counts/') return json({});
        return null;
      }));
      await page.goto('/panel/documents/1/edit');
      await titleField(page).fill('Contrato Actualizado');

      await page.getByRole('link', { name: /Volver a documentos/i }).click();
      await page.getByTestId('confirm-modal-secondary').click();

      await expect(page).toHaveURL(/\/panel\/documents(\?|$)/, { timeout: 60_000 });
      expect(patchCalled).toBe(false);
    });

    test('choosing to keep editing leaves the page and the edits in place', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:failure'],
    }, async ({ page }) => {
      // quality: allow-deep-link (el editor se alcanza por URL en todo el spec)
      await mockApi(page, baseHandler());
      await page.goto('/panel/documents/1/edit');
      await titleField(page).fill('Contrato Actualizado');

      await page.getByRole('link', { name: /Volver a documentos/i }).click();
      await page.getByRole('button', { name: 'Seguir editando' }).click();

      await expect(page).toHaveURL(/\/panel\/documents\/1\/edit/);
      await expect(titleField(page)).toHaveValue('Contrato Actualizado');
      await expect(notice(page)).toBeVisible();
    });

    // El refresh global vuelve a pedir el documento y pisaba el formulario sin
    // decir nada: la pérdida era invisible incluso para quien la causaba.
    test('the refresh button asks before it overwrites pending edits', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      // quality: allow-deep-link (el editor se alcanza por URL en todo el spec)
      await mockApi(page, baseHandler());
      await page.goto('/panel/documents/1/edit');
      await titleField(page).fill('Contrato Actualizado');

      await page.getByRole('button', { name: /Actualizar datos/i }).click();
      await page.getByRole('button', { name: 'Seguir editando' }).click();

      await expect(titleField(page)).toHaveValue('Contrato Actualizado');
    });

    // El test que habría cazado toda esta clase de bug: buscar no es editar.
    test('searching in the client picker raises no warning on its own', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (el editor se alcanza por URL en todo el spec)
      await mockApi(page, baseHandler());
      await page.goto('/panel/documents/1/edit');
      await expect(page.getByTestId('doc-client-autocomplete')).toHaveValue('Kore SAS');

      await page.getByTestId('doc-client-autocomplete').fill('otra');
      await titleField(page).click();

      await expect(notice(page)).toBeHidden();
      await expect(page.getByTestId('doc-client-autocomplete')).toHaveValue('Kore SAS');
    });

    test('searching in the folder picker raises no warning on its own', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (el editor se alcanza por URL en todo el spec)
      await mockApi(page, baseHandler(async ({ apiPath }) => (
        apiPath === 'documents/1/detail/' ? json({ ...mockDocument, folder: 3 }) : null
      )));
      await page.goto('/panel/documents/1/edit');
      await expect(page.getByTestId('doc-folder-select')).toHaveValue('Contratos');

      await page.getByTestId('doc-folder-select').fill('otra');
      await titleField(page).click();

      await expect(notice(page)).toBeHidden();
      await expect(page.getByTestId('doc-folder-select')).toHaveValue('Contratos');
    });
  });

  test.describe('Crear', () => {
    test('a create form opened inside a folder is not born dirty', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (el ?folder= de la URL ES el sujeto del test)
      await mockApi(page, baseHandler(async ({ apiPath }) => {
        if (apiPath.startsWith('documents/folder-client-suggestion/')) {
          return json({ client: 7, client_display_name: 'Kore SAS' });
        }
        return null;
      }));
      await page.goto('/panel/documents/create?folder=3');

      // La carpeta llegó del ?folder= y arrastró su cliente sugerido: con todo
      // eso puesto, el formulario sigue sin considerarse tocado.
      await expect(page.getByTestId('doc-folder-select')).toHaveValue('Contratos');
      await expect(page.getByTestId('doc-create-unsaved-notice')).toBeHidden();
      await expect(page.getByTestId('doc-client-autocomplete')).toHaveValue('Kore SAS');

      // Y el aviso sí responde a una edición real, ida y vuelta.
      await titleField(page).fill('Borrador');
      await expect(page.getByTestId('doc-create-unsaved-notice')).toContainText('Título sin guardar');

      await titleField(page).fill('');
      await expect(page.getByTestId('doc-create-unsaved-notice')).toBeHidden();
    });

    test('creating a document reaches the editor without the guard interrupting', {
      tag: [...ADMIN_DOCUMENT_UNSAVED_GUARD, '@role:admin', '@outcome:success'],
    }, async ({ page }) => {
      // quality: allow-deep-link (la creación arranca en su propia ruta)
      await mockApi(page, baseHandler(async ({ apiPath, method }) => {
        if (apiPath === 'documents/create-from-markdown/' && method === 'POST') {
          return json({ id: 1, title: 'Nuevo' });
        }
        return null;
      }));
      await page.goto('/panel/documents/create');

      await titleField(page).fill('Nuevo');
      await page.getByPlaceholder(/Escribe o pega tu contenido/i).fill('# Hola');
      await expect(page.getByTestId('doc-create-unsaved-notice')).toBeVisible();

      await page.getByRole('button', { name: /Crear Documento/i }).first().click();

      await expect(page).toHaveURL(/\/panel\/documents\/1\/edit/, { timeout: 30_000 });
    });
  });
});
