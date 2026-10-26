export const radarTypes = ['emails_failed', 'recurring_due', 'tasks_overdue', 'documents_overdue', 'proposals_stale'];
export const radarDestinations = {
  emails_failed: '/panel/emails?tab=history&email=42&radar=1',
  recurring_due: '/panel/accounting/recurring?recurring=42&radar=1',
  tasks_overdue: '/panel/tasks?task=42&radar=1',
  documents_overdue: '/panel/documents/42/edit?radar=1',
  proposals_stale: '/panel/proposals/42/edit?radar=1',
};
export const radarRecord = (type, id = 42) => ({
  id, type, title: `Pendiente ${type} ${id}`, recipient: 'cliente@example.test',
  client: 'ACME', assignee: 'Ana', priority: 'Alta', amount: '123000', currency: 'COP',
  sent_at: '2026-10-20T12:00:00Z', due_date: '2026-10-28', payment_method: 'T.C',
  error_message: 'No se pudo completar el envío de correo.', days_unopened: 12,
  eligible: true, can_resend: true, destination: radarDestinations[type],
});
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });
export function radarApi({ failList = false, missing = false, forbidden = false } = {}) {
  let listFailed = false;
  return async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/') return json({
      generated_at: '2026-10-26T12:00:00Z', finance: null,
      proposals: { pipeline_value: 0, pipeline_count: 0, total_proposals: 0, by_status: {} },
      operations: { tasks: {}, documents: {}, diagnostics: {}, emails: {}, hour_packages: {} },
      attention: radarTypes.map((type) => ({ type, severity: 'danger', count: 6, meta: {} })),
    });
    const detail = apiPath.match(/^panel\/dashboard\/attention\/([^/]+)\/42\/$/);
    if (detail) return json(missing ? { detail: 'Not found' } : forbidden ? { detail: 'Forbidden' } : radarRecord(detail[1]), missing ? 404 : forbidden ? 403 : 200);
    const list = apiPath.match(/^panel\/dashboard\/attention\/([^/]+)\/$/);
    if (list) {
      if (failList && !listFailed) { listFailed = true; return json({}, 503); }
      const page = Number(new URL(route.request().url()).searchParams.get('page') || 1);
      return json({ results: page === 1 ? Array.from({ length: 5 }, (_, n) => radarRecord(list[1], 42 + n)) : [radarRecord(list[1], 47)], total: 6, page, has_next: page === 1 });
    }
    if (apiPath === 'emails/history/') return json({ results: [{ ...radarRecord('emails_failed'), subject: radarRecord('emails_failed').title, status: 'failed', template_label: 'Manual', to_recipients: [{ email: 'cliente@example.test' }], attachments: [], copies: [], links: { content: [], template: [] }, metadata: {} }], total: 1, page: 1, has_next: false });
    if (apiPath === 'accounting/recurring/42/') return json({ id: 42, name: radarRecord('recurring_due').title, price: '123000', currency: 'COP', monthly_price: '123000', monthly_cop_cost: '123000', cop_equivalent: '123000', frequency: 'monthly', frequency_label: 'Mensual', is_active: true, category: 1, is_archived: false, payment_method: 'credit_card', payment_method_label: 'T.C' });
    if (apiPath === 'accounting/recurring-categories/') return json({ results: [{ id: 1, name: 'Servicios', order: 0 }] });
    if (apiPath === 'accounting/recurring/') return json({ results: [], meta: { usd_exchange_rate: 4000 } });
    if (apiPath === 'tasks/') {
      const board = new URL(route.request().url()).searchParams.get('board');
      return json(board === 'macro' ? { items: [] } : { todo: board === 'weekly' ? [{ id: 42, title: radarRecord('tasks_overdue').title, board_type: 'weekly', status: 'todo', priority: 'high' }] : [], in_progress: [], blocked: [], done: [] });
    }
    if (apiPath === 'documents/42/detail/') return json({ id: 42, title: radarRecord('documents_overdue').title, content_markdown: '# Cuenta de cobro', document_type_code: 'collection_account', commercial_status: 'issued', active_states: [], notes: [], is_generated_snapshot: false, language: 'es', text_formats: {} });
    if (apiPath === 'proposals/42/detail/') return json({ id: 42, uuid: '11111111-1111-4111-8111-111111111111', title: radarRecord('proposals_stale').title, client_name: 'ACME', client_email: 'cliente@example.test', status: 'sent', language: 'es', currency: 'COP', total_investment: '123000', sections: [], requirement_groups: [], is_active: true });
    return null;
  };
}
