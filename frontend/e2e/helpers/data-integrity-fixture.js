const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const completedAt = '2026-11-04T08:30:00Z';

export function integrityFinding(overrides = {}) {
  return {
    id: 91,
    fingerprint: 'dc9-document-without-folder-91',
    rule_id: 'DC9',
    title: 'Documento sin carpeta',
    message: 'El documento Acta de entrega no tiene una carpeta válida.',
    domain: 'documents',
    severity: 'high',
    resolution: { reason: 'Mover el documento a una carpeta activa.' },
    subjects: [{ model: 'content.document', id: 91, label: 'Acta de entrega' }],
    inputs: {
      folder_id: {
        label: 'Carpeta de destino',
        options: [{ value: 51, label: 'Actas · 51' }],
      },
    },
    suggestion: { folder_id: 51 },
    fixable_kinds: ['relink'],
    is_present: true,
    is_accepted: false,
    ...overrides,
  };
}

function dashboardSummary() {
  return {
    generated_at: completedAt,
    finance: null,
    proposals: { pipeline_value: 0, pipeline_count: 0, total_proposals: 0, by_status: {} },
    operations: { tasks: {}, documents: {}, diagnostics: {}, emails: {}, hour_packages: {} },
    attention: [],
  };
}

function visibleFindings(state, route) {
  const query = new URL(route.request().url()).searchParams;
  const status = query.get('status') || 'pending';
  const fingerprint = query.get('fingerprint');
  return state.findings.filter((finding) => {
    if (fingerprint && finding.fingerprint !== fingerprint) return false;
    if (status === 'all') return true;
    if (status === 'accepted') return finding.is_present && finding.is_accepted;
    if (status === 'resolved') return !finding.is_present;
    return finding.is_present && !finding.is_accepted;
  });
}

/**
 * Stateful API fixture for the data-integrity panel. The panel reloads after
 * each decision, so its responses deliberately reflect prior UI mutations.
 */
export function buildDataIntegrityApi(options = {}) {
  const state = {
    findings: [integrityFinding(options.finding)],
    scan: {
      id: 301,
      status: options.scanFailure ? 'failed' : 'completed',
      started_at: completedAt,
      finished_at: completedAt,
      coverage: { evaluated_rules: ['DC9'], skipped_rules: [] },
    },
    lastCompleted: options.scanFailure ? {
      id: 300,
      status: 'completed',
      started_at: '2026-11-03T08:30:00Z',
      finished_at: '2026-11-03T08:31:00Z',
      coverage: { evaluated_rules: ['DC9'], skipped_rules: [] },
    } : null,
    operations: [{
      operation_id: 701,
      kind: 'apply',
      reason: 'Corrección anterior',
      actor: 'admin@example.test',
      created_at: completedAt,
      reverted_by: null,
    }],
    reviews: [],
    calls: { scans: [], previews: [], applies: [], reviews: [], undos: [] },
  };

  const handler = async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/') return json(dashboardSummary());
    if (apiPath === 'document-folders/?scope=active' || apiPath === 'document-folders/') {
      return json([{ id: 51, name: 'Actas', is_archived: false, is_system_managed: false }]);
    }
    if (apiPath === 'data-integrity/findings/' && method === 'GET') {
      const results = visibleFindings(state, route);
      return json({ results, count: results.length, page: 1, pages: 1 });
    }
    if (apiPath === 'data-integrity/scans/' && method === 'GET') {
      return json({
        results: state.lastCompleted ? [state.scan, state.lastCompleted] : [state.scan],
        last_completed: state.lastCompleted || (state.scan.status === 'completed' ? state.scan : null),
      });
    }
    if (apiPath === 'data-integrity/scans/' && method === 'POST') {
      state.calls.scans.push(route.request().postDataJSON());
      return json({ id: state.scan.id, status: state.scan.status });
    }
    if (apiPath === `data-integrity/scans/${state.scan.id}/` && method === 'GET') return json(state.scan);
    if (apiPath === 'data-integrity/operations/' && method === 'GET') {
      return json({ results: state.operations, count: state.operations.length, page: 1, pages: 1 });
    }
    if (apiPath === 'data-integrity/reviews/' && method === 'GET') return json({ results: state.reviews });
    if (apiPath === 'data-integrity/fixes/preview/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      state.calls.previews.push(payload);
      if (options.blockedPreview) {
        return json({ impact_hash: 'blocked-impact', blocked: true, blockers: [{ message: 'El documento fue archivado y no puede moverse.' }], steps: [] });
      }
      return json({
        impact_hash: 'fresh-impact',
        blocked: false,
        blockers: [],
        steps: [{
          fingerprint: state.findings[0].fingerprint,
          changes: [{ label: 'Carpeta', before: 'Sin carpeta', after: 'Actas · 51' }],
          subjects: state.findings[0].subjects,
        }],
      });
    }
    if (apiPath === 'data-integrity/fixes/apply/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      state.calls.applies.push(payload);
      if (options.applyStatus) return json({ detail: 'La vista previa ya no coincide con los datos actuales.' }, options.applyStatus);
      state.findings[0].is_present = false;
      state.operations.unshift({
        operation_id: 702,
        kind: 'apply',
        reason: payload.reason,
        actor: 'admin@example.test',
        created_at: completedAt,
        reverted_by: null,
      });
      return json({ operation_id: 702 });
    }
    if (apiPath === 'data-integrity/reviews/apply/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      state.calls.reviews.push(payload);
      if (options.reviewStatus) return json({ detail: 'La decisión fue modificada por otra persona.' }, options.reviewStatus);
      state.findings[0].is_accepted = payload.action === 'accept';
      state.reviews.unshift({
        id: state.reviews.length + 1,
        action: payload.action,
        reason: payload.reason,
        actor: 'admin@example.test',
        created_at: completedAt,
      });
      return json({ action: payload.action });
    }
    if (apiPath === 'data-integrity/operations/701/undo/' && method === 'GET') {
      if (options.undoBlocked) return json({ impact_hash: 'blocked-undo', blocked: true, blockers: [{ message: 'Hay cambios posteriores que impiden deshacer.' }], steps: [] });
      return json({
        impact_hash: 'undo-impact',
        blocked: false,
        blockers: [],
        steps: [{ changes: [{ label: 'Carpeta', before: 'Actas · 51', after: 'Sin carpeta' }], subjects: state.findings[0].subjects }],
      });
    }
    if (apiPath === 'data-integrity/operations/701/undo/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      state.calls.undos.push(payload);
      if (options.undoStatus) return json({ detail: 'La operación ya fue revertida.' }, options.undoStatus);
      state.operations[0].reverted_by = 703;
      state.operations.unshift({ operation_id: 703, kind: 'undo', reason: payload.reason, actor: 'admin@example.test', created_at: completedAt });
      return json({ operation_id: 703 });
    }
    return null;
  };

  return { state, handler };
}
