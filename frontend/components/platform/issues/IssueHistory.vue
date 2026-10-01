<template>
  <div class="mb-5 space-y-4" data-testid="issue-history">
    <section class="rounded-xl border border-border-default p-3">
      <h3 class="text-xs font-semibold text-text-default">{{ t('platformIssues.original') }}</h3>
      <p v-if="context.origin_kind === 'published'" class="mt-1 break-words text-xs text-text-muted">{{ [context.contract_title, context.amendment_title, context.scope_title, context.phase_title, context.stage_title, context.requirement_title].filter(Boolean).join(' / ') }}</p>
      <p v-if="context.origin_kind === 'published'" class="mt-1 text-xs text-text-muted">{{ t('platformIssues.round', { round: context.publication_round, version: context.requirement_version }) }}</p>
      <p v-else class="mt-1 text-xs text-text-muted">{{ t(context.origin_kind === 'general' ? 'platformIssues.general' : 'platformIssues.legacy') }}</p>
    </section>
    <section v-if="ticket.responses?.length" class="space-y-2">
      <h3 class="text-xs font-semibold text-text-default">{{ t('platformIssues.responses') }}</h3>
      <article v-for="response in ticket.responses" :key="response.id" class="rounded-xl border border-border-default p-3">
        <p class="text-xs text-text-muted">{{ response.actor_name }} · {{ formatDate(response.created_at) }} <span v-if="response.is_internal">· {{ t('platformIssues.internal') }}</span></p>
        <p class="mt-1 whitespace-pre-wrap break-words text-sm text-text-default">{{ response.message }}</p>
        <p class="mt-1 text-xs text-text-muted" data-testid="issue-review-evidence">{{ t(`platformIssues.status.${response.status}`) }} · {{ t(`platformIssues.scope.${response.scope_result || 'indeterminate'}`) }}</p>
        <IssueAttachments :attachments="response.attachments" />
      </article>
    </section>
    <section v-if="ticket.history?.length" class="space-y-1">
      <h3 class="text-xs font-semibold text-text-default">{{ t('platformIssues.history') }}</h3>
      <p v-for="event in ticket.history" :key="event.id" class="text-xs text-text-muted">{{ t(`platformIssues.action.${event.action}`) }} · {{ t(`platformIssues.status.${event.status}`) }} · {{ formatDate(event.created_at) }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import IssueAttachments from './IssueAttachments.vue'
const props = defineProps({ ticket: { type: Object, required: true } })
const { t, locale } = useI18n()
const context = computed(() => props.ticket.origin_context || {})
function formatDate(value) { return new Date(value).toLocaleString(locale.value) }
</script>
