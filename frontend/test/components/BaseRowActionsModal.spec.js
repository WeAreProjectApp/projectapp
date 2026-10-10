/**
 * Tests for BaseRowActionsModal: the menu behind a list row's three-dot
 * button. It takes the same entries as BaseActionMenu, closes, and only then
 * runs the chosen entry.
 */
import { flushPromises, mount } from '@vue/test-utils'
import BaseRowActionsModal from '~/components/base/BaseRowActionsModal.vue'
import { getPanelAction } from '~/config/panelActions'

const NuxtLink = {
  name: 'NuxtLink',
  props: ['to'],
  template: '<a class="nuxt-link" :href="to"><slot /></a>',
}

function mountModal(props = {}) {
  return mount(BaseRowActionsModal, {
    props: {
      open: true,
      title: 'Acceso a GoDaddy',
      subtitle: 'Listo para compartir',
      testid: 'secure-link-actions-modal',
      items: [],
      ...props,
    },
    global: {
      components: { NuxtLink },
      stubs: {
        BaseModal: {
          props: ['modelValue', 'kind', 'lockScroll', 'titleId'],
          emits: ['close'],
          template: '<div v-if="modelValue" :data-lock-scroll="String(lockScroll)"><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

describe('BaseRowActionsModal', () => {
  it('names the record and lists its entries in the order given', () => {
    const wrapper = mountModal({
      items: [
        { action: 'view', label: 'Detalle e historial', testid: 'secure-link-open-7' },
        { action: 'copy', label: 'Copiar enlace', testid: 'secure-link-copy-7' },
        { divider: true },
        { action: 'delete', label: 'Eliminar', danger: true, testid: 'secure-link-delete-7' },
      ],
    })
    const modal = wrapper.get('[data-testid="secure-link-actions-modal"]')

    expect(modal.text()).toContain('Acceso a GoDaddy')
    expect(modal.text()).toContain('Listo para compartir')
    expect(modal.findAll('li [data-testid]').map((entry) => entry.attributes('data-testid'))).toEqual([
      'secure-link-open-7',
      'secure-link-copy-7',
      'secure-link-delete-7',
    ])
    expect(modal.find('li[role="separator"]').exists()).toBe(true)
  })

  // Bug caught: opening the next dialog in the same flush as this close made
  // the two dialogs trade focus traps and scroll locks.
  it('closes before it runs the chosen entry', async () => {
    const calls = []
    const wrapper = mountModal({
      onClose: () => calls.push('close'),
      items: [{ action: 'delete', label: 'Eliminar', testid: 'row-delete', onClick: () => calls.push('run') }],
    })

    await wrapper.get('[data-testid="row-delete"]').trigger('click')
    await flushPromises()

    expect(calls).toEqual(['close', 'run'])
  })

  it('opens route entries in place and external entries in a new tab', async () => {
    const wrapper = mountModal({
      items: [
        { action: 'edit', label: 'Editar', to: '/panel/blog/3/edit', testid: 'blog-post-edit-3' },
        { action: 'open-external', label: 'Ver en LinkedIn', href: 'https://www.linkedin.com/feed/update/1', testid: 'linkedin-post-open-1' },
      ],
    })

    const route = wrapper.get('[data-testid="blog-post-edit-3"]')
    expect(route.classes()).toContain('nuxt-link')
    expect(route.attributes('href')).toBe('/panel/blog/3/edit')

    const external = wrapper.get('[data-testid="linkedin-post-open-1"]')
    expect(external.element.tagName).toBe('A')
    expect(external.attributes('target')).toBe('_blank')
    expect(external.attributes('rel')).toBe('noopener noreferrer')

    await route.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('keeps a disabled entry inert and explains why', async () => {
    const onClick = jest.fn()
    const wrapper = mountModal({
      items: [
        {
          action: 'publish',
          label: 'Publicando…',
          disabled: true,
          description: 'La publicación ya está en curso.',
          testid: 'linkedin-post-publish-1',
          onClick,
        },
        { action: 'edit', label: 'Editar', to: '/panel/blog/3/edit', disabled: true, testid: 'blog-post-edit-3' },
      ],
    })
    const publish = wrapper.get('[data-testid="linkedin-post-publish-1"]')

    await publish.trigger('click')
    await flushPromises()

    expect(publish.attributes('disabled')).toBeDefined()
    expect(wrapper.get(`#${publish.attributes('aria-describedby')}`).text()).toBe('La publicación ya está en curso.')
    expect(onClick).not.toHaveBeenCalled()
    expect(wrapper.emitted('close')).toBeUndefined()
    // A dead link would still navigate: a disabled route entry is a button.
    expect(wrapper.get('[data-testid="blog-post-edit-3"]').element.tagName).toBe('BUTTON')
  })

  it('falls back to the registered label of the entry action', () => {
    const wrapper = mountModal({ items: [{ action: 'delete', testid: 'row-delete' }] })

    expect(wrapper.get('[data-testid="row-delete"]').text()).toBe(getPanelAction('delete').label)
  })

  it('closes from its Cerrar button without running an entry', async () => {
    const onClick = jest.fn()
    const wrapper = mountModal({ items: [{ action: 'copy', label: 'Copiar enlace', onClick }] })

    await wrapper.get('[data-testid="base-modal-actions"] button').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(onClick).not.toHaveBeenCalled()
  })

  // Bug caught: owners clear the row on close, which blanked the menu during its fade-out.
  it('keeps showing the closed row while the modal fades out', async () => {
    const wrapper = mount(BaseRowActionsModal, {
      props: {
        open: true,
        title: 'Acceso a GoDaddy',
        testid: 'secure-link-actions-modal',
        items: [{ action: 'copy', label: 'Copiar enlace', testid: 'secure-link-copy-7' }],
      },
      global: {
        components: { NuxtLink },
        // The real modal keeps its content mounted until the leave transition ends.
        stubs: { BaseModal: { template: '<div><slot /><slot name="footer" /></div>' } },
      },
    })

    await wrapper.setProps({ open: false, title: '', items: [] })

    expect(wrapper.text()).toContain('Acceso a GoDaddy')
    expect(wrapper.find('[data-testid="secure-link-copy-7"]').exists()).toBe(true)
  })

  it('leaves the page scroll lock to the modal it opens above', () => {
    const wrapper = mountModal({ lockScroll: false })

    expect(wrapper.get('[data-lock-scroll]').attributes('data-lock-scroll')).toBe('false')
  })
})
