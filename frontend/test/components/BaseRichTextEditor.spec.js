import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue';

const wrappers = [];

function mountEditor(props = {}) {
  const wrapper = mount(BaseRichTextEditor, {
    props: { modelValue: 'First paragraph', ...props },
    global: { components: { BaseSegmented } },
  });
  wrappers.push(wrapper);
  return wrapper;
}

function modeTabs(wrapper) {
  return wrapper.findAll('[role="tab"]');
}

function lastPayload(wrapper, event) {
  const events = wrapper.emitted(event);
  return events?.at(-1)?.[0];
}

beforeEach(() => {
  global.useI18n = () => ({ t: (key) => key });
});

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  delete global.useI18n;
});

describe('BaseRichTextEditor', () => {
  // Catches source edits being saved without declaring the new versioned rich-text format.
  it('saves a source edit with its exact Markdown payload and format', async () => {
    const wrapper = mountEditor();
    await nextTick();

    await modeTabs(wrapper)[1].trigger('click');
    await wrapper.get('[data-testid="rich-text-source-input"]').setValue('**Launch**\n\n- one');

    expect(lastPayload(wrapper, 'update:modelValue')).toBe('**Launch**\n\n- one');
    expect(lastPayload(wrapper, 'update:format')).toBe('markdown_html_v1');
  });

  // Catches legacy plain text being parsed as Markdown before an editor action explicitly upgrades it.
  it('keeps a plain legacy marker literal until an explicit source edit upgrades it', async () => {
    const wrapper = mountEditor({ modelValue: '**literal**', format: 'plain' });
    await nextTick();

    await modeTabs(wrapper)[1].trigger('click');
    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('**literal**');
    expect(wrapper.emitted('update:format')).toBeUndefined();
    await wrapper.get('[data-testid="rich-text-source-input"]').setValue('**published**');

    expect(lastPayload(wrapper, 'update:modelValue')).toBe('**published**');
    expect(lastPayload(wrapper, 'update:format')).toBe('markdown_html_v1');
  });

  // Catches visual/source toggles reserializing an untouched document or emitting accidental saves.
  it('preserves an untouched source byte-for-byte through twenty mode changes', async () => {
    const source = '<p style="text-align: justify">**Brief**</p>\n\n- Alpha\n- Beta';
    const wrapper = mountEditor({ modelValue: source });
    await nextTick();

    for (let turn = 0; turn < 10; turn += 1) {
      await modeTabs(wrapper)[1].trigger('click');
      expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe(source);
      await modeTabs(wrapper)[0].trigger('click');
    }

    await modeTabs(wrapper)[1].trigger('click');
    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe(source);
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(wrapper.emitted('update:format')).toBeUndefined();
  });

  // Catches the toolbar's visual table command failing to write a source representation that can be saved.
  it('serializes a visual table insertion into the emitted source payload', async () => {
    const wrapper = mountEditor({ modelValue: 'Agenda' });
    await nextTick();

    await wrapper.get('[aria-label="richText.table"]').trigger('click');
    await nextTick();

    expect(lastPayload(wrapper, 'update:modelValue')).toBe('Agenda\n\n| <p></p> | <p></p> | <p></p> |\n| --- | --- | --- |\n| <p></p> | <p></p> | <p></p> |\n| <p></p> | <p></p> | <p></p> |');
    expect(lastPayload(wrapper, 'update:format')).toBe('markdown_html_v1');
  });

  // Catches mode changes splitting source history so undo cannot restore an edit made before the switch.
  it('undoes a source edit after returning through visual mode', async () => {
    const wrapper = mountEditor({ modelValue: 'First' });
    await nextTick();

    await modeTabs(wrapper)[1].trigger('click');
    await wrapper.get('[data-testid="rich-text-source-input"]').setValue('Second');
    await modeTabs(wrapper)[0].trigger('click');
    await wrapper.get('[aria-label="richText.undo"]').trigger('click');
    await modeTabs(wrapper)[1].trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('First');
    expect(lastPayload(wrapper, 'update:modelValue')).toBe('First');
  });

  // Catches invalid source being lost when the reader tries to return to visual editing.
  it('keeps invalid source available and reports the conversion error', async () => {
    const invalidSource = '<script>steal()</script>';
    const wrapper = mountEditor({ initialMode: 'source' });
    await nextTick();

    await wrapper.get('[data-testid="rich-text-source-input"]').setValue(invalidSource);
    await modeTabs(wrapper)[0].trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe(invalidSource);
    expect(wrapper.get('[role="alert"]').text()).toBe('richText.invalidSource');
    expect(lastPayload(wrapper, 'update:modelValue')).toBe(invalidSource);
  });

  // Catches disabled editors still accepting a toolbar operation and creating a hidden draft change.
  it('disables editing controls without emitting a draft change', async () => {
    const wrapper = mountEditor({ disabled: true, initialMode: 'source' });
    await nextTick();

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.disabled).toBe(true);
    expect(wrapper.get('[aria-label="richText.undo"]').element.disabled).toBe(true);
    expect(wrapper.get('[aria-label="richText.redo"]').element.disabled).toBe(true);
    expect(wrapper.get('[aria-label="richText.bold"]').element.disabled).toBe(true);
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });
});
