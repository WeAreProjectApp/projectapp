import { mount } from '@vue/test-utils'
import ProcurementFilters from '../../components/Procurement/Filters.vue'
import BaseInput from '../../components/base/BaseInput.vue'

const originalUseI18n = global.useI18n

function mountFilters(modelValue = {}) {
  return mount(ProcurementFilters, {
    props: { modelValue },
    global: {
      components: { BaseInput },
      stubs: {
        BaseFormField: { template: '<div><slot /></div>' },
        BaseCheckbox: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input role="checkbox" type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
        },
      },
    },
  })
}

describe('ProcurementFilters', () => {
  beforeEach(() => {
    global.useI18n = () => ({ t: (key) => key })
  })

  afterEach(() => {
    global.useI18n = originalUseI18n
  })

  it('emits trimmed keyword phrases from pipe-separated text', async () => {
    // Falla si una frase completa deja de coincidir o se envían espacios como criterios.
    const wrapper = mountFilters()

    await wrapper.get('[data-testid="filter-keywords"]').setValue(' obra civil | mantenimiento vial ')

    expect(wrapper.emitted('update:modelValue')).toEqual([[{
      keywords: ['obra civil', 'mantenimiento vial'],
    }]])
  })

  it('emits trimmed UNSPSC codes from comma-separated text', async () => {
    // Falla si los códigos UNSPSC se mandan como un único criterio con comas.
    const wrapper = mountFilters()

    await wrapper.get('[data-testid="filter-unspsc_codes"]').setValue('72101500, 81101500 ')

    expect(wrapper.emitted('update:modelValue')).toEqual([[{
      unspsc_codes: ['72101500', '81101500'],
    }]])
  })

  it('removes a cleared filter from the emitted model', async () => {
    // Falla si un campo vacío sigue restringiendo la consulta del panel.
    const wrapper = mountFilters({ search: 'puente' })

    await wrapper.get('[data-testid="filter-search"]').setValue('')

    expect(wrapper.emitted('update:modelValue')).toEqual([[{}]])
  })

  it('starts with only-open opportunities selected', () => {
    // Falla si el filtro predeterminado deja de limitar la consulta a procesos abiertos.
    const wrapper = mountFilters()

    expect(wrapper.get('[role="checkbox"]').element.checked).toBe(true)
  })

  it('emits false after clearing the only-open checkbox', async () => {
    // Falla si el usuario no puede pedir procesos cerrados.
    const wrapper = mountFilters()

    await wrapper.get('[role="checkbox"]').setValue(false)

    expect(wrapper.emitted('update:modelValue')).toEqual([[{ is_open: false }]])
  })

  it('emits true after selecting the only-open checkbox again', async () => {
    // Falla si volver a marcar el control no restaura el filtro de procesos abiertos.
    const wrapper = mountFilters({ is_open: false })

    await wrapper.get('[role="checkbox"]').setValue(true)

    expect(wrapper.emitted('update:modelValue')).toEqual([[{ is_open: true }]])
  })
})
