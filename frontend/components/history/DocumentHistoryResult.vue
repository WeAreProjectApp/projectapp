<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import DocumentMarkdownBody from '~/components/panel/documents/DocumentMarkdownBody.vue';
import { documentContentDiff, historicalContent } from '~/utils/documentHistoryContent';
import { documentFieldGroups } from '~/utils/documentHistoryFields';
import DocumentHistoryFields from './DocumentHistoryFields.vue';

const props = defineProps({ active: { type: Object, required: true }, full: Boolean, objectId: { type: [Number, String], required: true } });
const { t, te } = useI18n();
const to = computed(() => props.active.to);
const before = computed(() => props.active.from?.snapshot || {});
const after = computed(() => to.value.snapshot || {});
const isReading = computed(() => props.full || !props.active.from);
const content = computed(() => isReading.value ? historicalContent(after.value) : documentContentDiff(before.value, after.value));
const groups = computed(() => documentFieldGroups(before.value, after.value, { labels: to.value.labels, t, te, full: isReading.value }));
const unchanged = computed(() => !isReading.value && !content.value.hunks.length && !groups.value.length);
const pdfUrl = computed(() => `/api/entity-history/document/${props.objectId}/versions/${to.value.id}/file/`);
const hasFile = computed(() => after.value.uploaded_pdf || after.value.generated_file);
</script>

<template>
  <div class="min-w-0 space-y-4" data-testid="history-result-content">
    <p v-if="!to.complete" class="rounded-lg bg-surface-raised p-3 text-sm text-text-muted">{{ t('documentHistory.incomplete') }}</p>
    <template v-else>
      <p v-if="!active.from && !full" class="text-sm text-text-muted">{{ t('documentHistory.initial') }}</p>
      <p v-if="content.pdf" class="rounded-lg bg-surface-raised p-3 text-sm text-text-muted">{{ t('documentHistory.pdfNotice') }}</p>
      <p v-if="content.unsupported" role="status" class="text-sm text-text-muted">{{ t('documentHistory.unsupported') }}</p>
      <p v-if="content.simplified" role="status" class="text-sm text-text-muted">{{ t('documentHistory.simplified') }}</p>
      <p v-if="unchanged" role="status" class="rounded-lg bg-surface-raised p-4 text-sm text-text-muted" data-testid="history-no-changes">{{ t('documentHistory.noChanges') }}</p>
      <section v-if="isReading && content.blocks.length" class="min-w-0 space-y-3" data-testid="history-full-content">
        <h4 class="text-sm font-semibold">{{ t('documentHistory.groups.content') }}</h4>
        <DocumentMarkdownBody :markdown="content.html" format="markdown_html_v1" />
      </section>
      <p v-else-if="isReading && !content.pdf" class="text-sm text-text-muted">{{ t('documentHistory.emptyContent') }}</p>
      <section v-if="!isReading && content.hunks.length" class="min-w-0 space-y-4" data-testid="history-rich-diff">
        <h4 class="text-sm font-semibold">{{ t('documentHistory.groups.content') }}</h4>
        <article v-for="(hunk, index) in content.hunks" :key="index" class="min-w-0 overflow-hidden rounded-lg border border-border-muted">
          <h5 class="bg-surface-raised px-3 py-2 text-sm font-medium">{{ hunk.blocks.find(block => block.kind !== 'context')?.item.section || t('documentHistory.groups.content') }}</h5>
          <p v-if="hunk.formatOnly" class="px-3 py-2 text-xs text-text-muted">{{ t('documentHistory.formatChange') }}</p>
          <div v-for="(block, blockIndex) in hunk.blocks" :key="blockIndex" class="min-w-0 p-3" :class="block.kind === 'removed' ? 'bg-danger-soft' : block.kind === 'added' ? 'bg-success-soft' : 'bg-surface'" :data-history-change="block.kind">
            <p class="mb-2 text-xs font-semibold" :class="block.kind === 'removed' ? 'text-danger-strong' : block.kind === 'added' ? 'text-success-strong' : 'text-text-muted'">
              {{ block.kind === 'removed' ? '− ' + t('documentHistory.removed') : block.kind === 'added' ? '+ ' + t('documentHistory.added') : t('documentHistory.context') }}
            </p>
            <DocumentMarkdownBody :markdown="block.item.html" format="markdown_html_v1" />
          </div>
        </article>
      </section>
      <DocumentHistoryFields :groups="groups" :full="isReading" :labels="to.labels" />
      <BaseButton v-if="hasFile" as="a" :to="pdfUrl" target="_blank" rel="noopener noreferrer" variant="secondary" size="sm">{{ t('documentHistory.openPdf') }}</BaseButton>
    </template>
  </div>
</template>

<style scoped>
:deep(.md-table) { display: block; max-width: 100%; overflow-x: auto; }
:deep(.md-code-block) { max-width: 100%; }
</style>
