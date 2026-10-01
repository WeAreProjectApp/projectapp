import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import IssueHistory from '../../../../components/platform/issues/IssueHistory.vue'

const labels = {
  'platformIssues.status.resolved': 'Resuelto por equipo',
  'platformIssues.scope.within_scope': 'Dentro del alcance',
  'platformIssues.scope.outside_scope': 'Fuera del alcance',
  'platformIssues.scope.indeterminate': 'Indeterminado',
  'platformIssues.original': 'Contexto original',
  'platformIssues.responses': 'Respuestas',
  'platformIssues.history': 'Historial',
}

describe('IssueHistory', () => {
  beforeEach(() => {
    global.useI18n = () => ({ t: (key) => labels[key] || key, locale: ref('en-US') })
  })

  afterEach(() => {
    delete global.useI18n
  })

  it('shows the three public scope labels without rendering malformed private evidence', () => {
    // Falla si el historial expone citas o contexto privado que el serializer no debía entregar.
    const wrapper = mount(IssueHistory, {
      props: {
        ticket: {
          origin_context: {
            origin_kind: 'published',
            contract_title: 'Contrato público',
            publication_round: 3,
            requirement_version: 2,
            private_context_note: 'No mostrar contexto interno.',
          },
          responses: [
            {
              id: 1, actor_name: 'Equipo', created_at: '2026-10-01T12:00:00Z', status: 'resolved',
              scope_result: 'within_scope', message: 'Se corrigió el defecto.', attachments: [],
              review_evidence: { private_citation: 'Cita privada de contrato.' },
            },
            {
              id: 2, actor_name: 'Equipo', created_at: '2026-10-01T12:01:00Z', status: 'resolved',
              scope_result: 'outside_scope', message: 'Requiere solicitud de cambio.', attachments: [],
              review_evidence: { private_citation: 'Cita privada de ampliación.' },
            },
            {
              id: 3, actor_name: 'Equipo', created_at: '2026-10-01T12:02:00Z', status: 'resolved',
              scope_result: 'indeterminate', message: 'No hay contrato aplicable.', attachments: [],
              review_evidence: { private_citation: 'Cita privada indeterminada.' },
            },
          ],
          history: [],
        },
      },
    })

    expect(wrapper.findAll('[data-testid="issue-review-evidence"]').map((item) => item.text())).toEqual([
      'Resuelto por equipo · Dentro del alcance',
      'Resuelto por equipo · Fuera del alcance',
      'Resuelto por equipo · Indeterminado',
    ])
    expect(wrapper.text()).not.toContain('No mostrar contexto interno.')
    expect(wrapper.text()).not.toContain('Cita privada de contrato.')
    expect(wrapper.text()).not.toContain('Cita privada de ampliación.')
    expect(wrapper.text()).not.toContain('Cita privada indeterminada.')
  })
})
