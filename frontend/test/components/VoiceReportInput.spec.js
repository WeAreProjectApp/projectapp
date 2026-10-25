import { ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import VoiceReportInput from '../../components/platform/VoiceReportInput.vue'

const messages = {
  'platformAI.reportByVoice': 'Describir con una nota de voz',
  'platformAI.record': 'Grabar o volver a grabar',
  'platformAI.transcribe': 'Convertir a texto',
  'platformAI.generate': 'Preparar texto estructurado',
  'platformAI.useText': 'Revisé el texto: usar en el formulario',
  'platformAI.discard': 'Descartar preparación',
}
const t = (key) => messages[key] || key
const mockStore = {
  voiceAvailable: true,
  refreshCapabilities: jest.fn(),
  recent: jest.fn(),
  transcribe: jest.fn(),
  generateReport: jest.fn(),
  job: jest.fn(),
  discard: jest.fn(),
}
const mockRecorder = {
  recording: ref(false), seconds: ref(0), audio: ref(null), audioUrl: ref(''),
  start: jest.fn(), stop: jest.fn(), clear: jest.fn(),
}

jest.mock('../../stores/platform-ai', () => ({ usePlatformAIStore: jest.fn(() => mockStore) }))
jest.mock('../../composables/useVoiceRecorder', () => ({ useVoiceRecorder: jest.fn(() => mockRecorder) }))

const BaseButton = {
  props: ['disabled'], emits: ['click'],
  template: '<button role="button" type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
}
const BaseTextarea = {
  props: ['modelValue', 'disabled'], emits: ['update:modelValue'],
  template: '<textarea v-bind="$attrs" :disabled="disabled" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}

function buttonNamed(wrapper, name) {
  return wrapper.findAll('[role="button"]').find((button) => button.text() === name)
}

describe('VoiceReportInput', () => {
  let originalRandomUUID

  beforeEach(() => {
    global.useI18n = () => ({ t, locale: ref('es-CO') })
    originalRandomUUID = global.crypto.randomUUID
    global.crypto.randomUUID = jest.fn(() => 'voice-request-7')
    mockStore.voiceAvailable = true
    mockStore.refreshCapabilities.mockResolvedValue(undefined)
    mockStore.recent.mockResolvedValue([])
    mockStore.transcribe.mockResolvedValue({ id: 'transcription-7', status: 'ready', transcript: 'El formulario no guarda.' })
    mockStore.generateReport.mockResolvedValue({
      id: 'draft-7', status: 'ready', proposal: {
        title: 'No guarda', description: 'El formulario falla al guardar.', expected_behavior: 'Debe guardar.',
        actual_behavior: 'No muestra confirmación.', steps_to_reproduce: ['Abrir formulario'], missing_details: [],
      },
    })
    mockStore.job.mockResolvedValue({ id: 'draft-7', operation: 'draft', proposal: {} })
    mockStore.discard.mockResolvedValue(undefined)
    mockRecorder.recording.value = false
    mockRecorder.seconds.value = 0
    mockRecorder.audio.value = null
    mockRecorder.audioUrl.value = ''
    mockRecorder.start.mockImplementation(async () => { mockRecorder.audio.value = new Blob(['voice'], { type: 'audio/webm' }) })
    mockRecorder.stop.mockReset()
    mockRecorder.clear.mockReset()
  })

  afterEach(() => {
    delete global.useI18n
    global.crypto.randomUUID = originalRandomUUID
    jest.clearAllMocks()
  })

  function renderInput() {
    return mount(VoiceReportInput, {
      props: { projectId: 41, scenario: 'bug' },
      global: {
        components: { BaseButton, BaseTextarea },
        stubs: { BaseAlert: { template: '<p role="alert"><slot /></p>' }, BaseFormField: { template: '<label><slot /></label>' } },
      },
    })
  }

  it('hides the voice entry when reporting is unavailable', async () => {
    // Falla si el interruptor efectivo deja visible un acceso que el servidor ya rechazó.
    mockStore.voiceAvailable = false
    const wrapper = renderInput()
    await flushPromises()

    expect(wrapper.text()).toBe('')
    wrapper.unmount()
  })

  it('applies the reviewed proposal without submitting the report', async () => {
    // Falla si la propuesta se envía automáticamente o descarta la corrección hecha por la persona.
    const wrapper = renderInput()
    await flushPromises()

    await buttonNamed(wrapper, 'Describir con una nota de voz').trigger('click')
    await flushPromises()
    await buttonNamed(wrapper, 'Grabar o volver a grabar').trigger('click')
    await flushPromises()
    await buttonNamed(wrapper, 'Convertir a texto').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="voice-transcript"]').setValue('El formulario no guarda al confirmar.')
    await buttonNamed(wrapper, 'Preparar texto estructurado').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="voice-proposal-description"]').setValue('El formulario falla tras confirmar la acción.')

    expect(wrapper.emitted('apply')).toBeUndefined()
    await buttonNamed(wrapper, 'Revisé el texto: usar en el formulario').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('apply')[0][0]).toEqual({
      title: 'No guarda', description: 'El formulario falla tras confirmar la acción.', expected_behavior: 'Debe guardar.',
      actual_behavior: 'No muestra confirmación.', steps_to_reproduce: ['Abrir formulario'], missing_details: [],
    })
    expect(mockStore.generateReport).toHaveBeenCalledWith(41, expect.objectContaining({
      transcription_id: 'transcription-7', transcript: 'El formulario no guarda al confirmar.', scenario: 'bug', language: 'es', request_id: 'voice-request-7',
    }))
    wrapper.unmount()
  })

  it('clears a reviewed proposal after the stage changes', async () => {
    // Falla si una propuesta de una etapa se puede aplicar dentro de otra etapa.
    const wrapper = mount(VoiceReportInput, {
      props: { projectId: 41, scenario: 'bug', stageId: 6 },
      global: {
        components: { BaseButton, BaseTextarea },
        stubs: { BaseAlert: { template: '<p role="alert"><slot /></p>' }, BaseFormField: { template: '<label><slot /></label>' } },
      },
    })
    await flushPromises()

    await buttonNamed(wrapper, 'Describir con una nota de voz').trigger('click')
    await buttonNamed(wrapper, 'Grabar o volver a grabar').trigger('click')
    await flushPromises()
    await buttonNamed(wrapper, 'Convertir a texto').trigger('click')
    await flushPromises()
    await buttonNamed(wrapper, 'Preparar texto estructurado').trigger('click')
    await flushPromises()
    await wrapper.setProps({ stageId: 7 })
    await flushPromises()

    expect(wrapper.text()).toBe('Describir con una nota de voz')
    expect(mockStore.recent).toHaveBeenCalledWith(41, 'bug', { stage_id: 6 })
    wrapper.unmount()
  })

  it('reuses the transcription request key after a network failure', async () => {
    // Falla si reintentar una nota duplica el trabajo facturable después de perder la conexión.
    mockStore.transcribe
      .mockRejectedValueOnce(new Error('Network lost'))
      .mockResolvedValueOnce({ id: 'transcription-7', status: 'ready', transcript: 'El formulario no guarda.' })
    const wrapper = renderInput()
    await flushPromises()

    await buttonNamed(wrapper, 'Describir con una nota de voz').trigger('click')
    await buttonNamed(wrapper, 'Grabar o volver a grabar').trigger('click')
    await flushPromises()
    await buttonNamed(wrapper, 'Convertir a texto').trigger('click')
    await flushPromises()
    await buttonNamed(wrapper, 'Convertir a texto').trigger('click')
    await flushPromises()

    expect(mockStore.transcribe.mock.calls[0][1].requestId).toBe('voice-request-7')
    expect(mockStore.transcribe.mock.calls[1][1].requestId).toBe('voice-request-7')
    expect(wrapper.get('[data-testid="voice-transcript"]').element.value).toBe('El formulario no guarda.')
    wrapper.unmount()
  })
})
