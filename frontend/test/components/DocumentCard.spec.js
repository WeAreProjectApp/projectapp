import { mount, flushPromises } from '@vue/test-utils'
import DocumentCard from '../../components/panel/documents/DocumentCard.vue'
import BaseRowLink from '../../components/base/BaseRowLink.vue'

const NuxtLink = {
  name: 'NuxtLink',
  props: ['to'],
  template: '<a :href="typeof to === \'string\' ? to : \'#\'"><slot /></a>',
}

const BaseTooltip = {
  name: 'BaseTooltip',
  props: ['text'],
  template: '<span :data-tooltip="text"><slot name="trigger" tooltip-id="test-tooltip" /><slot /></span>',
}

const BaseBadge = {
  name: 'BaseBadge',
  props: ['variant', 'size'],
  template: '<span><slot /></span>',
}

const baseDocument = {
  id: 7,
  title: 'Contrato de Servicios',
  client_name: 'ACME Corp',
  project_name: 'Proyecto Atlas',
  created_at: '2026-03-01T10:00:00Z',
  content_excerpt: '# Contrato\n\nAlcance con **términos**.',
  active_states: [
    {
      id: 11,
      duration_seconds: 172800,
      state: {
        id: 1, name: 'Enviado', color: 'blue', system_key: 'sent',
        group_mode: 'exclusive', group_order: 0, order: 1,
      },
    },
    {
      id: 12,
      duration_seconds: 3600,
      state: {
        id: 2, name: 'Solucionar bug', color: 'red', system_key: 'needs_fix',
        group_mode: 'additive', group_order: 1, order: 0,
      },
    },
    {
      id: 13,
      duration_seconds: 60,
      state: {
        id: 3, name: 'Urgente', color: 'orange', system_key: null,
        group_mode: 'additive', group_order: 1, order: 1,
      },
    },
  ],
}

const longNamedDocument = {
  ...baseDocument,
  title: 'Levantamiento_Fase_4_Multi-Tenant_24082026',
  folder_name: 'Respuesta_Etapa_3_Inventario',
}

async function mountCard(props = {}) {
  const wrapper = mount(DocumentCard, {
    props: { document: baseDocument, editTo: '/panel/documents/7/edit', ...props },
    global: { components: { NuxtLink, BaseTooltip, BaseBadge, BaseRowLink } },
  })
  await flushPromises() // DOMPurify dynamic import inside DocumentMarkdownBody
  return wrapper
}

describe('DocumentCard', () => {
  it('renders escaped punctuation without leaking its Markdown escape in the mini preview', async () => {
    // Falla si el resumen de tarjeta vuelve a mostrar la barra de escape antes del punto final.
    const wrapper = await mountCard({
      document: { ...baseDocument, content_excerpt: 'Texto de control sin formato\\.' },
    })

    expect(wrapper.text()).toContain('Texto de control sin formato.')
    expect(wrapper.text()).not.toContain('Texto de control sin formato\\.')
  })

  it('keeps literal backslashes inside mini-preview code', async () => {
    // Falla si corregir escapes borra barras que son contenido válido de un bloque de código.
    const wrapper = await mountCard({
      document: { ...baseDocument, content_excerpt: '```txt\nC:\\clientes\\contrato.pdf\n```' },
    })

    expect(wrapper.text()).toContain('C:\\clientes\\contrato.pdf')
  })

  it('renders title, active state, meta and mini-preview', async () => {
    const wrapper = await mountCard()

    expect(wrapper.text()).toContain('Contrato de Servicios')
    expect(wrapper.text()).toContain('Enviado')
    expect(wrapper.text()).toContain('ACME Corp')
    expect(wrapper.html()).toContain('markdown-preview--mini')
    expect(wrapper.text()).toContain('Alcance con')
  })

  // Falla si la tarjeta deja de exponer el ID que permite referenciar el documento.
  it('renders the document ID before the card title', async () => {
    const wrapper = await mountCard()
    const visibleId = wrapper.get('[data-testid="document-visible-id"]')
    const title = wrapper.get('[data-testid="document-card-open-7"]')

    expect(visibleId.text()).toBe('#7')
    expect(visibleId.element.compareDocumentPosition(title.element) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('puts a contained folder badge below an unbroken title', async () => {
    const wrapper = await mountCard({ document: longNamedDocument })
    const title = wrapper.get('[data-testid="document-card-open-7"]')
    const metadata = wrapper.get('[data-testid="document-card-title-meta-7"]')
    const folder = wrapper.get('[data-testid="document-card-folder-badge-7"]')

    expect(title.classes()).toEqual(expect.arrayContaining([
      'w-full', 'min-w-0', 'max-w-full', 'truncate',
    ]))
    expect(title.element.compareDocumentPosition(metadata.element) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy()
    expect(folder.classes()).toContain('[overflow-wrap:anywhere]')
  })

  it('renders the title as a link to the edit page', async () => {
    const wrapper = await mountCard()
    const link = wrapper.find('a[href="/panel/documents/7/edit"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('Contrato de Servicios')
  })

  it('shows the cycle first and limits additional state chips', async () => {
    const wrapper = await mountCard()

    expect(wrapper.text()).toContain('Enviado')
    expect(wrapper.text()).toContain('Solucionar bug')
    expect(wrapper.text()).not.toContain('Urgente')
    expect(wrapper.text()).toContain('+1')
    expect(wrapper.find('[title="1 estados más"]').exists()).toBe(true)
  })

  it('renders the derived commercial state instead of workflow episodes', async () => {
    const wrapper = await mountCard({
      document: {
        ...baseDocument,
        display_state: { key: 'sent', label: 'Enviada', variant: 'info' },
      },
    })

    expect(wrapper.get('[data-testid="document-card-derived-state-7"]').text()).toBe('Enviada')
    expect(wrapper.text()).not.toContain('Solucionar bug')
  })

  it('places workflow states before secondary metadata', async () => {
    const wrapper = await mountCard()
    const priority = wrapper.get('[data-testid="document-card-priority-row-7"]')
    const metadata = wrapper.get('[data-testid="document-card-secondary-meta-7"]')

    expect(priority.element.nextElementSibling).toBe(metadata.element)
  })

  it('orders secondary metadata by business priority', async () => {
    const wrapper = await mountCard()
    const text = wrapper.get('[data-testid="document-card-secondary-meta-7"]').text()

    expect(text.indexOf('2026')).toBeLessThan(text.indexOf('ACME Corp'))
    expect(text.indexOf('ACME Corp')).toBeLessThan(text.indexOf('Proyecto Atlas'))
  })

  it('falls back to created_at for archived metadata without an archive timestamp', async () => {
    const wrapper = await mountCard({
      archived: true,
      document: { ...baseDocument, archived_at: null },
    })
    const metadata = wrapper.get('[data-testid="document-card-secondary-meta-7"]').text()

    expect(metadata).toMatch(/Archivado · hace /)
    expect(metadata).not.toContain('Archivado · —')
  })

  it('emits open on card click and action on the kebab', async () => {
    const wrapper = await mountCard()

    await wrapper.trigger('click')
    expect(wrapper.emitted('open')).toHaveLength(1)

    await wrapper.find('button[aria-label="Acciones de Contrato de Servicios"]').trigger('click')
    expect(wrapper.emitted('action')).toHaveLength(1)
    // The kebab click must not also open the card.
    expect(wrapper.emitted('open')).toHaveLength(1)
  })

  it('forwards the click so the page can tell a plain open from a new tab', async () => {
    const wrapper = await mountCard()

    await wrapper.trigger('click')

    expect(wrapper.emitted('open')[0][0]).toBeInstanceOf(MouseEvent)
  })

  it('forwards a wheel click too, which is a different event entirely', async () => {
    const wrapper = await mountCard()

    await wrapper.trigger('auxclick', { button: 1 })

    expect(wrapper.emitted('open')).toHaveLength(1)
    expect(wrapper.emitted('open')[0][0].button).toBe(1)
  })

  it('opts the title out of the native link drag so the card keeps its own', async () => {
    const wrapper = await mountCard()

    expect(wrapper.get('a[href="/panel/documents/7/edit"]').attributes('draggable')).toBe('false')
    expect(wrapper.attributes('draggable')).toBe('true')
  })

  it('does not make issued collection accounts draggable', async () => {
    const wrapper = await mountCard({
      document: {
        ...baseDocument,
        document_type_code: 'collection_account',
        commercial_status: 'issued',
      },
    })

    expect(wrapper.attributes('draggable')).toBe('false')
  })

  it('exposes an accessible name for the kebab', async () => {
    const wrapper = await mountCard()
    const kebab = wrapper.find('button[aria-label="Acciones de Contrato de Servicios"]')
    expect(kebab.attributes('aria-label')).toBe('Acciones de Contrato de Servicios')
    expect(kebab.attributes('title')).toBeUndefined()
  })

  it('emits dragstart/dragend and dims while dragging', async () => {
    const wrapper = await mountCard({ dragging: true })

    expect(wrapper.classes()).toContain('opacity-50')
    await wrapper.trigger('dragstart')
    await wrapper.trigger('dragend')
    expect(wrapper.emitted('dragstart')).toHaveLength(1)
    expect(wrapper.emitted('dragend')).toHaveLength(1)
  })

  it('does not make a generated snapshot draggable', async () => {
    const wrapper = await mountCard({
      document: { ...baseDocument, is_generated_snapshot: true },
    })

    expect(wrapper.attributes('draggable')).toBe('false')
  })

  it('shows a placeholder when there is no excerpt', async () => {
    const wrapper = await mountCard({
      document: { ...baseDocument, content_excerpt: '', active_states: [] },
    })
    expect(wrapper.html()).not.toContain('markdown-preview--mini')
    expect(wrapper.find('[data-testid="document-empty-preview"]').exists()).toBe(true)
  })

  it('identifies a stored collection account as a PDF', async () => {
    const wrapper = await mountCard({
      document: {
        ...baseDocument,
        content_excerpt: '',
        active_states: [],
        document_type_code: 'collection_account',
        is_generated_snapshot: true,
      },
    })

    expect(wrapper.get('[data-testid="document-pdf-preview-label"]').text())
      .toBe('Cuenta de cobro · PDF')
  })

  it('opens the thread from its badge without opening the document', async () => {
    const wrapper = await mountCard({
      document: {
        ...baseDocument,
        thread_summary: { id: 3, title: 'Historia del contrato', document_count: 4 },
      },
    })

    const badge = wrapper.get('[data-testid="document-card-thread-open-7"]')
    expect(badge.text()).toContain('Hilo · 4')

    await badge.trigger('click')

    // Falla si el badge deja de ser puerta al hilo o arrastra la apertura del documento.
    expect(wrapper.emitted('thread')[0]).toEqual([wrapper.props('document')])
    expect(wrapper.emitted('open')).toBeFalsy()
  })
})
