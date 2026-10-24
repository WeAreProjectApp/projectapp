import { createPinia, setActivePinia } from 'pinia'
import { usePlatformChatbotStore } from '~/stores/platform-chatbot'
import { usePlatformApi } from '~/composables/usePlatformApi'

jest.mock('~/composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))

const enabled = { chatbot: { enabled: true, available: true, voice_available: false }, quota: { limit: 20, used: 1, remaining: 19 } }
let api
beforeEach(() => {
  setActivePinia(createPinia())
  api = { get: jest.fn().mockResolvedValue({ data: enabled }), post: jest.fn(), delete: jest.fn().mockResolvedValue({}) }
  usePlatformApi.mockReturnValue(api)
  Object.defineProperty(global.crypto, 'randomUUID', { configurable: true, value: jest.fn(() => '10000000-0000-4000-8000-000000000001') })
})

test('capability refresh preserves the shared remaining allowance', async () => {
  const store = usePlatformChatbotStore()

  await store.refreshCapabilities()

  expect(store.quota.remaining).toBe(19)
  expect(api.get).toHaveBeenCalledWith('/api/platform/ai/capabilities/', { baseURL: '' })
})

test('disabled capability stops conversation loading', async () => {
  api.get.mockResolvedValue({ data: { chatbot: { enabled: false, available: false } } })
  const store = usePlatformChatbotStore()

  await store.initialize()

  expect(store.enabled).toBe(false)
  expect(api.get).toHaveBeenCalledTimes(1)
})

test('account switch discards a late private conversation response', async () => {
  let finish
  api.get.mockReturnValue(new Promise((resolve) => { finish = resolve }))
  const store = usePlatformChatbotStore()
  store.bindActor('old-user')
  const loading = store.openConversation('old-conversation')

  store.bindActor('new-user')
  finish({ data: { conversation: { id: 'old-conversation' }, messages: [{ question: 'PRIVATE OLD ACCOUNT' }], quota: {} } })
  await loading

  expect(store.actorId).toBe('new-user')
  expect(store.messages).toEqual([])
  expect(store.conversation).toBeNull()
})

test('late capability response cannot restore a previous account', async () => {
  let finish
  api.get.mockReturnValue(new Promise((resolve) => { finish = resolve }))
  const store = usePlatformChatbotStore()
  store.bindActor('old-user')
  const loading = store.refreshCapabilities()

  store.bindActor('new-user')
  finish({ data: enabled })
  await loading

  expect(store.available).toBe(false)
  expect(store.quota).toBeNull()
})

test('technical retry preserves the logical request identifier', async () => {
  const store = usePlatformChatbotStore()
  store.conversation = { id: 'chat', language: 'es' }
  api.post.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce({ data: { id: 'turn', status: 'ready', answer: { text: 'Respuesta' } } })

  await store.send('Estado del proyecto', 'es')
  await store.send('Estado del proyecto', 'es')

  expect(api.post.mock.calls[0][1].request_id).toBe(api.post.mock.calls[1][1].request_id)
  expect(store.messages).toHaveLength(1)
})

test('dictated question includes the existing transcription receipt', async () => {
  const store = usePlatformChatbotStore()
  store.conversation = { id: 'chat', language: 'es' }
  api.post.mockResolvedValue({ data: { id: 'turn', status: 'ready' } })

  await store.send('Estado del proyecto', 'es', 'dictation-id')

  expect(api.post).toHaveBeenCalledWith('/api/platform/chatbot/conversations/chat/messages/', expect.objectContaining({ transcription_id: 'dictation-id' }), { baseURL: '' })
})

test('deleting history does not reset the shared quota marker', async () => {
  const store = usePlatformChatbotStore()
  store.conversation = { id: 'chat' }
  store.conversations = [{ id: 'chat' }]
  store.quota = { remaining: 0, used: 20, limit: 20 }

  await store.removeConversation()

  expect(store.quota.remaining).toBe(0)
  expect(store.conversations).toEqual([])
})

test('switching project ignores an earlier conversation response', async () => {
  let finish
  api.get.mockReturnValue(new Promise((resolve) => { finish = resolve }))
  const store = usePlatformChatbotStore()
  const loading = store.openConversation('old-chat')

  store.newConversation(7)
  finish({ data: { conversation: { id: 'old-chat', project_id: 2 }, messages: [{ question: 'Old scope' }] } })
  await loading

  expect(store.selectedProjectId).toBe(7)
  expect(store.messages).toEqual([])
})
