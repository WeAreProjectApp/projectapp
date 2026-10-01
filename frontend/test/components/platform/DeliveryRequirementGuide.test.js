import { mount } from '@vue/test-utils'
import DeliveryRequirementGuide from '../../../components/platform/delivery/DeliveryRequirementGuide.vue'
import spanish from '../../../locales/platformDelivery/es'
import english from '../../../locales/platformDelivery/en'

const createRequirement = (overrides = {}) => ({
  id: 20, key: 'product-test', title: 'Revisar los datos propios', review_status: 'in_review',
  guide: { environment: 'Tienda de pruebas', steps: ['Abre tus datos.'], expected_result: 'Se muestran tus datos.' }, ...overrides,
})
const translate = (messages) => (key) => key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key
const createRoleGuide = (overrides = {}) => ({
  role: 'Comprador', access: 'Entra con tu cuenta de comprador.', allowed_actions: 'Consultar tus pedidos.',
  steps: ['Abre Mis pedidos.'], expected_result: 'Se muestran tus pedidos.', blocked_actions: 'No editar el catálogo.',
  blocked_steps: ['Abre la dirección de edición de un producto.'], blocked_result: 'No se abre el formulario de edición.',
  dependencies: 'El gestor de catálogo prepara un producto en la etapa de catálogo.', ...overrides,
})

describe('Delivery requirement guide', () => {
  const wrappers = []
  beforeEach(() => { global.useI18n = () => ({ t: translate(spanish) }) })
  afterEach(() => { wrappers.forEach((wrapper) => wrapper.unmount()); wrappers.length = 0; delete global.useI18n })
  const renderGuide = (requirement = createRequirement()) => {
    const wrapper = mount(DeliveryRequirementGuide, { props: { requirement } })
    wrappers.push(wrapper)
    return wrapper
  }

  // Detecta un rol inventado o una etiqueta vacía en las guías sin roles del producto.
  it.each([undefined, '', ' \n '])('omits an unspecified product role (%p)', (role) => {
    const wrapper = renderGuide(createRequirement({ guide: { role, environment: 'Tienda de pruebas', steps: ['Abre tus datos.'], expected_result: 'Se muestran tus datos.' } }))
    expect(wrapper.findAll('dt').map((field) => field.text())).toEqual(['Ambiente de prueba', 'Qué debe pasar'])
    expect(wrapper.findAll('dd').map((field) => field.text())).toEqual(['Tienda de pruebas', 'Se muestran tus datos.'])
  })

  // Detecta encabezados sin instrucciones útiles o pasos vacíos en la vista del cliente.
  it('omits optional guide fields without content', () => {
    const wrapper = renderGuide(createRequirement({ guide: {
      role: '', environment: 'Tienda de pruebas', preparation: ' ', access: ' \n ', data: [],
      allowed_actions: [], blocked_actions: '', blocked_steps: [' ', '\n'], blocked_result: null,
      dependencies: ' ', steps: [' ', 'Abre tus datos.', '\n'], expected_result: 'Se muestran tus datos.', failure_signals: '',
    } }))
    expect(wrapper.findAll('dt').map((field) => field.text())).toEqual(['Ambiente de prueba', 'Qué debe pasar'])
    expect(wrapper.findAll('h6').map((heading) => heading.text())).toEqual(['Pasos para probar lo permitido'])
    expect(wrapper.findAll('li').map((step) => step.text())).toEqual(['Abre tus datos.'])
  })

  // Detecta la pérdida de las restricciones de un rol real del producto durante la vista del cliente.
  it.each([
    {
      role: 'Comprador', access: 'Entra con tu cuenta de comprador.', allowed_actions: 'Consultar tus pedidos.',
      blocked_actions: 'No editar el catálogo.', blocked_steps: ['Abre la dirección de edición de un producto.'],
      blocked_result: 'No se abre el formulario de edición.', dependencies: 'El gestor de catálogo prepara un producto en la etapa de catálogo.',
      steps: ['Abre Mis pedidos.'], expected_result: 'Se muestran tus pedidos.',
    },
    {
      role: 'Gestor de catálogo', access: 'Entra con tu cuenta de gestor de catálogo.', allowed_actions: 'Editar el catálogo.',
      blocked_actions: 'No modificar un pedido del comprador.', blocked_steps: ['Intenta guardar un cambio en un pedido ajeno.'],
      blocked_result: 'El pedido conserva sus datos.', dependencies: 'El comprador prepara un pedido en la etapa de pedidos.',
      steps: ['Abre el catálogo.', 'Edita un producto.'], expected_result: 'El producto muestra los cambios.',
    },
  ])('shows the restrictions for the $role product role', ({ role, access, allowed_actions, blocked_actions, blocked_steps, blocked_result, dependencies, steps, expected_result }) => {
    const wrapper = renderGuide(createRequirement({ guide: createRoleGuide({ role, access, allowed_actions, blocked_actions, blocked_steps, blocked_result, dependencies, steps, expected_result }) }))
    expect(wrapper.get('[data-testid="delivery-guide-field-role"] dd').text()).toBe(role)
    expect(wrapper.get('[data-testid="delivery-guide-field-access"] dd').text()).toBe(access)
    expect(wrapper.get('[data-testid="delivery-guide-field-allowed_actions"] dd').text()).toBe(allowed_actions)
    expect(wrapper.get('[data-testid="delivery-guide-field-blocked_actions"] dd').text()).toBe(blocked_actions)
    expect(wrapper.get('[data-testid="delivery-guide-blocked_steps"]').findAll('li').map((step) => step.text())).toEqual(blocked_steps)
    expect(wrapper.get('[data-testid="delivery-guide-field-blocked_result"] dd').text()).toBe(blocked_result)
    expect(wrapper.get('[data-testid="delivery-guide-field-dependencies"] dd').text()).toBe(dependencies)
  })

  // Detecta que los campos opcionales nuevos sustituyan la guía sencilla de una conformidad ya registrada.
  it('preserves an approved version one guide', () => {
    const wrapper = renderGuide(createRequirement({ review_status: 'approved', guide: {
      role: 'Encargado de bodega', environment: 'Bodega de pruebas', preparation: 'Usa el inventario preparado.',
      data: 'Producto P-42.', steps: ['Abre el inventario.', 'Busca el producto P-42.'],
      expected_result: 'El producto tiene diez unidades.', failure_signals: 'El producto no aparece.',
    } }))
    expect(wrapper.findAll('dd').map((field) => field.text())).toEqual(['Encargado de bodega', 'Bodega de pruebas', 'Usa el inventario preparado.', 'Producto P-42.', 'El producto tiene diez unidades.', 'El producto no aparece.'])
    expect(wrapper.findAll('li').map((step) => step.text())).toEqual(['Abre el inventario.', 'Busca el producto P-42.'])
    expect(wrapper.text()).toContain('Este requerimiento está aprobado. Las ampliaciones se preparan en una etapa nueva.')
  })

  // Detecta que las instrucciones de permisos queden sin traducción para el cliente que usa inglés.
  it('renders the permission guide labels in English', () => {
    global.useI18n = () => ({ t: translate(english) })
    const wrapper = renderGuide(createRequirement({ guide: createRoleGuide() }))
    expect(wrapper.findAll('dt').map((field) => field.text())).toEqual([
      'Role in the client’s product', 'Access needed before starting', 'What you can see and do', 'What should happen',
      'What you cannot see or do', 'What should happen when the action is blocked', 'What you need from other stages or roles',
    ])
    expect(wrapper.findAll('h6').map((heading) => heading.text())).toEqual(['Steps to test permitted actions', 'Steps to check the restriction'])
  })
})
