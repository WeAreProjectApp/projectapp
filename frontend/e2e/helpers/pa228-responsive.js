import { expect } from './test.js';
import { mockApi } from './api.js';
import { setAuthLocalStorage } from './auth.js';
import { waitForNuxtApp } from './navigation.js';
import { PANEL_VIEWPORTS } from '../../config/responsive.js';

export const moduleTitle = 'Gestión integral de operaciones comerciales con automatización de procesos y trazabilidad de clientes';
export const longConcept = 'QA RESPONSIVE — Implementación de plataforma con seguimiento financiero y conciliación de proyectos extensos';
export const longAmount = '$987.654.321.012 COP';
export const sources = Array.from({ length: 3 }, (_, index) => ({
  name: `Fuente ficticia ${index + 1}`,
  url: `https://example.test/investigacion/${index + 1}/documentacion-con-referencias-extensas?origen=qa-responsive`,
}));
export const funnelSteps = Array.from({ length: 12 }, (_, index) => ({
  section_type: `section-${index}`,
  section_title: `${index + 1}. Una experiencia visual que enamora con detalles completos del proyecto`,
  reached_count: 120 - index,
  drop_off_percent: index,
  in_executive_mode: index % 2 === 0,
}));
export const technicalSteps = [{
  section_type: 'technical_document_public',
  subsection_key: 'architecture',
  section_title: 'Arquitectura del sistema con integraciones comerciales y trazabilidad completa',
  reached_count: 42,
  drop_off_percent: 5,
}, {
  section_type: 'technical_document_public',
  subsection_key: 'quality',
  section_title: 'Calidad y monitoreo continuo de todos los procesos técnicos de la plataforma',
  reached_count: 0,
  drop_off_percent: 0,
}];

const proposal = {
  id: 1, uuid: 'pa228-proposal', title: 'Propuesta ficticia PA-228',
  client_name: 'Cliente ficticio responsive', client_email: 'qa@example.test',
  status: 'draft', language: 'es', currency: 'COP', total_investment: 5000000,
  sections: [{
    id: 11, section_type: 'investment', title: 'Inversión', is_enabled: true, order: 1,
    content_json: { modules: [{ id: 'pa228-module', title: moduleTitle, price: 5000000 }] },
  }, {
    id: 12, section_type: 'technical_document', title: 'Detalle técnico', is_enabled: true, order: 2,
    content_json: { purpose: 'Comprobar la distribución del editor.', epics: [] },
  }],
};

const income = {
  id: 979, concept: longConcept, notes: 'QA RESPONSIVE',
  kind: 'expected', kind_label: 'Esperado', origin: 'manual',
  client: 1, client_name: 'Cliente ficticio con nombre comercial muy extenso para validar el ajuste de su fila',
  project: 1, project_name: 'ProyectoDeIntegraciónConIdentificadorExtensoSinEspaciosParaValidarElAjuste',
  total_amount: '987654321012.00', paid_amount: '0.00', pending_amount: '987654321012.00',
  payment_status: 'pending', payment_status_label: 'Pendiente',
  collection_confidence: 'high', is_receivable_candidate: true,
  period_date: '2026-11-01', period_label: 'Noviembre 2026',
};

const recurringRows = Array.from({ length: 31 }, (_, index) => ({
  id: index + 1, name: `Pago ficticio del día ${index + 1}`, category: 1,
  category_name: 'Operación', price: String((index + 1) * 1000), currency: 'COP',
  monthly_price: String((index + 1) * 1000), monthly_cop_cost: String((index + 1) * 1000),
  billing_day: index + 1, frequency: 'monthly', frequency_label: 'Mensual',
  is_active: true, is_archived: false, cost_type: 'fixed', payment_method: 'cash',
}));

const proposals = {
  pipeline_value: 45000000, pipeline_count: 3, conversion_rate: 60, total_proposals: 12,
  by_status: { draft: 2, sent: 3, accepted: 4, rejected: 3 }, recent: [],
  monthly_trend: Array.from({ length: 6 }, (_, index) => ({
    month: `2026-${String(index + 5).padStart(2, '0')}-01`, sent: 12 + index, accepted: 4, rejected: 2,
  })),
};
const dashboard = {
  finance: { year: 2026, liquid_utility: 80000000, expected_utility: 110000000, monthly: [] },
  proposals, attention: [],
  additional_modules: { active_module_count: 2, active_share_count: 1, unopened_active_share_count: 0 },
  operations: { tasks: { open: 0, overdue: 0 }, documents: { by_status: {} }, diagnostics: { by_status: {} }, emails: { total_30d: 0 }, hour_packages: { active_count: 0 } },
};
const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

export async function setupPa228(page) {
  await page.clock.install({ time: new Date('2026-11-06T15:00:00Z') });
  await setAuthLocalStorage(page, {
    token: 'pa228-fixture-only',
    userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
  });
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'qa-responsive', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/') return json(dashboard);
    if (apiPath === 'proposals/dashboard/') return json(proposals);
    if (apiPath === 'proposals/1/' || apiPath === 'proposals/1/detail/') return json(proposal);
    if (apiPath === 'proposals/1/analytics/') return json({
      total_views: 120, unique_sessions: 120, sections: [], skipped_sections: [],
      funnel: [...funnelSteps, ...technicalSteps], sessions: [], timeline: [],
      daily_views: [], section_views: [], device_breakdown: {},
    });
    if (apiPath === 'proposals/1/email-preview/' && method === 'POST') {
      const { template_key: key } = route.request().postDataJSON();
      return json(`<p>Vista previa ficticia: ${key}</p>`);
    }
    if (apiPath.startsWith('blog/admin/')) return json({
      id: 1, title_es: 'Post ficticio PA-228', title_en: 'PA-228 fixture post',
      slug: 'pa228-fixture', content_es: '<p>Contenido ficticio.</p>', sources,
      category: 'ai', is_published: false, calendar_status: 'draft', date: '2026-11-06',
    });
    if (apiPath === 'accounting/settings/') return json({ income_default_view_mode: 'grouped', recurring_default_view_mode: 'grouped' });
    if (apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (apiPath === 'accounting/incomes/') return json({
      results: [income, { ...income, id: 980, concept: 'QA RESPONSIVE — Ingreso habitual', total_amount: '1250000.00', pending_amount: '1250000.00' }],
      meta: { expected_total: '987655571012.00', liquid_total: '522238000.00', lost_total: '900000.00', current_month_liquid: '97542000.00', received_pct: 50 },
    });
    if (apiPath === 'accounting/recurring/') return json({ results: recurringRows, meta: {} });
    if (apiPath === 'accounting/recurring-categories/') return json([{ id: 1, name: 'Operación', order: 0 }]);
    if (apiPath.startsWith('accounting/')) return json({ results: [], meta: {} });
    return null;
  });
}

/** Direct opening is required to compare initial layout with the same mounted view after resizing. */
export async function openPa228(page, route) {
  await setupPa228(page);
  // quality: allow-deep-link (PA-228 explicitly compares direct loads with desktop-to-mobile resizing without a reload)
  await page.goto(`/es-co${route}`, { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
}

export async function resizeFromDesktop(page, profile) {
  await page.setViewportSize(PANEL_VIEWPORTS.desktop);
  await page.setViewportSize(PANEL_VIEWPORTS[profile]);
}

/** Checks the element's real box, including ancestors that could clip it. */
export async function expectFitsHorizontally(locator) {
  await expect.poll(() => locator.evaluateAll((elements) => elements.map((element) => {
    const rect = element.getBoundingClientRect();
    const viewportWidth = document.documentElement.clientWidth;
    return rect.width > 0 && rect.left >= -1 && rect.right <= viewportWidth + 1;
  }))).not.toContain(false);
}

/** DOM text alone would pass with CSS ellipsis; measure the rendered fragments too. */
export async function expectReadable(locator) {
  await expectFitsHorizontally(locator);
  await expect.poll(() => locator.evaluateAll((elements) => elements.map((element) => {
    const box = element.getBoundingClientRect();
    const range = document.createRange();
    range.selectNodeContents(element);
    return [...range.getClientRects()].every((rect) => rect.left >= box.left - 1 && rect.right <= box.right + 1)
      && element.scrollWidth <= element.clientWidth + 1;
  }))).not.toContain(false);
}

export async function expectPageFits(page) {
  await expect.poll(() => page.evaluate(() => (
    Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
      - document.documentElement.clientWidth
  ))).toBeLessThanOrEqual(1);
}

export async function selectCalendar(page, profile) {
  const dialog = page.getByRole('dialog');
  if (['compact', 'portrait'].includes(profile)) {
    await dialog.getByRole('combobox', { name: 'Secciones', exact: true }).selectOption('calendar');
  } else {
    await dialog.getByRole('tab', { name: 'Calendario', exact: true }).click();
  }
}
