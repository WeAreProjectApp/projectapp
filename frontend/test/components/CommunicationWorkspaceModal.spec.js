const mockStore = {
  currentThread: null,
  isThreadLoading: false,
  isMutating: false,
  threadError: null,
  clearCurrentThread: jest.fn(),
  fetchThread: jest.fn(),
  fetchDocuments: jest.fn(),
  createMessage: jest.fn(),
  updateDraft: jest.fn(),
  markSent: jest.fn(),
  deleteDraft: jest.fn(),
  voidMessage: jest.fn(),
  correctDate: jest.fn(),
  setThreadOpen: jest.fn(),
  updateThread: jest.fn(),
};
const mockDocumentStore = { documents: [], fetchDocuments: jest.fn() };
const mockNotify = { success: jest.fn(), error: jest.fn(), warning: jest.fn() };

jest.mock('~/stores/communications', () => ({ useCommunicationsStore: () => mockStore }));
jest.mock('~/stores/documents', () => ({ useDocumentStore: () => mockDocumentStore }));
jest.mock('~/composables/usePanelNotify', () => ({ usePanelNotify: () => mockNotify }));

import { flushPromises, mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import CommunicationWorkspaceModal from '~/components/communications/CommunicationWorkspaceModal.vue';

global.useI18n = () => ({
  t: (key, values = {}) => ({
    'communicationFiling.threadId': `Hilo #${values.id}`,
    'communicationFiling.messageId': `Mensaje #${values.id}`,
    'communicationFiling.copy': 'Copiar texto',
    'communicationFiling.start': 'Ir al inicio',
    'communicationFiling.end': 'Ir al final',
    'communicationFiling.compose': 'Registrar comunicación',
    'communicationFiling.hideComposer': 'Ocultar formulario',
    'communicationFiling.details': 'Detalles del mensaje',
    'communicationFiling.invalidDate': 'Indica una fecha y hora válidas.',
    'communicationFiling.unfiled': 'Sin carpeta',
    'communicationFiling.move': 'Mover a carpeta',
    'communicationFiling.save': 'Guardar',
    'communicationFiling.cancel': 'Cancelar',
    'communicationFiling.threadMoved': 'Hilo movido',
  }[key] || key),
});

const BaseButtonStub = {
  emits: ['click'],
  template: '<button v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
};
const BaseActionButtonStub = {
  props: ['label'],
  emits: ['click'],
  template: '<button v-bind="$attrs" :aria-label="label" @click="$emit(\'click\', $event)">{{ label }}<slot /></button>',
};
const BaseModalStub = { props: ['modelValue', 'kind'], template: '<div v-if="modelValue" role="dialog" :data-modal-kind="kind"><slot /></div>' };
const BaseCollapseStub = { props: ['open'], template: '<div v-if="open"><slot /></div>' };
const BaseInputStub = {
  props: ['modelValue'], emits: ['update:modelValue'],
  template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)">',
};
const BaseTextareaStub = {
  props: ['modelValue'], emits: ['update:modelValue'],
  template: '<textarea v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
};
const BaseSelectStub = {
  props: ['modelValue', 'options'], emits: ['update:modelValue'],
  template: '<select v-bind="$attrs" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
};
const BaseActionMenuStub = {
  props: ['items', 'testid'],
  template: '<div :data-testid="testid"><button v-for="item in items" :key="item.label" @click="item.onClick">{{ item.label }}</button></div>',
};

function message(overrides = {}) {
  return {
    id: 81,
    direction: 'outgoing',
    channel: 'whatsapp',
    channel_display: 'WhatsApp',
    status: 'draft',
    status_display: 'Borrador',
    content: 'Texto exacto de la comunicación.',
    subject: '',
    occurred_at: '2026-01-10T12:30:00Z',
    reply_to_id: null,
    documents: [],
    date_corrections: [],
    voided_at: null,
    ...overrides,
  };
}

function thread(messages = [message()]) {
  return {
    id: 41,
    title: 'Aprobación de alcance',
    status: 'open',
    thread_kind: 'manual',
    client_id: 7,
    client_name: 'Ana Proyecto',
    project_id: 3,
    project_name: 'Portal de clientes',
    folder_id: null,
    folder_name: '',
    messages,
  };
}

function mountModal(messages = [message()], attachToDocument = false) {
  mockStore.currentThread = thread(messages);
  return mount(CommunicationWorkspaceModal, {
    props: { modelValue: true, threadId: 41 },
    ...(attachToDocument ? { attachTo: document.body } : {}),
    global: {
      stubs: {
        BaseActionButton: BaseActionButtonStub,
        BaseActionIcon: true,
        BaseActionMenu: BaseActionMenuStub,
        BaseAlert: { template: '<p role="alert"><slot /></p>' },
        BaseBadge: { template: '<span><slot /></span>' },
        BaseButton: BaseButtonStub,
        BaseCheckbox: true,
        BaseCollapse: BaseCollapseStub,
        BaseEmptyState: true,
        BaseFormField: { template: '<label><slot /></label>' },
        BaseFormRow: { template: '<div><slot /></div>' },
        BaseInput: BaseInputStub,
        BaseModal: BaseModalStub,
        BaseModalActions: { template: '<div><slot /></div>' },
        BaseSelect: BaseSelectStub,
        BaseSkeleton: true,
        BaseTextarea: BaseTextareaStub,
        CommunicationFolderPicker: true,
        NuxtLink: { template: '<a><slot /></a>' },
      },
    },
  });
}

describe('CommunicationWorkspaceModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore.isThreadLoading = false;
    mockStore.isMutating = false;
    mockStore.threadError = null;
    mockStore.fetchThread.mockResolvedValue({ success: true });
    mockStore.createMessage.mockResolvedValue({ success: true, data: { id: 91 } });
    mockStore.markSent.mockResolvedValue({ success: true });
    mockDocumentStore.documents = [];
    mockDocumentStore.fetchDocuments.mockResolvedValue({ success: true });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
  });

  // Falla si un hilo existente vuelve a abrir un formulario que oculta la conversación.
  it('keeps the composer collapsed for an existing thread', async () => {
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="communication-composer-toggle"]').attributes('aria-expanded')).toBe('false');
    expect(wrapper.findAll('[data-testid="communication-composer"]')).toHaveLength(0);
  });

  // Falla si un hilo vacío deja de abrir directamente el registro de su primer mensaje.
  it('opens the composer for an empty thread', async () => {
    const wrapper = mountModal([]);
    await flushPromises();

    expect(wrapper.get('[data-testid="communication-composer-toggle"]').attributes('aria-expanded')).toBe('true');
    expect(wrapper.findAll('[data-testid="communication-composer"]')).toHaveLength(1);
  });

  // Falla si responder no revela el formulario ni conserva la referencia a su mensaje origen.
  it('opens and focuses the composer when replying', async () => {
    const wrapper = mountModal([message({ id: 82, status: 'sent', status_display: 'Enviado' })], true);
    await flushPromises();

    const replyButton = wrapper.get('[data-testid="communication-message-82"]')
      .findAll('button')
      .find((button) => button.text() === 'Responder');
    await replyButton.trigger('click');
    await flushPromises();
    await nextTick();

    expect(wrapper.get('[data-testid="communication-composer"]').text()).toContain('Respuesta al mensaje #82');
    expect(document.activeElement).toBe(wrapper.get('[data-testid="communication-message-content"]').element);
    wrapper.unmount();
  });

  // Falla si ocultar los detalles o el formulario borra datos ya redactados.
  it('preserves drafted content and date while the sections are folded', async () => {
    const wrapper = mountModal();
    await flushPromises();
    await wrapper.get('[data-testid="communication-composer-toggle"]').trigger('click');
    await wrapper.get('[data-testid="communication-details-toggle"]').trigger('click');
    await wrapper.get('[data-testid="communication-message-content"]').setValue('Respuesta preparada para el cliente.');
    await wrapper.get('[data-testid="communication-message-date"]').setValue('2026-01-12T09:45');
    await wrapper.get('[data-testid="communication-details-toggle"]').trigger('click');
    await wrapper.get('[data-testid="communication-composer-toggle"]').trigger('click');
    await wrapper.get('[data-testid="communication-composer-toggle"]').trigger('click');
    await wrapper.get('[data-testid="communication-details-toggle"]').trigger('click');

    expect(wrapper.get('[data-testid="communication-message-content"]').element.value).toBe('Respuesta preparada para el cliente.');
    expect(wrapper.get('[data-testid="communication-message-date"]').element.value).toBe('2026-01-12T09:45');
    expect(wrapper.get('[data-testid="communication-details-summary"]').text()).toContain('Saliente · WhatsApp ·');
  });

  // Falla si un error de fecha permanece oculto dentro de los detalles plegados.
  it('reveals message details when an invalid date blocks saving', async () => {
    const wrapper = mountModal();
    await flushPromises();
    await wrapper.get('[data-testid="communication-composer-toggle"]').trigger('click');
    await wrapper.get('[data-testid="communication-message-content"]').setValue('Respuesta preparada.');
    await wrapper.get('[data-testid="communication-details-toggle"]').trigger('click');
    await wrapper.get('[data-testid="communication-message-date"]').setValue('fecha inválida');
    await wrapper.get('[data-testid="communication-details-toggle"]').trigger('click');
    await wrapper.get('[data-testid="communication-save-draft"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="communication-details-toggle"]').attributes('aria-expanded')).toBe('true');
    expect(mockNotify.warning).toHaveBeenCalledWith({ title: 'Indica una fecha y hora válidas.' });
  });

  // Falla si copiar deja de enviar exactamente el contenido del mensaje al portapapeles.
  it('copies exactly the message content and confirms success', async () => {
    const wrapper = mountModal();
    await flushPromises();
    await wrapper.get('[data-testid="communication-copy-81"]').trigger('click');
    await flushPromises();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Texto exacto de la comunicación.');
    expect(mockNotify.success).toHaveBeenCalledWith({ title: 'Texto copiado' });
  });

  // Falla si un rechazo del portapapeles parece una copia exitosa.
  it('reports the clipboard rejection without confirming a copy', async () => {
    navigator.clipboard.writeText.mockRejectedValue(new Error('denied'));
    const wrapper = mountModal();
    await flushPromises();
    await wrapper.get('[data-testid="communication-copy-81"]').trigger('click');
    await flushPromises();

    expect(mockNotify.error).toHaveBeenCalledWith({ title: 'No se pudo copiar el texto' });
    expect(mockNotify.success).not.toHaveBeenCalledWith({ title: 'Texto copiado' });
  });

  // Falla si marcar enviado vuelve a mostrarse como acción directa o pierde el borrador objetivo.
  it('keeps mark sent inside the overflow menu', async () => {
    jest.useFakeTimers().setSystemTime(new Date('2026-01-15T10:00:00Z'));
    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.get('[data-testid="communication-message-actions-81"]').text()).toBe('Marcar enviadoEditar borradorEliminar borrador');
    expect(wrapper.findAll('[data-testid="communication-mark-sent-81"]')).toHaveLength(0);
    await wrapper.get('[data-testid="communication-message-actions-81"] button').trigger('click');
    await flushPromises();

    expect(mockStore.markSent).toHaveBeenCalledWith(81, '2026-01-15T10:00:00.000Z');
    jest.useRealTimers();
  });

  // Falla si los atajos desplazan el modal completo en vez del historial.
  it('scrolls the timeline container to its beginning and end', async () => {
    const wrapper = mountModal();
    await flushPromises();
    const timeline = wrapper.get('[data-testid="communication-timeline"]').element;
    Object.defineProperty(timeline, 'scrollHeight', { configurable: true, value: 812 });
    timeline.scrollTo = jest.fn();

    await wrapper.get('[data-testid="communication-scroll-start"]').trigger('click');
    await wrapper.get('[data-testid="communication-scroll-end"]').trigger('click');

    expect(timeline.scrollTo).toHaveBeenNthCalledWith(1, { top: 0, behavior: 'smooth' });
    expect(timeline.scrollTo).toHaveBeenNthCalledWith(2, { top: 812, behavior: 'smooth' });
  });

  // Falla si mover el hilo vuelve a abrir un formulario ancho para un único selector.
  it('opens the folder move as a confirmation-width dialog', async () => {
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="communication-move-folder"]').trigger('click');

    const moveDialog = wrapper.get('[role="dialog"] [role="dialog"]');
    expect(moveDialog.text()).toContain('Mover a carpeta');
    expect(moveDialog.attributes('data-modal-kind')).toBe('confirm');
  });
});
