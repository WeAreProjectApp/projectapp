import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import AppiWidget from '~/components/platform/AppiWidget.vue'
import { APPI_COPY } from '~/config/appiCopy'
import { usePlatformAIStore } from '~/stores/platform-ai'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformChatbotStore } from '~/stores/platform-chatbot'
import { usePlatformHelpSurface } from '~/composables/usePlatformHelpSurface'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
jest.mock('../../composables/useVoiceRecorder', () => ({ useVoiceRecorder: jest.fn() }))

const { usePlatformApi } = require('../../composables/usePlatformApi')
const { useVoiceRecorder } = require('../../composables/useVoiceRecorder')

const Button = {
  props: ['disabled', 'type'], emits: ['click'],
  template: '<button role="button" :disabled="disabled" :type="type || \'button\'" @click="$emit(\'click\', $event)"><slot /></button>',
}
const Modal = { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' }
const Link = { props: ['to'], template: '<a role="link" :href="to"><slot /></a>' }
const recorder = {
  recording: ref(false), seconds: ref(0), audio: ref(null), audioUrl: ref(''),
  start: jest.fn(), stop: jest.fn(), clear: jest.fn(),
}
const capabilities = (remaining = 4) => ({
  chatbot: { enabled: true, available: true, voice_available: true },
  quota: { remaining, limit: 5, used: 5 - remaining },
})
const historyConversation = { id: 'history-9', project_id: 9, language: 'es', title: 'Estado de Nova' }

function buttonNamed(wrapper, label) {
  return wrapper.findAll('[role="button"]').find((button) => button.text() === label)
}

describe('AppiWidget', () => {
  let api
  let auth
  let chatbot
  let ai
  let helpState
  let helpApp
  let originalRandomUUID
  let wrapper

  beforeEach(() => {
    setActivePinia(createPinia())
    api = { get: jest.fn(), post: jest.fn(), delete: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    useVoiceRecorder.mockReturnValue(recorder)
    api.get.mockImplementation((url) => {
      if (url === '/api/platform/ai/capabilities/') return Promise.resolve({ data: capabilities(4) })
      if (url === 'projects/') return Promise.resolve({ data: [{ id: 7, name: 'Atlas' }, { id: 9, name: 'Nova' }] })
      if (url === '/api/platform/chatbot/conversations/') return Promise.resolve({ data: { results: [historyConversation] } })
      if (url === '/api/platform/chatbot/conversations/history-9/') {
        return Promise.resolve({ data: { conversation: historyConversation, messages: [], quota: { remaining: 4, limit: 5, used: 1 }, next_before: null } })
      }
      throw new Error(`Unexpected GET ${url}`)
    })
    api.post.mockImplementation((url) => {
      if (url === '/api/platform/ai/transcriptions/') return Promise.resolve({ data: { id: 'receipt-7', status: 'ready', transcript: '¿Qué bloquea Atlas?' } })
      if (url === '/api/platform/chatbot/conversations/') return Promise.resolve({ data: { id: 'conversation-7', language: 'es', project_id: 7 } })
      if (url === '/api/platform/chatbot/conversations/conversation-7/messages/') {
        return Promise.resolve({ data: { id: 'message-7', status: 'ready', question: '¿Qué bloquea Atlas?', quota: { remaining: 3, limit: 5, used: 2 }, answer: { text: 'Falta la aprobación.', verified_at: '2026-10-24T12:00:00Z' } } })
      }
      throw new Error(`Unexpected POST ${url}`)
    })
    api.delete.mockResolvedValue(undefined)
    recorder.recording.value = false
    recorder.seconds.value = 0
    recorder.audio.value = null
    recorder.audioUrl.value = ''
    recorder.start.mockReset()
    recorder.stop.mockReset()
    recorder.clear.mockReset()
    helpState = ref(null)
    helpApp = {}
    global.useI18n = () => ({ locale: ref('es-CO') })
    global.useLocalePath = () => (path) => path
    global.useRoute = () => ({ path: '/platform/projects/7', params: { id: '7' } })
    global.useState = () => helpState
    global.useNuxtApp = () => helpApp
    originalRandomUUID = global.crypto.randomUUID
    global.crypto.randomUUID = jest.fn(() => 'request-appi-7')
    auth = usePlatformAuthStore()
    auth.$patch({ user: { user_id: 'client-7' }, role: 'client' })
    chatbot = usePlatformChatbotStore()
    ai = usePlatformAIStore()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    jest.useRealTimers()
    global.crypto.randomUUID = originalRandomUUID
    delete global.useI18n
    delete global.useLocalePath
    delete global.useRoute
    delete global.useState
    delete global.useNuxtApp
    jest.clearAllMocks()
  })

  async function renderOpenWidget() {
    wrapper = mount(AppiWidget, {
      global: { stubs: { BaseButton: Button, BaseModal: Modal, NuxtLink: Link, AppiAvatar: true, PlatformAIQuotaMeter: true } },
    })
    await flushPromises()
    await wrapper.get('[data-testid="appi-launcher"]').trigger('click')
    await flushPromises()
  }

  async function completeReadyTranscription() {
    recorder.audio.value = new Blob(['voice'], { type: 'audio/webm' })
    await flushPromises()
    await buttonNamed(wrapper, APPI_COPY.es.transcribe).trigger('click')
    await flushPromises()
  }

  it('redeems a completed dictation receipt through its chat reply', async () => {
    // Falla si la transcripción o la respuesta deja a voz y Appi con cuotas distintas, o borra un recibo antes de canjearlo.
    await renderOpenWidget()
    await completeReadyTranscription()

    expect(chatbot.draft).toBe('¿Qué bloquea Atlas?')
    expect(ai.capabilities.quota.remaining).toBe(4)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(chatbot.quota.remaining).toBe(3)
    expect(ai.capabilities.quota.remaining).toBe(3)
    expect(api.post).toHaveBeenCalledWith('/api/platform/chatbot/conversations/conversation-7/messages/', {
      request_id: 'request-appi-7', question: '¿Qué bloquea Atlas?', transcription_id: 'receipt-7',
    }, { baseURL: '' })
    expect(api.delete).toHaveBeenCalledWith('/api/platform/ai/transcriptions/receipt-7/', { baseURL: '' })
    expect(api.delete).toHaveBeenCalledTimes(1)
  })

  it('keeps a completed dictation receipt after a failed reply', async () => {
    // Falla si perder la respuesta del chat consume una dictación que la persona todavía puede reintentar.
    api.post.mockImplementation((url) => {
      if (url === '/api/platform/ai/transcriptions/') return Promise.resolve({ data: { id: 'receipt-7', status: 'ready', transcript: '¿Qué bloquea Atlas?' } })
      if (url === '/api/platform/chatbot/conversations/') return Promise.resolve({ data: { id: 'conversation-7', language: 'es', project_id: 7 } })
      if (url === '/api/platform/chatbot/conversations/conversation-7/messages/') return Promise.reject(new Error('offline'))
      throw new Error(`Unexpected POST ${url}`)
    })
    await renderOpenWidget()
    await completeReadyTranscription()
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe(APPI_COPY.es.error)
    expect(api.delete).toHaveBeenCalledTimes(0)
    expect(wrapper.get('[data-testid="appi-question"]').element.value).toBe('¿Qué bloquea Atlas?')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.post).toHaveBeenLastCalledWith('/api/platform/chatbot/conversations/conversation-7/messages/', {
      request_id: 'request-appi-7', question: '¿Qué bloquea Atlas?', transcription_id: 'receipt-7',
    }, { baseURL: '' })
    expect(global.crypto.randomUUID).toHaveBeenCalledTimes(2)
  })

  test.each([
    ['project', async (mounted) => mounted.get('[data-testid="appi-project"]').setValue('9')],
    ['history', async (mounted) => mounted.get('[data-testid="appi-history"]').setValue('history-9')],
  ])('releases a dictation receipt before changing $0', async (_transitionName, transition) => {
    // Falla si una dictación privada se usa en otro proyecto o historial, o si cambiar de contexto borra el texto sin enviar.
    await renderOpenWidget()
    await completeReadyTranscription()
    expect(wrapper.get('[data-testid="appi-history"]').find('option[value="history-9"]').text()).toBe('Estado de Nova')
    await transition(wrapper)
    await flushPromises()

    expect(chatbot.draft).toBe('¿Qué bloquea Atlas?')
    expect(api.delete).toHaveBeenCalledWith('/api/platform/ai/transcriptions/receipt-7/', { baseURL: '' })
    expect(api.delete).toHaveBeenCalledTimes(1)
  })

  it('resets the private chat session after the authenticated account changes', async () => {
    // Falla si cambiar de cuenta conserva el historial, la cuota o una dictación privada de la cuenta anterior.
    await renderOpenWidget()
    await completeReadyTranscription()
    chatbot.$patch({ conversation: { id: 'conversation-7' }, messages: [{ id: 'message-7', status: 'ready' }], quota: { remaining: 3, limit: 5, used: 2 } })
    auth.$patch({ user: { user_id: 'client-8' } })
    await flushPromises()

    expect(chatbot.actorId).toBe('client-8')
    expect(chatbot.conversation).toBeNull()
    expect(chatbot.messages).toEqual([])
    expect(chatbot.quota).toEqual({ remaining: 4, limit: 5, used: 1 })
    expect(api.delete).toHaveBeenCalledWith('/api/platform/ai/transcriptions/receipt-7/', { baseURL: '' })
  })

  it('retries a failed pending dictation with its original request', async () => {
    // Falla si reintentar una respuesta pendiente cobra otra cuota, pierde la reserva de voz o descarta su trabajo antes de completarlo.
    let messagePostCount = 0
    api.get.mockImplementation((url) => {
      if (url === '/api/platform/ai/capabilities/') return Promise.resolve({ data: capabilities(4) })
      if (url === 'projects/') return Promise.resolve({ data: [{ id: 7, name: 'Atlas' }, { id: 9, name: 'Nova' }] })
      if (url === '/api/platform/chatbot/conversations/') return Promise.resolve({ data: { results: [] } })
      if (url === '/api/platform/chatbot/conversations/conversation-7/messages/message-202/') {
        return Promise.resolve({ data: { id: 'message-202', request_id: 'request-appi-7', status: 'failed', question: '¿Qué bloquea Atlas?', quota: { remaining: 3, limit: 5, used: 2 } } })
      }
      throw new Error(`Unexpected GET ${url}`)
    })
    api.post.mockImplementation((url) => {
      if (url === '/api/platform/ai/transcriptions/') return Promise.resolve({ data: { id: 'receipt-7', status: 'ready', transcript: '¿Qué bloquea Atlas?' } })
      if (url === '/api/platform/chatbot/conversations/') return Promise.resolve({ data: { id: 'conversation-7', language: 'es', project_id: 7 } })
      if (url === '/api/platform/chatbot/conversations/conversation-7/messages/') {
        messagePostCount += 1
        if (messagePostCount === 1) return Promise.resolve({ data: { id: 'message-202', request_id: 'request-appi-7', status: 'pending', question: '¿Qué bloquea Atlas?', quota: { remaining: 3, limit: 5, used: 2 } } })
        return Promise.resolve({ data: { id: 'message-202', request_id: 'request-appi-7', status: 'ready', question: '¿Qué bloquea Atlas?', quota: { remaining: 3, limit: 5, used: 2 }, answer: { text: 'La aprobación sigue pendiente.', verified_at: '2026-10-24T12:00:00Z' } } })
      }
      throw new Error(`Unexpected POST ${url}`)
    })
    await renderOpenWidget()
    await completeReadyTranscription()
    jest.useFakeTimers()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    jest.advanceTimersByTime(1500)
    await flushPromises()

    expect(chatbot.quota).toEqual({ remaining: 3, limit: 5, used: 2 })
    expect(wrapper.get('[data-testid="appi-question"]').element.value).toBe('¿Qué bloquea Atlas?')
    expect(api.delete).toHaveBeenCalledTimes(0)
    await wrapper.get('[data-testid="appi-message-failed"]').get('[role="button"]').trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenNthCalledWith(3, '/api/platform/chatbot/conversations/conversation-7/messages/', {
      request_id: 'request-appi-7', question: '¿Qué bloquea Atlas?', transcription_id: 'receipt-7',
    }, { baseURL: '' })
    expect(api.post).toHaveBeenNthCalledWith(4, '/api/platform/chatbot/conversations/conversation-7/messages/', {
      request_id: 'request-appi-7', question: '¿Qué bloquea Atlas?', transcription_id: 'receipt-7',
    }, { baseURL: '' })
    expect(chatbot.quota).toEqual({ remaining: 3, limit: 5, used: 2 })
    expect(api.delete).toHaveBeenCalledWith('/api/platform/ai/transcriptions/receipt-7/', { baseURL: '' })
    expect(api.delete).toHaveBeenCalledTimes(1)
  })

  it('keeps an unsent question when another help surface closes Appi', async () => {
    // Falla si abrir otra ayuda descarta una pregunta que la persona todavía no envió.
    await renderOpenWidget()
    chatbot.draft = 'No cierres esta pregunta'
    usePlatformHelpSurface().requestSurface('tour')
    await flushPromises()

    expect(chatbot.draft).toBe('No cierres esta pregunta')
    expect(wrapper.get('[data-testid="appi-launcher"]').text()).toBe('Appi')
  })

  it('suppresses the proactive hint while a guided tour is active', async () => {
    // Falla si una sugerencia de Appi compite visualmente con las instrucciones del recorrido guiado.
    jest.useFakeTimers()
    helpState.value = 'tour'
    wrapper = mount(AppiWidget, {
      global: { stubs: { BaseButton: Button, BaseModal: Modal, NuxtLink: Link, AppiAvatar: true, PlatformAIQuotaMeter: true } },
    })
    await flushPromises()
    jest.advanceTimersByTime(8000)
    await flushPromises()

    expect(wrapper.text()).not.toContain(APPI_COPY.es.welcomeHint)
    expect(wrapper.get('[data-testid="appi-launcher"]').text()).toBe('Appi')
  })
})
