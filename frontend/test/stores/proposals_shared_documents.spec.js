import { createPinia, setActivePinia } from 'pinia';
import { useProposalStore } from '../../stores/proposals';
import { create_request, get_request, patch_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({ create_request: jest.fn(), get_request: jest.fn(), put_request: jest.fn(), patch_request: jest.fn(), delete_request: jest.fn() }));

const proposal = () => ({
  id: 3, title: 'Portal Atlas', proposal_source_hash: 'current-proposal-version',
  sections: [{ id: 10, title: 'Detalle técnico', proposal_source_hash: 'section-opened-version', content_json: { title: 'Versión guardada' } }],
  proposal_documents: [],
});

beforeEach(() => { jest.clearAllMocks(); setActivePinia(createPinia()); get_request.mockResolvedValue({ data: proposal() }); });

describe('Proposal shared document writes', () => {
  // Falla si un refresco de la propuesta reemplaza la versión que leyó el formulario y permite sobrescribir un cambio concurrente.
  it('preserves the form source version when saving metadata', async () => {
    const store = useProposalStore();
    store.currentProposal = proposal();
    patch_request.mockResolvedValue({ data: { ...proposal(), title: 'Atlas aprobado' } });

    const result = await store.updateProposal(3, { title: 'Atlas aprobado', source_hash: 'form-opened-version' });

    expect(patch_request).toHaveBeenCalledWith('proposals/3/update/', { title: 'Atlas aprobado', source_hash: 'form-opened-version' });
    expect(result).toMatchObject({ success: true, data: { title: 'Atlas aprobado' } });
    expect(store.currentProposal.title).toBe('Atlas aprobado');
  });

  // Falla si guardar una sección usa la versión de otra sección editada más recientemente.
  it('sends the source version belonging to the edited section', async () => {
    const store = useProposalStore();
    store.currentProposal = proposal();
    patch_request.mockResolvedValue({ data: { section: { id: 10, title: 'Alcance confirmado', content_json: { title: 'Alcance confirmado' } } }, headers: { 'x-proposal-version': 'section-saved-version' } });

    await store.updateSection(10, { title: 'Alcance confirmado' });

    expect(patch_request).toHaveBeenCalledWith('proposals/sections/10/update/', { title: 'Alcance confirmado', source_hash: 'section-opened-version' });
    expect(store.currentProposal.sections[0]).toEqual({ id: 10, title: 'Alcance confirmado', content_json: { title: 'Alcance confirmado' }, proposal_source_hash: 'section-saved-version' });
  });

  // Falla si el conflicto de versión destruye la edición local antes de que el usuario pueda revisarla.
  it('keeps the current section when a stale save is rejected', async () => {
    const store = useProposalStore();
    store.currentProposal = proposal();
    const errorLog = jest.spyOn(console, 'error').mockImplementation(() => {});
    patch_request.mockRejectedValue({ response: { status: 409, data: { detail: 'La fuente cambió.', code: 'proposal_source_changed' } } });

    const result = await store.updateSection(10, { title: 'Mi título pendiente' });

    expect(result).toMatchObject({ success: false, errors: { detail: 'La fuente cambió.', code: 'proposal_source_changed' } });
    expect(store.currentProposal.sections[0]).toEqual({ id: 10, title: 'Detalle técnico', proposal_source_hash: 'section-opened-version', content_json: { title: 'Versión guardada' } });
    expect(store.isUpdating).toBe(false);
    errorLog.mockRestore();
  });

  // Falla si una carga binaria omite el control de versión o lo reemplaza con el último dato visto por otro formulario.
  it('preserves the explicit source version in an attachment upload', async () => {
    const store = useProposalStore();
    store.currentProposal = proposal();
    const form = new FormData();
    form.append('source_hash', 'attachment-opened-version');
    form.append('title', 'Anexo firmado');
    form.append('file', new File(['annex'], 'anexo.pdf', { type: 'application/pdf' }));
    create_request.mockResolvedValue({ data: { id: 31, title: 'Anexo firmado' } });

    const result = await store.uploadProposalDocument(3, form);

    expect(create_request).toHaveBeenCalledWith('proposals/3/documents/upload/', form);
    expect(form.getAll('source_hash')).toEqual(['attachment-opened-version']);
    expect(result).toMatchObject({ success: true, data: { id: 31, title: 'Anexo firmado' } });
  });
});
