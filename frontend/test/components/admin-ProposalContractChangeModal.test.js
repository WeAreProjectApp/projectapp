import { mount, flushPromises } from '@vue/test-utils';

const mockPreviewContractChange = jest.fn();
const mockConfirmContractChange = jest.fn();
const mockCancelContractChange = jest.fn();
const mockNotify = { success: jest.fn() };

jest.mock('../../stores/proposals', () => ({
  useProposalStore: () => ({
    previewContractChange: mockPreviewContractChange,
    confirmContractChange: mockConfirmContractChange,
    cancelContractChange: mockCancelContractChange,
  }),
}));
jest.mock('~/composables/usePanelNotify', () => ({ usePanelNotify: () => mockNotify }));

import ProposalContractChangeModal from '../../components/BusinessProposal/admin/ProposalContractChangeModal.vue';

const proposal = { id: 118, status: 'accepted', contract_modality: 'single', contract_params: {} };

function mountModal(props = {}) {
  return mount(ProposalContractChangeModal, {
    props: { proposal, modality: 'split', ...props },
    global: {
      stubs: {
        BaseModal: { template: '<div><slot /><slot name="footer" /></div>' },
        BaseButton: {
          props: ['disabled', 'disabledReason'],
          emits: ['click'],
          template: '<button v-bind="$attrs" :disabled="disabled" :title="disabled ? disabledReason : undefined" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseTextarea: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<textarea v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseInput: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
      },
    },
  });
}

describe('ProposalContractChangeModal', () => {
  beforeEach(() => {
    mockPreviewContractChange.mockReset();
    mockConfirmContractChange.mockReset();
    mockCancelContractChange.mockReset();
    mockNotify.success.mockReset();
  });

  it('requires a change note before a closed proposal can be reviewed', async () => {
    // Falla si una propuesta aceptada puede entrar a confirmación sin la nota de auditoría obligatoria.
    const wrapper = mountModal();
    const review = wrapper.get('[data-testid="contract-change-preview"]');

    await review.trigger('click');

    expect(review.element.disabled).toBe(true);
    expect(review.attributes('title')).toBe('Completa la nota y resuelve el conflicto antes de revisar.');
    expect(mockPreviewContractChange).not.toHaveBeenCalled();
    expect(mockConfirmContractChange).not.toHaveBeenCalled();
  });

  it('shows the missing service term returned by the preview endpoint', async () => {
    // Falla si la validación del servicio se reduce a un error genérico y oculta el dato que falta.
    mockPreviewContractChange.mockRejectedValue({
      response: {
        data: {
          error: 'Completa los datos del servicio.',
          details: { service_renewal_notice_days: 'Indica el preaviso de renovación.' },
        },
      },
    });
    const wrapper = mountModal();

    await wrapper.get('[data-testid="contract-change-note"]').setValue('Separación firmada por el cliente.');
    await wrapper.get('[data-testid="contract-change-service_initial_term"]').setValue('12 meses');
    await wrapper.get('[data-testid="contract-change-service_renewal_notice_days"]').setValue('');
    await wrapper.get('[data-testid="contract-change-service_termination_notice_days"]').setValue('30');
    await wrapper.get('[data-testid="contract-change-preview"]').trigger('click');
    await flushPromises();

    expect(mockPreviewContractChange).toHaveBeenCalledWith(118, {
      contract_modality: 'split',
      change_note: 'Separación firmada por el cliente.',
      contract_params: {
        service_initial_term: '12 meses',
        service_renewal_notice_days: '',
        service_termination_notice_days: 30,
      },
    });
    expect(wrapper.get('[role="alert"]').text()).toBe('Completa los datos del servicio.');
    expect(wrapper.text()).toContain('Indica el preaviso de renovación.');
  });

  it('confirms a reviewed change only after rendering its contract sources', async () => {
    // Falla si la revisión no muestra qué contrato es personalizado o confirma un identificador distinto.
    mockPreviewContractChange.mockResolvedValue({
      confirmation_id: 'confirm-118',
      impact: {
        previous_modality: 'single',
        contract_modality: 'split',
        contracts: [
          { variant: 'product', action: 'move', source: 'custom' },
          { variant: 'service', action: 'create', source: 'default' },
        ],
        archive: [],
        warnings: [],
        linked_documents: [],
        contract_params: {
          service_initial_term: '12 meses',
          service_renewal_notice_days: 30,
          service_termination_notice_days: 30,
        },
      },
    });
    mockConfirmContractChange.mockResolvedValue({ id: 118, contract_modality: 'split' });
    const wrapper = mountModal();

    await wrapper.get('[data-testid="contract-change-note"]').setValue('Separación aprobada.');
    await wrapper.get('[data-testid="contract-change-service_initial_term"]').setValue('12 meses');
    await wrapper.get('[data-testid="contract-change-service_renewal_notice_days"]').setValue('30');
    await wrapper.get('[data-testid="contract-change-service_termination_notice_days"]').setValue('30');
    await wrapper.get('[data-testid="contract-change-preview"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="contract-change-impact"]').text()).toContain('Contrato de producto: Trasladar sin cambiar el contenido · Personalizado');
    expect(wrapper.get('[data-testid="contract-change-impact"]').text()).toContain('Contrato de servicio: Crear desde plantilla · Plantilla');

    await wrapper.get('[data-testid="contract-change-confirm"]').trigger('click');
    await flushPromises();

    expect(mockConfirmContractChange).toHaveBeenCalledWith(118, 'confirm-118');
    expect(wrapper.emitted('changed')).toEqual([[]]);
    expect(mockNotify.success).toHaveBeenCalledWith('Modalidad de contrato actualizada.');
  });

  it('reviews a snapshot restoration with its identifier and change note', async () => {
    // Falla si restaurar reenvía la modalidad o los plazos en vez de restaurar la instantánea elegida.
    mockPreviewContractChange.mockResolvedValue({
      confirmation_id: 'restore-41',
      impact: {
        previous_modality: 'split',
        contract_modality: 'single',
        contracts: [{ variant: 'combined', action: 'restore', source: 'custom' }],
        archive: [],
        warnings: [],
        linked_documents: [],
        contract_params: {},
      },
    });
    const wrapper = mountModal({ snapshotId: 41, modality: '' });

    await wrapper.get('[data-testid="contract-change-note"]').setValue('Restaurar el contrato firmado.');
    await wrapper.get('[data-testid="contract-change-preview"]').trigger('click');
    await flushPromises();

    expect(mockPreviewContractChange).toHaveBeenCalledWith(118, {
      snapshot_id: 41,
      change_note: 'Restaurar el contrato firmado.',
    });
    expect(wrapper.get('[data-testid="contract-change-impact"]').text()).toContain('Contrato único: Restaurar copia guardada · Personalizado');
  });
});
