<template>
  <form class="mb-5 space-y-3 rounded-xl border border-border-default p-4" data-testid="issue-reopen" @submit.prevent="submit">
    <h3 class="text-sm font-semibold text-text-default">{{ t('platformIssues.reopen') }}</h3>
    <p class="text-xs text-text-muted">{{ t('platformIssues.reopenHint') }}</p>
    <label for="issue-reopen-message" class="block text-xs text-text-muted">{{ t('platformIssues.reopenLabel') }}</label>
    <textarea id="issue-reopen-message" v-model="content" required rows="3" class="w-full rounded-xl border border-border-default bg-surface px-3 py-2 text-sm text-text-default" />
    <IssueEvidenceFields v-model="evidence" :project-id="projectId" kind="bug" :ticket-id="ticket.id" id="issue-reopen-evidence" />
    <p v-if="error" role="alert" class="text-xs text-error">{{ error }}</p>
    <BaseButton variant="accent" type="submit" :disabled="busy || !content.trim()">{{ t(busy ? 'platformIssues.sending' : 'platformIssues.reopenSubmit') }}</BaseButton>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { usePlatformBugReportsStore } from '~/stores/platform-bug-reports'
import IssueEvidenceFields from './IssueEvidenceFields.vue'
const props = defineProps({ ticket: { type: Object, required: true }, projectId: { type: [Number, String], required: true } })
const emit = defineEmits(['updated'])
const { t } = useI18n()
const store = usePlatformBugReportsStore()
const content = ref('')
const evidence = ref({ document_ids: [] })
const busy = ref(false)
const error = ref('')
let retry = null
async function submit() {
  if (busy.value) return
  if (!content.value.trim()) { error.value = t('platformIssues.messageRequired'); return }
  busy.value = true
  const payload = { content: content.value.trim(), document_ids: evidence.value.document_ids, expected_version: props.ticket.version }
  const fingerprint = JSON.stringify(payload)
  if (retry?.fingerprint !== fingerprint) retry = { fingerprint, requestId: crypto.randomUUID() }
  const result = await store.reopenBugReport(props.projectId, props.ticket.id, { ...payload, request_id: retry.requestId })
  busy.value = false
  if (result.success) emit('updated', result.data)
  else error.value = result.message
}
</script>
