import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import AppiChatPanel from '~/components/platform/AppiChatPanel.vue'
import { APPI_COPY } from '~/config/appiCopy'

const Button = { props: ['disabled', 'type'], emits: ['click'], template: '<button role="button" :disabled="disabled" :type="type || \'button\'" @click="$emit(\'click\', $event)"><slot /></button>' }
const Modal = { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' }
const Link = { props: ['to'], template: '<a role="link" :href="to"><slot /></a>' }
const makeStore = () => reactive({
  projects: [{ id: 7, name: 'My project' }], selectedProjectId: 7, messages: [], conversations: [], conversation: null,
  quota: { remaining: 20, limit: 20, used: 0 }, available: true, isSubmitting: false, isLoading: false, waiting: false,
  draft: 'Estado del proyecto', error: false, nextBefore: null,
})
const render = (store, extras = {}) => mount(AppiChatPanel, {
  props: { modelValue: true, store, copy: APPI_COPY.es, ...extras },
  global: { stubs: { BaseModal: Modal, BaseButton: Button, NuxtLink: Link, AppiAvatar: true, PlatformAIQuotaMeter: true } },
})
const buttonNamed = (wrapper, label) => wrapper.findAll('[role="button"]').find((button) => button.text() === label)
beforeEach(() => { global.useLocalePath = () => (path) => path })

test('purpose explains Appi limited scope', () => {
  const wrapper = render(makeStore())

  expect(wrapper.text()).toContain(APPI_COPY.es.purpose)
})

test('exhausted quota prevents a new question', async () => {
  const store = makeStore()
  store.quota.remaining = 0
  const wrapper = render(store)

  await wrapper.find('form').trigger('submit')

  expect(wrapper.emitted()).toEqual({})
  expect(wrapper.get('[data-testid="appi-send"]').element.disabled).toBe(true)
})

test('reserved dictation can finish when no new quota remains', async () => {
  const store = makeStore()
  store.quota.remaining = 0
  const wrapper = render(store, { hasReceipt: true })

  await wrapper.find('form').trigger('submit')

  expect(wrapper.emitted('submit')).toHaveLength(1)
})

test('answer content is rendered as escaped text', () => {
  const store = makeStore()
  store.messages = [{ id: 'one', status: 'ready', question: 'Pregunta', freshness: 'current', answer: { text: '<img src=x onerror=alert(1)>', verified_at: '2026-10-24T12:00:00Z' } }]
  const wrapper = render(store)

  expect(wrapper.get('[data-testid="appi-answer"]').text()).toContain('<img src=x onerror=alert(1)>')
  expect(wrapper.find('[data-testid="appi-answer"] img').exists()).toBe(false)
})

test('guide refuses a backslash in a platform action path', () => {
  const store = makeStore()
  store.messages = [{ id: 'one', status: 'ready', freshness: 'current', answer: {
    text: '1. Abre Proyectos.', verified_at: '2026-10-24T12:00:00Z',
    actions: [{ label: 'Unsafe', href: '/platform/projects/7\\escape', target_key: 'bad' }],
  } }]
  const wrapper = render(store)

  expect(wrapper.get('[data-testid="appi-answer"]').text()).toBe('1. Abre Proyectos.')
  expect(wrapper.findAll('[role="link"]')).toHaveLength(0)
})

test('historical answer is visibly marked stale', () => {
  const store = makeStore()
  store.messages = [{ id: 'one', question: 'Estado', status: 'ready', freshness: 'stale', answer: { text: 'Avance 25 %', verified_at: '2026-10-23T12:00:00Z' } }]
  const wrapper = render(store)

  expect(wrapper.text()).toContain(APPI_COPY.es.stale)
})

test('unavailable historical query has no response content', () => {
  const store = makeStore()
  store.messages = [{ id: 'one', question: '', status: 'unavailable', answer: null }]
  const wrapper = render(store)

  expect(wrapper.text()).toContain(APPI_COPY.es.hidden)
  expect(wrapper.get('[data-testid="appi-messages"]').text()).toBe(APPI_COPY.es.hidden)
})

test('failed reply emits its question when no dictation receipt remains', async () => {
  // Falla si el reintento deja de recuperar la pregunta fallida cuando no hay una dictación reservada.
  const store = makeStore()
  store.messages = [{ id: 'failed-7', question: '¿Qué falta?', status: 'failed', answer: null }]
  const wrapper = render(store)

  await buttonNamed(wrapper, APPI_COPY.es.retry).trigger('click')

  expect(wrapper.emitted('retry')[0][0]).toBe('¿Qué falta?')
})

test('dictation receipt blocks retry for a completed historical answer', async () => {
  // Falla si una dictación reservada puede reenviar una pregunta histórica distinta antes de revisarse.
  const store = makeStore()
  store.messages = [{ id: 'ready-7', question: '¿Qué falta?', status: 'ready', freshness: 'current', answer: { text: 'Falta aprobar.', verified_at: '2026-10-24T12:00:00Z' } }]
  const wrapper = render(store, { hasReceipt: true })

  await buttonNamed(wrapper, APPI_COPY.es.requery).trigger('click')

  expect(wrapper.emitted('retry')).toBeUndefined()
  expect(buttonNamed(wrapper, APPI_COPY.es.requery).element.disabled).toBe(true)
})

test('dictation receipt retries only its matching failed request', async () => {
  // Falla si una reserva de dictado permite repetir otra pregunta histórica en lugar de su fallo recuperable.
  const store = makeStore()
  store.messages = [
    { id: 'failed-current', request_id: 'request-7', question: '¿Qué bloquea Atlas?', status: 'failed', answer: null },
    { id: 'failed-history', request_id: 'request-older', question: '¿Qué cerró Nova?', status: 'failed', answer: null },
  ]
  const wrapper = render(store, { hasReceipt: true, receiptRequestId: 'request-7' })
  const [currentRow, historyRow] = wrapper.findAll('[data-testid="appi-message-failed"]')

  await currentRow.get('[role="button"]').trigger('click')
  await historyRow.get('[role="button"]').trigger('click')

  expect(wrapper.emitted('retry')[0][0]).toBe('¿Qué bloquea Atlas?')
  expect(historyRow.get('[role="button"]').element.disabled).toBe(true)
})

test('dictation retry keeps its bound question readonly', () => {
  // Falla si una reserva de dictado permite modificar la pregunta que debe volver a usar su misma clave de solicitud.
  const store = makeStore()
  const wrapper = render(store, { hasReceipt: true, receiptRequestId: 'request-7' })

  expect(wrapper.get('[data-testid="appi-question"]').element.readOnly).toBe(true)
  expect(buttonNamed(wrapper, APPI_COPY.es.suggestionStatus).element.disabled).toBe(true)
})

test('unavailable historical rows omit their retained private content', () => {
  // Falla si una respuesta que quedó en memoria reaparece después de que el servidor retiró su disponibilidad.
  const store = makeStore()
  store.messages = [{ id: 'hidden-7', question: '¿Qué falta?', status: 'unavailable', answer: { text: 'Respuesta retirada', verified_at: '2026-10-24T12:00:00Z' } }]
  const wrapper = render(store)

  expect(wrapper.get('[data-testid="appi-messages"]').text()).toBe(APPI_COPY.es.hidden)
})

test('guide links retain only platform destinations', () => {
  // Falla si una acción o fuente suministrada por el proveedor puede navegar fuera de la plataforma.
  const store = makeStore()
  store.messages = [{ id: 'guide-7', status: 'ready', freshness: 'current', answer: {
    text: 'Consulta estas referencias.', verified_at: '2026-10-24T12:00:00Z',
    actions: [{ label: 'Proyecto', href: '/platform/projects/7', target_key: 'project' }, { label: 'Externo', href: 'https://outside.test/action', target_key: 'outside-action' }],
    sources: [{ id: 'source-7', label: 'Estado', href: '/platform/projects/7/status' }, { id: 'source-outside', label: 'Proveedor', href: 'https://outside.test/source' }],
  } }]
  const wrapper = render(store)

  expect(wrapper.findAll('[role="link"]').map((link) => link.attributes('href'))).toEqual(['/platform/projects/7', '/platform/projects/7/status'])
})

test('English panel explains its purpose in English', () => {
  const wrapper = render(makeStore(), { copy: APPI_COPY.en })

  expect(wrapper.text()).toContain('learn how to use your platform')
  expect(wrapper.get('[data-testid="appi-send"]').text()).toBe('Send question')
})
