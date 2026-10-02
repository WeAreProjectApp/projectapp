import { flushPromises, mount } from '@vue/test-utils'
import ProjectClientAccessPolicyEditor from '../../../components/projects/client-access/ProjectClientAccessPolicyEditor.vue'

global.useI18n = () => ({ t: (key) => key })

function matrix(siteUrl = false) {
  return {
    production: { site_url: siteUrl, admin_url: false, admin_username: false, admin_password: false },
    staging: { site_url: false, admin_url: false, admin_username: false, admin_password: false },
  }
}

function policy(overrides = {}) {
  return {
    version: 5,
    source_token: 'source-token-5',
    permissions: matrix(),
    effective_permissions: matrix(),
    available_fields: {
      production: { site_url: true, admin_url: true, admin_username: true, admin_password: false },
      staging: { site_url: false, admin_url: false, admin_username: false, admin_password: false },
    },
    ...overrides,
  }
}

function mountEditor(api) {
  return mount(ProjectClientAccessPolicyEditor, { props: { api, projectId: 42 } })
}

describe('ProjectClientAccessPolicyEditor', () => {
  it('disables a policy field without an available source', async () => {
    // Falla si el panel deja habilitar una fuente de acceso que el proyecto no posee.
    const api = {
      policy: jest.fn().mockResolvedValue(policy()),
      events: jest.fn().mockResolvedValue({ results: [], count: 0, page: 1 }),
    }
    const wrapper = mountEditor(api)
    await flushPromises()

    expect(wrapper.get('[data-testid="client-access-enable-production-admin_password"]').attributes('disabled')).toBe('')
    expect(wrapper.get('[data-testid="client-access-enable-production-site_url"]').attributes('disabled')).toBeUndefined()
  })

  it('saves a source-bound policy version', async () => {
    // Falla si una edición sobreescribe una política desactualizada o deja de ligar los grants a sus fuentes.
    const saved = policy({
      version: 6,
      effective_permissions: matrix(true),
      permissions: matrix(true),
    })
    const api = {
      policy: jest.fn().mockResolvedValue(policy()),
      updatePolicy: jest.fn().mockResolvedValue(saved),
      preview: jest.fn().mockResolvedValue({
        environments: [{
          environment: 'production',
          site_url: 'https://cliente.example',
          credential_actions: ['admin_password'],
          secret: 'never-render-this',
        }],
      }),
      events: jest.fn().mockResolvedValue({ results: [], count: 0, page: 1 }),
    }
    const wrapper = mountEditor(api)
    await flushPromises()

    await wrapper.get('[data-testid="client-access-enable-production-site_url"]').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(api.updatePolicy).toHaveBeenCalledWith({
      expected_version: 5,
      source_token: 'source-token-5',
      permissions: matrix(true),
    })
    expect(wrapper.get('[data-testid="client-access-preview"]').text()).toContain('https://cliente.example')
    expect(wrapper.get('[data-testid="client-access-preview"]').text()).toContain('projectClientAccess.admin_password')
    expect(wrapper.text()).not.toContain('never-render-this')
  })
})
