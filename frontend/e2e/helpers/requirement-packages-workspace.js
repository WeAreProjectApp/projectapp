import { mockApi } from './api.js';
import { mockPlatformClient } from './platform-auth.js';

export const REQUIREMENT_PACKAGE_PROJECT = {
  id: 1,
  name: 'Atlas Workspace',
  description: 'Proyecto de pruebas para paquetes por talla',
  status: 'active',
  status_label: 'Activo',
  progress: 55,
  client_id: mockPlatformClient.id,
  client_name: 'Client E2E',
  current_state: { id: 1, name: 'Activo', system_key: 'active', color: 'emerald' },
};

export const REQUIREMENT_PACKAGE_ORDER_ID = '11111111-1111-4111-8111-111111111111';
export const REQUIREMENT_PACKAGE_NEW_ORDER_ID = '22222222-2222-4222-8222-222222222222';
export const REQUIREMENT_PACKAGE_PAID_ORDER_ID = '33333333-3333-4333-8333-333333333333';
export const REQUIREMENT_PACKAGE_QUOTE_DIGEST = 'a3f18b32b1d1b3361e64e3c50b07c3de12986f0e644f1fbd6e93b6a961e68d52';

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const error = (detail, status = 400) => json({ detail }, status);

const paged = (results) => ({ count: results.length, results });

function examples() {
  return {
    sizes: [
      { size: 'XS', definition: 'Ajuste puntual sobre una salida existente.', source: 'project', examples: ['Cambiar el texto de bienvenida de Atlas'] },
      { size: 'S', definition: 'Cambio pequeño que reutiliza una vista existente.', source: 'generic', examples: ['Agregar un filtro a un listado existente'] },
      { size: 'M', definition: 'Mejora acotada con varias salidas relacionadas.', source: 'generic', examples: ['Crear un reporte con filtros y exportación'] },
      { size: 'L', definition: 'Alcance que requiere cotización independiente.', source: 'generic', examples: ['Integrar una fuente externa delimitada'] },
      { size: 'XL', definition: 'Cambio transversal que requiere cotización independiente.', source: 'generic', examples: ['Construir un flujo transversal con permisos'] },
      { size: 'PROJECT', definition: 'Iniciativa completa que se cotiza como proyecto.', source: 'generic', examples: ['Construir un módulo nuevo completo'] },
    ],
  };
}

function fixture({ admin = false } = {}) {
  const request = {
    id: 701,
    title: 'Mostrar el estado del pedido',
    description: 'Necesito ver el estado del pedido en el espacio de Atlas.',
    status: 'offered',
    version: 4,
    suggested_order_id: REQUIREMENT_PACKAGE_PAID_ORDER_ID,
    proposal: {
      id: 801,
      size: 'S',
      scope: 'Mostrar el estado confirmado del pedido.',
      explanation: 'Reutiliza el listado y no añade un flujo nuevo.',
      assumptions: 'El estado ya está disponible en la API.',
      delivery_from: '2026-11-17',
      delivery_until: '2026-11-20',
      schedule_conditions: 'Después de validar el diseño.',
      examples: ['Agregar un filtro a un listado existente'],
      warranty: false,
    },
    proposals: [],
  };
  const externalOrder = {
    id: REQUIREMENT_PACKAGE_ORDER_ID,
    method: 'external',
    status: 'pending',
    total: '1190000',
    currency: 'COP',
    expires_at: null,
    snapshot: { name: 'Paquete Atlas', counts: { XS: 2, S: 1, M: 0 } },
  };
  const paidOrder = {
    id: REQUIREMENT_PACKAGE_PAID_ORDER_ID,
    method: 'external',
    status: 'paid',
    total: '2380000',
    currency: 'COP',
    expires_at: '2027-11-12T00:00:00Z',
    snapshot: { name: 'Paquete Atlas ampliado', counts: { XS: 2, S: 2, M: 0 } },
  };
  return {
    admin,
    balances: { XS: 2, S: 1, M: 0 },
    examples: examples(),
    catalog: [{
      package_id: 101,
      name: 'Paquete Atlas',
      counts: { XS: 2, S: 1, M: 0 },
      subtotal: '1000000',
      tax_rate: 19,
      total: '1190000',
      currency: 'COP',
      validity_months: 12,
      terms: 'Válido para Atlas y no transferible.',
      quote_digest: REQUIREMENT_PACKAGE_QUOTE_DIGEST,
      online_available: true,
    }],
    requests: [request],
    orders: [externalOrder, paidOrder],
    movements: [{
      id: 901,
      kind: 'debit',
      quantity: -1,
      size: 'S',
      reason: 'Aceptación previa',
      created_at: '2026-11-01T00:00:00Z',
    }],
    settings: { nationality: 'COL', tax_rate: 19, version: 3 },
    customExamples: { XS: ['Cambiar el texto de bienvenida de Atlas'] },
    genericExamples: { XS: ['Cambiar una etiqueta visible'], S: ['Agregar un filtro'] },
    nextRequestId: 702,
  };
}

function overview(state) {
  return {
    is_admin: state.admin,
    balances: state.balances,
    examples: state.examples,
    catalog: state.catalog,
    requests: paged(state.requests),
    orders: paged(state.orders),
    movements: paged(state.movements),
    settings: state.settings,
  };
}

/**
 * Stateful API fixture for the workspace. Tests use this through visible UI
 * controls; state changes make each assertion fail if the UI stops issuing
 * its request or stops rendering the returned outcome.
 */
export async function mockRequirementPackagesWorkspace(page, options = {}) {
  const state = fixture({ admin: options.admin });
  const calls = [];
  const failures = options.failures || {};
  const queueRows = options.queueRows || [{
    id: 701,
    title: state.requests[0].title,
    project_id: REQUIREMENT_PACKAGE_PROJECT.id,
    project_name: REQUIREMENT_PACKAGE_PROJECT.name,
    status: state.requests[0].status,
  }];

  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/' && method === 'GET') {
      return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    }
    if (apiPath === 'accounts/me/' && method === 'GET') return json(options.user || mockPlatformClient);
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([REQUIREMENT_PACKAGE_PROJECT]);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') return json(REQUIREMENT_PACKAGE_PROJECT);
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') return json([]);

    if (apiPath === 'requirement-packages/admin/projects/' && method === 'GET') {
      return json({ results: [REQUIREMENT_PACKAGE_PROJECT] });
    }
    if (apiPath === 'requirement-packages/admin/requests/' && method === 'GET') {
      if (failures.queue) return error('No pudimos cargar la bandeja.', failures.queue);
      const params = new URL(route.request().url()).searchParams;
      const search = params.get('search') || '';
      const status = params.get('status') || '';
      const results = queueRows.filter((row) => (
        (!search || `${row.title} ${row.project_name}`.toLowerCase().includes(search.toLowerCase()))
        && (!status || row.status === status)
      ));
      return json({ count: results.length, pending_count: results.length, results });
    }

    if (apiPath === 'requirement-packages/examples/' && method === 'GET') {
      return json({ generic_examples: state.genericExamples, custom_examples: {} , generic_revision: 2, project_revision: 0 });
    }
    if (apiPath === 'requirement-packages/examples/' && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      if (failures.examples) return error('La versión de ejemplos cambió. Recarga antes de publicar.', failures.examples);
      state.genericExamples = route.request().postDataJSON().examples;
      return json({ revision: 3 });
    }
    if (apiPath === 'requirement-packages/examples/history/' && method === 'GET') {
      return json({ count: 1, results: [{ id: 30, created_at: '2026-11-12', note: 'Ajuste para Atlas' }] });
    }

    if (!apiPath.startsWith('requirement-packages/projects/1/')) return null;
    const path = apiPath.slice('requirement-packages/projects/1/'.length);
    if (path === '' && method === 'GET') {
      if (failures.overview) return error('No pudimos cargar los paquetes.', failures.overview);
      return json(overview(state));
    }
    if (path === 'evaluation-context/' && method === 'GET') {
      return json({ definition: { signals: [
        { id: 'signal-xs', size: 'XS', label: 'Cambia una salida visible' },
        { id: 'signal-s', size: 'S', label: 'Reutiliza una vista existente' },
      ] } });
    }
    if (path === 'examples/' && method === 'GET') {
      return json({ generic_examples: state.genericExamples, custom_examples: state.customExamples, generic_revision: 2, project_revision: 4 });
    }
    if (path === 'examples/' && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      if (failures.examples) return error('La versión de ejemplos cambió. Recarga antes de publicar.', failures.examples);
      state.customExamples = route.request().postDataJSON().examples;
      return json({ revision: 5 });
    }
    if (path === 'examples/history/' && method === 'GET') {
      return json({ count: 1, results: [{ id: 31, created_at: '2026-11-12', note: 'Ejemplo propio de Atlas' }] });
    }
    if (path === 'requests/' && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      if (failures.request) return error('Describe el resultado esperado antes de enviarlo.', failures.request);
      const body = route.request().postDataJSON();
      const created = { id: state.nextRequestId++, title: body.title, description: body.description, status: 'pending', version: 1, proposal: null, proposals: [] };
      state.requests.unshift(created);
      return json(created, 201);
    }
    const requestMatch = path.match(/^requests\/(\d+)\/$/);
    if (requestMatch && method === 'GET') {
      const item = state.requests.find((row) => row.id === Number(requestMatch[1]));
      return item ? json(item) : error('Solicitud no disponible.', 404);
    }
    const evaluateMatch = path.match(/^requests\/(\d+)\/evaluate\/$/);
    if (evaluateMatch && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      const item = state.requests.find((row) => row.id === Number(evaluateMatch[1]));
      item.status = 'evaluating';
      item.version += 1;
      return json(item);
    }
    const offerMatch = path.match(/^requests\/(\d+)\/offer\/$/);
    if (offerMatch && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      if (failures.offer) return error('Selecciona las señales aplicables antes de enviar la propuesta.', failures.offer);
      const item = state.requests.find((row) => row.id === Number(offerMatch[1]));
      const body = route.request().postDataJSON();
      item.status = 'offered';
      item.version += 1;
      item.proposal = { id: 900, ...body, examples: ['Agregar un filtro a un listado existente'] };
      item.proposals = [{ id: 900, size: body.size, created_at: '2026-11-12', explanation: body.explanation }];
      return json(item);
    }
    const decideMatch = path.match(/^requests\/(\d+)\/decide\/$/);
    if (decideMatch && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      if (failures.decision) return error('No pudimos registrar tu decisión. Inténtalo de nuevo.', failures.decision);
      const item = state.requests.find((row) => row.id === Number(decideMatch[1]));
      const body = route.request().postDataJSON();
      item.status = body.decision === 'accept' ? 'accepted' : 'objected';
      if (body.decision === 'accept' && !item.proposal.warranty) state.balances[item.proposal.size] -= 1;
      return json(item);
    }
    if (path === 'orders/' && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      if (failures.order) return error('No pudimos crear la compra. Inténtalo de nuevo.', failures.order);
      const body = route.request().postDataJSON();
      const order = { id: REQUIREMENT_PACKAGE_NEW_ORDER_ID, method: body.method, status: 'pending', total: '1190000', currency: 'COP', snapshot: { name: 'Paquete Atlas', counts: { XS: 2, S: 1, M: 0 } }, expires_at: null };
      state.orders.unshift(order);
      return json(order, 201);
    }
    const externalMatch = path.match(/^orders\/([^/]+)\/confirm-external\/$/);
    if (externalMatch && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      if (failures.external) return error('No pudimos confirmar el pago externo.', failures.external);
      const order = state.orders.find((row) => row.id === externalMatch[1]);
      order.status = 'paid';
      order.expires_at = '2027-11-12T00:00:00Z';
      for (const [size, count] of Object.entries(order.snapshot.counts)) state.balances[size] += count;
      return json(order);
    }
    const reverseMatch = path.match(/^movements\/(\d+)\/reverse\/$/);
    if (reverseMatch && method === 'POST') {
      calls.push({ apiPath, method, body: route.request().postDataJSON() });
      if (failures.reverse) return error('No pudimos revertir el consumo.', failures.reverse);
      state.movements.unshift({ id: 902, kind: 'reversal', quantity: 1, size: 'S', reason: route.request().postDataJSON().reason, created_at: '2026-11-12T00:00:00Z' });
      state.balances.S += 1;
      return json(state.movements[0]);
    }
    return null;
  });

  return { state, calls };
}
