import { mount, flushPromises } from '@vue/test-utils';
import { ref } from 'vue';
import ProposalSharedBinary from '../../components/BusinessProposal/admin/ProposalSharedBinary.vue';
import { create_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({ create_request: jest.fn() }));

let wrapper;
async function selectFile() {
  const input = wrapper.get('[data-testid="shared-binary-file"]');
  Object.defineProperty(input.element, 'files', { value: [new File(['new annex'], 'anexo-nuevo.pdf', { type: 'application/pdf' })], configurable: true });
  await input.trigger('change');
}
function open() {
  wrapper = mount(ProposalSharedBinary, { props: { source: { document_id: 91, source_hash: 'version-opened', can_replace_binary: true } }, global: { stubs: { NuxtLink: { template: '<a><slot /></a>' } } } });
}

beforeEach(() => { jest.clearAllMocks(); global.useI18n = () => ({ locale: ref('es-co') }); });
afterEach(() => { wrapper?.unmount(); delete global.useI18n; });

describe('ProposalSharedBinary', () => {
  // Falla si el gestor sustituye el archivo vigente en vez de guardar una revisión pendiente con su versión de origen.
  it('saves the selected attachment as a pending draft', async () => {
    create_request.mockResolvedValue({ data: { document: { source_hash: 'version-saved' } } });
    open();
    await selectFile();
    await wrapper.get('[data-testid="shared-binary-save"]').trigger('click');
    await flushPromises();

    const [endpoint, body] = create_request.mock.calls[0];
    expect(endpoint).toBe('documents/91/proposal-source/');
    expect(body.get('source_hash')).toBe('version-opened');
    expect(body.get('file').name).toBe('anexo-nuevo.pdf');
    expect(wrapper.get('[role="status"]').text()).toBe('Borrador guardado. Revisa el nuevo paquete para hacerlo vigente.');
    expect(wrapper.emitted('updated')).toEqual([[]]);
    expect(wrapper.get('[data-testid="shared-binary-save"]').element.disabled).toBe(true);
  });

  // Falla si un conflicto borra el adjunto o lo reintenta contra una versión que el usuario no revisó.
  it('preserves the file after a source version conflict', async () => {
    create_request.mockRejectedValue({ response: { status: 409 } });
    open();
    await selectFile();
    await wrapper.get('[data-testid="shared-binary-save"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="shared-binary-save"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe('La fuente cambió. Conservamos tu archivo; revisa la versión actual antes de reintentar.');
    expect(create_request.mock.calls.map(([, body]) => [body.get('source_hash'), body.get('file').name])).toEqual([
      ['version-opened', 'anexo-nuevo.pdf'], ['version-opened', 'anexo-nuevo.pdf'],
    ]);
    expect(wrapper.emitted('updated')).toBeUndefined();
    expect(wrapper.get('[data-testid="shared-binary-save"]').element.disabled).toBe(false);
  });

  // Falla si una caída del servidor muestra una confirmación o pierde el archivo seleccionado.
  it('reports a failed draft save without clearing the attachment', async () => {
    create_request.mockRejectedValue({ response: { status: 503 } });
    open();
    await selectFile();
    await wrapper.get('[data-testid="shared-binary-save"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe('No se pudo guardar el borrador. Conservamos tu archivo.');
    expect(wrapper.findAll('[role="status"]')).toHaveLength(0);
    expect(wrapper.get('[data-testid="shared-binary-save"]').element.disabled).toBe(false);
    expect(wrapper.emitted('updated')).toBeUndefined();
  });
});
