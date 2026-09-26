import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ViewOperationalExplorer from '../../components/views/ViewOperationalExplorer.vue'

const BaseButtonStub = {
  emits: ['click'],
  template: '<button type="button" @click="$emit(\'click\', $event)"><slot /></button>',
}

const BaseActionButtonStub = {
  props: ['action', 'label'],
  emits: ['click'],
  template: '<button type="button" :data-action="action" @click="$emit(\'click\', $event)">{{ label }}</button>',
}

const BaseBadgeStub = { template: '<span><slot /></span>' }
const SidebarIconStub = { props: ['name'], template: '<span :data-icon="name" />' }

function mountExplorer(props = {}) {
  return mount(ViewOperationalExplorer, {
    props: {
      selectedNodeId: null,
      selectedTourId: null,
      showRelations: true,
      ...props,
    },
    global: {
      stubs: {
        BaseButton: BaseButtonStub,
        BaseActionButton: BaseActionButtonStub,
        BaseBadge: BaseBadgeStub,
        BaseActionIcon: true,
        SidebarIcon: SidebarIconStub,
      },
    },
  })
}

describe('ViewOperationalExplorer', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1195 })
    window.requestAnimationFrame = jest.fn(() => 1)
    window.cancelAnimationFrame = jest.fn()
    window.matchMedia = jest.fn(() => ({
      matches: false,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    }))
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('renders the three product spaces', () => {
    const wrapper = mountExplorer()

    expect(wrapper.findAll('[data-testid^="view-explorer-node-"]')).toHaveLength(3)
    expect(wrapper.text()).toContain('Panel interno')
    expect(wrapper.text()).toContain('Plataforma de clientes')
    expect(wrapper.text()).toContain('Experiencias públicas')
    expect(wrapper.text()).toContain('118 vistas relacionadas')
  })

  it('selects a space from the orbit', async () => {
    const wrapper = mountExplorer()

    await wrapper.get('[data-testid="view-explorer-node-panel-internal"]').trigger('click')

    expect(wrapper.emitted('select')).toEqual([['panel-internal']])
  })

  it('renders the Panel module ring', () => {
    const wrapper = mountExplorer({ selectedNodeId: 'panel-internal' })

    expect(wrapper.findAll('[data-testid^="view-explorer-node-"]')).toHaveLength(8)
    expect(wrapper.text()).toContain('Panorama y tareas')
    expect(wrapper.text()).toContain('Control financiero')
  })

  it('renders the Platform capability ring', () => {
    const wrapper = mountExplorer({ selectedNodeId: 'client-platform' })

    expect(wrapper.findAll('[data-testid^="view-explorer-node-"]')).toHaveLength(8)
    expect(wrapper.text()).toContain('Seguimiento del trabajo')
  })

  it('renders public content and commercial experiences', () => {
    const wrapper = mountExplorer({ selectedNodeId: 'public-experiences' })

    expect(wrapper.findAll('[data-testid^="view-explorer-node-"]')).toHaveLength(7)
    expect(wrapper.text()).toContain('Contenido y prueba social')
    expect(wrapper.text()).toContain('Módulos adicionales')
    expect(wrapper.text()).toContain('Programa de Alianza')
    expect(wrapper.text()).toContain('Propuesta comercial')
    expect(wrapper.text()).toContain('Enlaces seguros')
  })

  it('previews module context on hover without selecting it', async () => {
    const wrapper = mountExplorer({ selectedNodeId: 'panel-internal' })
    const contentNode = wrapper.get('[data-testid="view-explorer-node-panel-content"]')

    await contentNode.trigger('mouseenter')
    expect(wrapper.get('[data-testid="view-explorer-detail"]').text()).toContain('Vista previa')
    expect(wrapper.get('[data-testid="view-explorer-detail"]').text()).toContain('Contenido')
    expect(wrapper.emitted('select')).toBeUndefined()

    await contentNode.trigger('mouseleave')
    expect(wrapper.get('[data-testid="view-explorer-detail"]').text()).toContain('Panel interno')
  })

  it('draws the curated Platform relationships', () => {
    const wrapper = mountExplorer({ selectedNodeId: 'client-platform' })

    expect(wrapper.findAll('[data-testid="view-explorer-relation"]')).toHaveLength(9)
  })

  it('toggles the relationship layer', async () => {
    const wrapper = mountExplorer({ selectedNodeId: 'client-platform' })

    await wrapper.get('[data-testid="view-explorer-relations-toggle"]').trigger('click')

    expect(wrapper.emitted('update:showRelations')).toEqual([[false]])
  })

  it('finds a capability by its operational benefit', async () => {
    const wrapper = mountExplorer()

    await wrapper.get('#view-explorer-search').setValue('aprobación trazable')

    expect(wrapper.get('[data-testid="view-explorer-search-results"]').text())
      .toContain('Documentos y aprobaciones')
  })

  it('opens a capability from search results', async () => {
    const wrapper = mountExplorer()
    await wrapper.get('#view-explorer-search').setValue('aprobación trazable')

    await wrapper.get('[data-testid="view-explorer-search-results"] button').trigger('click')

    expect(wrapper.emitted('select')).toEqual([['platform-documents']])
  })

  it('shows the technical reference below a feature', () => {
    const wrapper = mountExplorer({ selectedNodeId: 'platform-document-portal' })

    expect(wrapper.get('[data-testid="view-explorer-detail"]').text())
      .toContain('Referencia técnica secundaria')
    expect(wrapper.get('[data-testid="view-explorer-detail"]').text()).toContain('/platform/documents')
  })

  it('starts a guided tour from a product space', async () => {
    const wrapper = mountExplorer({ selectedNodeId: 'panel-internal' })

    await wrapper.get('[data-testid="view-explorer-start-tour"]').trigger('click')

    expect(wrapper.emitted('start-tour')).toEqual([['panel-internal']])
  })

  it('advances and exits an active guided tour', async () => {
    const wrapper = mountExplorer({
      selectedNodeId: 'panel-overview-work',
      selectedTourId: 'panel-internal',
    })

    expect(wrapper.get('[data-testid="view-explorer-tour-controls"]').text()).toContain('Paso 1 de 8')
    await wrapper.get('[data-testid="view-explorer-tour-next"]').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['panel-commercial']])

    await wrapper.get('[data-testid="view-explorer-tour-stop"]').trigger('click')
    expect(wrapper.emitted('stop-tour')).toHaveLength(1)
  })

  it('uses cards instead of the orbit in compact layouts', async () => {
    window.innerWidth = 412

    const wrapper = mountExplorer({ selectedNodeId: 'public-experiences' })
    await nextTick()

    expect(wrapper.find('[data-testid="view-explorer-center"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid^="view-explorer-node-"]')).toHaveLength(7)
    expect(wrapper.text()).toContain('Selecciona una tarjeta para continuar')
  })

  it('explains when reduced motion disables automatic rotation', async () => {
    window.matchMedia = jest.fn(() => ({
      matches: true,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    }))

    const wrapper = mountExplorer()
    await nextTick()

    expect(wrapper.text()).toContain('desactivado por tu preferencia de movimiento reducido')
  })

  it('clears an unknown node from URL state', () => {
    const wrapper = mountExplorer({ selectedNodeId: 'unknown-capability' })

    expect(wrapper.emitted('select')).toEqual([[null]])
  })
})
