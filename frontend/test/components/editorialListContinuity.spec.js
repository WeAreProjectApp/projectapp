import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import BaseRichTextListEditor from '../../components/base/BaseRichTextListEditor.vue';
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';

let wrapper;
beforeEach(() => { global.useI18n = () => ({ t: key => key }); });
afterEach(() => { wrapper?.unmount(); delete global.useI18n; });

function mountList() {
  wrapper = mount(BaseRichTextListEditor, {
    props: { modelValue: 'First\nSecond', formatPath: '/items',
      'onUpdate:modelValue': value => wrapper.setProps({ modelValue: value }),
      'onUpdate:formats': formats => wrapper.setProps({ formats }),
    },
    global: { components: { BaseSegmented } },
  });
  return wrapper.findAllComponents(BaseRichTextEditor)[0];
}

// Inline spaces are content, even when array entries use one physical line.
it('preserves the space between adjacent formatted words in one list entry', async () => {
  const editor = mountList();
  await editor.findAll('[role="tab"]')[1].trigger('click');

  await editor.get('textarea').setValue('**Alpha** *beta*');
  await nextTick();

  expect(wrapper.props('modelValue').split('\n')[0]).toContain('</strong> <em>');
});

// Storage normalization must not reset the history of an active item editor.
it('keeps undo available after the parent stores a formatted list entry', async () => {
  const editor = mountList();
  await editor.findAll('[role="tab"]')[1].trigger('click');

  await editor.get('textarea').setValue('**Alpha**');
  await nextTick();
  await editor.get('[aria-label="richText.undo"]').trigger('click');

  expect(editor.get('textarea').element.value).toBe('First');
});

// Legacy interpretations must not change merely because another item is edited.
it('leaves the format of an untouched legacy entry undeclared', async () => {
  mountList();
  const second = wrapper.findAllComponents(BaseRichTextEditor)[1];
  await second.findAll('[role="tab"]')[1].trigger('click');

  await second.get('textarea').setValue('**Updated second**');

  expect(wrapper.props('formats')).toEqual({ '/items/1': 'markdown_html_v1' });
  expect(wrapper.props('modelValue').split('\n')[0]).toBe('First');
});
