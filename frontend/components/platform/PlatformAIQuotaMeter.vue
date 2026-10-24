<script setup>
import { computed } from 'vue'
const props = defineProps({ quota: { type: Object, default: null } })
const { t, locale } = useI18n()
const nextAt = computed(() => props.quota?.next_available_at ? new Date(props.quota.next_available_at).toLocaleString(locale.value) : '')
</script>

<template>
  <div v-if="quota" class="space-y-1 text-sm text-text-muted" data-testid="platform-ai-quota" data-tour="ai-quota" aria-live="polite">
    <p>{{ t('platformAI.quotaSummary', { used: quota.used, limit: quota.limit, remaining: quota.remaining }) }}</p>
    <progress :value="Math.min(quota.used, quota.limit)" :max="quota.limit" class="h-2 w-full accent-primary" :aria-label="t('platformAI.quotaLabel')" />
    <p>{{ t('platformAI.quotaWindow', { minutes: quota.window_minutes }) }} <span v-if="nextAt">{{ t('platformAI.quotaNext', { date: nextAt }) }}</span></p>
    <p v-if="quota.remaining === 0" class="text-danger-strong">{{ t('platformAI.quotaEmpty') }}</p>
  </div>
</template>
