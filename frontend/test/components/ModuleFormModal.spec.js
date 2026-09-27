import { mount } from '@vue/test-utils'
import ModuleFormModal from '../../components/AdditionalModules/ModuleFormModal.vue'
import BaseFormField from '../../components/base/BaseFormField.vue'
import BaseInput from '../../components/base/BaseInput.vue'
import BaseTextarea from '../../components/base/BaseTextarea.vue'
import BaseSelect from '../../components/base/BaseSelect.vue'
import BaseSegmented from '../../components/base/BaseSegmented.vue'

const translations = {
  'additionalModules.moduleCreateTitle': 'Agregar módulo',
  'additionalModules.moduleEditTitle': 'Editar módulo',
  'additionalModules.noPriceNotice': 'Sin precios',
  'additionalModules.close': 'Cerrar',
  'additionalModules.category': 'Categoría',
  'additionalModules.slug': 'Slug estable',
  'additionalModules.icon': 'Ícono',
  'additionalModules.spanish': 'Español',
  'additionalModules.english': 'English',
  'additionalModules.name': 'Nombre',
  'additionalModules.summary': 'Resumen',
  'additionalModules.whatIsField': 'Qué es',
  'additionalModules.purposeField': 'Para qué sirve',
  'additionalModules.problemsField': 'Qué resuelve',
  'additionalModules.integrationsField': 'Qué se integra',
  'additionalModules.requirementsField': 'Qué hace falta',
  'additionalModules.cancel': 'Cancelar',
  'additionalModules.save': 'Guardar',
}

global.useI18n = jest.fn(() => ({ t: (key) => translations[key] || key }))

function mountModal() {
  return mount(ModuleFormModal, {
    props: {
      modelValue: false,
      categories: [{ id: 4, name_es: 'Infraestructura', is_active: true }],
    },
    global: {
      components: { BaseFormField, BaseInput, BaseTextarea, BaseSelect, BaseSegmented },
      stubs: {
        BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>' },
        BaseButton: { template: '<button v-bind="$attrs" :type="$attrs.type || \'button\'"><slot /></button>' },
        BaseModalActions: { template: '<div><slot /></div>' },
        BaseAlert: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('ModuleFormModal', () => {
  function expectDescribedError(wrapper, selector, message) {
    const control = wrapper.get(selector)
    const errorId = control.attributes('aria-describedby')
    const error = wrapper.findAll('[role="alert"]')
      .find((node) => node.attributes('id') === errorId)
    expect(control.attributes('aria-invalid')).toBe('true')
    expect(error.exists()).toBe(true)
    expect(error.text()).toBe(message)
  }

  async function openForm(wrapper) {
    await wrapper.setProps({ modelValue: true })
  }

  // Falla si cualquier requerido vacío, incluidas las listas, deja de marcarse junto a su control.
  it('marks every missing module field with its described error', async () => {
    const wrapper = mountModal()
    await openForm(wrapper)
    await wrapper.get('[data-testid="additional-module-form"]').trigger('submit')

    expect(wrapper.emitted('save')).toBeUndefined()
    expectDescribedError(wrapper, '[data-testid="additional-module-slug"]', 'Escribe el identificador del módulo.')
    expectDescribedError(wrapper, '[data-testid="additional-module-name-es"]', 'Escribe el nombre en español.')
    expectDescribedError(wrapper, '[data-testid="additional-module-summary-es"]', 'Escribe el resumen en español.')
    expectDescribedError(wrapper, '[data-testid="additional-module-what-es"]', 'Explica qué es el módulo en español.')
    expectDescribedError(wrapper, '[data-testid="additional-module-purpose-es"]', 'Explica para qué sirve en español.')
    expectDescribedError(wrapper, '[data-testid="additional-module-problems-es"]', 'Agrega al menos un problema en español.')
    expectDescribedError(wrapper, '[data-testid="additional-module-integrations-es"]', 'Agrega al menos una integración en español.')
    expectDescribedError(wrapper, '[data-testid="additional-module-requirements-es"]', 'Agrega al menos un requisito en español.')
    expectDescribedError(wrapper, '[data-testid="additional-module-name-en"]', 'Escribe el nombre en inglés.')
    expectDescribedError(wrapper, '[data-testid="additional-module-summary-en"]', 'Escribe el resumen en inglés.')
    expectDescribedError(wrapper, '[data-testid="additional-module-what-en"]', 'Explica qué es el módulo en inglés.')
    expectDescribedError(wrapper, '[data-testid="additional-module-purpose-en"]', 'Explica para qué sirve en inglés.')
    expectDescribedError(wrapper, '[data-testid="additional-module-problems-en"]', 'Agrega al menos un problema en inglés.')
    expectDescribedError(wrapper, '[data-testid="additional-module-integrations-en"]', 'Agrega al menos una integración en inglés.')
    expectDescribedError(wrapper, '[data-testid="additional-module-requirements-en"]', 'Agrega al menos un requisito en inglés.')
  })

  // Falla si un faltante inglés deja al usuario en una pestaña que no muestra el primer campo a corregir.
  it('opens the English tab for missing English module fields', async () => {
    const wrapper = mountModal()
    await openForm(wrapper)
    await wrapper.get('[data-testid="additional-module-form"]').trigger('submit')

    expect(wrapper.get('[role="tab"][aria-selected="true"]').text()).toBe('English')
  })
})
