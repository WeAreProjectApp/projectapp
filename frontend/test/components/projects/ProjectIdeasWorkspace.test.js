import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ProjectIdeasWorkspace from '../../../components/projects/ideas/ProjectIdeasWorkspace.vue'

global.useI18n = () => ({ t: (key) => key })

function createApi(overrides = {}) {
  return {
    list: jest.fn().mockResolvedValue({ results: [], count: 0, page: 1 }),
    create: jest.fn().mockResolvedValue({ id: 1, text: 'Nueva idea' }),
    edit: jest.fn(),
    archive: jest.fn(),
    restore: jest.fn(),
    revisions: jest.fn(),
    collections: jest.fn(),
    collect: jest.fn(),
    collection: jest.fn(),
    ...overrides,
  }
}

function mountWorkspace(props = {}) {
  setActivePinia(createPinia())
  return mount(ProjectIdeasWorkspace, {
    props: {
      projectId: 42,
      api: createApi(),
      isAdmin: false,
      canWrite: true,
      ...props,
    },
    global: {
      stubs: {
        ProjectIdeaHistory: true,
        ProjectIdeaCollectionBuilder: true,
      },
    },
  })
}

describe('ProjectIdeasWorkspace', () => {
  it('hides writing controls for an impersonated project session', async () => {
    // Falla si una sesión suplantada recupera controles de creación o edición desde la interfaz.
    const wrapper = mountWorkspace({
      canWrite: false,
      api: createApi({ list: jest.fn().mockResolvedValue({
        results: [{ id: 7, text: 'Idea existente', can_edit: true, revision_number: 1, created_at: '2026-10-01T12:00:00Z' }],
        count: 1,
        page: 1,
      }) }),
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="project-idea-text"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('projectIdeas.edit')
  })

  it('keeps the idea draft after its creation request fails', async () => {
    // Falla si un error de red borra una sugerencia que el cliente todavía necesita reenviar.
    const api = createApi({
      create: jest.fn().mockRejectedValue({ response: { data: { detail: 'No se pudo guardar' } } }),
    })
    const wrapper = mountWorkspace({ api })
    await flushPromises()

    const textarea = wrapper.get('[data-testid="project-idea-text"]')
    await textarea.setValue('Mantener este borrador')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.create).toHaveBeenCalledWith(expect.objectContaining({ text: 'Mantener este borrador' }))
    expect(wrapper.get('[data-testid="project-idea-text"]').element.value).toBe('Mantener este borrador')
    expect(wrapper.get('[role="alert"]').get('p').text()).toBe('No se pudo guardar')
  })
})
