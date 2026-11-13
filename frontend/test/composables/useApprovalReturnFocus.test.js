import { mount, flushPromises } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';
import { useApprovalReturnFocus } from '~/composables/useApprovalReturnFocus';

let wrapper;
let visible;
let frames;
let opener;
let destination;
let destinationResolver;

function button(text) {
  const node = document.createElement('button');
  node.textContent = text;
  document.body.append(node);
  return node;
}

function openReview(returnTo = () => destination) {
  opener.focus();
  visible = ref(true);
  destinationResolver = ref(returnTo);
  wrapper = mount(defineComponent({
    setup() {
      useApprovalReturnFocus(visible, destinationResolver);
      return {};
    },
    template: '<div />',
  }));
  const confirmation = button('Confirmar');
  confirmation.focus();
}

async function closeReview() {
  visible.value = false;
  await flushPromises();
  frames.splice(0).forEach((callback) => callback());
}

beforeEach(() => {
  frames = [];
  jest.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
    frames.push(callback);
    return frames.length;
  });
  jest.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
  // JSDOM has no layout; model the browser's visible geometry at that boundary.
  jest.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{ width: 200, height: 40 }]);
  opener = button('Revisar');
  destination = button('Abrir la misma propuesta');
});

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = '';
  window.history.replaceState({}, '', '/');
  jest.restoreAllMocks();
});

describe('Approval return focus (PA-260/D1)', () => {
  it('returns mouse focus to the surviving trigger', async () => {
    openReview();

    await closeReview();

    expect(document.activeElement).toBe(opener);
  });

  it.each([
    ['removed', (node) => node.remove()],
    ['hidden', (node) => { node.style.display = 'none'; }],
    ['disabled', (node) => { node.disabled = true; }],
  ])('focuses the same record destination when Review is %s', async (_reason, change) => {
    openReview();
    change(opener);

    await closeReview();

    expect(document.activeElement).toBe(destination);
  });

  it('uses the destination delivered with the opening render', async () => {
    openReview(null);
    destinationResolver.value = () => destination;
    opener.remove();

    await closeReview();

    expect(document.activeElement).toBe(destination);
  });

  it('leaves focus in a newly opened dialog', async () => {
    openReview();
    const dialog = document.createElement('section');
    dialog.setAttribute('role', 'dialog');
    const control = button('Control del otro diálogo');
    dialog.append(control);
    document.body.append(dialog);
    control.focus();

    await closeReview();

    expect(document.activeElement).toBe(control);
  });

  it('keeps the destination page focus after navigation', async () => {
    openReview();
    window.history.pushState({}, '', '/panel/projects');
    const nextPage = button('Proyecto abierto');
    nextPage.focus();

    await closeReview();

    expect(document.activeElement).toBe(nextPage);
  });

  it('ignores a close belonging to an earlier modal opening', async () => {
    openReview();
    visible.value = false;
    await flushPromises();
    visible.value = true;
    const newControl = button('Control de la revisión nueva');
    newControl.focus();

    frames.splice(0).forEach((callback) => callback());

    expect(document.activeElement).toBe(newControl);
  });

  it('uses the destination when the initial page had no focused control', async () => {
    visible = ref(true);
    wrapper = mount(defineComponent({
      setup() { useApprovalReturnFocus(visible, ref(() => destination)); },
      template: '<div />',
    }));

    await closeReview();

    expect(document.activeElement).toBe(destination);
  });
});
