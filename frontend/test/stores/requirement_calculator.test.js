import { createPinia, setActivePinia } from 'pinia';
import { useRequirementCalculatorStore } from '../../stores/requirement_calculator';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
}));

const { get_request, create_request, patch_request } = require('../../stores/services/request_http');

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

describe('useRequirementCalculatorStore', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useRequirementCalculatorStore();
    jest.clearAllMocks();
  });

  // Falla si una respuesta lenta reemplaza la versión elegida más recientemente o apaga busy antes de tiempo.
  it('keeps the latest project version while two detail requests are pending', async () => {
    const first = deferred();
    const latest = deferred();
    get_request.mockReturnValueOnce(first.promise).mockReturnValueOnce(latest.promise);

    const firstLoad = store.loadProjectVersion(14);
    const latestLoad = store.loadProjectVersion(29);

    first.resolve({ data: { id: 14, status: 'draft' } });
    await firstLoad;

    expect(store.busy).toBe(true);
    expect(store.projectVersion).toBeNull();

    latest.resolve({ data: { id: 29, status: 'approved' } });
    await latestLoad;

    expect(store.busy).toBe(false);
    expect(store.projectVersion).toEqual({ id: 29, status: 'approved' });
  });

  // quality: allow-mock-only (createDraft intentionally exposes only a bounded HTTP command and returns its server result.)
  // Falla si crear un borrador apunta a otra ruta o elimina el if_match entregado por el panel.
  it('creates a project draft with the supplied concurrency token', async () => {
    const payload = { base_revision_id: 7, note: 'Negociación inicial', if_match: 'project-8-v3' };
    create_request.mockResolvedValue({ data: { id: 41, status: 'draft' } });

    const result = await store.createDraft(8, payload);

    expect(create_request).toHaveBeenCalledWith('requirement-calculator/projects/8/', payload);
    expect(result).toEqual({ id: 41, status: 'draft' });
  });

  // quality: allow-mock-only (saveDraft intentionally exposes only a bounded HTTP command and returns its server result.)
  // Falla si guardar parámetros usa otra ruta o pierde el if_match entregado por el panel.
  it('patches a project draft with the supplied concurrency token', async () => {
    const payload = { definition: { calibration: { deviation_percent: '25' } }, if_match: 'draft-41-v2' };
    patch_request.mockResolvedValue({ data: { id: 41, status: 'draft' } });

    const result = await store.saveDraft(41, payload);

    expect(patch_request).toHaveBeenCalledWith('requirement-calculator/project-versions/41/', payload);
    expect(result).toEqual({ id: 41, status: 'draft' });
  });

  // quality: allow-mock-only (approveDraft intentionally exposes only a bounded HTTP command and returns its server result.)
  // Falla si aprobar un borrador apunta a otra ruta o pierde el if_match entregado por el panel.
  it('approves a project draft with the supplied concurrency token', async () => {
    const payload = { note: 'Aprobada por el responsable', if_match: 'draft-41-v4' };
    create_request.mockResolvedValue({ data: { id: 41, status: 'approved' } });

    const result = await store.approveDraft(41, payload);

    expect(create_request).toHaveBeenCalledWith('requirement-calculator/project-versions/41/approve/', payload);
    expect(result).toEqual({ id: 41, status: 'approved' });
  });
});
