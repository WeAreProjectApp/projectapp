import { mount } from '@vue/test-utils';
import ProposalEmailsTab from '../../components/BusinessProposal/admin/ProposalEmailsTab.vue';
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import { usePanelNotify } from '../../composables/usePanelNotify';

const notify = usePanelNotify();

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

const proposalStore = {
  updateProposal: jest.fn(),
  sendComposedEmail: jest.fn(),
  fetchEmailHistory: jest.fn(),
  fetchEmailDefaults: jest.fn(),
};

global.useProposalStore = jest.fn(() => proposalStore);

const baseProposal = {
  id: 42,
  client_name: 'Carlos',
  client_email: 'carlos@example.com',
  email_intro: 'Esta propuesta centraliza las solicitudes para responder más rápido.',
  status: 'sent',
};

const EmailRecipientFieldsStub = {
  name: 'EmailRecipientFields',
  props: ['toRecipients', 'ccRecipients'],
  emits: ['update:toRecipients', 'update:ccRecipients'],
  template: `
    <input
      type="email"
      placeholder="correo@ejemplo.com"
      :value="toRecipients[0]?.email || ''"
      @input="$emit('update:toRecipients', $event.target.value ? [{ email: $event.target.value }] : [])"
    >
  `,
};

function buildHistoryEntry(overrides = {}) {
  return {
    id: 1,
    subject: 'Seguimiento',
    recipient: 'carlos@example.com',
    status: 'sent',
    sent_at: '2026-04-10T10:00:00Z',
    metadata: {
      greeting: 'Hola Carlos',
      sections: ['Primer bloque'],
      footer: 'Footer',
      attachment_names: ['brief.pdf'],
    },
    ...overrides,
  };
}

function mountTab(props = {}) {
  return mount(ProposalEmailsTab, {
    props: {
      proposal: baseProposal,
      ...props,
    },
    global: {
      stubs: {
        EmailRecipientFields: EmailRecipientFieldsStub,
        NuxtLink: { template: '<a><slot /></a>' },
      },
      components: { BaseRichTextEditor, BaseSegmented },
    },
  });
}

const richTextSource = (wrapper, testId) => wrapper.get(`[data-testid="${testId}"] [data-testid="rich-text-source-input"]`);
const introSource = (wrapper) => richTextSource(wrapper, 'proposal-email-intro');

describe('ProposalEmailsTab', () => {
  const originalUseI18n = global.useI18n;

  beforeEach(() => {
    global.useI18n = () => ({ t: (key) => key });
    jest.useFakeTimers();
    proposalStore.sendComposedEmail.mockReset();
    proposalStore.updateProposal.mockReset();
    proposalStore.fetchEmailHistory.mockReset();
    proposalStore.fetchEmailDefaults.mockReset();
    proposalStore.fetchEmailDefaults.mockResolvedValue({
      success: true,
      data: {
        greeting: 'Hola Carlos',
        footer: 'Quedamos atentos.',
      },
    });
    proposalStore.fetchEmailHistory.mockResolvedValue({
      success: true,
      data: {
        results: [],
        page: 1,
        has_next: false,
      },
    });
    proposalStore.sendComposedEmail.mockResolvedValue({ success: true });
    proposalStore.updateProposal.mockResolvedValue({ success: true });
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    notify.clearAll();
  });

  afterAll(() => {
    if (originalUseI18n) global.useI18n = originalUseI18n;
    else delete global.useI18n;
  });

  it('loads defaults and history on mount with the proposal-email base path', async () => {
    mountTab();
    await flushPromises();

    expect(proposalStore.fetchEmailDefaults).toHaveBeenCalledWith(42, 'proposal-email');
    expect(proposalStore.fetchEmailHistory).toHaveBeenCalledWith(42, 1, 'proposal-email');
  });

  it('lets a draft save an empty personalized message without loading follow-up data', async () => {
    const wrapper = mountTab({
      proposal: { ...baseProposal, status: 'draft', email_intro: '' },
    });
    await flushPromises();

    expect(proposalStore.fetchEmailDefaults).not.toHaveBeenCalled();
    expect(proposalStore.fetchEmailHistory).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('Requerido para enviar');

    await introSource(wrapper).setValue('   ');
    await wrapper.get('[data-testid="proposal-email-intro-save"]').trigger('click');
    await flushPromises();

    expect(proposalStore.updateProposal).toHaveBeenCalledWith(42, {
      email_intro: '',
      text_formats: { '/email_intro': 'markdown_html_v1' },
    });
    expect(wrapper.emitted('email-intro-saved')[0]).toEqual(['']);
  });

  it('keeps an edited message visible when saving fails', async () => {
    proposalStore.updateProposal.mockResolvedValueOnce({
      success: false,
      message: 'No fue posible guardar el mensaje.',
    });
    const wrapper = mountTab();
    await flushPromises();

    const intro = introSource(wrapper);
    await intro.setValue('Mensaje nuevo para el cliente.');
    await wrapper.get('[data-testid="proposal-email-intro-save"]').trigger('click');
    await flushPromises();

    expect(intro.element.value).toBe('Mensaje nuevo para el cliente.');
    expect(wrapper.text()).toContain('No fue posible guardar el mensaje.');
    expect(wrapper.emitted('email-intro-saved')).toBeUndefined();
  });

  it('falls back to empty recipient and generic greeting when the proposal has no client data', async () => {
    proposalStore.fetchEmailDefaults.mockResolvedValueOnce({ success: true, data: {} });
    const wrapper = mountTab({
      proposal: {
        id: 42,
        client_name: '',
        client_email: '',
        email_intro: '',
        status: 'sent',
      },
    });
    await flushPromises();

    expect(wrapper.get('input[placeholder="correo@ejemplo.com"]').element.value).toBe('');
    expect(wrapper.get('input[placeholder="Hola Carlos"]').element.value).toBe('Hola');
    expect(wrapper.findAll('button').find((button) => button.text().includes('Enviar correo')).attributes('disabled')).toBeDefined();
  });

  it('renders the empty history state when there are no entries', async () => {
    const wrapper = mountTab();
    await flushPromises();

    expect(wrapper.text()).toContain('No se han enviado correos desde esta propuesta.');
  });

  it('switches to branded mode and reloads defaults and history', async () => {
    const wrapper = mountTab();
    await flushPromises();

    await wrapper.findAll('button').find((button) => button.text().includes('General')).trigger('click');
    await flushPromises();

    expect(proposalStore.fetchEmailDefaults).toHaveBeenLastCalledWith(42, 'branded-email');
    expect(proposalStore.fetchEmailHistory).toHaveBeenLastCalledWith(42, 1, 'branded-email');
  });

  it('disables the send button until recipient, subject, and one section have content', async () => {
    const wrapper = mountTab();
    await flushPromises();

    const sendButton = wrapper.findAll('button').find((button) => button.text().includes('Enviar correo'));
    expect(sendButton.attributes('disabled')).toBeDefined();

    await wrapper.get('input[placeholder="Asunto del correo"]').setValue('Asunto');
    await wrapper.get('textarea[placeholder="Escribe el contenido de esta sección..."]').setValue('Contenido');

    expect(sendButton.attributes('disabled')).toBeUndefined();
  });

  it('adds and removes composer sections from the UI', async () => {
    const wrapper = mountTab();
    await flushPromises();

    await wrapper.findAll('button').find((button) => button.text().includes('Agregar sección')).trigger('click');
    expect(wrapper.text()).toContain('Sección 2');

    await wrapper.find('button[aria-label="Eliminar"]').trigger('click');
    expect(wrapper.text()).not.toContain('Sección 2');
  });

  it('shows a validation error for files with disallowed extensions', async () => {
    const wrapper = mountTab();
    await flushPromises();

    const fileInput = wrapper.find('input[type="file"]');
    const file = new File(['bad'], 'malware.exe', { type: 'application/octet-stream' });
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [file],
    });

    await fileInput.trigger('change');

    expect(wrapper.text()).toContain('malware.exe: tipo no permitido');
  });

  it('ignores file change events with no selected files', async () => {
    const wrapper = mountTab();
    await flushPromises();

    const fileInput = wrapper.find('input[type="file"]');
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [],
    });

    await fileInput.trigger('change');

    expect(wrapper.text()).not.toContain('tipo no permitido');
  });

  it('shows a validation error for oversized files', async () => {
    const wrapper = mountTab();
    await flushPromises();

    const fileInput = wrapper.find('input[type="file"]');
    const file = new File(['x'.repeat(10)], 'large.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', {
      configurable: true,
      value: 16 * 1024 * 1024,
    });
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [file],
    });

    await fileInput.trigger('change');

    expect(wrapper.text()).toContain('large.pdf: excede 15 MB');
  });

  it('adds valid attachments and allows removing them', async () => {
    const wrapper = mountTab();
    await flushPromises();

    const fileInput = wrapper.find('input[type="file"]');
    const file = new File(['pdf'], 'brief.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [file],
    });

    await fileInput.trigger('change');
    expect(wrapper.text()).toContain('brief.pdf');

    await wrapper.find('button[aria-label="Eliminar"]').trigger('click');
    expect(wrapper.text()).not.toContain('brief.pdf');
  });

  it('sends a composed email and resets the form after a successful response', async () => {
    const wrapper = mountTab();
    await flushPromises();

    await wrapper.get('input[placeholder="Asunto del correo"]').setValue('Seguimiento de propuesta');
    await wrapper.find('textarea[placeholder="Escribe el contenido de esta sección..."]').setValue('Primer bloque');

    await wrapper.findAll('button').find((button) => button.text().includes('Enviar correo')).trigger('click');
    await flushPromises();

    const [, formData, basePath] = proposalStore.sendComposedEmail.mock.calls[0];
    expect(basePath).toBe('proposal-email');
    expect(formData.get('recipient_emails')).toBe('["carlos@example.com"]');
    expect(formData.get('cc_emails')).toBe('[]');
    expect(formData.get('subject')).toBe('Seguimiento de propuesta');
    expect(formData.get('greeting')).toBe('Hola Carlos');
    expect(formData.get('sections')).toBe(JSON.stringify([{ text: 'Primer bloque', markdown: true }]));
    expect(notify.notifications.value[0]).toMatchObject({ type: 'success', title: 'Correo enviado correctamente.' });

    jest.advanceTimersByTime(5000);
    expect(notify.notifications.value).toHaveLength(0);
  });

  it('appends attachments to the form data when sending', async () => {
    const wrapper = mountTab();
    await flushPromises();

    const fileInput = wrapper.find('input[type="file"]');
    const file = new File(['pdf'], 'brief.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [file],
    });
    await fileInput.trigger('change');

    await wrapper.get('input[placeholder="Asunto del correo"]').setValue('Seguimiento con adjunto');
    await wrapper.find('textarea[placeholder="Escribe el contenido de esta sección..."]').setValue('Primer bloque');
    await wrapper.findAll('button').find((button) => button.text().includes('Enviar correo')).trigger('click');
    await flushPromises();

    const [, formData] = proposalStore.sendComposedEmail.mock.calls[0];
    expect(formData.getAll('attachments')).toHaveLength(1);
    expect(formData.getAll('attachments')[0].name).toBe('brief.pdf');
  });

  it('shows a fallback error when the send request fails', async () => {
    proposalStore.sendComposedEmail.mockResolvedValueOnce({ success: false });
    const wrapper = mountTab();
    await flushPromises();

    await wrapper.get('input[placeholder="Asunto del correo"]').setValue('Seguimiento de propuesta');
    await wrapper.find('textarea[placeholder="Escribe el contenido de esta sección..."]').setValue('Primer bloque');

    await wrapper.findAll('button').find((button) => button.text().includes('Enviar correo')).trigger('click');
    await flushPromises();

    expect(notify.notifications.value[0]).toMatchObject({ type: 'error', title: 'Error al enviar el correo. Intenta de nuevo.' });
  });

  it('renders history entries and toggles the expanded detail view', async () => {
    proposalStore.fetchEmailHistory.mockResolvedValueOnce({
      success: true,
      data: {
        results: [buildHistoryEntry()],
        page: 1,
        has_next: false,
      },
    });

    const wrapper = mountTab();
    await flushPromises();

    expect(wrapper.text()).toContain('Seguimiento');
    await wrapper.findAll('button').find((button) => button.text().includes('carlos@example.com')).trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Primer bloque');
    expect(wrapper.text()).toContain('brief.pdf');
  });

  it('collapses an expanded history entry on the second toggle', async () => {
    proposalStore.fetchEmailHistory.mockResolvedValueOnce({
      success: true,
      data: {
        results: [buildHistoryEntry()],
        page: 1,
        has_next: false,
      },
    });

    const wrapper = mountTab();
    await flushPromises();

    const historyButton = wrapper.findAll('button').find((button) => button.text().includes('carlos@example.com'));
    await historyButton.trigger('click');
    await flushPromises();
    // BaseCollapse keeps the body in the DOM; it toggles aria-hidden instead.
    const collapse = () => wrapper
      .findAll('[aria-hidden]')
      .find((node) => node.text().includes('Primer bloque'));
    expect(collapse().attributes('aria-hidden')).toBe('false');

    await historyButton.trigger('click');
    await flushPromises();
    expect(collapse().attributes('aria-hidden')).toBe('true');
  });

  it('renders unknown history status values and blank dates without formatting them', async () => {
    proposalStore.fetchEmailHistory.mockResolvedValueOnce({
      success: true,
      data: {
        results: [
          buildHistoryEntry({
            id: 2,
            status: 'queued',
            sent_at: null,
          }),
        ],
        page: 1,
        has_next: false,
      },
    });

    const wrapper = mountTab();
    await flushPromises();

    expect(wrapper.text()).toContain('queued');
    expect(wrapper.text()).toContain('carlos@example.com');
  });

  it('loads the next history page when the load more button is clicked', async () => {
    proposalStore.fetchEmailHistory
      .mockResolvedValueOnce({
        success: true,
        data: {
          results: [buildHistoryEntry({ id: 1, subject: 'Primero' })],
          page: 1,
          has_next: true,
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          results: [buildHistoryEntry({ id: 2, subject: 'Segundo' })],
          page: 2,
          has_next: false,
        },
      });

    const wrapper = mountTab();
    await flushPromises();
    await wrapper.findAll('button').find((button) => button.text().includes('Cargar más')).trigger('click');
    await flushPromises();

    expect(proposalStore.fetchEmailHistory).toHaveBeenLastCalledWith(42, 2, 'proposal-email');
    expect(wrapper.text()).toContain('Segundo');
  });
});
