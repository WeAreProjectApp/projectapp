import { defineComponent, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { useVoiceRecorder } from '../../composables/useVoiceRecorder'

const RecorderProbe = defineComponent({
  setup() {
    const recorder = useVoiceRecorder()
    const error = ref('')
    async function startRecording() {
      try { await recorder.start() } catch (reason) { error.value = reason.message }
    }
    return { ...recorder, error, startRecording }
  },
  template: `
    <div>
      <button data-testid="record-start" type="button" @click="startRecording">start</button>
      <button data-testid="record-stop" type="button" @click="stop">stop</button>
      <span data-testid="record-seconds">{{ seconds }}</span>
      <span data-testid="recording-state">{{ recording ? 'recording' : 'stopped' }}</span>
      <span data-testid="audio-url">{{ audioUrl }}</span>
      <span data-testid="record-error">{{ error }}</span>
    </div>
  `,
})

class FakeMediaRecorder {
  static instances = []
  static isTypeSupported = jest.fn((type) => type === 'audio/webm;codecs=opus')

  constructor(stream, options) {
    this.stream = stream
    this.options = options
    this.state = 'inactive'
    this.ondataavailable = null
    this.onstop = null
    this.onerror = null
    FakeMediaRecorder.instances.push(this)
  }

  start() { this.state = 'recording' }

  stop() {
    if (this.state !== 'recording') return
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['voice'], { type: this.options.mimeType }) })
    this.onstop?.()
  }
}

describe('useVoiceRecorder', () => {
  let originalMediaRecorder
  let originalMediaDevices
  let originalCreateObjectURL
  let originalRevokeObjectURL
  let stream
  let track

  beforeEach(() => {
    jest.useFakeTimers()
    FakeMediaRecorder.instances = []
    originalMediaRecorder = global.MediaRecorder
    originalMediaDevices = navigator.mediaDevices
    originalCreateObjectURL = URL.createObjectURL
    originalRevokeObjectURL = URL.revokeObjectURL
    track = { stop: jest.fn() }
    stream = { getTracks: jest.fn(() => [track]) }
    Object.defineProperty(global, 'MediaRecorder', { configurable: true, value: FakeMediaRecorder })
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: jest.fn().mockResolvedValue(stream) } })
    URL.createObjectURL = jest.fn(() => 'blob:voice-note')
    URL.revokeObjectURL = jest.fn()
  })

  afterEach(() => {
    Object.defineProperty(global, 'MediaRecorder', { configurable: true, value: originalMediaRecorder })
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: originalMediaDevices })
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
    jest.useRealTimers()
  })

  it('stops a recording at sixty seconds', async () => {
    // Falla si una nota continúa capturando audio después del límite de un minuto.
    const wrapper = mount(RecorderProbe)

    await wrapper.get('[data-testid="record-start"]').trigger('click')
    await Promise.resolve()
    jest.advanceTimersByTime(60_000)
    await nextTick()

    expect(wrapper.get('[data-testid="record-seconds"]').text()).toBe('60')
    expect(wrapper.get('[data-testid="recording-state"]').text()).toBe('stopped')
    expect(FakeMediaRecorder.instances[0].state).toBe('inactive')
    wrapper.unmount()
  })

  it('surfaces a denied microphone permission', async () => {
    // Falla si el rechazo del navegador parece una grabación iniciada.
    navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(new Error('Permission denied'))
    const wrapper = mount(RecorderProbe)

    await wrapper.get('[data-testid="record-start"]').trigger('click')
    await Promise.resolve()

    expect(wrapper.get('[data-testid="recording-state"]').text()).toBe('stopped')
    expect(wrapper.get('[data-testid="record-error"]').text()).toBe('Permission denied')
    expect(FakeMediaRecorder.instances).toHaveLength(0)
    wrapper.unmount()
  })

  it('releases the microphone when the recorder stops', async () => {
    // Falla si detener una nota conserva un micrófono activo en el navegador.
    const wrapper = mount(RecorderProbe)

    await wrapper.get('[data-testid="record-start"]').trigger('click')
    await Promise.resolve()
    await wrapper.get('[data-testid="record-stop"]').trigger('click')

    expect(track.stop).toHaveBeenCalled()
    expect(wrapper.get('[data-testid="audio-url"]').text()).toBe('blob:voice-note')
    wrapper.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:voice-note')
  })

  it('releases a microphone granted after the component unmounts', async () => {
    // Falla si cerrar el formulario mientras aparece el permiso deja un micrófono activo.
    let resolveMedia
    navigator.mediaDevices.getUserMedia.mockImplementationOnce(() => new Promise((resolve) => { resolveMedia = resolve }))
    const wrapper = mount(RecorderProbe)

    await wrapper.get('[data-testid="record-start"]').trigger('click')
    wrapper.unmount()
    resolveMedia(stream)
    await Promise.resolve()

    expect(track.stop).toHaveBeenCalled()
    expect(FakeMediaRecorder.instances).toHaveLength(0)
  })
})
