<template>
  <dl class="divide-y divide-border-default rounded-xl border border-border-default" data-testid="secure-link-content">
    <div
      v-for="field in fields"
      :key="field.key"
      class="flex min-w-0 flex-col gap-2 px-4 py-3 panel-portrait:flex-row panel-portrait:items-start panel-portrait:gap-4"
      :data-testid="`secure-link-value-${field.key}`"
    >
      <dt class="text-sm font-medium text-text-muted panel-portrait:w-44 panel-portrait:shrink-0">{{ field.label }}</dt>
      <dd class="flex min-w-0 flex-1 items-start gap-2">
        <span
          class="min-w-0 flex-1 whitespace-pre-wrap text-sm text-text-default [overflow-wrap:anywhere]"
          :class="{ 'font-mono': field.kind === 'secret' }"
          :data-testid="`secure-link-text-${field.key}`"
        >{{ isMasked(field) ? '••••••••' : field.value }}</span>
        <BaseActionButton
          v-if="field.kind === 'secret'"
          :action="shown[field.key] ? 'hide' : 'view'"
          :label="shown[field.key] ? t('secureLinks.fields.hide') : t('secureLinks.fields.show')"
          size="sm"
          :data-testid="`secure-link-reveal-${field.key}`"
          @click="shown[field.key] = !shown[field.key]"
        />
        <BaseActionButton
          action="copy"
          :label="t('secureLinks.fields.copy', { label: field.label })"
          :status-label="feedback(field).label"
          :status-tone="feedback(field).tone"
          size="sm"
          :data-testid="`secure-link-copy-${field.key}`"
          @click="copy(field)"
        />
      </dd>
    </div>
  </dl>
</template>

<script setup>
import { reactive } from 'vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';

/**
 * Displays revealed values. Secrets start masked; values live only in the
 * parent's ephemeral state and are never rendered as HTML.
 */
defineProps({
  fields: { type: Array, default: () => [] },
});
const { t } = useI18n();
const clipboard = useClipboardFeedback();
const shown = reactive({});

function isMasked(field) {
  return field.kind === 'secret' && !shown[field.key];
}

function feedback(field) {
  return clipboard.feedbackFor(`secure-link-${field.key}`);
}

function copy(field) {
  return clipboard.copyText({
    key: `secure-link-${field.key}`,
    text: field.value,
    successLabel: t('secureLinks.fields.copied'),
    errorLabel: t('secureLinks.copyFailed'),
  });
}
</script>
