import { mount } from '@vue/test-utils'
import CategoryManagerModal from '../../components/AdditionalModules/CategoryManagerModal.vue'
import BaseFormField from '../../components/base/BaseFormField.vue'
import BaseInput from '../../components/base/BaseInput.vue'

const translations = {
  'additionalModules.slug': 'Slug estable',
  'additionalModules.categoryNameEs': 'Nombre en español',
  'additionalModules.categoryNameEn': 'Nombre en inglés',
  'additionalModules.categoryFormTitle': 'Administrar categorías',
  'additionalModules.orderHelp': 'Orden',
  'additionalModules.close': 'Cerrar',
  'additionalModules.addCategory': 'Agregar categoría',
  'additionalModules.editCategory': 'Editar categoría',
  'additionalModules.cancel': 'Cancelar',
  'additionalModules.save': 'Guardar',
  'additionalModules.active': 'Activo',
  'additionalModules.retired': 'Retirado',
  'additionalModules.title': 'Módulos',
  'additionalModules.edit': 'Editar',
  'additionalModules.retire': 'Retirar',
  'additionalModules.restore': 'Restaurar',
}

global.useI18n = jest.fn(() => ({ t: (key) => translations[key] || key }))

function mountModal() {
  return mount(CategoryManagerModal, {
    props: { modelValue: false, categories: [] },
    global: {
      components: { BaseFormField, BaseInput },
      stubs: {
        BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>' },
        BaseButton: { template: '<button v-bind="$attrs" :type="$attrs.type || \'button\'"><slot /></button>' },
        BaseModalActions: { template: '<div><slot /></div>' },
        BaseAlert: { template: '<div><slot /></div>' },
        BaseBadge: { template: '<span><slot /></span>' },
      },
    },
  })
}

describe('CategoryManagerModal', () => {
  function expectDescribedError(wrapper, testId, message) {
    const control = wrapper.get(`[data-testid="${testId}"]`)
    const errorId = control.attributes('aria-describedby')
    const error = wrapper.findAll('[role="alert"]')
      .find((node) => node.attributes('id') === errorId)
    expect(control.attributes('aria-invalid')).toBe('true')
    expect(error.exists()).toBe(true)
    expect(error.text()).toBe(message)
  }

  async function openCreateForm(wrapper) {
    await wrapper.setProps({ modelValue: true })
    await wrapper.get('[data-testid="additional-category-add"]').trigger('click')
  }

  // Falla si una categoría incompleta se emite o si alguno de sus campos no conserva el aviso asociado.
  it('marks every empty category field with its described error', async () => {
    const wrapper = mountModal()
    await openCreateForm(wrapper)
    await wrapper.find('form').trigger('submit')

    expect(wrapper.emitted('save')).toBeUndefined()
    expectDescribedError(wrapper, 'additional-category-slug', 'Completa slug estable.')
    expectDescribedError(wrapper, 'additional-category-name-es', 'Completa nombre en español.')
    expectDescribedError(wrapper, 'additional-category-name-en', 'Completa nombre en inglés.')
  })

  // Falla si editar el slug borra los avisos pendientes de los otros idiomas.
  it('clears only the edited category slug error', async () => {
    const wrapper = mountModal()
    await openCreateForm(wrapper)
    await wrapper.find('form').trigger('submit')

    const slug = wrapper.get('[data-testid="additional-category-slug"]')
    await slug.setValue('hosting')

    expect(slug.attributes('aria-invalid')).toBeUndefined()
    expect(slug.attributes('aria-describedby')).toBeUndefined()
    expectDescribedError(wrapper, 'additional-category-name-es', 'Completa nombre en español.')
    expectDescribedError(wrapper, 'additional-category-name-en', 'Completa nombre en inglés.')
  })
})
