<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformChatbotStore } from '~/stores/platform-chatbot'
import { usePlatformAIStore } from '~/stores/platform-ai'
import { usePlatformHelpSurface } from '~/composables/usePlatformHelpSurface'
import { useVoiceRecorder } from '~/composables/useVoiceRecorder'
import { APPI_COPY } from '~/config/appiCopy'
import AppiAvatar from './AppiAvatar.vue'
import AppiChatPanel from './AppiChatPanel.vue'

const props = defineProps({ suppressProactiveHints: Boolean })
const auth = usePlatformAuthStore(), store = usePlatformChatbotStore(), ai = usePlatformAIStore()
const surface = usePlatformHelpSurface()
const { locale } = useI18n(), route = useRoute()
const language = computed(() => locale.value.startsWith('en') ? 'en' : 'es')
const copy = computed(() => APPI_COPY[language.value])
const open = ref(false), hint = ref(false), voiceBusy = ref(false), voiceError = ref(''), transcriptionId = ref('')
const { recording, seconds, audio, audioUrl, start, stop, clear } = useVoiceRecorder()
let unregister, hintTimer, capabilitiesTimer, disposed = false, voiceController, delayTimer, finishDelay, voiceRequestId = ''
const close = () => { open.value = false; stop(); store.stopPolling(); surface.releaseSurface('chat') }
function setOpen(value) {
  if (!value) return close()
  surface.requestSurface('chat'); open.value = true; hint.value = false; store.hintSeen = true
  store.initialize().then(() => { if (store.conversation) store.openConversation(store.conversation.id) })
  if (!store.conversation && route.path.includes('/platform/projects/') && /^\d+$/.test(String(route.params.id))) store.selectedProjectId = Number(route.params.id)
}
function cancelVoice() { voiceController?.abort(); clearTimeout(delayTimer); finishDelay?.() }
async function discardVoice() {
  cancelVoice(); stop(); clear(); voiceRequestId = ''; voiceError.value = ''; voiceBusy.value = false
  const id = transcriptionId.value; transcriptionId.value = ''
  if (id) { try { await ai.discard(id) } catch { /* The server also expires private jobs. */ } }
}
async function changeProject(value) { await discardVoice(); store.newConversation(value) }
async function openHistory(id) { await discardVoice(); await store.openConversation(id) }
async function newChat() { await discardVoice(); store.newConversation() }
async function record() {
  voiceError.value = ''
  try { await discardVoice(); await start() } catch { voiceError.value = copy.value.voiceError }
}
async function transcribe() {
  voiceBusy.value = true; voiceError.value = ''; voiceController = new AbortController()
  const controller = voiceController, projectId = store.selectedProjectId
  try {
    voiceRequestId ||= crypto.randomUUID()
    let job = await ai.transcribe(audio.value, { purpose: 'chatbot', projectId, requestId: voiceRequestId })
    if (controller.signal.aborted || disposed) return
    transcriptionId.value = job.id
    const began = Date.now()
    while (['pending', 'processing'].includes(job.status)) {
      if (Date.now() - began > 120000) throw new Error('timeout')
      await new Promise((resolve) => { finishDelay = resolve; delayTimer = setTimeout(resolve, 1500) })
      if (controller.signal.aborted || disposed) return
      job = await ai.job(job.id, controller.signal)
    }
    if (job.status !== 'ready') throw new Error('failed')
    if (!controller.signal.aborted && !disposed && store.selectedProjectId === projectId) { store.draft = job.transcript; clear() }
  } catch { if (!controller.signal.aborted && !disposed) voiceError.value = copy.value.voiceError }
  finally { if (!disposed && !controller.signal.aborted) { voiceBusy.value = false; await store.refreshCapabilities() } }
}
async function submit(question = store.draft) {
  const receipt = transcriptionId.value
  const sent = await store.send(question.trim(), language.value, receipt || null)
  if (sent && receipt) await discardVoice()
}
onMounted(async () => {
  unregister = surface.registerSurface('chat', close)
  if (auth.isClient) await store.refreshCapabilities()
  capabilitiesTimer = setInterval(() => { if (auth.isClient) store.refreshCapabilities() }, 45000)
  hintTimer = setTimeout(() => {
    if (!store.hintSeen && store.available && !open.value && !props.suppressProactiveHints && !surface.isTourActive.value) hint.value = true
    store.hintSeen = true
  }, 8000)
})
watch(() => store.enabled, (enabled) => { if (!enabled) { close(); discardVoice() } })
watch([() => store.capabilities, () => store.quota], ([capabilities, quota]) => {
  ai.capabilities = capabilities ? { ...capabilities, quota } : null
})
watch(() => [props.suppressProactiveHints, surface.isTourActive.value], ([suppressed, tour]) => { if (suppressed || tour) { hint.value = false; store.hintSeen = true } })
watch(() => [auth.user?.user_id ?? auth.user?.id, auth.role], ([id]) => {
  close(); discardVoice(); store.bindActor(id)
  if (auth.isClient) store.refreshCapabilities()
}, { immediate: true, flush: 'sync' })
onBeforeUnmount(() => { disposed = true; clearTimeout(hintTimer); clearInterval(capabilitiesTimer); cancelVoice(); store.stopPolling(); unregister?.() })
</script>

<template>
  <div v-if="auth.isClient && store.enabled">
    <div v-if="!open" class="fixed bottom-5 right-4 z-40 flex max-w-[calc(100vw-2rem)] flex-col items-end gap-2 sm:right-6">
      <p v-if="hint" class="max-w-64 rounded-2xl border border-border-default bg-surface p-3 text-sm text-text-default shadow-lg" role="status">{{ copy.welcomeHint }}</p>
      <BaseButton variant="secondary" :aria-label="copy.open" :disabled="!store.available" :disabled-reason="copy.unavailable" class="flex items-center gap-2 rounded-full shadow-lg" data-tour="platform-appi-launcher" data-testid="appi-launcher" @click="setOpen(true)"><AppiAvatar class="h-12 w-12" /><span class="pr-2 font-semibold">Appi</span></BaseButton>
    </div>
    <AppiChatPanel :model-value="open" :store="store" :copy="copy" :has-receipt="!!transcriptionId" :voice-busy="voiceBusy || recording" @update:model-value="setOpen" @project="changeProject" @submit="submit()" @retry="submit($event)" @history="openHistory" @new="newChat">
      <template #voice>
        <div v-if="store.voiceAvailable" class="space-y-2">
          <p v-if="voiceError" role="alert" class="text-xs text-danger-strong">{{ voiceError }}</p>
          <div class="flex flex-wrap items-center gap-2">
            <BaseButton v-if="!recording" variant="ghost" size="sm" :disabled="voiceBusy || store.waiting || store.quota?.remaining === 0" :disabled-reason="copy.quotaEmpty" @click="record">{{ copy.record }}</BaseButton>
            <BaseButton v-else variant="danger" size="sm" @click="stop">{{ copy.stop }} · {{ seconds }} / 60</BaseButton>
            <BaseButton v-if="audio && !recording" variant="secondary" size="sm" :loading="voiceBusy" :disabled="voiceBusy || store.waiting" :disabled-reason="copy.sending" @click="transcribe">{{ copy.transcribe }}</BaseButton>
            <BaseButton v-if="audio || transcriptionId" variant="ghost" size="sm" @click="discardVoice">{{ copy.discard }}</BaseButton>
          </div>
          <audio v-if="audioUrl" :src="audioUrl" controls class="w-full" :aria-label="copy.recording" />
          <p class="text-xs text-text-muted">{{ transcriptionId && !voiceBusy ? copy.review : copy.voiceHint }}</p>
        </div>
      </template>
    </AppiChatPanel>
  </div>
</template>
