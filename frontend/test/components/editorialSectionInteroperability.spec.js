import { mount } from '@vue/test-utils';

jest.mock('~/components/BusinessProposal/admin/EmojiIconField.vue', () => ({
  __esModule: true,
  default: {
    name: 'EmojiIconField',
    props: ['modelValue', 'label', 'placeholder'],
    template: `
      <label>
        <span>{{ label }}</span>
        <input
          :value="modelValue"
          :placeholder="placeholder"
          @input="$emit('update:modelValue', $event.target.value)"
        />
      </label>
    `,
  },
}));

import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import SectionEditor from '../../components/BusinessProposal/admin/SectionEditor.vue';
import TechnicalDocumentEditor from '../../components/BusinessProposal/admin/TechnicalDocumentEditor.vue';

const wrappers = [];

function sourceTab(wrapper) {
  return wrapper.findAll('[role="tab"]').find((tab) => tab.text() === 'richText.source');
}

async function editSource(wrapper, value) {
  await sourceTab(wrapper).trigger('click');
  await wrapper.get('[data-testid="rich-text-source-input"]').setValue(value);
}

function saveButton(wrapper, label) {
  return wrapper.findAll('button').find((button) => button.text().includes(label));
}

function render(component, props) {
  const wrapper = mount(component, {
    props,
    global: {
      components: { BaseRichTextEditor, BaseSegmented },
      stubs: {
        Teleport: true,
        Transition: true,
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  });
  wrappers.push(wrapper);
  return wrapper;
}

beforeEach(() => {
  global.useI18n = () => ({ t: (key) => key });
});

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  delete global.useI18n;
});

describe('section editorial interoperability', () => {
  it('moves a greeting root format into local metadata after source editing', async () => {
    const wrapper = render(SectionEditor, {
      section: {
        id: 41,
        title: 'Greeting',
        section_type: 'greeting',
        is_wide_panel: false,
        content_json: { clientName: 'Ana', inspirationalQuote: 'Mensaje original' },
        text_formats: { '/content_json/inspirationalQuote': 'markdown' },
      },
    });
    await editSource(wrapper, '**nuevo**');
    await saveButton(wrapper, 'Guardar Sección').trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload;
    expect(payload.text_formats).toEqual({});
    expect(payload.content_json.inspirationalQuote).toBe('**nuevo**');
    expect(payload.content_json.text_formats).toEqual({
      '/inspirationalQuote': 'markdown_html_v1',
    });
  });

  it('moves a technical purpose root format into local metadata after source editing', async () => {
    const wrapper = render(TechnicalDocumentEditor, {
      section: {
        id: 42,
        title: 'Technical',
        is_wide_panel: false,
        content_json: { purpose: 'Propósito original', stack: [], epics: [] },
        text_formats: { '/content_json/purpose': 'markdown' },
      },
      moduleLinkOptions: [],
      itemLinkOptions: [],
      expandAll: false,
    });
    await editSource(wrapper, '**nuevo**');
    await saveButton(wrapper, 'Guardar detalle técnico').trigger('click');

    const payload = wrapper.emitted('save')[0][0].payload;
    expect(payload.text_formats).toEqual({});
    expect(payload.content_json.purpose).toBe('**nuevo**');
    expect(payload.content_json.text_formats).toEqual({
      '/purpose': 'markdown_html_v1',
    });
  });
});
