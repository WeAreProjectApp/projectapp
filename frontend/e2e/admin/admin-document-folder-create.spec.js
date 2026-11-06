import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_FOLDER_MANAGE } from '../helpers/flow-tags.js';
import { folderProject, setupFolderCreation } from '../helpers/document-folder-creation.js';

test.setTimeout(60_000);

async function openProject(page) {
  await page.goto('/es-co/panel/documents', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('documents-navigation-project-40').click();
}

async function openCreation(page, name) {
  await page.getByTestId('documents-new-folder').click();
  await page.getByTestId('folder-form-name').fill(name);
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, { token: 'folder-create-test', userAuth: { id: 8700, role: 'admin', is_staff: true } });
});

for (const origin of [
  { label: 'project root', parent: 200, path: folderProject.name, open: openProject },
  { label: 'open subfolder', parent: 201, path: `${folderProject.name} / Entregables`, open: async (page) => {
    await openProject(page);
    await page.getByRole('row', { name: /Entregables/ }).click();
  } },
]) {
  test(`creates a folder inside the ${origin.label}`, {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = await setupFolderCreation(page);
    await origin.open(page);
    await openCreation(page, 'Carpeta creada desde cabecera');
    await expect(page.getByTestId('folder-form-destination')).toHaveText(`Destino: ${origin.path}`);

    await page.getByTestId('folder-form-save').click();

    await expect.poll(() => state.created).toMatchObject({ parent: origin.parent, project: 40, client: 7 });
    await expect(page.getByRole('row', { name: /Carpeta creada desde cabecera/ })).toBeVisible();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('row', { name: /Carpeta creada desde cabecera/ })).toBeVisible();
  });
}

test('retains the selected project when it has no managed root', {
  tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const state = await setupFolderCreation(page, { root: false });
  await openProject(page);
  await openCreation(page, 'Carpeta del proyecto sin raíz');
  await expect(page.getByTestId('folder-form-destination')).toContainText('Ninguna (carpeta raíz)');

  await page.getByTestId('folder-form-save').click();

  await expect.poll(() => state.created).toMatchObject({ parent: null, project: 40, client: 7 });
  await expect(page.getByRole('row', { name: /Carpeta del proyecto sin raíz/ })).toBeVisible();
});

test('keeps the form open when the folder name is rejected', {
  tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:error'],
}, async ({ page }) => {
  await setupFolderCreation(page, { failCreate: true });
  await openProject(page);
  await openCreation(page, 'Nombre repetido');

  await page.getByTestId('folder-form-save').click();

  await expect(page.getByText('Ya existe una carpeta con ese nombre.')).toBeVisible();
  await expect(page.getByTestId('folder-form-name')).toHaveValue('Nombre repetido');
  await expect(page.getByTestId('folder-form-destination')).toContainText(folderProject.name);
});

test('cancels creation without adding a folder', {
  tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const state = await setupFolderCreation(page);
  await openProject(page);
  await openCreation(page, 'Carpeta cancelada');

  await page.getByTestId('folder-form-cancel').click();

  await expect(page.getByTestId('folder-form-name')).toHaveCount(0);
  expect(state.created).toBeNull();
  await expect(page.getByRole('row', { name: /Carpeta cancelada/ })).toHaveCount(0);
});

test('creates inside the matching subfolder identified by its branch', {
  tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const state = await setupFolderCreation(page);
  await openProject(page);
  await page.getByRole('button', { name: /Gestionar/i }).click();
  const parent = page.getByTestId('folder-manager-parent');
  await parent.fill('aprob');
  await expect(page.getByTestId('folder-manager-parent-detail-202')).toHaveText(`${folderProject.name} / Entregables`);
  await page.getByTestId('folder-manager-parent-option-202').click();
  await expect(parent).toHaveValue(`${folderProject.name} / Entregables / Diseño aprobado`);
  await page.getByTestId('folder-manager-new-name').fill('Revisión elegida');

  await page.getByRole('button', { name: 'Crear', exact: true }).click();

  await expect.poll(() => state.created).toMatchObject({ parent: 202, project: 40, client: 7 });
  await expect(page.getByTestId('folder-manager-branch-800')).toHaveText(`${folderProject.name} / Entregables / Diseño aprobado`);
  await page.getByRole('button', { name: 'Cerrar', exact: true }).last().click();
  await page.getByRole('row', { name: /Entregables/ }).click();
  await page.getByRole('row', { name: /Diseño aprobado/ }).click();
  await expect(page.getByRole('row', { name: /Revisión elegida/ })).toBeVisible();
});
