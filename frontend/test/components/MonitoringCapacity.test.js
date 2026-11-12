import { flushPromises, mount } from '@vue/test-utils'
import MonitoringCapacity from '../../components/monitoring/MonitoringCapacity.vue'

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn(), put_request: jest.fn() }))

const { get_request, put_request } = require('../../stores/services/request_http')

global.useI18n = () => ({ t: key => key, locale: { value: 'es-CO' } })

const MonitoringSelectStub = {
  props: ['modelValue', 'label', 'options'],
  emits: ['update:modelValue'],
  template: '<select :data-testid="`capacity-select-${label}`" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
}

const BaseInputStub = {
  props: ['id', 'modelValue'],
  emits: ['update:modelValue'],
  template: '<input :data-testid="id" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}

const BaseButtonStub = { props: ['type'], template: '<button role="button" :type="type || \'button\'"><slot /></button>' }
const BasePaginationStub = { emits: ['go'], template: '<button role="button" type="button" @click="$emit(\'go\', 2)">next history</button>' }

const allocation = (overrides = {}) => ({
  version: 6,
  cpu_mode: 'assigned', cpu_vcpu: 4,
  ram_mode: 'assigned', ram_bytes: 2147483648,
  storage_mode: 'shared', storage_bytes: null,
  ...overrides,
})

function mountCapacity() {
  return mount(MonitoringCapacity, {
    props: { resourceId: 'project-9' },
    global: { stubs: { MonitoringSelect: MonitoringSelectStub, BaseInput: BaseInputStub, BaseFormField: { template: '<div><slot /></div>' }, BaseButton: BaseButtonStub, BasePagination: BasePaginationStub } },
  })
}

function buttonWithLabel(wrapper, label) {
  return wrapper.findAll('[role="button"]').find(button => button.text() === label)
}

describe('MonitoringCapacity', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    get_request.mockResolvedValue({ data: { resource: { name: 'Proyecto Atlas' }, server_name: 'Servidor Norte', allocation: allocation() } })
  })

  afterEach(() => jest.restoreAllMocks())

  it('sends assigned GiB as bytes while keeping shared capacity null', async () => {
    // Falla si RAM se guarda en GiB, o si una dimensión compartida se envía como capacidad exclusiva.
    put_request.mockResolvedValue({ data: { resource: { name: 'Proyecto Atlas' }, server_name: 'Servidor Norte', allocation: allocation({ ram_bytes: 3758096384 }) } })
    const wrapper = mountCapacity()
    await flushPromises()

    await wrapper.get('[data-testid="capacity-ram"]').setValue('3.5')
    await buttonWithLabel(wrapper, 'monitoring.saveCapacity').trigger('click')
    await flushPromises()

    expect(put_request).toHaveBeenCalledWith('monitoring/resources/project-9/capacity/', {
      version: 6,
      cpu_mode: 'assigned', cpu_vcpu: 4,
      ram_mode: 'assigned', ram_bytes: 3758096384,
      storage_mode: 'shared', storage_bytes: null,
    })
    expect(wrapper.get('[role="status"]').text()).toBe('monitoring.capacitySaved')
  })

  it.each(['0', 'sin medida'])('rejects the invalid assigned RAM value %s without saving', async value => {
    // Falla si un valor no positivo o no numérico llega a cambiar la capacidad registrada.
    const wrapper = mountCapacity()
    await flushPromises()

    await wrapper.get('[data-testid="capacity-ram"]').setValue(value)
    await buttonWithLabel(wrapper, 'monitoring.saveCapacity').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('monitoring.invalidCapacity')
    expect(put_request).toHaveBeenCalledTimes(0)
  })

  it('keeps the edited allocation visible after a version conflict', async () => {
    // Falla si un conflicto de versión descarta el valor que el operador necesita corregir o volver a enviar.
    put_request.mockRejectedValue({ response: { status: 409 } })
    const wrapper = mountCapacity()
    await flushPromises()

    await wrapper.get('[data-testid="capacity-cpu"]').setValue('7')
    await buttonWithLabel(wrapper, 'monitoring.saveCapacity').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('monitoring.capacityConflict')
    expect(wrapper.get('[data-testid="capacity-cpu"]').element.value).toBe('7')
  })

  it('reloads the displayed capacity when its parent refreshes the resource', async () => {
    // Falla si Actualizar conserva la asignación anterior después de que el servidor entrega una nueva versión.
    get_request
      .mockResolvedValueOnce({ data: { resource: { name: 'Proyecto Atlas' }, server_name: 'Servidor Norte', allocation: allocation() } })
      .mockResolvedValueOnce({ data: { resource: { name: 'Proyecto Boreal' }, server_name: 'Servidor Sur', allocation: allocation({ version: 7, cpu_vcpu: 6 }) } })
    const wrapper = mountCapacity()
    await flushPromises()

    await wrapper.setProps({ refreshKey: 1 })
    await flushPromises()

    expect(get_request.mock.calls).toEqual([
      ['monitoring/resources/project-9/capacity/'],
      ['monitoring/resources/project-9/capacity/'],
    ])
    expect(wrapper.get('[data-testid="monitoring-capacity"]').text()).toContain('Proyecto Boreal · monitoring.serverLabel: Servidor Sur')
  })

  it('loads capacity history and moves it to the requested second page', async () => {
    // Falla si Historial no presenta quién hizo el cambio y cuándo, o si su paginación no solicita la página siguiente.
    const date = jest.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('12 Nov 2026, 09:30')
    get_request
      .mockResolvedValueOnce({ data: { resource: { name: 'Proyecto Atlas' }, server_name: 'Servidor Norte', allocation: allocation() } })
      .mockResolvedValueOnce({ data: { count: 2, page_size: 1, results: [{ id: 41, actor_name: 'Ana Ruiz', created_at: '2026-11-12T14:30:00Z', before: allocation({ cpu_vcpu: 2 }), after: allocation({ cpu_vcpu: 4 }) }] } })
      .mockResolvedValueOnce({ data: { count: 2, page_size: 1, results: [{ id: 42, actor_name: 'Luis Mora', created_at: '2026-11-11T14:30:00Z', before: allocation({ ram_bytes: 1073741824 }), after: allocation({ ram_bytes: 2147483648 }) }] } })
    const wrapper = mountCapacity()
    await flushPromises()

    // MonitoringCapacity exposes only the section test id; its native history disclosure has no stable selector yet.
    const history = wrapper.get('[data-testid="monitoring-capacity"]').find('details')
    history.element.open = true
    await history.trigger('toggle')
    await flushPromises()

    expect(wrapper.text()).toContain('Ana Ruiz · 12 Nov 2026, 09:30')
    expect(wrapper.text()).toContain('monitoring.cpu: 2 vCPU → 4 vCPU')

    await wrapper.findAll('[role="button"]').find(button => button.text() === 'next history').trigger('click')
    await flushPromises()

    expect(get_request.mock.calls).toEqual([
      ['monitoring/resources/project-9/capacity/'],
      ['monitoring/resources/project-9/capacity/history/', { params: { page: 1 } }],
      ['monitoring/resources/project-9/capacity/history/', { params: { page: 2 } }],
    ])
    expect(wrapper.text()).toContain('Luis Mora · 12 Nov 2026, 09:30')
    date.mockRestore()
  })
})
