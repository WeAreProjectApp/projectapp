import { flushPromises, mount } from '@vue/test-utils'
import ProjectIdeaCollectionCard from '../../../components/projects/ideas/ProjectIdeaCollectionCard.vue'

global.useI18n = () => ({ t: (key) => key })

function mountCard(api) {
  return mount(ProjectIdeaCollectionCard, {
    props: { collection: { id: 7, title: 'Alternativas futuras', item_count: 1 }, api },
    global: { stubs: { NuxtLink: { template: '<a><slot /></a>' } } },
  })
}

describe('ProjectIdeaCollectionCard', () => {
  it('loads the frozen texts only on request', async () => {
    const api = { collection: jest.fn().mockResolvedValue({ id: 7, items: [{ author: 'Cliente', text: 'Texto seleccionado' }] }) }
    const wrapper = mountCard(api)
    expect(api.collection).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="idea-collection-open"]').trigger('click')
    await flushPromises()
    expect(api.collection).toHaveBeenCalledWith(7)
    expect(wrapper.text()).toContain('Cliente: Texto seleccionado')
    wrapper.unmount()
  })

  it('discards a delayed snapshot from another collection', async () => {
    let resolve
    const api = { collection: jest.fn(() => new Promise((done) => { resolve = done })) }
    const wrapper = mountCard(api)
    await wrapper.get('[data-testid="idea-collection-open"]').trigger('click')
    await wrapper.setProps({ collection: { id: 8, title: 'Otra recopilación', item_count: 1 } })
    resolve({ id: 7, items: [{ author: 'Cliente anterior', text: 'Texto de otra colección' }] })
    await flushPromises()
    expect(wrapper.text()).toContain('Otra recopilación')
    expect(wrapper.text()).not.toContain('Texto de otra colección')
    wrapper.unmount()
  })
})
