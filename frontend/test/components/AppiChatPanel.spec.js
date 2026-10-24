import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import AppiChatPanel from '~/components/platform/AppiChatPanel.vue'
import { APPI_COPY } from '~/config/appiCopy'

const Button = { props: ['disabled', 'type'], emits: ['click'], template: '<button :disabled="disabled" :type="type || \'button\'" @click="$emit(\'click\', $event)"><slot /></button>' }
const Modal = { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' }
const Link = { props: ['to'], template: '<a :href="to"><slot /></a>' }
const makeStore = () => reactive({
  projects: [{ id: 7, name: 'My project' }], selectedProjectId: 7, messages: [], conversations: [], conversation: null,
  quota: { remaining: 20, limit: 20, used: 0 }, available: true, isSubmitting: false, isLoading: false, waiting: false,
  draft: 'Estado del proyecto', error: false, nextBefore: null,
})
const render = (store, extras = {}) => mount(AppiChatPanel, {
  props: { modelValue: true, store, copy: APPI_COPY.es, ...extras },
  global: { stubs: { BaseModal: Modal, BaseButton: Button, NuxtLink: Link, AppiAvatar: true, PlatformAIQuotaMeter: true } },
})
beforeEach(() => { global.useLocalePath = () => (path) => path })

test('purpose explains the finite project and platform scope', () => {
  const wrapper = render(makeStore())

  expect(wrapper.text()).toContain(APPI_COPY.es.purpose)
})

test('exhausted quota prevents a new question', async () => {
  const store = makeStore()
  store.quota.remaining = 0
  const wrapper = render(store)

  await wrapper.find('form').trigger('submit')

  expect(wrapper.emitted('submit')).toBeUndefined()
  expect(wrapper.get('[data-testid="appi-send"]').attributes('disabled')).toBeDefined()
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

test('guide offers only an internal platform destination', () => {
  const store = makeStore()
  store.messages = [{ id: 'one', status: 'ready', freshness: 'current', answer: {
    text: '1. Abre Proyectos.', verified_at: '2026-10-24T12:00:00Z',
    actions: [{ label: 'Reportar bug', href: '/platform/projects/7/bugs', target_key: 'project-bugs' }, { label: 'Unsafe', href: 'https://outside.test', target_key: 'bad' }],
  } }]
  const wrapper = render(store)

  expect(wrapper.find('a[href="/platform/projects/7/bugs"]').exists()).toBe(true)
  expect(wrapper.find('a[href="https://outside.test"]').exists()).toBe(false)
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
  expect(wrapper.find('[data-testid="appi-answer"]').exists()).toBe(false)
})

test('English panel explains its purpose in English', () => {
  const wrapper = render(makeStore(), { copy: APPI_COPY.en })

  expect(wrapper.text()).toContain('learn how to use your platform')
  expect(wrapper.get('[data-testid="appi-send"]').text()).toBe('Send question')
})
