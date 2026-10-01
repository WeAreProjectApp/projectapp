import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import PlatformSecureLinkDetail from '../../../components/platform/secureLinks/PlatformSecureLinkDetail.vue'

jest.mock('../../../stores/platform-secure-links', () => ({ usePlatformSecureLinksStore: jest.fn() }))

const { usePlatformSecureLinksStore } = require('../../../stores/platform-secure-links')
const link = { id: 7, title: 'Database access', status: 'active', updated_at: '2026-10-01T12:00:00Z', capabilities: { copy_url: false, revoke: true, reactivate: true }, replaces: null, replaced_by: null }
const stubs = {
  BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
  BaseAlert: { template: '<div><slot /></div>' },
  BaseFormField: { template: '<label><slot /></label>' },
  BaseInput: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
  BaseSelect: { props: ['modelValue', 'options'], emits: ['update:modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', Number($event.target.value))"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>' },
  BaseButton: { props: ['type', 'loading'], emits: ['click'], template: '<button :type="type || \'button\'" :disabled="loading" @click="$emit(\'click\')"><slot /></button>' },
}

function mountDetail() {
  return mount(PlatformSecureLinkDetail, { props: { link }, global: { stubs } })
}

describe('PlatformSecureLinkDetail', () => {
  let store
  let wrapper

  beforeEach(async () => {
    global.useI18n = () => ({ t: (key) => key, locale: ref('es-co') })
    store = { events: jest.fn().mockResolvedValue({ success: true, data: { results: [], page: 1, count: 0 } }), revoke: jest.fn().mockResolvedValue({ success: true, data: { link: { ...link, status: 'revoked' } } }), reactivate: jest.fn().mockResolvedValue({ success: true, data: { link: { ...link, status: 'active' }, url: 'https://example.test/#reactivate-fake-token' } }), rename: jest.fn(), copyURL: jest.fn() }
    usePlatformSecureLinksStore.mockReturnValue(store)
    wrapper = mountDetail()
    await flushPromises()
  })

  afterEach(() => { wrapper.unmount(); delete global.useI18n })

  it('waits for an explicit confirmation before revoking', async () => {
    // Fails if opening the revoke confirmation changes an active link immediately.
    await wrapper.get('[data-testid="platform-secure-revoke"]').trigger('click')

    expect(store.revoke).toHaveBeenCalledTimes(0)
    await wrapper.get('[data-testid="platform-secure-confirm"]').trigger('click')
    await flushPromises()

    expect(store.revoke).toHaveBeenCalledWith(7)
  })

  it('uses the selected validity only after reactivation is confirmed', async () => {
    // Fails if reactivation starts before confirmation or ignores the requested validity.
    await wrapper.get('[data-testid="platform-secure-reactivate"]').trigger('click')
    await wrapper.get('#platform-secure-reactivate-validity').setValue('3')

    expect(store.reactivate).toHaveBeenCalledTimes(0)
    await wrapper.get('[data-testid="platform-secure-confirm"]').trigger('click')
    await flushPromises()

    expect(store.reactivate).toHaveBeenCalledWith(expect.objectContaining({ id: 7, updated_at: '2026-10-01T12:00:00Z' }), 3)
  })
})
