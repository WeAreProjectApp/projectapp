/**
 * Tests for the folder picker helpers in utils/folderOptions.js.
 *
 * Lo que se fija acá es lo que hace usable el selector de carpeta de un
 * documento: los nombres se repiten por diseño (cada proyecto tiene su
 * «Entregables»), así que cada opción tiene que decir dónde está y de quién es,
 * y las carpetas del archivado automático no se ofrecen porque el backend las
 * rechaza como destino de un documento hecho a mano.
 */

import {
  buildFolderPickerOptions,
  filterFolderPickerOptions,
  folderPathLabel,
  resolveFolderPreselection,
} from '../../utils/folderOptions';

const VASTAGO = { project: 21, project_name: 'Vástago', client: 7, client_display_name: 'Vástago SAS' };
const KORE = { project: 22, project_name: 'Kore', client: 9, client_display_name: 'Kore SAS' };

// En el orden en que las sirve el store (el del panel lateral).
const FOLDERS = [
  {
    id: 5, name: 'Vástago', parent: null, folder_kind: 'project', ...VASTAGO,
    managed_project_state: { name: 'Activo', system_key: 'active' },
  },
  { id: 6, name: 'Cuentas de cobro', parent: 5, is_system_managed: true, ...VASTAGO },
  { id: 15, name: 'Anuladas a mano', parent: 6, ...VASTAGO },
  { id: 7, name: 'Entregables', parent: 5, ...VASTAGO },
  { id: 17, name: 'Sprint 1', parent: 7, ...VASTAGO },
  {
    id: 8, name: 'Kore', parent: null, folder_kind: 'project', ...KORE,
    managed_project_state: { name: 'Suspendido', system_key: 'suspended' },
  },
  { id: 9, name: 'Entregables', parent: 8, ...KORE },
  { id: 12, name: 'Plantillas', parent: null, folder_kind: 'manual' },
  { id: 13, name: 'Archivo viejo', parent: null, folder_kind: 'manual', is_archived: true },
  { id: 16, name: 'Huérfana', parent: 13, folder_kind: 'manual' },
  { id: 14, name: 'Kore SAS', parent: null, folder_kind: 'client', client: 9, client_display_name: 'Kore SAS' },
  // Sin clave `parent`: así llegan algunos fixtures mínimos.
  { id: 3, name: 'Contratos' },
];

function optionsById() {
  return Object.fromEntries(buildFolderPickerOptions(FOLDERS).map((option) => [option.id, option]));
}

describe('buildFolderPickerOptions', () => {
  it('walks the active tree parents-first, skipping archived and system-managed rows but not their manual children', () => {
    const ids = buildFolderPickerOptions(FOLDERS).map((option) => option.id);

    expect(ids).toEqual([5, 15, 7, 17, 8, 9, 12, 16, 14, 3]);
  });

  it('labels every option with its full path so repeated names stay distinct', () => {
    const options = optionsById();

    expect(options[7].pathLabel).toBe('Vástago / Entregables');
    expect(options[9].pathLabel).toBe('Kore / Entregables');
    expect(options[17].pathLabel).toBe('Vástago / Entregables / Sprint 1');
    expect(options[15].pathLabel).toBe('Vástago / Cuentas de cobro / Anuladas a mano');
  });

  it('describes location, owner and a non-active project state on the second line', () => {
    const options = optionsById();

    expect(options[5].detail).toBe('Carpeta del proyecto · Vástago SAS');
    expect(options[7].detail).toBe('Vástago · Vástago SAS');
    expect(options[9].detail).toBe('Kore · Kore SAS · Suspendido');
    expect(options[12].detail).toBe('Carpetas propias');
    expect(options[14].detail).toBe('Carpeta del cliente');
  });

  it('treats a row without parent, or under an inactive parent, as a root', () => {
    const options = optionsById();

    expect(options[3]).toMatchObject({ pathLabel: 'Contratos', detail: 'Carpetas propias' });
    expect(options[16]).toMatchObject({ pathLabel: 'Archivo viejo / Huérfana', detail: 'Archivo viejo' });
  });

  it('returns no options for a payload that is not a list', () => {
    expect(buildFolderPickerOptions({})).toEqual([]);
    expect(buildFolderPickerOptions(null)).toEqual([]);
  });
});

describe('filterFolderPickerOptions', () => {
  it('filters by every typed token across path and owner, accent- and case-blind', () => {
    const options = buildFolderPickerOptions(FOLDERS);
    const ids = (term) => filterFolderPickerOptions(options, term).map((option) => option.id);

    expect(ids('vastago entre')).toEqual([7, 17]);
    expect(ids('VÁSTAGO/Entregables')).toEqual([7, 17]);
    expect(ids('kore sas')).toEqual([8, 14, 9]);
    expect(filterFolderPickerOptions(options, '  ')).toBe(options);
  });

  it('ranks name matches before path-only matches, keeping tree order', () => {
    const options = buildFolderPickerOptions(FOLDERS);

    const ids = filterFolderPickerOptions(options, 'entregables').map((option) => option.id);

    expect(ids).toEqual([7, 9, 17]);
  });
});

describe('folderPathLabel', () => {
  it('builds the path of any listed folder, archived or system-managed included', () => {
    const cycle = [{ id: 1, name: 'A', parent: 2 }, { id: 2, name: 'B', parent: 1 }];

    expect(folderPathLabel(FOLDERS, 6)).toBe('Vástago / Cuentas de cobro');
    expect(folderPathLabel(FOLDERS, '7')).toBe('Vástago / Entregables');
    expect(folderPathLabel(FOLDERS, 13)).toBe('Archivo viejo');
    expect(folderPathLabel(FOLDERS, 99)).toBe('');
    expect(folderPathLabel(cycle, 1)).toBe('B / A');
  });
});

describe('resolveFolderPreselection', () => {
  it('resolves a preselected folder to itself or its nearest pickable ancestor', () => {
    expect(resolveFolderPreselection(FOLDERS, '7').folderId).toBe(7);
    expect(resolveFolderPreselection(FOLDERS, 6))
      .toEqual({ folderId: 5, requested: expect.objectContaining({ id: 6 }) });
    expect(resolveFolderPreselection(FOLDERS, 13))
      .toEqual({ folderId: null, requested: expect.objectContaining({ id: 13 }) });
    expect(resolveFolderPreselection(FOLDERS, 99)).toEqual({ folderId: null, requested: null });
    expect(resolveFolderPreselection(FOLDERS, 'all')).toEqual({ folderId: null, requested: null });
    expect(resolveFolderPreselection({}, 7)).toEqual({ folderId: null, requested: null });
  });
});
