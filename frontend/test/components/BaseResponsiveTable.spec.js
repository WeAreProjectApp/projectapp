import { mount } from '@vue/test-utils'

import BaseResponsiveTable from '~/components/base/BaseResponsiveTable.vue'
import { formatMoney } from '~/utils/formatMoney'

const rows = [{
  id: 1,
  name: 'Proyecto Aurora',
  owner: 'María Gómez',
  amount: 1250000,
  internal: 'No mostrar',
  status: 'Activo',
}]

const columns = [
  {
    key: 'name',
    label: 'Proyecto',
    size: 'name',
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'owner',
    label: 'Responsable',
    responsive: { compact: 'group', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'amount',
    label: 'Valor',
    format: 'money',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'internal',
    label: 'Interno',
    responsive: { compact: 'hide', portrait: 'hide', landscape: 'hide' },
  },
  {
    key: 'status',
    label: 'Estado',
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
]

function mountTable(props = {}) {
  return mount(BaseResponsiveTable, {
    props: { columns, rows, showActions: false, ...props },
  })
}

const resizableColumns = columns.map((column, index) => ({
  ...column,
  columnWidth: index === 0
    ? { min: 160, default: 240, max: 400, resizable: true }
    : { min: 96, default: 96, max: 96, fixed: true },
}))

describe('BaseResponsiveTable', () => {
  beforeEach(() => window.localStorage.clear())

  it('keeps, groups and hides compact columns from each explicit policy', () => {
    const wrapper = mountTable()
    const headers = wrapper.findAll('th')

    expect(headers[0].classes()).toContain('table-cell')
    expect(headers[1].classes()).toContain('hidden')
    expect(headers[3].classes()).toContain('hidden')

    const compact = wrapper.get('[data-testid="responsive-group-compact"]')
    expect(compact.text()).toContain('Responsable')
    expect(compact.text()).toContain('María Gómez')
    expect(compact.text()).toContain(formatMoney(1250000, 'COP'))
    expect(compact.text()).not.toContain('Interno')
  })

  it('promotes declared columns independently at portrait and landscape widths', () => {
    const wrapper = mountTable()
    const headers = wrapper.findAll('th')

    expect(headers[1].classes()).toContain('panel-portrait:table-cell')
    expect(headers[2].classes()).toContain('panel-portrait:hidden')
    expect(headers[2].classes()).toContain('panel-landscape:table-cell')
    expect(headers[3].classes()).toContain('panel-landscape:hidden')
    expect(headers[3].classes()).toContain('panel-desktop:table-cell')
  })

  it('uses the primary column as the predictable home for grouped details', () => {
    const wrapper = mountTable()
    const row = wrapper.get('[data-testid="accounting-row-1"]')

    expect(row.findAll('[data-testid="responsive-group-compact"]')).toHaveLength(1)
    expect(row.findAll('[data-testid="responsive-group-portrait"]')).toHaveLength(1)
    expect(row.findAll('[data-testid="responsive-group-landscape"]')).toHaveLength(0)
  })

  it('removes the scroll floor below landscape only after a policy is declared', () => {
    const priority = mountTable().get('table')
    const legacy = mountTable({
      columns: [{ key: 'name', label: 'Proyecto' }],
    }).get('table')

    expect(priority.classes()).toContain('base-responsive-table--priority')
    expect(priority.element.style.getPropertyValue('--table-min-width')).toMatch(/rem$/)
    expect(priority.element.style.minWidth).toBe('')
    expect(legacy.classes()).not.toContain('base-responsive-table--priority')
    expect(legacy.element.style.minWidth).toMatch(/rem$/)
  })

  it('warns when a mixed declaration would make an automatic choice', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => {})

    mountTable({
      columns: [columns[0], { key: 'owner', label: 'Responsable' }],
    })

    expect(warn).toHaveBeenCalledWith(expect.stringContaining('Missing: owner'))
    warn.mockRestore()
  })

  it('uses a consumer test id prefix', () => {
    const wrapper = mountTable({ testIdPrefix: 'diagnostic' })

    expect(wrapper.find('[data-testid="diagnostic-row-1"]').exists()).toBe(true)
  })

  it('wraps variable text without allowing an intrinsic-width escape', () => {
    const wrapper = mountTable({
      rows: [{ ...rows[0], name: 'Levantamiento_Fase_4_Multi-Tenant_24082026' }],
    })
    const content = wrapper.get('[data-text-policy="wrap"]')

    expect(content.classes()).toEqual(expect.arrayContaining([
      'min-w-0', 'w-full', '[overflow-wrap:anywhere]',
    ]))
  })


  it('omits legacy actions for custom action menus', () => {
    const wrapper = mountTable({ showActions: true, showDefaultActions: false })

    expect(wrapper.find('[aria-label="Editar"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Eliminar"]').exists()).toBe(false)
  })

  it('orders the leading control tracks', () => {
    const wrapper = mountTable({
      selectable: true,
      showActions: true,
      showDefaultActions: false,
      rowActionsLayout: 'menu-start',
    })

    const headers = wrapper.get('thead tr').findAll('th')
    expect(headers[0].find('input[type="checkbox"]').exists()).toBe(true)
    expect(headers[1].attributes('data-testid')).toBe('accounting-actions-header')
    expect(headers[2].text()).toBe('Proyecto')

    const cells = wrapper.get('[data-testid="accounting-row-1"]').findAll('td')
    expect(cells[0].find('input[type="checkbox"]').exists()).toBe(true)
    expect(cells[1].attributes('data-testid')).toBe('accounting-actions-cell-1')
    expect(cells[2].text()).toContain('Proyecto Aurora')
  })

  it('renders the fixed blank menu header', () => {
    const wrapper = mountTable({
      showActions: true,
      showDefaultActions: false,
      rowActionsLayout: 'menu-start',
    })
    const header = wrapper.get('[data-testid="accounting-actions-header"]')

    expect(header.attributes('aria-label')).toBe('Acciones')
    expect(header.text()).toBe('')
    expect(header.element.style.width).toBe('3.5rem')
  })

  it('pins leading control tracks in the fixed table layout', () => {
    const wrapper = mountTable({
      selectable: true,
      showActions: true,
      showDefaultActions: false,
      rowActionsLayout: 'menu-start',
    })
    const table = wrapper.get('table')
    const controlTracks = wrapper.findAll('colgroup col')

    // The layout comes from CSS: fixed from landscape up, auto below it.
    expect(table.classes()).toContain('base-responsive-table--fluid-menu')
    expect(table.element.style.tableLayout).toBe('')
    // Only the control tracks: a data <col> would keep a hidden column's share.
    expect(controlTracks).toHaveLength(2)
    expect(controlTracks[0].element.style.width).toBe('2.5rem')
    expect(controlTracks[1].element.style.width).toBe('3.5rem')
  })

  it('keeps the inline fixed layout on a menu-start table without a policy', () => {
    const wrapper = mountTable({
      columns: [{ key: 'name', label: 'Proyecto' }, { key: 'status', label: 'Estado' }],
      showActions: true,
      showDefaultActions: false,
      rowActionsLayout: 'menu-start',
    })
    const table = wrapper.get('table')

    expect(table.element.style.tableLayout).toBe('fixed')
    expect(table.classes()).not.toContain('base-responsive-table--fluid-menu')
    // Kebab track plus one <col> per data column, exactly as before.
    expect(wrapper.findAll('colgroup col')).toHaveLength(3)
  })

  // Bug caught: hidden columns kept their desktop share in the fixed layout and
  // left a blank band beside the visible ones.
  it('renormalizes menu-start header widths per profile', () => {
    const wrapper = mountTable({
      showActions: true,
      showDefaultActions: false,
      rowActionsLayout: 'menu-start',
    })
    const [name, owner, , internal] = wrapper.get('thead tr').findAll('th').slice(1)
    const share = (header, profile) => header.element.style.getPropertyValue(`--col-w-${profile}`)

    expect(share(name, 'landscape')).toBe('37.04%')
    expect(share(owner, 'landscape')).toBe('18.52%')
    expect(share(internal, 'landscape')).toBe('0.00%')
    expect(share(name, 'desktop')).toBe('31.25%')
    // Below landscape the layout is auto and the headers take no share at all.
    expect(share(name, 'compact')).toBe('')
    expect(name.element.style.width).toBe('')
    expect(name.classes()).toContain('base-responsive-table__fluid-th')
  })

  it('keeps inline-end headers on their declared width', () => {
    const wrapper = mountTable({ showActions: true, showDefaultActions: false })
    const name = wrapper.get('thead tr').findAll('th')[0]

    expect(name.element.style.width).toBe('26.85%')
    expect(name.element.style.getPropertyValue('--col-w-compact')).toBe('')
  })

  it('floors the landscape scroll width on the columns landscape keeps', () => {
    const table = mountTable({
      showActions: true,
      showDefaultActions: false,
      rowActionsLayout: 'menu-start',
    }).get('table')

    expect(table.element.style.getPropertyValue('--table-min-width-landscape')).toBe('30.50rem')
    expect(table.element.style.getPropertyValue('--table-min-width')).toBe('35.50rem')
  })

  it('keeps custom menu activation out of interactive row navigation', async () => {
    const wrapper = mount(BaseResponsiveTable, {
      props: {
        columns,
        rows,
        interactiveRows: true,
        showDefaultActions: false,
        rowActionsLayout: 'menu-start',
      },
      slots: {
        'row-actions': '<button data-testid="custom-row-menu">Abrir</button>',
      },
    })

    await wrapper.get('[data-testid="custom-row-menu"]').trigger('click')
    await wrapper.get('[data-testid="accounting-actions-cell-1"]')
      .trigger('auxclick', { button: 1 })

    expect(wrapper.emitted('row-click')).toBeUndefined()
    expect(wrapper.emitted('row-auxclick')).toBeUndefined()
  })

  it('preserves the labeled trailing action column by default', () => {
    const wrapper = mountTable({ showActions: true, showDefaultActions: false })
    const headers = wrapper.get('thead tr').findAll('th')

    expect(headers[0].text()).toBe('Proyecto')
    expect(headers.at(-1).text()).toBe('Acciones')
  })

  it('uses the selected background and consumer row classes together', () => {
    const wrapper = mountTable({
      selectable: true,
      selected: [1],
      rowClass: () => 'opacity-60',
    })
    const row = wrapper.get('[data-testid="accounting-row-1"]')

    expect(row.classes()).toContain('bg-primary-soft')
    expect(row.classes()).toContain('opacity-60')
  })

  it('emits row gestures only when interactive rows are enabled', async () => {
    const wrapper = mountTable({ interactiveRows: true })
    const row = wrapper.get('[data-testid="accounting-row-1"]')

    await row.trigger('click')
    await row.trigger('auxclick', { button: 1 })

    expect(wrapper.emitted('row-click')?.[0]?.[0]).toEqual(rows[0])
    expect(wrapper.emitted('row-auxclick')?.[0]?.[0]).toEqual(rows[0])
  })

  it('uses a business label for selectable rows when declared', () => {
    const wrapper = mountTable({
      selectable: true,
      selectionLabel: (row) => `Seleccionar ${row.name}`,
    })

    expect(wrapper.get('[data-testid="accounting-select-1"]').attributes('aria-label'))
      .toBe('Seleccionar Proyecto Aurora')
  })

  it('renders an opt-in column resize separator', () => {
    const wrapper = mountTable({
      columns: resizableColumns,
      columnWidthsKey: 'test-table-widths',
    })

    const handle = wrapper.get('[data-testid="accounting-resize-name"]')
    expect(handle.attributes('role')).toBe('separator')
    expect(handle.attributes('aria-valuenow')).toBe('240')
  })

  it('persists a keyboard column resize', async () => {
    const wrapper = mountTable({
      columns: resizableColumns,
      columnWidthsKey: 'test-table-widths',
    })

    await wrapper.get('[data-testid="accounting-resize-name"]')
      .trigger('keydown', { key: 'ArrowRight' })

    expect(window.localStorage.getItem('test-table-widths')).toBe('{"name":256}')
  })

  it('clears the preference on reset', async () => {
    window.localStorage.setItem('test-table-widths', '{"name":320}')
    const wrapper = mountTable({
      columns: resizableColumns,
      columnWidthsKey: 'test-table-widths',
    })

    const handle = wrapper.get('[data-testid="accounting-resize-name"]')
    await handle.trigger('dblclick')

    expect(handle.attributes('aria-valuenow')).toBe('240')
    expect(window.localStorage.getItem('test-table-widths')).toBeNull()
  })
})
