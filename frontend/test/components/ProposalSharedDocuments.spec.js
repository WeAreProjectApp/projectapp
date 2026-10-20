import { mount, flushPromises } from '@vue/test-utils';
import { ref } from 'vue';
import { createPinia, setActivePinia } from 'pinia';
import ProposalSharedDocuments from '../../components/BusinessProposal/admin/ProposalSharedDocuments.vue';
import BaseModal from '../../components/base/BaseModal.vue';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseSelect from '../../components/base/BaseSelect.vue';
import BaseTextarea from '../../components/base/BaseTextarea.vue';
import { get_request, create_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn(), create_request: jest.fn(), patch_request: jest.fn() }));

function createPacket(overrides = {}) {
  return {
    source_hash: 'approved-source', package_number: 2, confirmed: true, use_proposal_contracts: true,
    client: { profile_id: 7, name: 'Atlas' },
    linked_project: { id: 41, name: 'Portal Atlas', client_profile_id: 7 },
    commercial_summary: { title: 'Portal Atlas', total_investment: '5000000', currency: 'COP', payment_milestones: [], hosting_tiers: [] },
    contracts: { available: true, modality: 'single', documents: [{ id: 61, title: 'Contrato Atlas' }] },
    optional_documents: [],
    confirmed_files: [{ id: 8, title: 'Contrato Atlas', filename: 'contrato-v2.pdf', document_type: 'contract', download_url: '/api/proposals/3/approval/files/8/' }],
    shared_documents: [{
      document_id: 91, source_key: 'contract:single', current_file_id: 8, is_current: true, has_pending_changes: false,
      history: [
        { id: 8, package_number: 2, title: 'Contrato Atlas', filename: 'contrato-v2.pdf', download_url: '/api/proposals/3/approval/files/8/' },
        { id: 6, package_number: 1, title: 'Contrato Atlas', filename: 'contrato-v1.pdf', download_url: '/api/proposals/3/approval/files/6/' },
      ],
    }],
    ...overrides,
  };
}

let packet;
let wrapper;

async function open(props = {}) {
  setActivePinia(createPinia());
  wrapper = mount(ProposalSharedDocuments, {
    props: { proposalId: 3, ...props }, attachTo: document.body,
    global: {
      components: { BaseModal, BaseFormField, BaseInput, BaseSelect, BaseTextarea },
      stubs: {
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        PanelDownloadLink: { props: ['url', 'filename', 'label'], template: '<a :href="url" :download="filename">{{ label || filename }}</a>' },
        Teleport: { template: '<div><slot /></div>' }, Transition: false,
      },
    },
  });
  await flushPromises();
}

beforeEach(() => {
  jest.clearAllMocks();
  global.useI18n = () => ({ locale: ref('es-co') });
  global.useLocalePath = () => path => path;
  Object.defineProperty(global.crypto, 'randomUUID', { value: () => 'd2cfaa64-9afe-4932-b089-426357f4a729', configurable: true });
  packet = createPacket();
  get_request.mockImplementation(async url => ({ data: url.includes('/approval/') ? structuredClone(packet) : url.startsWith('projects/') ? { results: [] } : [] }));
  create_request.mockResolvedValue({ data: { package_number: 3 } });
});

afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = '';
  delete global.useI18n;
  delete global.useLocalePath;
});

describe('ProposalSharedDocuments', () => {
  // Falla si el gestor abre otro documento en lugar de la identidad compartida vigente.
  it('links the current package to its document identity', async () => {
    await open();

    expect(wrapper.get('[data-testid="proposal-shared-documents"]').text()).toContain('Paquete vigente 2 · Al día');
    expect(wrapper.get('a[href="/panel/documents/91/edit"]').text()).toBe('Contrato Atlas');
  });

  // Falla si los cambios en la fuente reemplazan la descarga aprobada antes de confirmar otra revisión.
  it('marks a pending draft while retaining approved revision links', async () => {
    packet.shared_documents[0].has_pending_changes = true;
    await open();

    expect(wrapper.text()).toContain('Paquete vigente 2 · Borrador pendiente');
    expect(wrapper.get('a[href="/api/proposals/3/approval/files/8/"]').attributes('download')).toBe('contrato-v2.pdf');
    expect(wrapper.text()).toContain('Las descargas aprobadas se conservan hasta confirmar un nuevo paquete.');
  });

  // Falla si consultar revisiones pierde el archivo de un paquete anterior.
  it('opens the immutable revision history', async () => {
    await open();
    await wrapper.get('summary').trigger('click');

    expect(wrapper.findAll('a[download]').map(link => [link.text(), link.attributes('href')])).toEqual([
      ['Contrato Atlas · v2', '/api/proposals/3/approval/files/8/'],
      ['Contrato Atlas · v1', '/api/proposals/3/approval/files/6/'],
    ]);
  });

  // Falla si abrir la revisión deja el modal bloqueado en reintentar el paquete ya confirmado.
  it('opens confirmation for a new package', async () => {
    await open();
    await wrapper.get('[data-testid="proposal-revision-open"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="approval-confirm"]').text()).toBe('Confirmar nueva versión');
    expect(wrapper.get('[data-testid="approval-contract-switch"]').attributes('aria-checked')).toBe('true');
    expect(create_request).not.toHaveBeenCalled();
  });

  // Falla si confirmar una revisión deja visible el paquete anterior hasta recargar toda la página.
  it('refreshes the displayed package after confirmation', async () => {
    await open();
    await wrapper.get('[data-testid="proposal-revision-open"]').trigger('click');
    await flushPromises();
    packet = createPacket({ package_number: 3 });
    await wrapper.get('[data-testid="approval-confirm"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="proposal-shared-documents"]').text()).toContain('Paquete vigente 3 · Al día');
    expect(wrapper.findAll('[data-testid="proposal-approval-modal"]')).toHaveLength(0);
    expect(create_request).toHaveBeenCalledWith('proposals/3/approval/revisions/', expect.objectContaining({ source_hash: 'approved-source', action: 'confirm', accept_proposal: false }));
  });

  // Falla si un error de consulta oculta el motivo por el que faltan los documentos del cierre.
  it('reports a failed approval document request', async () => {
    get_request.mockRejectedValue(new Error('Service unavailable'));
    await open();

    expect(wrapper.get('[role="alert"]').text()).toBe('No se pudieron cargar los documentos aprobados.');
    expect(wrapper.findAll('[data-testid="proposal-revision-open"]')).toHaveLength(0);
  });
  // Falla si guardar la fuente deja el indicador del borrador desactualizado en el gestor.
  it('reloads pending state when the source refresh key changes', async () => {
    await open();
    packet.shared_documents[0].has_pending_changes = true;
    await wrapper.setProps({ refreshKey: 'source-version-next' });
    await flushPromises();

    expect(wrapper.get('[data-testid="proposal-shared-documents"]').text()).toContain('Paquete vigente 2 · Borrador pendiente');
    expect(get_request).toHaveBeenCalledTimes(2);
  });

  // Falla si navegar a otra propuesta fallida muestra documentos privados de la propuesta anterior.
  it('clears the previous proposal documents when the next request fails', async () => {
    await open();
    get_request.mockRejectedValue(new Error('Service unavailable'));
    await wrapper.setProps({ proposalId: 4 });
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe('No se pudieron cargar los documentos aprobados.');
    expect(wrapper.findAll('a[href="/panel/documents/91/edit"]')).toHaveLength(0);
    expect(wrapper.text()).not.toContain('Paquete vigente 2');
  });

});
