import { mockApi } from './api.js';

export const monitoringCaseTitle = 'Consulta N+1 en catálogo de Mimittos';
export const monitoringServerTitle = 'Espacio libre bajo el umbral';
export const monitoringReportTitle = 'Informe semanal de rendimiento';
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

export function monitoringCase({ state = 'pending', title = monitoringCaseTitle, kind = 'project', activities = [] } = {}) {
  const resource = kind === 'server' ? { id: 2, name: 'VPS de producción', kind: 'server' } : { id: 1, name: 'Mimittos', kind: 'project', server: 2 };
  return {
    id: kind === 'server' ? 72 : 71, title, resource, source: kind === 'server' ? 12 : 11,
    source_name: kind === 'server' ? 'Healthcheck' : 'Silk', source_key: kind === 'server' ? 'healthcheck' : 'silk', severity: kind === 'server' ? 'critical' : 'warning',
    state, condition: 'active', first_seen_at: '2026-09-19T10:00:00Z', last_seen_at: '2026-09-19T10:05:00Z',
    detections: 3, version: 3, summary: '',
    evidence: kind === 'server' ? { metric: 'disk_free', value: 8, unit: '%' } : { rule: 'n_plus_one', query_count: 12 },
    activities: { results: activities, count: activities.length, page: 1, page_size: 25 },
    deliveries: { results: [], count: 0, page: 1, page_size: 25 },
    history_bounds: { activities: activities.length, deliveries: 0 },
  };
}

export function installMonitoringMock(page, options = {}) {
  const state = { detail: monitoringCase(), requests: [], revision: 'fixture-v1', snapshots: {}, failures: {}, ...(options.state || {}) };
  const catalog = options.catalog || {
    resources: [{ id: 1, name: 'Mimittos', kind: 'project', server: 2 }, { id: 2, name: 'VPS de producción', kind: 'server' }],
    sources: [
      { id: 11, resource: 1, resource_name: 'Mimittos', key: 'silk', name: 'Silk', health: 'current', expected_interval: 300, last_seen_at: '2026-09-19T10:05:00Z', last_error: '' },
      { id: 12, resource: 2, resource_name: 'VPS de producción', key: 'healthcheck', name: 'Healthcheck', health: 'stale', expected_interval: 300, last_seen_at: '2026-09-19T09:00:00Z', last_error: 'Sin espacio suficiente' },
    ],
  };
  const report = { id: 91, title: monitoringReportTitle, resource: { id: 1, name: 'Mimittos', kind: 'project' }, source: 11, source_name: 'Silk', observed_at: '2026-09-18T09:00:00Z', text: '# Rendimiento\nSe detectaron 12 consultas N+1.' };
  state.capacity = state.capacity || { resource: catalog.resources[0], server_name: 'VPS de producción', consumption: null, consumption_status: 'unavailable', allocation: { version: 1, cpu_mode: 'assigned', cpu_vcpu: '0.400', ram_mode: 'assigned', ram_bytes: 2 * 1024 ** 3, storage_mode: 'shared', storage_bytes: null, updated_at: '2026-09-19T10:05:00Z' } };
  state.capacityHistory = state.capacityHistory || [];
  const metrics = { cpu_percent: 25, cpu_count: 2, load_1m: 1, ram_total_bytes: 4 * 1024 ** 3, ram_used_bytes: 2 * 1024 ** 3, disk_total_bytes: 80 * 1024 ** 3, disk_used_bytes: 60 * 1024 ** 3, observed_at: '2026-09-19T10:05:00Z' };
  const failOnce = name => { if (!options[name] || state.failures[name]) return false; state.failures[name] = true; return true; };
  const envelope = (records, params, isReport) => {
    const requested = Math.max(1, Number(params.page) || 1);
    let snapshot = params.snapshot;
    if (!snapshot || snapshot === 'new' || !state.snapshots[snapshot]) {
      const filtered = records.filter(record => {
        const date = (record.last_seen_at || record.observed_at).slice(0, 10);
        return (!params.resource || String(record.resource.id) === params.resource) && (!params.source || String(record.source) === params.source) && (!params.state || record.state === params.state) && (!params.severity || record.severity === params.severity) && (!params.condition || record.condition === params.condition) && (params.followup !== 'true' || ['pending', 'reviewing'].includes(record.state)) && (!params.since || date >= params.since) && (!params.until || date <= params.until) && (!params.search || record.title.toLowerCase().includes(params.search.toLowerCase()));
      });
      snapshot = `fixture-snapshot-${Object.keys(state.snapshots).length + 1}`;
      state.snapshots[snapshot] = structuredClone(filtered);
    }
    const matching = state.snapshots[snapshot];
    const current = Math.min(requested, Math.max(1, Math.ceil(matching.length / 25)));
    const active = { critical: 0, warning: 0, info: 0 };
    matching.filter(record => record.condition === 'active').forEach(record => { active[record.severity]++; });
    return { results: matching.slice((current - 1) * 25, current * 25), count: matching.length, page: current, page_size: 25, snapshot, captured_at: '2026-09-19T10:05:00Z', revision: state.revision,
      summary: { total: matching.length, active, followup: matching.filter(record => ['pending', 'reviewing'].includes(record.state)).length, sources: { current: 1 }, latest_report_at: isReport ? matching[0]?.observed_at : null }, attention: options.includeAttention && !isReport ? matching.filter(record => record.condition === 'active').slice(0, 10) : [] };
  };
  return mockApi(page, async ({ apiPath, method, route }) => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    if (apiPath.startsWith('monitoring/') && method === 'GET') state.requests.push({ apiPath, params });
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/' && method === 'GET') return json({ finance: null, proposals: { total_proposals: 0, by_status: {}, recent: [] }, additional_modules: {}, operations: {}, attention: [] });
    if (apiPath === 'monitoring/catalog/' && method === 'GET') return options.catalogFailure ? json({ detail: 'falló' }, 500) : json(catalog);
    if (apiPath === 'monitoring/status/' && method === 'GET') return options.statusFailure ? json({ detail: 'falló' }, 500) : json({ revision: state.revision, hosts: params.kind === 'project' ? [] : [{ id: 2, name: 'VPS de producción', metrics: options.noHistory ? null : metrics, health: options.noHistory ? 'no_data' : 'current', pressure: [] }] });
    if (apiPath === 'monitoring/servers/2/series/' && method === 'GET') {
      if (failOnce('seriesFailureOnce')) return json({ detail: 'falló' }, 500);
      return json({ period: params.period || '24h', interval_seconds: 60, last_observed_at: options.noHistory ? null : metrics.observed_at, capacity: options.noHistory ? null : { cpu_count: 2, ram_total_bytes: metrics.ram_total_bytes, disk_total_bytes: metrics.disk_total_bytes }, points: [
        { timestamp: Date.parse('2026-09-19T10:04:00Z'), count: 0, average: { cpu_percent: null, cpu_count: null, ram_used_bytes: null, ram_total_bytes: null, disk_used_bytes: null, disk_total_bytes: null, load_1m: null }, max: {} },
        { timestamp: Date.parse(metrics.observed_at), count: options.noHistory ? 0 : 1, average: options.noHistory ? {} : metrics, max: options.noHistory ? {} : metrics },
      ] });
    }
    if (apiPath === 'monitoring/resources/1/capacity/' && method === 'GET') return options.capacityLoadFailure ? json({ detail: 'falló' }, 500) : json(state.capacity);
    if (apiPath === 'monitoring/resources/1/capacity/' && method === 'PUT') {
      const payload = route.request().postDataJSON(); state.requests.push({ apiPath, payload });
      if (options.capacityConflict) return json({ detail: 'conflicto' }, 409);
      if (options.capacityFailure) return json({ detail: 'falló' }, 500);
      const before = state.capacity.allocation;
      state.capacity.allocation = { ...payload, version: payload.version + 1, updated_at: '2026-09-19T10:06:00Z' };
      state.capacityHistory.unshift({ id: state.capacityHistory.length + 1, actor_name: 'admin', before, after: state.capacity.allocation, created_at: '2026-09-19T10:06:00Z' });
      return json(state.capacity);
    }
    if (apiPath === 'monitoring/resources/1/capacity/history/' && method === 'GET') return json({ results: state.capacityHistory.slice(((Number(params.page) || 1) - 1) * 25, (Number(params.page) || 1) * 25), count: state.capacityHistory.length, page: Number(params.page) || 1, page_size: 25 });
    if (apiPath === 'monitoring/cases/' && method === 'GET') {
      if (options.listFailure) return json({ detail: 'falló' }, 500);
      if (failOnce('snapshotExpiredOnce')) return json({ detail: 'consulta vencida' }, 409);
      const first = params.kind === 'server' ? monitoringCase({ title: monitoringServerTitle, kind: 'server' }) : state.detail;
      const records = [first, ...Array.from({ length: Math.max(0, (options.corpusSize || 1) - 1) }, (_, index) => ({ ...first, id: 100 + index, title: `Observación de prueba ${index + 2}` }))];
      return json(envelope(records, params, false));
    }
    if (apiPath === 'monitoring/reports/' && method === 'GET') {
      if (options.reportsFailure) return json({ detail: 'falló' }, 500);
      if (failOnce('reportsExpiredOnce')) return json({ detail: 'consulta vencida' }, 409);
      return json(envelope([report], params, true));
    }
    if ((apiPath === 'monitoring/cases/71/' || apiPath === 'monitoring/cases/72/') && method === 'GET') return options.detailFailure ? json({ detail: 'falló' }, 500) : json(apiPath.includes('/72/') ? monitoringCase({ title: monitoringServerTitle, kind: 'server' }) : state.detail);
    if (apiPath === 'monitoring/reports/91/' && method === 'GET') return json(report);
    if (apiPath === 'monitoring/cases/71/state/' && method === 'POST') {
      const payload = route.request().postDataJSON(); state.requests.push({ apiPath, payload });
      if (options.stateFailure) return json({ detail: 'falló' }, 500);
      if (options.stateConflict) return json({ detail: 'conflicto' }, 409);
      state.detail = { ...state.detail, state: payload.state, version: state.detail.version + 1 };
      return json(state.detail);
    }
    if (apiPath === 'monitoring/cases/71/notes/' && method === 'POST') {
      const payload = route.request().postDataJSON(); state.requests.push({ apiPath, payload });
      if (options.noteFailure) return json({ detail: 'falló' }, 500);
      if (options.noteValidation) return json({ text: ['La nota no es válida.'] }, 400);
      const activity = { id: state.detail.activities.count + 1, actor_name: 'admin', text: payload.text, created_at: '2026-09-19T10:06:00Z', from_state: '', to_state: '' };
      state.detail = { ...state.detail, activities: { ...state.detail.activities, results: [activity, ...state.detail.activities.results], count: state.detail.activities.count + 1 } };
      return json(activity, 201);
    }
    return null;
  }).then(() => state);
}
