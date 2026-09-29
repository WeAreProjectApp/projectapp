import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick, ref } from 'vue';

import BaseFloatingListbox from '../../components/base/BaseFloatingListbox.vue';
import BaseModal from '../../components/base/BaseModal.vue';

const mountedWrappers = [];
let frameCallbacks;
let frameId;

function box({ left, top, width, height }) {
  return {
    x: left,
    y: top,
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    toJSON: () => ({}),
  };
}

function flushAnimationFrames() {
  const callbacks = [...frameCallbacks.values()];
  frameCallbacks.clear();
  callbacks.forEach((callback) => callback(performance.now()));
}

async function mountList({
  anchorBox = box({ left: 100, top: 100, width: 240, height: 40 }),
  props = {},
} = {}) {
  const owner = document.createElement('div');
  const ownerControl = document.createElement('button');
  const anchor = document.createElement('input');
  ownerControl.dataset.testid = 'owner-control';
  owner.append(ownerControl, anchor);
  document.body.appendChild(owner);
  anchor.getBoundingClientRect = jest.fn(() => anchorBox);

  const wrapper = mount(BaseFloatingListbox, {
    props: {
      id: 'floating-options',
      open: true,
      anchor,
      owner,
      ...props,
    },
    slots: { default: '<button type="button">Opción</button>' },
  });
  mountedWrappers.push(wrapper);
  await flushPromises();
  await nextTick();

  const panel = document.getElementById('floating-options');
  Object.defineProperty(panel, 'scrollHeight', { configurable: true, value: 200 });
  flushAnimationFrames();
  await nextTick();
  return { anchor, owner, ownerControl, panel, wrapper };
}

function mountModalListbox() {
  const Harness = defineComponent({
    components: { BaseFloatingListbox, BaseModal },
    setup() {
      return {
        anchor: ref(null),
        listOpen: ref(true),
        modalOpen: ref(true),
      };
    },
    template: `
      <BaseModal v-model="modalOpen">
        <h2>Asignar cliente</h2>
        <input id="modal-anchor" ref="anchor" data-testid="modal-anchor">
        <BaseFloatingListbox
          id="modal-floating-options"
          :open="listOpen"
          :anchor="anchor"
          :owner="anchor"
          @close="listOpen = false"
        >
          <button id="modal-floating-last" data-testid="modal-floating-last" type="button">Última opción</button>
        </BaseFloatingListbox>
      </BaseModal>
    `,
  });
  const wrapper = mount(Harness, { attachTo: document.body });
  mountedWrappers.push(wrapper);
  return wrapper;
}

async function settleModalListbox() {
  await flushPromises();
  flushAnimationFrames();
  await nextTick();
}

describe('BaseFloatingListbox', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 800 });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 600 });
    frameCallbacks = new Map();
    frameId = 0;
    jest.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      frameId += 1;
      frameCallbacks.set(frameId, callback);
      return frameId;
    });
    jest.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => {
      frameCallbacks.delete(id);
    });
    global.ResizeObserver = class ResizeObserver {
      observe() {}

      disconnect() {}
    };
  });

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount());
    delete global.ResizeObserver;
    jest.restoreAllMocks();
    document.body.innerHTML = '';
  });

  // Falla si la lista deja de exponer la semántica que usan los lectores de pantalla.
  it('exposes listbox semantics', async () => {
    const { panel } = await mountList({ props: { ariaLabel: 'Duración inicial' } });

    expect(panel.getAttribute('role')).toBe('listbox');
    expect(panel.getAttribute('aria-label')).toBe('Duración inicial');
  });

  // Falla si una lista ancha vuelve a salir por el borde horizontal de la pantalla.
  it('clamps a wide listbox to the viewport gutter', async () => {
    const { panel } = await mountList({
      anchorBox: box({ left: 700, top: 100, width: 900, height: 40 }),
    });

    expect(panel.style.width).toBe('768px');
    expect(panel.style.left).toBe('16px');
  });

  // Falla si una lista con espacio inferior aparece despegada de su campo de búsqueda.
  it('positions the listbox below its anchor', async () => {
    const { panel } = await mountList();

    expect(panel.style.top).toBe('144px');
  });

  // Falla si una lista larga deja de limitar su propia región desplazable.
  it('caps the listbox height at 320 pixels', async () => {
    const { panel } = await mountList();

    expect(panel.style.maxHeight).toBe('320px');
  });

  // Falla si una lista larga deja de avisar que necesita su siguiente página.
  it('requests more rows near its scroll end', async () => {
    const { panel, wrapper } = await mountList();
    Object.defineProperty(panel, 'scrollHeight', { configurable: true, value: 600 });
    Object.defineProperty(panel, 'clientHeight', { configurable: true, value: 320 });
    Object.defineProperty(panel, 'scrollTop', { configurable: true, value: 240 });

    panel.dispatchEvent(new Event('scroll'));

    expect(wrapper.emitted('reach-end')).toEqual([[]]);
  });

  // Falla si una lista cerca del borde inferior deja de abrirse por encima del campo.
  it('opens above the anchor when that side has more usable space', async () => {
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 500 });
    const { panel } = await mountList({
      anchorBox: box({ left: 120, top: 430, width: 260, height: 40 }),
    });

    expect(panel.style.top).toBe('226px');
  });

  // Falla si un clic dentro del control dueño o de sus opciones cierra la lista.
  test.each([
    ['owner control', ({ ownerControl }) => ownerControl],
    ['listbox', ({ panel }) => panel],
  ])('keeps a press on the %s open', async (_label, selectTarget) => {
    const list = await mountList();

    selectTarget(list).dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }));

    expect(list.wrapper.emitted('close')).toBeUndefined();
  });

  // Falla si un clic fuera del control no permite cerrar una búsqueda abierta.
  it('closes after an outside press', async () => {
    const { wrapper } = await mountList();

    document.body.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }));

    expect(wrapper.emitted('close')).toEqual([[]]);
  });

  // Falla si Escape alcanza el modal antes de cerrar sólo la lista de resultados.
  it('closes on Escape before the event can reach a parent modal', async () => {
    const parentEscape = jest.fn();
    window.addEventListener('keydown', parentEscape);
    const { wrapper } = await mountList();
    const event = new KeyboardEvent('keydown', {
      key: 'Escape',
      bubbles: true,
      cancelable: true,
    });

    window.dispatchEvent(event);

    expect(wrapper.emitted('close')).toEqual([[]]);
    expect(event.defaultPrevented).toBe(true);
    expect(parentEscape).not.toHaveBeenCalled();
    window.removeEventListener('keydown', parentEscape);
  });

  // Falla si un selector fuera de un modal no puede usar el portal seguro del documento.
  it('uses the document body outside a modal', async () => {
    const { panel } = await mountList();

    expect(panel.parentElement).toBe(document.body);
  });

  // Falla si cerrar una lista independiente deja resultados obsoletos en el documento.
  it('removes the standalone listbox after it closes', async () => {
    const { panel, wrapper } = await mountList();

    expect(panel.textContent).toBe('Opción');

    await wrapper.setProps({ open: false });

    expect(document.getElementById('floating-options')).toBeNull();
  });

  // Falla si un listbox dentro de un modal vuelve a depender del panel que puede recortarlo.
  // quality: allow-fragile-selector (role=dialog verifies the teleported list remains inside the modal's accessible boundary)
  it('places modal results in the dialog floating layer', async () => {
    mountModalListbox();
    await settleModalListbox();

    const listbox = document.getElementById('modal-floating-options');
    const dialog = document.querySelector('[role="dialog"]');
    const modalPanel = document.getElementById('modal-anchor').parentElement;

    expect(dialog.contains(listbox)).toBe(true);
    expect(modalPanel.contains(listbox)).toBe(false);
  });

  // Falla si una lista flotante permite que el panel del modal cree una segunda barra de desplazamiento.
  it('locks the modal panel scroll while its listbox is open', async () => {
    mountModalListbox();
    await settleModalListbox();

    const panel = document.getElementById('modal-anchor').parentElement;

    expect(panel.getAttribute('data-floating-layer-open')).toBe('true');
  });

  // Falla si el panel permanece bloqueado después de cerrar la lista de resultados.
  it('restores modal panel scrolling after the listbox closes', async () => {
    mountModalListbox();
    await settleModalListbox();

    document.body.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }));
    await nextTick();

    const panel = document.getElementById('modal-anchor').parentElement;
    expect(panel.getAttribute('data-modal-kind')).toBe('md');
    expect(panel.getAttribute('data-floating-layer-open')).toBeNull();
  });

  // Falla si Tab desde la última opción portalizada escapa del diálogo.
  it('traps focus from the last floating option inside the dialog', async () => {
    mountModalListbox();
    await settleModalListbox();

    const lastOption = document.getElementById('modal-floating-last');
    const anchor = document.getElementById('modal-anchor');
    lastOption.focus();
    lastOption.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Tab',
      bubbles: true,
      cancelable: true,
    }));

    expect(document.activeElement).toBe(anchor);
  });
});
