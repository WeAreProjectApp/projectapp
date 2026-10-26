import { defineComponent } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import { useRadarFocus } from '../../composables/useRadarFocus';

let wrapper;
beforeEach(() => jest.useFakeTimers());
afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = '';
  jest.useRealTimers();
});
function mountTarget(target) {
  wrapper = mount(defineComponent({
    setup() { return { focus: useRadarFocus() }; },
    template: `<div><button @click="focus('#radar-target')">Mostrar registro</button>${target}</div>`,
  }), { attachTo: document.body });
  return wrapper;
}

it('keeps a destination link in the keyboard tab order', async () => {
  const host = mountTarget('<a id="radar-target" href="/panel/tasks?task=42">Tarea pendiente</a>');

  await host.get('button').trigger('click');
  await flushPromises();

  expect(document.activeElement).toBe(host.get('a').element);
  expect(host.get('a').element.tabIndex).toBe(0);
});

it('focuses a record without adding a keyboard tab stop', async () => {
  const host = mountTarget('<section id="radar-target">Registro pendiente</section>');

  await host.get('button').trigger('click');
  await flushPromises();

  expect(document.activeElement).toBe(host.get('section').element);
  expect(host.get('section').element.tabIndex).toBe(-1);
});
