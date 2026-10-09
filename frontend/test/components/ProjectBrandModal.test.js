import { mount, flushPromises } from '@vue/test-utils'
import ProjectBrandModal from '~/components/panel/projects/ProjectBrandModal.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseInput from '~/components/base/BaseInput.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import { create_request, get_request, patch_request } from '~/stores/services/request_http'

jest.mock('~/stores/services/request_http', () => ({
  create_request: jest.fn(), get_request: jest.fn(), patch_request: jest.fn(), delete_request: jest.fn(),
}))

global.useI18n = () => ({ t: key => key })
global.useLocalePath = () => path => path
const mountLibrary = () => mount(ProjectBrandModal, {
  props: { project: { id: 1, name: 'Brand project' } },
  global: { components: { BaseFormField, BaseInput, BaseSelect }, stubs: {
    BaseModal: { template: '<div><slot /></div>' },
    BaseButton: { template: '<button :disabled="disabled"><slot /></button>', props: ['disabled'] },
    BaseActionButton: true, NuxtLink: { template: '<a><slot /></a>' },
  } },
})
const button = (wrapper, label) => wrapper.findAll('button').find(item => item.text() === label)

beforeEach(() => {
  jest.resetAllMocks()
  get_request.mockImplementation(url => Promise.resolve({ data: url === 'linktrees/admin/'
    ? [{ id: 'tree', name: 'Company', handle: 'company', project: null }]
    : { assets: [], linktrees: [] } }))
})

test('a failed association preserves the selection and leaves the project unchanged', async () => {
  patch_request.mockRejectedValue(new Error('offline'))
  const wrapper = mountLibrary()
  await flushPromises()
  await wrapper.get('select[aria-label="projectBrand.chooseLinktree"]').setValue('tree')
  await button(wrapper, 'projectBrand.link').trigger('click')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toBe('projectBrand.saveError')
  expect(wrapper.get('select[aria-label="projectBrand.chooseLinktree"]').element.value).toBe('tree')
  expect(wrapper.text()).toContain('projectBrand.noLinktrees')
})

test('oversized files show validation without starting an upload', async () => {
  const wrapper = mountLibrary()
  await flushPromises()
  await wrapper.get('#brand-title').setValue('Large asset')
  const file = new File(['content'], 'large.zip')
  Object.defineProperty(file, 'size', { value: 25 * 1024 * 1024 + 1 })
  Object.defineProperty(wrapper.get('#brand-file').element, 'files', { value: [file] })
  await wrapper.get('#brand-file').trigger('change')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toBe('projectBrand.tooLarge')
  expect(create_request).not.toHaveBeenCalled()
})

test('retry restores the library after a failed load', async () => {
  get_request.mockRejectedValueOnce(new Error('offline'))
  const wrapper = mountLibrary()
  await flushPromises()
  expect(wrapper.find('form').exists()).toBe(false)
  await button(wrapper, 'projectBrand.retry').trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('projectBrand.noAssets')
  expect(wrapper.find('form').exists()).toBe(true)
})
