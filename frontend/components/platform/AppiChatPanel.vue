<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import AppiAvatar from './AppiAvatar.vue'
import PlatformAIQuotaMeter from './PlatformAIQuotaMeter.vue'

const props = defineProps({
  modelValue: Boolean, store: { type: Object, required: true }, copy: { type: Object, required: true },
  hasReceipt: Boolean, voiceBusy: Boolean, receiptRequestId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'submit', 'project', 'retry', 'history', 'new'])
const localePath = useLocalePath()
const log = ref(null), input = ref(null), deleting = ref(false)
const disabled = computed(() => props.store.isSubmitting || props.store.waiting || props.voiceBusy || !props.store.available || (props.store.quota?.remaining === 0 && !props.hasReceipt))
const reason = computed(() => !props.store.available ? props.copy.unavailable : props.store.quota?.remaining === 0 && !props.hasReceipt ? props.copy.quotaEmpty : props.copy.sending)
const suggestions = computed(() => props.store.selectedProjectId
  ? [props.copy.suggestionStatus, props.copy.suggestionHealth, props.copy.suggestionBug, props.copy.suggestionDocs]
  : [props.copy.suggestionBug, props.copy.suggestionDocs])
const destination = (href) => typeof href === 'string' && /^\/platform\//.test(href) && !href.includes('\\') ? localePath(href) : null
watch(() => props.store.messages.map((row) => `${row.id}:${row.status}`).join(','), async () => {
  await nextTick()
  if (log.value) log.value.scrollTop = log.value.scrollHeight
})
watch(() => props.modelValue, () => { deleting.value = false })

function send() {
  if (disabled.value || !props.store.draft.trim() || props.store.draft.length > 2000) return
  emit('submit')
}
</script>

<template>
  <BaseModal :model-value="modelValue" kind="form" full-height initial-focus="[data-testid='appi-question']" @update:model-value="emit('update:modelValue', $event)">
    <div class="flex h-full min-h-0 flex-col bg-surface text-text-default" data-tour="platform-appi-panel" data-testid="appi-panel">
      <header class="shrink-0 space-y-3 border-b border-border-default p-4">
        <div class="flex items-start justify-between gap-3">
          <div class="flex min-w-0 items-center gap-3">
            <AppiAvatar class="h-14 w-14" />
            <div class="min-w-0"><h2 class="text-xl font-semibold">Appi</h2><p class="text-sm text-text-muted">{{ copy.purpose }}</p></div>
          </div>
          <BaseButton variant="ghost" icon-only :aria-label="copy.close" data-tour="platform-appi-close" @click="emit('update:modelValue', false)">×</BaseButton>
        </div>
        <label class="block text-xs font-medium text-text-muted">
          {{ copy.project }}
          <select :value="store.selectedProjectId || ''" class="mt-1 w-full rounded-xl border border-border-default bg-surface p-2 text-sm text-text-default" :disabled="store.isSubmitting || store.waiting || voiceBusy" data-testid="appi-project" @change="emit('project', $event.target.value)">
            <option value="">{{ copy.all }}</option><option v-for="project in store.projects" :key="project.id" :value="project.id">{{ project.name }}</option>
          </select>
        </label>
        <div class="flex flex-wrap items-center gap-2">
          <label class="min-w-0 flex-1 text-xs text-text-muted">
            <span class="sr-only">{{ copy.history }}</span>
            <select :value="store.conversation?.id || ''" class="w-full rounded-lg border border-border-default bg-surface p-2 text-sm" :disabled="store.isSubmitting || voiceBusy" data-testid="appi-history" @change="$event.target.value && emit('history', $event.target.value)">
              <option value="">{{ copy.history }}</option><option v-for="conversation in store.conversations" :key="conversation.id" :value="conversation.id">{{ conversation.title || 'Appi' }}</option>
            </select>
          </label>
          <BaseButton variant="secondary" size="sm" :disabled="store.isSubmitting || voiceBusy" :disabled-reason="copy.sending" @click="emit('new')">{{ copy.newChat }}</BaseButton>
          <BaseButton v-if="store.conversation" variant="danger-ghost" size="sm" :disabled="store.isSubmitting || voiceBusy" :disabled-reason="copy.sending" @click="deleting = true">{{ copy.delete }}</BaseButton>
        </div>
        <div v-if="deleting" class="space-y-2 rounded-xl border border-border-default p-3" role="alert">
          <p class="text-sm">{{ copy.confirmDelete }}</p><div class="flex flex-wrap gap-2"><BaseButton variant="danger" size="sm" @click="store.removeConversation(); deleting = false">{{ copy.delete }}</BaseButton><BaseButton variant="secondary" size="sm" @click="deleting = false">{{ copy.cancel }}</BaseButton></div>
        </div>
      </header>

      <div ref="log" class="min-h-0 flex-1 space-y-4 overflow-y-auto p-4" role="log" aria-live="polite" aria-relevant="additions text" data-testid="appi-messages">
        <BaseButton v-if="store.nextBefore" variant="ghost" size="sm" :loading="store.isLoading" @click="store.loadOlder()">{{ copy.older }}</BaseButton>
        <div v-if="!store.messages.length" class="space-y-4 py-4 text-center"><AppiAvatar class="mx-auto h-24 w-24" /><p class="font-medium">{{ copy.empty }}</p></div>
        <article v-for="row in store.messages" :key="row.id" class="space-y-2" :data-testid="`appi-message-${row.status}`">
          <p v-if="row.question" class="ml-6 whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm bg-primary p-3 text-sm text-on-primary">{{ row.question }}</p>
          <div v-if="row.status === 'ready' && row.answer" class="space-y-3 rounded-2xl rounded-tl-sm border border-border-default bg-surface-muted p-3">
            <p v-if="row.freshness === 'stale'" class="text-xs font-semibold text-text-muted">{{ copy.stale }}</p>
            <p class="whitespace-pre-wrap break-words text-sm" data-testid="appi-answer">{{ row.answer.text }}</p>
            <div v-if="row.answer.actions?.length" class="flex flex-wrap gap-2"><template v-for="action in row.answer.actions" :key="action.target_key"><NuxtLink v-if="destination(action.href)" :to="destination(action.href)" class="rounded-lg border border-border-default px-3 py-2 text-sm font-medium text-text-brand" @click="emit('update:modelValue', false)">{{ action.label }}</NuxtLink></template></div>
            <div v-if="row.answer.sources?.length" class="space-y-1 text-xs"><p class="font-semibold">{{ copy.sources }}</p><template v-for="source in row.answer.sources" :key="source.id"><NuxtLink v-if="destination(source.href)" :to="destination(source.href)" class="block break-words text-text-brand underline underline-offset-2" @click="emit('update:modelValue', false)">{{ source.label }}</NuxtLink></template></div>
            <p class="text-xs text-text-muted">{{ copy.checked }}: {{ new Date(row.answer.verified_at).toLocaleString() }}</p>
            <BaseButton variant="ghost" size="sm" :disabled="disabled || hasReceipt" :disabled-reason="hasReceipt ? copy.review : reason" @click="emit('retry', row.question)">{{ copy.requery }}</BaseButton>
          </div>
          <div v-else-if="row.status === 'failed'" class="space-y-2 rounded-xl border border-border-default p-3 text-sm" role="status"><p>{{ copy.failed }}</p><BaseButton variant="secondary" size="sm" :disabled="disabled || (hasReceipt && row.request_id !== receiptRequestId)" :disabled-reason="hasReceipt ? copy.retryDictation : reason" @click="emit('retry', row.question)">{{ copy.retry }}</BaseButton></div>
          <p v-else-if="row.status === 'unavailable'" class="text-sm text-text-muted">{{ copy.hidden }}</p>
          <p v-else class="text-sm text-text-muted" role="status">{{ copy.sending }}</p>
        </article>
      </div>

      <form class="shrink-0 space-y-3 border-t border-border-default bg-surface p-4" @submit.prevent="send">
        <PlatformAIQuotaMeter :quota="store.quota" />
        <p v-if="store.error" role="alert" class="text-sm text-danger-strong">{{ copy.error }}</p>
        <div v-if="!store.waiting" class="flex gap-2 overflow-x-auto pb-1"><BaseButton v-for="suggestion in suggestions" :key="suggestion" variant="secondary" size="sm" class="shrink-0" :disabled="disabled || !!receiptRequestId" :disabled-reason="receiptRequestId ? copy.retryDictation : reason" @click="store.draft = suggestion; input?.focus()">{{ suggestion }}</BaseButton></div>
        <slot name="voice" />
        <label class="sr-only" for="appi-question">{{ copy.placeholder }}</label>
        <textarea id="appi-question" ref="input" v-model="store.draft" required rows="2" maxlength="2000" :placeholder="copy.placeholder" :readonly="!!receiptRequestId" :disabled="store.isSubmitting || store.waiting || voiceBusy" class="w-full resize-none rounded-xl border border-border-default bg-surface-muted p-3 text-sm text-text-default" data-testid="appi-question" />
        <p v-if="store.draft.length > 2000" role="alert" class="text-xs text-danger-strong">{{ copy.tooLong }}</p>
        <div class="flex items-center justify-between gap-3"><p class="text-xs text-text-muted">{{ copy.private }}</p><BaseButton type="submit" variant="primary" :disabled="disabled" :disabled-reason="reason" :loading="store.isSubmitting" data-testid="appi-send">{{ copy.send }}</BaseButton></div>
      </form>
    </div>
  </BaseModal>
</template>
