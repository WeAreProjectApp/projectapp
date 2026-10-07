import { mount } from '@vue/test-utils'
import DeliveryAuthoringForm from '../../../components/platform/delivery/DeliveryAuthoringForm.vue'
import spanish from '../../../locales/platformDelivery/es'

const createDraft = (overrides = {}) => ({ key: 'client-guide', title: 'Invoice validation', ...overrides })
const translate = (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], spanish) || key
const createTracedGuide = () => createDraft({
  stage_id: 11, context_id: 'ba809dd2-35c1-4857-8b1c-b1c43e24c925',
  source_references: [{ source_key: 'source-1', locator: 'lines:1-2', quote: 'Validar inventario.' }],
})
const createProductGuide = (overrides = {}) => ({
  role: 'Comprador invitado', environment: 'Tienda de pruebas', preparation: 'Usa una cuenta de prueba.',
  access: 'Cuenta preparada.', data: 'Pedido P-42 propio.', allowed_actions: 'Consultar pedidos propios.',
  steps: ['Abre Mis pedidos.'], expected_result: 'Sólo aparecen los pedidos propios.', failure_signals: 'Se muestran pedidos ajenos.',
  blocked_actions: 'No consultar pedidos ajenos.', blocked_steps: ['Abre el enlace de un pedido ajeno.'],
  blocked_result: 'El acceso se rechaza.', dependencies: 'Registro prepara la cuenta.', ...overrides,
})

describe('Delivery draft authoring', () => {
  const wrappers = []
  beforeEach(() => { global.useI18n = () => ({ t: translate }) })
  afterEach(() => { wrappers.forEach((wrapper) => wrapper.unmount()); wrappers.length = 0; delete global.useI18n })
  const renderForm = (props = {}) => {
    const wrapper = mount(DeliveryAuthoringForm, { props: { entity: 'contracts', initial: createDraft({ document_id: 7 }), documents: [{ id: 7, title: 'Existing agreement' }], ...props }, global: { stubs: { NuxtLink: { template: '<a><slot /></a>' } } } })
    wrappers.push(wrapper)
    return wrapper
  }

  it('submits a contract using the contract API fields', async () => {
    const wrapper = renderForm()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0]).toEqual({ key: 'client-guide', title: 'Invoice validation', document_id: 7, proposal_document_id: null, approval_file_id: null, client_visible: true })
  })

  it('links a scope to its original contract', async () => {
    const wrapper = renderForm({ entity: 'scopes', initial: createDraft({ contract_id: 8, description: 'Agreed work', amendment_id: 2 }), contracts: [{ id: 8, title: 'Service agreement', amendments: [{ id: 2, title: 'Additional work' }] }] })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0]).toEqual({ key: 'client-guide', title: 'Invoice validation', description: 'Agreed work', contract_id: 8, amendment_id: 2, is_current: true })
  })

  it('keeps a new stage attached to the selected phase', async () => {
    const wrapper = renderForm({ entity: 'stages', initial: createDraft({ phase_id: 3 }) })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0].phase_id).toBe(3)
  })

  it('turns separate guide lines into ordered test steps', async () => {
    const wrapper = renderForm({ entity: 'requirements', initial: createDraft({ stage_id: 11 }) })
    await wrapper.get('#delivery-author-steps').setValue('Open invoices\n\nSelect the prepared invoice')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0].guide.steps).toEqual(['Open invoices', 'Select the prepared invoice'])
  })

  // Detecta un rol de Platform inventado cuando las fuentes no distinguen roles del producto.
  it('leaves the product role empty in a manual guide', async () => {
    const wrapper = renderForm({ entity: 'requirements', initial: createDraft({ stage_id: 11 }) })
    expect(wrapper.get('[data-testid="delivery-author-role"]').element.value).toBe('')
    expect(wrapper.get('[data-testid="delivery-author-role-hint"]').text()).toBe('Indica sólo un rol del producto que conste en las fuentes, no un rol de acceso a Platform. Si no hay roles definidos, deja este campo vacío.')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0].guide.role).toBe('')
  })

  // Detecta que una corrección descarte el rol del producto o sus instrucciones de acceso y bloqueo.
  it.each([
    {
      role: 'Comprador', access: 'Entra con tu cuenta de comprador y un pedido propio.',
      allowed_actions: 'Consulta tus pedidos.', blocked_actions: 'No puedes editar el catálogo.',
      blocked_steps: ['Abre la dirección de edición de un producto.', 'Intenta guardar un cambio.'],
      blocked_result: 'El formulario no se abre y el catálogo no cambia.',
      dependencies: 'La etapa de catálogo prepara un producto; el gestor de catálogo lo publica.',
      data: 'Pedido P-42 propio.', steps: ['Abre Mis pedidos.'], expected_result: 'Sólo aparecen tus pedidos.', failure_signals: 'Se muestran pedidos ajenos.',
    },
    {
      role: 'Gestor de catálogo', access: 'Entra con la cuenta de gestor de catálogo.',
      allowed_actions: 'Consulta y edita los productos.', blocked_actions: 'No puedes modificar un pedido del comprador.',
      blocked_steps: ['Abre un pedido creado por el comprador.', 'Intenta cambiar sus datos.'],
      blocked_result: 'La edición se rechaza y el pedido conserva sus datos.',
      dependencies: 'La etapa de pedidos requiere que el comprador cree un pedido de prueba.',
      data: 'Producto P-42 y pedido de prueba.', steps: ['Abre el catálogo.', 'Edita el producto P-42.'], expected_result: 'El producto muestra los cambios.', failure_signals: 'El producto conserva los datos anteriores.',
    },
  ])('keeps the $role product instructions after correction', async ({ role, access, allowed_actions, blocked_actions, blocked_steps, blocked_result, dependencies, data, steps, expected_result, failure_signals }) => {
    const wrapper = renderForm({ entity: 'requirements', initial: createDraft({ stage_id: 11, guide: createProductGuide() }) })
    expect([
      wrapper.get('[data-testid="delivery-author-access"]').element.value,
      wrapper.get('[data-testid="delivery-author-allowed_actions"]').element.value,
      wrapper.get('[data-testid="delivery-author-blocked_actions"]').element.value,
      wrapper.get('[data-testid="delivery-author-blocked_steps"]').element.value,
      wrapper.get('[data-testid="delivery-author-blocked_result"]').element.value,
      wrapper.get('[data-testid="delivery-author-dependencies"]').element.value,
    ]).toEqual(['Cuenta preparada.', 'Consultar pedidos propios.', 'No consultar pedidos ajenos.', 'Abre el enlace de un pedido ajeno.', 'El acceso se rechaza.', 'Registro prepara la cuenta.'])
    await wrapper.get('[data-testid="delivery-author-role"]').setValue(role)
    await wrapper.get('[data-testid="delivery-author-access"]').setValue(access)
    await wrapper.get('[data-testid="delivery-author-allowed_actions"]').setValue(allowed_actions)
    await wrapper.get('[data-testid="delivery-author-data"]').setValue(data)
    await wrapper.get('[data-testid="delivery-author-steps"]').setValue(steps.join('\n'))
    await wrapper.get('[data-testid="delivery-author-expected_result"]').setValue(expected_result)
    await wrapper.get('[data-testid="delivery-author-failure_signals"]').setValue(failure_signals)
    await wrapper.get('[data-testid="delivery-author-blocked_actions"]').setValue(blocked_actions)
    await wrapper.get('[data-testid="delivery-author-blocked_steps"]').setValue(` ${blocked_steps[0]} \n\n ${blocked_steps[1]} `)
    await wrapper.get('[data-testid="delivery-author-blocked_result"]').setValue(blocked_result)
    await wrapper.get('[data-testid="delivery-author-dependencies"]').setValue(dependencies)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0]).toEqual({
      key: 'client-guide', title: 'Invoice validation', description: '', order: 0, stage_id: 11,
      guide: {
        role, environment: 'Tienda de pruebas', preparation: 'Usa una cuenta de prueba.', access,
        data, allowed_actions, steps, expected_result, failure_signals,
        blocked_actions, blocked_steps, blocked_result, dependencies,
      },
    })
  })

  it('requires review of the retained citations before correcting a traced guide', async () => {
    const wrapper = renderForm({ entity: 'requirements', initial: createTracedGuide() })
    await wrapper.get('#delivery-author-expected_result').setValue('The prepared inventory appears.')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.get('[data-testid="delivery-authoring-provenance"]').text()).toContain('Validar inventario.')
    expect(wrapper.get('[data-testid="delivery-authoring-save"]').element.disabled).toBe(true)
  })

  it('preserves the original citations in a reviewed guide correction', async () => {
    const initial = createTracedGuide()
    const wrapper = renderForm({ entity: 'requirements', initial })
    await wrapper.get('#delivery-author-expected_result').setValue('The prepared inventory appears.')
    await wrapper.get('[data-testid="delivery-guide-human-reviewed"] input').setValue(true)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')[0][0]).toEqual(expect.objectContaining({
      context_id: initial.context_id, source_references: initial.source_references,
      guide: expect.objectContaining({ expected_result: 'The prepared inventory appears.' }),
    }))
  })

  it('requires renewed source review after editing a confirmed correction', async () => {
    const wrapper = renderForm({ entity: 'requirements', initial: createTracedGuide() })
    await wrapper.get('[data-testid="delivery-guide-human-reviewed"] input').setValue(true)
    expect(wrapper.get('[data-testid="delivery-authoring-save"]').element.disabled).toBe(false)
    await wrapper.get('#delivery-author-title').setValue('Validate prepared inventory')
    expect(wrapper.get('[data-testid="delivery-guide-human-reviewed"] input').element.checked).toBe(false)
    expect(wrapper.get('[data-testid="delivery-authoring-save"]').element.disabled).toBe(true)
  })

  // Detecta que se guarde una prueba de bloqueo corregida sin revisar nuevamente las citas conservadas.
  it('requires renewed source review after correcting restriction steps', async () => {
    const wrapper = renderForm({ entity: 'requirements', initial: createTracedGuide() })
    await wrapper.get('[data-testid="delivery-guide-human-reviewed"] input').setValue(true)
    await wrapper.get('[data-testid="delivery-author-blocked_steps"]').setValue('Intenta editar el catálogo como comprador.')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[data-testid="delivery-guide-human-reviewed"] input').element.checked).toBe(false)
    expect(wrapper.get('[data-testid="delivery-authoring-save"]').element.disabled).toBe(true)
    expect(wrapper.emitted('submit')).toBeUndefined()
  })
})
