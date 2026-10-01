import { flushPromises, mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import PlatformSecureLinksWorkspace from '../../../components/platform/secureLinks/PlatformSecureLinksWorkspace.vue'

jest.mock('../../../stores/platform-secure-links', () => ({ usePlatformSecureLinksStore: jest.fn() }))
jest.mock('../../../stores/platform-auth', () => ({ usePlatformAuthStore: jest.fn() }))

const { usePlatformSecureLinksStore } = require('../../../stores/platform-secure-links')
const { usePlatformAuthStore } = require('../../../stores/platform-auth')

const deferred = () => {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}

const stubs = {
  BaseAlert: { template: '<div><slot /></div>' },
  BaseFormField: { template: '<label><slot /></label>' },
  BaseInput: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
  BaseSelect: { props: ['modelValue', 'options'], emits: ['update:modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>' },
  BaseButton: { props: ['type', 'loading'], emits: ['click'], template: '<button :type="type || \'button\'" :disabled="loading" @click="$emit(\'click\')"><slot /></button>' },
  PlatformSecureLinkForm: { template: '<div data-testid="platform-secure-form">fake-secret-for-test</div>' },
  PlatformSecureLinkDetail: { template: '<div data-testid="platform-secure-detail" />' },
}

function buildStore() {
  return reactive({
    page: 1, types: [{ key: 'credentials' }], links: [], count: 0, loading: false, error: '',
    clear: jest.fn(), fetchLinks: jest.fn().mockResolvedValue({ success: true }), fetchTypes: jest.fn().mockResolvedValue({ success: true }),
  })
}

function mountWorkspace(projectId = 1) {
  return mount(PlatformSecureLinksWorkspace, { props: { projectId }, global: { stubs } })
}

describe('PlatformSecureLinksWorkspace', () => {
  let auth
  let store
  let wrapper

  beforeEach(async () => {
    global.useI18n = () => ({ t: (key) => key, locale: ref('es-co') })
    auth = reactive({ isClient: true, user: { id: 4 } })
    store = buildStore()
    usePlatformAuthStore.mockReturnValue(auth)
    usePlatformSecureLinksStore.mockReturnValue(store)
    wrapper = mountWorkspace()
    await flushPromises()
  })

  afterEach(() => { wrapper.unmount(); delete global.useI18n })

  it('closes the creation form after its project changes', async () => {
    // Fails if a project change leaves a previous project's secret draft visible.
    await wrapper.get('[data-testid="platform-secure-new"]').trigger('click')
    expect(wrapper.get('[data-testid="platform-secure-form"]').text()).toBe('fake-secret-for-test')
    const clearsBeforeChange = store.clear.mock.calls.length

    await wrapper.setProps({ projectId: 2 })
    await flushPromises()

    expect(store.clear).toHaveBeenCalledTimes(clearsBeforeChange + 1)
    expect(wrapper.findAll('[data-testid="platform-secure-form"]')).toHaveLength(0)
  })

  it('closes the creation form after client access is lost', async () => {
    // Fails if a role change leaves a client-only secret draft visible in the workspace.
    await wrapper.get('[data-testid="platform-secure-new"]').trigger('click')
    expect(wrapper.get('[data-testid="platform-secure-form"]').text()).toBe('fake-secret-for-test')
    const clearsBeforeRoleChange = store.clear.mock.calls.length

    auth.isClient = false
    await flushPromises()

    expect(store.clear).toHaveBeenCalledTimes(clearsBeforeRoleChange + 1)
    expect(wrapper.findAll('[data-testid="platform-secure-form"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('platformSecureLinks.clientOnly')
  })

  it('does not load a catalog after an obsolete project refresh completes', async () => {
    // Fails if project A resumes after project B is selected and fetches an extra catalog.
    const projectARefresh = deferred()
    wrapper.unmount()
    store.fetchLinks.mockReturnValueOnce(projectARefresh.promise).mockResolvedValueOnce({ success: true })
    store.fetchTypes.mockReset().mockResolvedValue({ success: true })
    wrapper = mountWorkspace()

    await wrapper.setProps({ projectId: 2 })
    await flushPromises()
    expect(store.fetchTypes).toHaveBeenCalledTimes(1)

    projectARefresh.resolve({ success: true })
    await flushPromises()

    expect(store.fetchTypes).toHaveBeenCalledTimes(1)
  })

  it('does not show a catalog error returned by an obsolete project request', async () => {
    // Fails if a failed catalog request from project A overwrites project B's successful state.
    const projectATypes = deferred()
    wrapper.unmount()
    store.fetchLinks.mockReset().mockResolvedValue({ success: true })
    store.fetchTypes.mockReset().mockReturnValueOnce(projectATypes.promise).mockResolvedValueOnce({ success: true })
    wrapper = mountWorkspace()

    await flushPromises()
    await wrapper.setProps({ projectId: 2 })
    await flushPromises()
    expect(store.fetchTypes).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('[data-testid="platform-secure-catalog-error"]')).toHaveLength(0)

    projectATypes.resolve({ success: false })
    await flushPromises()

    expect(wrapper.findAll('[data-testid="platform-secure-catalog-error"]')).toHaveLength(0)
  })
})
