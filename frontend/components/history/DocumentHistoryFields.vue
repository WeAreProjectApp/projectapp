<script setup>
import { useI18n } from '#imports';
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import HistoryValue from './HistoryValue.vue';

defineProps({ groups: { type: Array, default: () => [] }, full: Boolean, labels: { type: Object, default: () => ({}) } });
const { t } = useI18n();
</script>

<template>
  <component
    :is="group.key === 'technical' ? 'details' : 'section'"
    v-for="group in groups" :key="group.key"
    class="min-w-0 space-y-3 rounded-lg border border-border-muted p-3"
    :data-testid="`history-group-${group.key}`"
  >
    <component :is="group.key === 'technical' ? 'summary' : 'h4'" class="text-sm font-semibold" :class="{ 'cursor-pointer': group.key === 'technical' }">
      {{ t(`documentHistory.groups.${group.key}`) }}
      <span class="font-normal text-text-muted">({{ group.values.length }})</span>
    </component>
    <div v-for="field in group.values" :key="field.key" class="min-w-0 space-y-2 border-t border-border-muted pt-2">
      <p class="text-sm font-medium">{{ field.label }}</p>
      <p v-if="field.formatOnly && !full" class="text-xs text-text-muted">{{ t('documentHistory.formatChange') }}</p>
      <template v-for="side in full ? ['next'] : ['old', 'next']" :key="side">
        <div class="min-w-0 rounded-lg p-3" :class="full ? 'bg-surface' : side === 'old' ? 'bg-danger-soft' : 'bg-success-soft'">
          <p v-if="!full" class="mb-2 text-xs font-semibold" :class="side === 'old' ? 'text-danger-strong' : 'text-success-strong'">
            {{ side === 'old' ? '− ' + t('documentHistory.before') : '+ ' + t('documentHistory.after') }}
          </p>
          <BaseRichTextContent
            v-if="typeof field[side]?.value === 'string' && field[side].format !== 'plain'"
            :source="field[side].value" :format="field[side].format"
          />
          <HistoryValue v-else :value="field[side]?.value ?? null" :labels="labels" />
        </div>
      </template>
    </div>
  </component>
</template>
