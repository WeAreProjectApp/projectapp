/**
 * Tests for ComposedEmailPreview.vue.
 *
 * Covers: fetch-on-mount payload shape (filters empty sections, optional
 * proposal_id), iframe srcdoc rendering, error state, manual refresh.
 */

const mockEmailStore = {
  isLoadingPreview: false,
  previewEmail: jest.fn(),
};

jest.mock('../../stores/emails', () => ({
  useEmailStore: () => mockEmailStore,
}));

import { mount } from '@vue/test-utils';
import ComposedEmailPreview from '../../components/ComposedEmailPreview.vue';

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

// Native click falls through to the parent's @click listener; re-emitting
// would double-fire it.
const BaseButtonStub = {
  template: '<button><slot /></button>',
};

function mountPreview(props = {}) {
  return mount(ComposedEmailPreview, {
    props: {
      subject: 'Asunto',
      greeting: 'Hola Carlos',
      sections: [
        { id: 1, text: 'Contenido', markdown: false },
        { id: 2, text: '   ', markdown: false },
        { id: 3, text: '**md**', markdown: true },
      ],
      footer: 'Pie',
      attachmentNames: ['doc.pdf'],
      ...props,
    },
    global: { stubs: { BaseButton: BaseButtonStub } },
  });
}

describe('ComposedEmailPreview', () => {
  beforeEach(() => {
    mockEmailStore.previewEmail.mockReset();
    mockEmailStore.isLoadingPreview = false;
    mockEmailStore.previewEmail.mockResolvedValue({
      success: true,
      data: { subject: 'Asunto', html_preview: '<!doctype html><p>preview</p>' },
    });
  });

  it('fetches the preview on mount with non-empty sections only', async () => {
    mountPreview();
    await flushPromises();

    expect(mockEmailStore.previewEmail).toHaveBeenCalledWith({
      subject: 'Asunto',
      greeting: 'Hola Carlos',
      sections: [
        { text: 'Contenido', markdown: false },
        { text: '**md**', markdown: true },
      ],
      footer: 'Pie',
      text_formats: {},
      attachment_names: ['doc.pdf'],
    });
  });

  it('includes proposal_id in the payload when provided', async () => {
    mountPreview({ proposalId: 42 });
    await flushPromises();

    expect(mockEmailStore.previewEmail.mock.calls[0][0].proposal_id).toBe(42);
  });

  it('renders the returned html inside a sandboxed iframe', async () => {
    const wrapper = mountPreview();
    await flushPromises();

    const iframe = wrapper.find('iframe');
    expect(iframe.exists()).toBe(true);
    expect(iframe.attributes('srcdoc')).toContain('preview');
    expect(iframe.attributes('sandbox')).toBe('allow-same-origin');
  });

  it('shows an error message when the preview request fails', async () => {
    mockEmailStore.previewEmail.mockResolvedValue({ success: false, error: 'boom' });
    const wrapper = mountPreview();
    await flushPromises();

    expect(wrapper.text()).toContain('No se pudo generar la vista previa');
    expect(wrapper.find('iframe').exists()).toBe(false);
  });

  it('re-fetches when the refresh button is clicked', async () => {
    const wrapper = mountPreview();
    await flushPromises();
    expect(mockEmailStore.previewEmail).toHaveBeenCalledTimes(1);

    await wrapper.find('button').trigger('click');
    await flushPromises();

    expect(mockEmailStore.previewEmail).toHaveBeenCalledTimes(2);
  });
});
