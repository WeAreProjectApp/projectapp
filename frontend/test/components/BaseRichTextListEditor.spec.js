import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import BaseRichTextListEditor from '../../components/base/BaseRichTextListEditor.vue';

const wrappers = [];

function render(props = {}) {
  const wrapper = mount(BaseRichTextListEditor, {
    props: {
      modelValue: 'Untouched\nSecond item',
      formatPath: '/paragraphs',
      formats: { '/paragraphs/1': 'plain' },
      ...props,
    },
    global: { components: { BaseSegmented } },
  });
  wrappers.push(wrapper);
  return wrapper;
}

function lastPayload(wrapper, event) {
  return wrapper.emitted(event)?.at(-1)?.[0];
}

beforeEach(() => { global.useI18n = () => ({ t: (key) => key }); });
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  delete global.useI18n;
});

describe('BaseRichTextListEditor', () => {
  // Catches formatting markup injecting literal row breaks and turning one list entry into several entries.
  it.each([
    ['bold text', '**Bold**', 'strong', 'Bold'],
    ['a nested list', '- Alpha\n- Beta', 'li', 'Alpha'],
    ['a table', '| Column |\n| --- |\n| Value |', 'td', 'Value'],
  ])('keeps %s inside its first list entry', async (_name, source, selector, text) => {
    const wrapper = render();
    await nextTick();

    await wrapper.findAll('[role="tab"]')[1].trigger('click');
    await wrapper.findAll('[data-testid="rich-text-source-input"]')[0].setValue(source);

    // quality: allow-fragile-selector (Semantic HTML tags are the persisted formatting contract of this list entry.)
    const stored = lastPayload(wrapper, 'update:modelValue').split('\n');
    expect(stored).toHaveLength(2);
    expect(stored[1]).toBe('Second item');
    const reader = document.createElement('div');
    reader.innerHTML = stored[0];
    expect(reader.querySelector(selector).textContent).toBe(text);
    expect(lastPayload(wrapper, 'update:formats')).toEqual({
      '/paragraphs/0': 'markdown_html_v1',
      '/paragraphs/1': 'plain',
    });
  });

  // Catches deletion retaining a removed element's format or assigning later styles to the wrong entry.
  it('remaps remaining element formats after removing the middle entry', async () => {
    const wrapper = render({
      modelValue: 'First\nSecond\nThird',
      formats: {
        '/paragraphs/0': 'plain',
        '/paragraphs/1': 'markdown_html_v1',
        '/paragraphs/2': 'whatsapp_v1',
      },
    });
    await nextTick();

    const removeButtons = wrapper.findAll('button').filter((button) => button.text() === 'richText.removeItem');
    await removeButtons[1].trigger('click');

    expect(lastPayload(wrapper, 'update:modelValue')).toBe('First\nThird');
    expect(lastPayload(wrapper, 'update:formats')).toEqual({
      '/paragraphs/0': 'plain',
      '/paragraphs/1': 'whatsapp_v1',
    });
  });
});
