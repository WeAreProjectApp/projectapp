import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
}));

import EntityHistoryPanel from '../../components/history/EntityHistoryPanel.vue';
import { create_request, get_request } from '../../stores/services/request_http';

const makeList = (entries = []) => ({
  count: entries.length,
  num_pages: 1,
  results: entries,
  latest_change: null,
  last_sent_version: null,
});

const makeEntry = (id, number) => ({
  id,
  number,
  action: 'updated',
  occurred_at: '2026-09-22T12:00:00Z',
  actor: 'Ana Admin',
  source: 'http',
  fields: [{ label: 'Título' }],
  complete: true,
});

const makeVersion = (id, number, overrides = {}) => ({
  id,
  number,
  complete: true,
  changes: [{ field: 'title', label: 'Título', old: 'Antes', new: `Documento ${number}` }],
  snapshot: { title: `Documento ${number}` },
  protected_fields: [],
  previous_id: null,
  ...overrides,
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function mountPanel(props = {}) {
  setActivePinia(createPinia());
  return mount(EntityHistoryPanel, {
    attachTo: document.body,
    props: { entityType: 'document', objectId: 8, ...props },
    global: { plugins: [createPinia()] },
  });
}

function buttonByText(wrapper, text) {
  return wrapper.findAll('button').find((button) => button.text() === text);
}

describe('EntityHistoryPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  // Falla si un error de carga deja el historial sin una recuperación visible.
  it('recovers a failed list request through the visible retry', async () => {
    get_request
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ data: makeList([makeEntry(31, 4)]) });
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain('No se pudo cargar el historial. Intenta de nuevo.');

    await buttonByText(wrapper, 'Reintentar').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenCalledTimes(2);
    expect(get_request).toHaveBeenLastCalledWith('entity-history/document/8/?page=1&order=recent');
    expect(wrapper.get('[data-testid="history-entry-31"]').text()).toContain('Modificado');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);

    wrapper.unmount();
  });

  // Falla si una respuesta tardía de otra entidad reemplaza el historial actual.
  it('keeps the newer entity list when the prior list request resolves last', async () => {
    const firstList = deferred();
    const secondList = deferred();
    get_request.mockImplementationOnce(() => firstList.promise).mockImplementationOnce(() => secondList.promise);
    const wrapper = mountPanel({ objectId: 8 });

    await wrapper.setProps({ objectId: 9 });
    secondList.resolve({ data: makeList([makeEntry(92, 7)]) });
    await flushPromises();
    firstList.resolve({ data: makeList([makeEntry(81, 2)]) });
    await flushPromises();

    expect(wrapper.get('[data-testid="history-entry-92"]').text()).toContain('v7');
    expect(wrapper.find('[data-testid="history-entry-81"]').exists()).toBe(false);

    wrapper.unmount();
  });

  // Falla si una consulta de versión lenta reemplaza la última versión elegida.
  it('keeps the later version detail when the earlier version request resolves last', async () => {
    const firstVersion = deferred();
    const secondVersion = deferred();
    get_request.mockImplementation((url) => {
      if (url.includes('versions/101/')) return firstVersion.promise;
      if (url.includes('versions/102/')) return secondVersion.promise;
      return Promise.resolve({ data: makeList([makeEntry(101, 1), makeEntry(102, 2)]) });
    });
    const wrapper = mountPanel();
    await flushPromises();

    await buttonByText(wrapper.get('[data-testid="history-entry-101"]'), 'Consultar').trigger('click');
    await buttonByText(wrapper.get('[data-testid="history-entry-102"]'), 'Consultar').trigger('click');
    secondVersion.resolve({ data: makeVersion(102, 2) });
    await flushPromises();
    firstVersion.resolve({ data: makeVersion(101, 1) });
    await flushPromises();

    expect(wrapper.get('[data-testid="history-version-detail"]').text()).toContain('Versión 2');
    expect(wrapper.get('[data-testid="history-version-detail"]').text()).toContain('Documento 2');
    expect(wrapper.get('[data-testid="history-version-detail"]').text()).not.toContain('Documento 1');

    wrapper.unmount();
  });

  // Falla si una contraseña revelada sobrevive al cambio de versión.
  it('clears revealed secrets after leaving the active version', async () => {
    get_request.mockImplementation((url) => {
      if (url.includes('versions/201/')) {
        return Promise.resolve({ data: makeVersion(201, 1, {
          protected_fields: ['access.production.password'],
        }) });
      }
      if (url.includes('versions/202/')) return Promise.resolve({ data: makeVersion(202, 2) });
      return Promise.resolve({ data: makeList([makeEntry(201, 1), makeEntry(202, 2)]) });
    });
    create_request.mockResolvedValue({ data: { secret: 'clave-produccion-2026' } });
    const wrapper = mountPanel();
    await flushPromises();

    await buttonByText(wrapper.get('[data-testid="history-entry-201"]'), 'Consultar').trigger('click');
    await flushPromises();
    await buttonByText(wrapper, 'Revelar contraseña · Producción').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith(
      'entity-history/document/8/versions/201/reveal/',
      { field: 'access.production.password' },
    );
    expect(wrapper.get('[data-testid="history-revealed"]').text()).toBe('clave-produccion-2026');

    await buttonByText(wrapper.get('[data-testid="history-entry-202"]'), 'Consultar').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="history-version-detail"]').text()).toContain('Versión 2');
    expect(wrapper.find('[data-testid="history-revealed"]').exists()).toBe(false);

    wrapper.unmount();
  });

  function mockThreePageHistory() {
    get_request.mockImplementation((url) => {
      if (url.includes('versions/31/')) {
        return Promise.resolve({ data: makeVersion(31, 31, {
          snapshot: { generated_file: '/media/proposal-v31.pdf' },
        }) });
      }
      if (url.includes('page=2')) {
        return Promise.resolve({ data: {
          ...makeList([makeEntry(31, 31)]), count: 43, num_pages: 3,
        } });
      }
      if (url.includes('page=3')) {
        return Promise.resolve({ data: {
          ...makeList([makeEntry(41, 41)]), count: 43, num_pages: 3,
        } });
      }
      return Promise.resolve({ data: { ...makeList([makeEntry(1, 1)]), count: 43, num_pages: 3 } });
    });
  }

  async function goToSecondPage(wrapper) {
    await buttonByText(wrapper, '2').trigger('click');
    await flushPromises();
  }

  // Falla si la paginación no aclara qué tramo de las 43 versiones se está viendo.
  it('shows the exact range for the second history page', async () => {
    mockThreePageHistory();
    const wrapper = mountPanel();
    await flushPromises();

    await goToSecondPage(wrapper);

    expect(wrapper.get('[aria-label="Paginación del historial"]').text()).toContain('Mostrando 21–40 de 43');
    wrapper.unmount();
  });

  // Falla si avanzar una página pierde el orden reciente que eligió el usuario.
  it('requests the next history page with recent ordering', async () => {
    mockThreePageHistory();
    const wrapper = mountPanel();
    await flushPromises();

    await goToSecondPage(wrapper);
    await wrapper.get('[aria-label="Paginación del historial"] [aria-label="Página siguiente"]').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenLastCalledWith('entity-history/document/8/?page=3&order=recent');
    wrapper.unmount();
  });

  // Falla si cambiar de página cierra una versión seleccionada o pierde su archivo histórico.
  it('keeps the selected version and its PDF download after pagination', async () => {
    mockThreePageHistory();
    const wrapper = mountPanel();
    await flushPromises();

    await goToSecondPage(wrapper);
    await buttonByText(wrapper.get('[data-testid="history-entry-31"]'), 'Consultar').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenLastCalledWith('entity-history/document/8/versions/31/');
    expect(wrapper.get('[href="/api/entity-history/document/8/versions/31/file/"]').text()).toBe('Ver PDF de esta versión');

    await wrapper.get('[aria-label="Paginación del historial"] [aria-label="Página siguiente"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="history-version-detail"]').text()).toContain('Versión 31');
    wrapper.unmount();
  });

  // Falla si la respuesta tardía de una revelación vuelve a mostrar una clave de la versión anterior.
  it('does not display a late V1 reveal after switching to V2', async () => {
    const pendingReveal = deferred();
    get_request.mockImplementation((url) => {
      if (url.includes('versions/301/')) {
        return Promise.resolve({ data: makeVersion(301, 1, {
          protected_fields: ['access.production.password'],
        }) });
      }
      if (url.includes('versions/302/')) return Promise.resolve({ data: makeVersion(302, 2) });
      return Promise.resolve({ data: makeList([makeEntry(301, 1), makeEntry(302, 2)]) });
    });
    create_request.mockReturnValue(pendingReveal.promise);
    const wrapper = mountPanel();
    await flushPromises();

    await buttonByText(wrapper.get('[data-testid="history-entry-301"]'), 'Consultar').trigger('click');
    await flushPromises();
    await buttonByText(wrapper, 'Revelar contraseña · Producción').trigger('click');
    await buttonByText(wrapper.get('[data-testid="history-entry-302"]'), 'Consultar').trigger('click');
    await flushPromises();
    pendingReveal.resolve({ data: { secret: 'clave-antigua-no-visible' } });
    await flushPromises();

    expect(wrapper.get('[data-testid="history-version-detail"]').text()).toContain('Versión 2');
    expect(wrapper.find('[data-testid="history-revealed"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('clave-antigua-no-visible');

    wrapper.unmount();
  });
});
