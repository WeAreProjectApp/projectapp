import { flushPromises, mount } from '@vue/test-utils';
import { createPinia } from 'pinia';

jest.mock('~/stores/services/request_http', () => ({ get_request: jest.fn(), create_request: jest.fn() }));
jest.mock('#imports', () => {
  const messages = require('../../locales/documentHistory/es').default;
  const { ref } = require('vue');
  const value = (key) => key.split('.').slice(1).reduce((current, part) => current?.[part], messages);
  return {
    useI18n: () => ({
      locale: ref('es-co'), te: (key) => typeof value(key) === 'string',
      t: (key, params = {}) => String(value(key) || key).replace(/\{(\w+)\}/g, (_, name) => params[name] ?? ''),
    }),
  };
});

import DocumentHistoryPanel from '~/components/history/DocumentHistoryPanel.vue';
import { create_request, get_request } from '~/stores/services/request_http';

const entry = (id, number = id) => ({ id, number, complete: true, action: 'updated', actor: 'Ana', occurred_at: '2026-11-13T12:00:00Z', fields: [{ label: 'Contenido' }] });
const version = (id, extra = {}) => ({ ...entry(id), snapshot: { title: 'Contrato', content_markdown: id === 1 ? '# Alcance\n\nAnterior' : '# Alcance\n\nNuevo' }, previous_id: id === 1 ? null : 1, labels: {}, ...extra });
const listing = (results = [entry(2), entry(1)], extra = {}) => ({ results, count: results.length, num_pages: 1, ...extra });
const data = (value) => Promise.resolve({ data: value });
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
}
function setup({ list = listing(), versions = {}, compare = {} } = {}) {
  get_request.mockImplementation((url) => {
    const match = url.match(/versions\/(\d+)\//);
    if (match) return data(versions[match[1]] || version(Number(match[1])));
    if (url.includes('compare/')) return data(compare);
    return data(list);
  });
  return mount(DocumentHistoryPanel, { props: { objectId: 8 }, global: { plugins: [createPinia()] }, attachTo: document.body });
}
const consult = (wrapper, id) => wrapper.get(`[data-testid="history-entry-${id}"]`).find('button').trigger('click');

describe('document history panel', () => {
  let wrapper;
  beforeEach(() => {
    jest.clearAllMocks();
    window.scrollTo = jest.fn();
    Element.prototype.scrollIntoView = jest.fn();
    Element.prototype.scrollTo = jest.fn();
  });
  afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; });

  it('shows the current order in a project dropdown', async () => {
    wrapper = setup();
    await flushPromises();

    expect(wrapper.get('[data-testid="history-order"]').text()).toContain('Más reciente primero');
    expect(wrapper.find('select').exists()).toBe(false);
  });

  it('renders one history pagination', async () => {
    wrapper = setup({ list: listing([entry(2)], { count: 25, num_pages: 2 }) });
    await flushPromises();

    expect(wrapper.findAll('nav[aria-label="Paginación del historial"]')).toHaveLength(1);
  });

  it('queries the previous revision on consultation', async () => {
    wrapper = setup();
    await flushPromises();
    await consult(wrapper, 2);
    await flushPromises();

    expect(get_request).toHaveBeenCalledWith('entity-history/document/8/compare/?from=1&to=2');
    expect(wrapper.get('[data-testid="history-comparison-heading"]').text()).toContain('Comparación v1 → v2');
    expect(wrapper.get('[data-history-change="removed"]').text()).toContain('Anterior');
    expect(wrapper.get('[data-history-change="added"]').text()).toContain('Nuevo');
  });

  it('shows immediate feedback while a revision loads', async () => {
    wrapper = setup();
    await flushPromises();
    const pending = deferred();
    get_request.mockReturnValueOnce(pending.promise);
    await consult(wrapper, 2);

    expect(wrapper.get('[data-testid="history-version-detail"] [role="status"]').text()).toBe('Consultando versión…');
    expect(wrapper.get('[data-testid="history-entry-2"]').attributes('aria-current')).toBe('true');
  });

  it('shows the initial revision without an invented predecessor', async () => {
    wrapper = setup();
    await flushPromises();
    await consult(wrapper, 1);
    await flushPromises();

    expect(wrapper.get('[data-testid="history-version-detail"]').text()).toContain('Versión inicial');
    expect(get_request.mock.calls.filter(([url]) => url.includes('compare/'))).toHaveLength(0);
  });

  it('returns from the complete reading to the same comparison', async () => {
    wrapper = setup();
    await flushPromises();
    await consult(wrapper, 2);
    await flushPromises();
    await wrapper.get('[data-testid="history-full-version"]').trigger('click');
    await flushPromises();
    expect(wrapper.get('[data-testid="history-full-content"]').text()).toContain('Nuevo');
    await wrapper.get('[data-testid="history-full-version"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-history-change="removed"]').text()).toContain('Anterior');
    expect(get_request.mock.calls.filter(([url]) => url.includes('compare/'))).toHaveLength(1);
  });

  it('clears a previous comparison when a checkbox selection changes', async () => {
    wrapper = setup();
    await flushPromises();
    await consult(wrapper, 2);
    await flushPromises();
    await wrapper.get('[aria-label="Seleccionar versión 1"]').setValue(true);

    expect(wrapper.find('[data-testid="history-rich-diff"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="history-selection"]').text()).toContain('v1');
  });

  it('limits comparison selection to two revisions', async () => {
    wrapper = setup({ list: listing([entry(3), entry(2), entry(1)]) });
    await flushPromises();
    await wrapper.get('[aria-label="Seleccionar versión 1"]').setValue(true);
    await wrapper.get('[aria-label="Seleccionar versión 2"]').setValue(true);

    expect(wrapper.get('[aria-label="Seleccionar versión 3"]').element.disabled).toBe(true);
    expect(wrapper.get('[data-testid="history-selection"]').text()).toContain('v1 → v2');
  });

  it('orders selected revisions chronologically', async () => {
    wrapper = setup();
    await flushPromises();
    await wrapper.get('[aria-label="Seleccionar versión 2"]').setValue(true);
    await wrapper.get('[aria-label="Seleccionar versión 1"]').setValue(true);
    await wrapper.get('[data-testid="history-compare"]').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenCalledWith('entity-history/document/8/compare/?from=1&to=2');
  });

  it('rejects a late result from an earlier consultation', async () => {
    wrapper = setup();
    await flushPromises();
    const pending = deferred();
    get_request.mockReturnValueOnce(pending.promise);
    await consult(wrapper, 2);
    await consult(wrapper, 1);
    await flushPromises();
    pending.resolve({ data: version(2) });
    await flushPromises();

    expect(wrapper.get('[data-testid="history-version-detail"]').text()).toContain('Versión 1');
    expect(wrapper.find('[data-testid="history-rich-diff"]').exists()).toBe(false);
  });

  it('retries a failed comparison for the same revision', async () => {
    wrapper = setup();
    await flushPromises();
    get_request.mockReturnValueOnce(data(version(2))).mockReturnValueOnce(data(version(1))).mockRejectedValueOnce(new Error('unavailable'));
    await consult(wrapper, 2);
    await flushPromises();
    await wrapper.get('[role="alert"] button').trigger('click');
    await flushPromises();

    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="history-comparison-heading"]').text()).toContain('v1 → v2');
  });

  it('explains identical revisions', async () => {
    wrapper = setup({ versions: { 2: version(2, { snapshot: version(1).snapshot }) } });
    await flushPromises();
    await consult(wrapper, 2);
    await flushPromises();

    expect(wrapper.get('[data-testid="history-no-changes"]').text()).toBe('No hay diferencias entre estas versiones.');
  });

  it('consults historical versions without issuing a write', async () => {
    wrapper = setup();
    await flushPromises();
    await consult(wrapper, 2);
    await flushPromises();

    expect(create_request).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="history-version-detail"]').text()).toContain('v1 → v2');
  });

  it('clears the old document consultation when its identity changes', async () => {
    wrapper = setup();
    await flushPromises();
    await consult(wrapper, 2);
    await flushPromises();
    await wrapper.setProps({ objectId: 9 });
    await flushPromises();

    expect(wrapper.find('[data-testid="history-rich-diff"]').exists()).toBe(false);
    expect(get_request).toHaveBeenLastCalledWith('entity-history/document/9/?page=1&order=recent');
  });
});
