import { mockApi } from './api.js';

export const adminAuth = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };
export const pricingSettings = {
  default_view_mode: 'table', xs_price_cop: '50000', s_price_cop: '125000', m_price_cop: '360000',
  foreign_multiplier: '1.4', usa_multiplier: '1.8', exchange_rate: '4000',
  alliance_xs_count: 4, alliance_s_count: 2, alliance_m_count: 1,
};
export const colombiaPackages = [
  { id: 1, pricing_model: 'requirements', nationality: 'COL', currency: 'COP', name_es: 'Ágil', name_en: 'Agile', note_es: 'Ajustes acotados.', note_en: 'Bounded adjustments.', xs_count: 30, s_count: 0, m_count: 0, validity_months: 12, reference_price: '1500000', discount_percent: 10, savings: '150000', total_price: '1350000', is_active: true, order: 1 },
  { id: 2, pricing_model: 'requirements', nationality: 'COL', currency: 'COP', name_es: 'Pro', name_en: 'Pro', note_es: 'Evolución continua.', note_en: 'Continuous evolution.', xs_count: 30, s_count: 20, m_count: 0, validity_months: 12, reference_price: '4000000', discount_percent: 15, savings: '600000', total_price: '3400000', is_active: true, order: 2 },
  { id: 3, pricing_model: 'requirements', nationality: 'COL', currency: 'COP', name_es: 'Premium', name_en: 'Premium', note_es: 'Mayor ahorro.', note_en: 'Highest savings.', xs_count: 30, s_count: 20, m_count: 10, validity_months: 12, reference_price: '7600000', discount_percent: 25, savings: '1900000', total_price: '5700000', is_active: true, order: 3 },
];
export const foreignPackages = [
  { ...colombiaPackages[0], id: 4, nationality: 'EXT', currency: 'USD', name_es: 'Ágil exterior', name_en: 'Foreign Agile', reference_price: '525.00', total_price: '472.50' },
];

export async function mockRequirementPackages(page, { settings = pricingSettings, col = colombiaPackages, afterSettingsCol, ext = foreignPackages, usa = [], updateStatus = 200, updateBody, packageUpdateBody, createStatus = 201, createBody, detail = colombiaPackages[0], deleteStatus = 204, restoreStatus = 200, capture = {} } = {}) {
  let activeCol = col;
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return adminAuth;
    if (apiPath === 'hour-packages/admin/settings/' && method === 'GET') return { status: 200, contentType: 'application/json', body: JSON.stringify(settings) };
    if (apiPath === 'hour-packages/admin/settings/update/' && method === 'PATCH') {
      capture.settings = route.request().postDataJSON();
      if (updateStatus < 400 && afterSettingsCol) activeCol = afterSettingsCol;
      return { status: updateStatus, contentType: 'application/json', body: JSON.stringify(updateBody || { ...settings, ...capture.settings }) };
    }
    if (apiPath === 'hour-packages/admin/' && method === 'GET') {
      const market = new URL(route.request().url()).searchParams.get('nationality');
      return { status: 200, contentType: 'application/json', body: JSON.stringify(market === 'EXT' ? ext : market === 'USA' ? usa : activeCol) };
    }
    if (apiPath === 'hour-packages/admin/create/' && method === 'POST') {
      capture.create = route.request().postDataJSON();
      return { status: createStatus, contentType: 'application/json', body: JSON.stringify(createBody || { ...detail, ...capture.create, id: 10 }) };
    }
    if (apiPath === `hour-packages/admin/${detail.id}/detail/` && method === 'GET') return { status: 200, contentType: 'application/json', body: JSON.stringify(detail) };
    if (apiPath === `hour-packages/admin/${detail.id}/update/` && method === 'PATCH') {
      capture.update = route.request().postDataJSON();
      return { status: updateStatus, contentType: 'application/json', body: JSON.stringify(packageUpdateBody || { ...detail, ...capture.update }) };
    }
    if (apiPath === 'hour-packages/admin/1/delete/' && method === 'DELETE') {
      capture.deleted = true;
      return { status: deleteStatus, contentType: 'application/json', body: '' };
    }
    if (apiPath === 'hour-packages/admin/restore-defaults/' && method === 'POST') {
      capture.restore = route.request().postDataJSON();
      activeCol = colombiaPackages;
      return { status: restoreStatus, contentType: 'application/json', body: JSON.stringify(activeCol) };
    }
    return null;
  });
  return capture;
}
