import { mount, flushPromises } from '@vue/test-utils';

const mockFetchContractSnapshots = jest.fn();
const mockFetchContractSnapshot = jest.fn();

jest.mock('../../stores/proposals', () => ({
  useProposalStore: () => ({
    fetchContractSnapshots: mockFetchContractSnapshots,
    fetchContractSnapshot: mockFetchContractSnapshot,
  }),
}));

import ProposalContractSnapshots from '../../components/BusinessProposal/admin/ProposalContractSnapshots.vue';

const proposal = { id: 118, status: 'accepted', contract_modality: 'split' };

function mountSnapshots() {
  return mount(ProposalContractSnapshots, {
    props: { proposal },
    global: {
      stubs: {
        BaseButton: {
          props: ['disabled'],
          emits: ['click'],
          template: '<button v-bind="$attrs" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseModal: { template: '<div><slot /></div>' },
        DocumentMarkdownBody: { props: ['markdown'], template: '<article>{{ markdown }}</article>' },
        PanelDownloadLink: { props: ['url', 'filename'], template: '<a :href="url">{{ filename }}</a>' },
        ProposalContractChangeModal: {
          props: ['snapshotId'],
          emits: ['changed'],
          template: '<button data-testid="restore-confirm" @click="$emit(\'changed\')">Restaurar instantánea {{ snapshotId }}</button>',
        },
      },
    },
  });
}

describe('ProposalContractSnapshots', () => {
  beforeEach(() => {
    mockFetchContractSnapshots.mockReset();
    mockFetchContractSnapshot.mockReset();
  });

  it('shows the saved modality transition and change note', async () => {
    // Falla si el historial no muestra qué cambio produjo una instantánea recuperable.
    mockFetchContractSnapshots.mockResolvedValue({
      total: 1,
      snapshots: [{
        snapshot_id: 41,
        from_modality: 'single',
        to_modality: 'split',
        actor: 'Ana Admin',
        created_at: '2026-10-01T12:00:00Z',
        change_note: 'El cliente firmó dos documentos.',
      }],
    });
    const wrapper = mountSnapshots();

    await wrapper.get('[data-testid="contract-snapshots-load"]').trigger('click');
    await flushPromises();

    expect(mockFetchContractSnapshots).toHaveBeenCalledWith(118, 0);
    expect(wrapper.text()).toContain('Contrato único → Producto y servicio');
    expect(wrapper.text()).toContain('El cliente firmó dos documentos.');
  });

  it('renders the literal Markdown saved in a selected snapshot', async () => {
    // Falla si consultar una instantánea muestra otro contrato o pierde su contenido personalizado.
    mockFetchContractSnapshots.mockResolvedValue({
      total: 1,
      snapshots: [{ snapshot_id: 41, from_modality: 'single', to_modality: 'split', actor: 'Ana', created_at: '2026-10-01T12:00:00Z', change_note: 'Nota' }],
    });
    mockFetchContractSnapshot.mockResolvedValue({
      snapshot_id: 41,
      payload: { documents: [{ document_id: 81, title: 'Contrato de producto', source: 'custom', markdown: '# Contrato firmado el 30 de septiembre de 2026' }] },
    });
    const wrapper = mountSnapshots();

    await wrapper.get('[data-testid="contract-snapshots-load"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="contract-snapshot-read-41"]').trigger('click');
    await flushPromises();

    expect(mockFetchContractSnapshot).toHaveBeenCalledWith(118, 41);
    expect(wrapper.text()).toContain('# Contrato firmado el 30 de septiembre de 2026');
    expect(wrapper.get('a').attributes('href')).toBe('/api/proposals/118/contract/snapshots/41/files/81/');
  });

  it('refreshes the history after restoring a snapshot', async () => {
    // Falla si restaurar deja visible un historial desactualizado o no solicita recargar la propuesta.
    mockFetchContractSnapshots.mockResolvedValue({
      total: 1,
      snapshots: [{ snapshot_id: 41, from_modality: 'single', to_modality: 'split', actor: 'Ana', created_at: '2026-10-01T12:00:00Z', change_note: 'Nota' }],
    });
    const wrapper = mountSnapshots();

    await wrapper.get('[data-testid="contract-snapshots-load"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="contract-snapshot-restore-41"]').trigger('click');
    await wrapper.get('[data-testid="restore-confirm"]').trigger('click');
    await flushPromises();

    expect(mockFetchContractSnapshots).toHaveBeenLastCalledWith(118, 0);
    expect(wrapper.emitted('refresh')).toEqual([[]]);
  });
});
