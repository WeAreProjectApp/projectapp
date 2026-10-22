import { flushPromises, mount } from '@vue/test-utils'

const mockVideoStore = {
  fetchResource: jest.fn(),
  updateResource: jest.fn(),
}
const mockExplainersStore = {
  fetchSettings: jest.fn(),
}

jest.mock('../../stores/video_resources', () => ({
  useVideoResourcesStore: jest.fn(() => mockVideoStore),
}))
jest.mock('../../stores/explainer_videos', () => ({
  useExplainerVideosStore: jest.fn(() => mockExplainersStore),
}))
jest.mock('#imports', () => {
  const messages = jest.requireActual('../../locales/videoResources/es').default
  return {
    useI18n: () => ({
      t: (key, params = {}) => {
        const message = messages[key.split('.').pop()] || key
        return Object.entries(params).reduce(
          (text, [name, value]) => text.replace(`{${name}}`, value),
          message,
        )
      },
    }),
  }
})

import VideoResourceManager from '../../components/resources/VideoResourceManager.vue'

const uploadedResource = {
  key: 'proposal:es',
  revision: 3,
  mode: 'uploaded',
  video: { src: '/api/video-resources/id/previous/video/', poster: '/previous.webp' },
  filename: 'previous.mp4',
  size: 1024,
}

const freshResource = {
  ...uploadedResource,
  revision: 4,
  video: { src: '/api/video-resources/id/next/video/', poster: '/next.webp' },
  filename: 'next.mp4',
}

const baseStubs = {
  BaseAlert: { template: '<p role="status"><slot /></p>' },
  BaseButton: { template: '<button role="button" v-bind="$attrs"><slot /></button>' },
  BaseFormField: {
    props: ['label', 'error'],
    template: '<label><span>{{ label }}</span><slot /><p v-if="error" role="alert">{{ error }}</p></label>',
  },
  BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>' },
  BaseModalActions: { template: '<div><slot /></div>' },
  BaseSelect: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
  },
}

function actionButton(wrapper, label) {
  return wrapper.findAll('[role="button"]').find((button) => button.text() === label)
}

function makeVideoFile({ name = 'video.mp4', type = 'video/mp4', size = 1024 } = {}) {
  const file = new File(['video'], name, { type })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

async function selectFile(wrapper, file) {
  const input = wrapper.get('[type="file"]')
  Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
  await input.trigger('change')
}

function mountManager(props = {}) {
  return mount(VideoResourceManager, { props, global: { stubs: baseStubs } })
}

describe('VideoResourceManager', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockVideoStore.fetchResource.mockResolvedValue(uploadedResource)
    mockVideoStore.updateResource.mockResolvedValue(freshResource)
  })

  it.each([
    ['un archivo con otro formato', makeVideoFile({ name: 'video.mov', type: 'video/quicktime' }), 'Selecciona un archivo MP4.'],
    ['un archivo mayor que 250 MiB', makeVideoFile({ size: 250 * 1024 * 1024 + 1 }), 'El video debe tener contenido y pesar como máximo 250 MB.'],
  ])('rejects %s before starting its upload', async (_scenario, file, expectedError) => {
    // Fails if the panel sends an invalid media file to the video upload endpoint.
    const wrapper = mountManager()
    await flushPromises()

    await selectFile(wrapper, file)
    await actionButton(wrapper, 'Sustituir video').trigger('click')

    expect(wrapper.get('[role="alert"]').text()).toBe(expectedError)
    expect(mockVideoStore.updateResource).toHaveBeenCalledTimes(0)
  })

  it('submits a Scrum MP4 multipart request', async () => {
    // Fails if the Scrum manager sends media to another module or drops multipart metadata.
    const wrapper = mountManager({ module: 'building-on-demand' })
    await flushPromises()
    const file = makeVideoFile({ name: 'presentation.mp4', size: 4096 })

    await selectFile(wrapper, file)
    await actionButton(wrapper, 'Sustituir video').trigger('click')
    await flushPromises()

    const [path, payload, options] = mockVideoStore.updateResource.mock.calls[0]
    expect(path).toBe('video-resources/admin/modules/building-on-demand/es/')
    expect(payload).toBeInstanceOf(FormData)
    expect(payload.get('action')).toBe('upload')
    expect(payload.get('revision')).toBe('3')
    expect(payload.get('file')).toBe(file)
    expect(options).toEqual(expect.objectContaining({
      signal: expect.any(AbortSignal),
      onUploadProgress: expect.any(Function),
    }))
  })

  it('updates the Scrum preview after an upload', async () => {
    // Fails if a successful Scrum upload leaves the manager preview on the replaced resource.
    const wrapper = mountManager({ module: 'building-on-demand' })
    await flushPromises()
    await selectFile(wrapper, makeVideoFile({ name: 'presentation.mp4', size: 4096 }))
    await actionButton(wrapper, 'Sustituir video').trigger('click')
    await flushPromises()

    expect(wrapper.get('[aria-label="Vista previa del video"]').attributes('src'))
      .toBe('/api/video-resources/id/next/video/')
  })

  it('emits the updated Scrum resource after an upload', async () => {
    // Fails if the parent cannot receive the uploaded Scrum resource.
    const wrapper = mountManager({ module: 'building-on-demand' })
    await flushPromises()
    await selectFile(wrapper, makeVideoFile({ name: 'presentation.mp4', size: 4096 }))
    await actionButton(wrapper, 'Sustituir video').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('updated')).toEqual([[freshResource]])
  })

  it('refreshes public visibility settings after a Scrum upload', async () => {
    // Fails if an uploaded Scrum resource does not refresh the setting used by the public card.
    const wrapper = mountManager({ module: 'building-on-demand' })
    await flushPromises()
    await selectFile(wrapper, makeVideoFile({ name: 'presentation.mp4', size: 4096 }))
    await actionButton(wrapper, 'Sustituir video').trigger('click')
    await flushPromises()

    expect(mockExplainersStore.fetchSettings).toHaveBeenCalledTimes(1)
  })

  it('loads the matching Scrum resource after changing the language', async () => {
    // Fails if the language picker keeps administering the Spanish Scrum video while English is selected.
    const wrapper = mountManager({ module: 'building-on-demand' })
    await flushPromises()

    await wrapper.setProps({ language: 'en' })
    await flushPromises()

    expect(mockVideoStore.fetchResource).toHaveBeenLastCalledWith(
      'video-resources/admin/modules/building-on-demand/en/',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('refreshes the preview after a stale revision response', async () => {
    // Fails if a concurrent replacement leaves the panel showing an obsolete video.
    mockVideoStore.updateResource.mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'El recurso cambió.' } },
    })
    mockVideoStore.fetchResource
      .mockResolvedValueOnce(uploadedResource)
      .mockResolvedValueOnce(freshResource)
    const wrapper = mountManager()
    await flushPromises()

    await selectFile(wrapper, makeVideoFile())
    await actionButton(wrapper, 'Sustituir video').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('El recurso cambió.')
    expect(mockVideoStore.fetchResource).toHaveBeenCalledWith('video-resources/admin/modules/proposal/es/')
    expect(wrapper.get('[aria-label="Vista previa del video"]').attributes('src'))
      .toBe('/api/video-resources/id/next/video/')
  })
})
