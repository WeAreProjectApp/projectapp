import { mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import { vAutoResize } from '../../utils/autoResizeDirective';

// jsdom has no layout: the content height is stubbed, and the box model comes
// from inline styles, which getComputedStyle does resolve.
const BOX = 'line-height: 20px; padding-top: 12px; padding-bottom: 12px; border: 1px solid;';

function mountTextarea({ boxSizing = 'border-box', contentHeight = 0, text = 'Hola' } = {}) {
  jest.spyOn(Element.prototype, 'scrollHeight', 'get').mockReturnValue(contentHeight);
  const Host = defineComponent({
    directives: { autoResize: vAutoResize },
    setup: () => ({ text: ref(text), style: `${BOX} box-sizing: ${boxSizing};` }),
    template: '<textarea v-model="text" v-auto-resize rows="3" :style="style" />',
  });
  return mount(Host);
}

describe('vAutoResize', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('adds the borders so a border-box textarea shows its last line', () => {
    const wrapper = mountTextarea({ contentHeight: 500 });

    expect(wrapper.get('textarea').element.style.height).toBe('502px');
  });

  it('sizes a content-box textarea to its content alone', () => {
    const wrapper = mountTextarea({ boxSizing: 'content-box', contentHeight: 500 });

    expect(wrapper.get('textarea').element.style.height).toBe('500px');
  });

  it('keeps the rows as the minimum height of a short text', () => {
    const wrapper = mountTextarea({ contentHeight: 30 });

    // 3 rows × 20px + 24px of padding + 2px of border.
    expect(wrapper.get('textarea').element.style.height).toBe('86px');
  });

  it('grows again when the text gets longer', async () => {
    const wrapper = mountTextarea({ contentHeight: 120 });
    jest.spyOn(Element.prototype, 'scrollHeight', 'get').mockReturnValue(260);

    await wrapper.get('textarea').setValue('Hola\n\nUn correo mucho más largo.');

    expect(wrapper.get('textarea').element.style.height).toBe('262px');
  });
});
