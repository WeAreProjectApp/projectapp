import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import PlatformSecureLinkForm from '../../../components/platform/secureLinks/PlatformSecureLinkForm.vue'

jest.mock('../../../stores/platform-secure-links', () => ({ usePlatformSecureLinksStore: jest.fn() }))

const { usePlatformSecureLinksStore } = require('../../../stores/platform-secure-links')
const fakeTypes = [{ key: 'credentials', label_es: 'Credenciales', label_en: 'Credentials', fields: [] }]
const mounted = []

const stubs = {
  BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
  BaseAlert: { template: '<div><slot /></div>' },
  BaseFormField: { template: '<label><slot /></label>' },
  BaseInput: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
  BaseSelect: { props: ['modelValue', 'options'], emits: ['update:modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>' },
  BaseButton: { props: ['type', 'loading'], emits: ['click'], template: '<button role="button" :type="type || \'button\'" :disabled="loading" @click="$emit(\'click\')"><slot /></button>' },
  SecureLinkTypeField: { template: '<div />' },
  SecureLinkFields: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input data-testid="secure-link-field-password" :value="modelValue.password || \'\'" @input="$emit(\'update:modelValue\', { password: $event.target.value })" />' },
}

function mountForm() {
  const wrapper = mount(PlatformSecureLinkForm, { global: { stubs } })
  mounted.push(wrapper)
  return wrapper
}

describe('PlatformSecureLinkForm', () => {
  let store
  let uuidSpy

  beforeEach(() => {
    global.useI18n = () => ({ t: (key) => key, locale: ref('es-co') })
    store = { types: fakeTypes, create: jest.fn() }
    usePlatformSecureLinksStore.mockReturnValue(store)
    uuidSpy = jest.spyOn(globalThis.crypto, 'randomUUID').mockReturnValueOnce('11111111-1111-4111-8111-111111111111').mockReturnValueOnce('22222222-2222-4222-8222-222222222222')
  })

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
    uuidSpy.mockRestore()
    delete global.useI18n
  })

  it('starts a new request identifier only from its explicit action', async () => {
    // Fails if a request-id conflict silently retries with a different creation identity.
    store.create.mockResolvedValue({ success: false, code: 'request_id_conflict' })
    const wrapper = mountForm()
    await wrapper.get('[data-testid="platform-secure-title"]').setValue('Database access')

    await wrapper.get('[data-testid="platform-secure-form"]').trigger('submit')
    await flushPromises()
    await wrapper.get('[data-testid="platform-secure-form"]').trigger('submit')
    await flushPromises()
    await wrapper.findAll('[role="button"]').find((button) => button.text() === 'platformSecureLinks.newRequest').trigger('click')
    await wrapper.get('[data-testid="platform-secure-form"]').trigger('submit')
    await flushPromises()

    expect(store.create.mock.calls[0][0].request_id).toBe('11111111-1111-4111-8111-111111111111')
    expect(store.create.mock.calls[1][0].request_id).toBe('11111111-1111-4111-8111-111111111111')
    expect(store.create.mock.calls[2][0].request_id).toBe('22222222-2222-4222-8222-222222222222')
  })

  it('clears a secret draft when the form closes before creation returns', async () => {
    // Fails if a late creation response restores a URL or secret after the form closed.
    let resolveCreation
    store.create.mockImplementation(() => new Promise((resolve) => { resolveCreation = resolve }))
    const wrapper = mountForm()
    await wrapper.get('[data-testid="platform-secure-title"]').setValue('Database access')
    await wrapper.get('[data-testid="secure-link-field-password"]').setValue('fake-secret-for-test')

    await wrapper.get('[data-testid="platform-secure-form"]').trigger('submit')
    await wrapper.get('[data-testid="platform-secure-close"]').trigger('click')
    resolveCreation({ success: true, data: { link: { id: 7 }, url: 'https://example.test/#late-fake-token' } })
    await flushPromises()

    expect(wrapper.get('[data-testid="secure-link-field-password"]').element.value).toBe('')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.findAll('[data-testid="platform-secure-url"]')).toHaveLength(0)
  })
})
