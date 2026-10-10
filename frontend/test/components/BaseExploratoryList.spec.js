import { mount } from '@vue/test-utils'

import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue'

const rows = [{ id: 7, name: 'Proyecto Aurora', status: 'Activo', internal: 'Privado' }]
const columns = [
  { key: 'name', label: 'Proyecto', mobile: 'primary' },
  { key: 'status', label: 'Estado', mobile: 'secondary' },
  { key: 'internal', label: 'Interno', mobile: 'hidden' },
]

function mockViewport(mobile) {
  window.matchMedia = jest.fn().mockReturnValue({
    matches: mobile,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  })
}

async function mountList(mobile, { props = {}, slots = {} } = {}) {
  mockViewport(mobile)
  const wrapper = mount(BaseExploratoryList, {
    props: { columns, rows, cardTestIdPrefix: 'project', ...props },
    slots,
  })
  await wrapper.vm.$nextTick()
  return wrapper
}

const menuSlots = {
  'row-select': '<input type="checkbox" aria-label="Seleccionar" />',
  'row-actions': '<button type="button" data-testid="row-menu">Menú</button>',
}

function mountMenuStart(mobile, props = {}) {
  return mountList(mobile, {
    props: { rowActionsLayout: 'menu-start', showSelection: true, interactiveRows: true, ...props },
    slots: menuSlots,
  })
}

describe('BaseExploratoryList', () => {
  afterEach(() => { delete window.matchMedia })

  it('renders only the wide table outside the compact and portrait profiles', async () => {
    const wrapper = await mountList(false)

    expect(wrapper.find('table').exists()).toBe(true)
    expect(wrapper.find('article').exists()).toBe(false)
    expect(wrapper.text()).toContain('Privado')
  })

  it('renders only one stacked card on compact and portrait screens', async () => {
    const wrapper = await mountList(true)

    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.findAll('article')).toHaveLength(1)
    expect(wrapper.get('[data-testid="project-7"]').text()).toContain('Proyecto Aurora')
  })

  it('keeps explicit mobile details and omits hidden fields from the card', async () => {
    const wrapper = await mountList(true)
    const card = wrapper.get('[data-testid="project-7"]')

    expect(card.text()).toContain('Estado')
    expect(card.text()).toContain('Activo')
    expect(card.text()).not.toContain('Privado')
  })

  it('contains unbroken values in both table and card representations', async () => {
    const wide = await mountList(false)
    const wideContent = wide.get('tbody td > div')
    expect(wideContent.classes()).toContain('[overflow-wrap:anywhere]')

    wide.unmount()
    const compact = await mountList(true)
    const cardContent = compact.get('[data-testid="project-7"] .font-medium')
    expect(cardContent.classes()).toContain('[overflow-wrap:anywhere]')
  })

  it('orders the selection, the menu and then the data in menu-start tables', async () => {
    const wrapper = await mountMenuStart(false)

    const headers = wrapper.get('thead tr').findAll('th')
    expect(headers[1].attributes('data-testid')).toBe('project-actions-header')
    expect(headers[2].text()).toBe('Proyecto')
    expect(headers.at(-1).text()).toBe('Interno')

    const cells = wrapper.get('[data-testid="project-7"]').findAll('td')
    expect(cells[0].find('input[type="checkbox"]').exists()).toBe(true)
    expect(cells[1].attributes('data-testid')).toBe('project-actions-cell-7')
    expect(cells[1].find('[data-testid="row-menu"]').exists()).toBe(true)
    expect(cells[2].text()).toContain('Proyecto Aurora')
  })

  it('renders the menu header blank and on the fixed 56 px track', async () => {
    const wrapper = await mountMenuStart(false)
    const header = wrapper.get('[data-testid="project-actions-header"]')

    expect(header.attributes('aria-label')).toBe('Acciones')
    expect(header.text()).toBe('')
    expect(header.element.style.width).toBe('3.5rem')
    expect(wrapper.get('[data-testid="project-actions-cell-7"]').element.style.width).toBe('3.5rem')
  })

  it('keeps the menu out of row activation on tables and cards', async () => {
    const wide = await mountMenuStart(false)
    await wide.get('[data-testid="row-menu"]').trigger('click')
    await wide.get('[data-testid="project-actions-cell-7"]').trigger('auxclick', { button: 1 })
    expect(wide.emitted('row-click')).toBeUndefined()
    expect(wide.emitted('row-auxclick')).toBeUndefined()

    wide.unmount()
    const compact = await mountMenuStart(true)
    await compact.get('[data-testid="row-menu"]').trigger('click')
    await compact.get('[data-testid="row-menu"]').trigger('keydown', { key: 'Enter' })
    expect(compact.emitted('row-click')).toBeUndefined()
  })

  it('leads each mobile card with the menu and drops the card footer', async () => {
    const wrapper = await mountMenuStart(true)
    const card = wrapper.get('[data-testid="project-7"]')
    const header = card.get('div')

    expect(header.get('[data-testid="project-actions-cell-7"]').find('[data-testid="row-menu"]').exists()).toBe(true)
    expect(card.html().indexOf('row-menu')).toBeLessThan(card.html().indexOf('Proyecto Aurora'))
    expect(card.findAll('[data-testid="row-menu"]')).toHaveLength(1)
  })

  it('keeps the labeled trailing column by default', async () => {
    const wrapper = await mountList(false, { slots: { 'row-actions': menuSlots['row-actions'] } })

    expect(wrapper.find('[data-testid="project-actions-header"]').exists()).toBe(false)
    expect(wrapper.get('thead tr').findAll('th').at(-1).text()).toBe('Acciones')
    expect(wrapper.get('[data-testid="project-7"]').findAll('td').at(-1).find('[data-testid="row-menu"]').exists()).toBe(true)
  })
})
