<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from '#imports';
import type { Editor } from '@tiptap/vue-3';
import {
  BoldIcon, ItalicIcon, UnderlineIcon, StrikethroughIcon, ListBulletIcon,
  NumberedListIcon, CodeBracketIcon, LinkIcon, TableCellsIcon,
  Bars3BottomLeftIcon, Bars3CenterLeftIcon, Bars3BottomRightIcon, Bars3Icon,
  ChatBubbleLeftRightIcon, ArrowUturnLeftIcon, ArrowUturnRightIcon,
} from '@heroicons/vue/24/outline';
import BaseButton from './BaseButton.vue';
import BaseActionMenu from './BaseActionMenu.vue';

const props = defineProps<{ editor: Editor | null; revision: number; disabled: boolean }>();
const emit = defineEmits<{
  run: [command: string, argument?: unknown];
  link: [];
  insert: [source: string];
  callout: [kind: string];
  clear: [];
}>();
const { t } = useI18n();
const blocked = computed(() => props.disabled || !props.editor);
const active = (name: string | Record<string, unknown>) => {
  void props.revision;
  return props.editor?.isActive(name) || false;
};
const attribute = (name: string, key: string) => {
  void props.revision;
  return props.editor?.getAttributes(name)[key];
};
const heading = computed(() => attribute('heading', 'level') || 'p');
const availability: Record<string, () => boolean | undefined> = {
  sinkListItem: () => props.editor?.can().sinkListItem('listItem'),
  liftListItem: () => props.editor?.can().liftListItem('listItem'),
  addRowAfter: () => props.editor?.can().addRowAfter(),
  deleteRow: () => props.editor?.can().deleteRow(),
  addColumnAfter: () => props.editor?.can().addColumnAfter(),
  deleteColumn: () => props.editor?.can().deleteColumn(),
  toggleHeaderRow: () => props.editor?.can().toggleHeaderRow(),
  mergeCells: () => props.editor?.can().mergeCells(),
  splitCell: () => props.editor?.can().splitCell(),
  deleteTable: () => props.editor?.can().deleteTable(),
};
function can(command: string) {
  void props.revision;
  return !blocked.value && (availability[command]?.() ?? true);
}
function reason(command: string) {
  return props.disabled ? t('richText.readOnly') : can(command)
    ? '' : t(command === 'mergeCells' ? 'richText.selectCells' : 'richText.contextSelection');
}
const textTools = [
  { name: 'bold', command: 'toggleBold', icon: BoldIcon },
  { name: 'italic', command: 'toggleItalic', icon: ItalicIcon },
  { name: 'underline', command: 'toggleUnderline', icon: UnderlineIcon },
  { name: 'strike', command: 'toggleStrike', icon: StrikethroughIcon },
  { name: 'code', command: 'toggleCode', icon: CodeBracketIcon },
];
const paragraphTools = [
  { name: 'bulletList', command: 'toggleBulletList', icon: ListBulletIcon },
  { name: 'orderedList', command: 'toggleOrderedList', icon: NumberedListIcon },
  { name: 'blockquote', command: 'toggleBlockquote', icon: ChatBubbleLeftRightIcon },
];
const alignments = [
  { name: 'left', icon: Bars3BottomLeftIcon }, { name: 'center', icon: Bars3CenterLeftIcon },
  { name: 'right', icon: Bars3BottomRightIcon }, { name: 'justify', icon: Bars3Icon },
];
const tableCommands = ['addRowAfter', 'addColumnAfter', 'toggleHeaderRow', 'mergeCells', 'splitCell', 'deleteRow', 'deleteColumn', 'deleteTable'];
const callouts = ['NOTE', 'TIP', 'IMPORTANT', 'WARNING', 'CAUTION'];
const insertItems = computed(() => [
  { label: t('richText.table'), onClick: () => emit('run', 'insertTable', { rows: 3, cols: 3, withHeaderRow: true }) },
  { label: t('richText.codeBlock'), onClick: () => emit('run', 'toggleCodeBlock') },
  { label: t('richText.separator'), onClick: () => emit('run', 'setHorizontalRule') },
  { label: t('richText.toc'), onClick: () => emit('insert', '[TOC]\n\n') },
  ...callouts.map(kind => ({ label: t(`richText.callout${kind}`), onClick: () => emit('callout', kind) })),
]);
function colorInput(name: string, key: string, fallback: number[]) {
  const value = attribute(name, key) || '';
  const channels = value.match(/\d+/g)?.map(Number) || fallback;
  return '#' + channels.slice(0, 3).map((part: number) => part.toString(16).padStart(2, '0')).join('');
}
const inputValue = (event: Event) => (event.target as HTMLInputElement).value;
</script>

<template>
  <div class="border-b border-border-default bg-surface p-2" data-testid="document-format-toolbar" role="toolbar" :aria-label="t('richText.formatting')">
    <div class="flex flex-wrap items-center gap-2">
      <div class="flex flex-wrap items-center gap-1" role="group" :aria-label="t('richText.textGroup')">
        <span class="w-full px-1 text-xs font-medium text-text-subtle">{{ t('richText.textGroup') }}</span>
        <BaseButton v-for="tool in textTools" :key="tool.name" variant="ghost" size="sm" icon-only :aria-label="t(`richText.${tool.name}`)" :title="t(`richText.${tool.name}`)" :aria-pressed="active(tool.name)" :disabled="blocked" :disabled-reason="t('richText.readOnly')" :class="{ 'bg-surface-raised': active(tool.name) }" @mousedown.prevent @click="emit('run', tool.command)">
          <component :is="tool.icon" class="h-5 w-5" aria-hidden="true" />
        </BaseButton>
        <BaseButton variant="ghost" size="sm" icon-only :aria-label="t('richText.link')" :title="t('richText.link')" :aria-pressed="active('link')" :disabled="blocked" :disabled-reason="t('richText.readOnly')" @mousedown.prevent @click="emit('link')"><LinkIcon class="h-5 w-5" aria-hidden="true" /></BaseButton>
      </div>
      <div class="flex flex-wrap items-center gap-1" role="group" :aria-label="t('richText.paragraphGroup')">
        <span class="w-full px-1 text-xs font-medium text-text-subtle">{{ t('richText.paragraphGroup') }}</span>
        <select :value="heading" class="min-h-11 max-w-full rounded-lg border border-border-default bg-input-bg px-2 text-sm text-input-text" :aria-label="t('richText.heading')" :disabled="blocked" :title="disabled ? t('richText.readOnly') : t('richText.heading')" @change="emit('run', inputValue($event) === 'p' ? 'setParagraph' : 'setHeading', inputValue($event) === 'p' ? undefined : { level: Number(inputValue($event)) })">
          <option value="p">{{ t('richText.paragraph') }}</option>
          <option v-for="level in [1, 2, 3, 4, 5, 6]" :key="level" :value="level">{{ t('richText.headingLevel', { level }) }}</option>
        </select>
        <BaseButton v-for="tool in paragraphTools" :key="tool.name" variant="ghost" size="sm" icon-only :aria-label="t(`richText.${tool.name}`)" :title="t(`richText.${tool.name}`)" :aria-pressed="active(tool.name)" :disabled="blocked" :disabled-reason="t('richText.readOnly')" :class="{ 'bg-surface-raised': active(tool.name) }" @mousedown.prevent @click="emit('run', tool.command)"><component :is="tool.icon" class="h-5 w-5" aria-hidden="true" /></BaseButton>
        <BaseButton v-for="tool in [{ name: 'outdent', command: 'liftListItem', icon: ArrowUturnLeftIcon }, { name: 'indent', command: 'sinkListItem', icon: ArrowUturnRightIcon }]" :key="tool.name" variant="ghost" size="sm" icon-only :aria-label="t(`richText.${tool.name}`)" :title="t(`richText.${tool.name}`)" :disabled="!can(tool.command)" :disabled-reason="disabled ? t('richText.readOnly') : t('richText.listSelection')" @mousedown.prevent @click="emit('run', tool.command, 'listItem')"><component :is="tool.icon" class="h-5 w-5" aria-hidden="true" /></BaseButton>
      </div>
      <div class="flex flex-wrap items-center gap-1" role="group" :aria-label="t('richText.alignmentGroup')">
        <span class="w-full px-1 text-xs font-medium text-text-subtle">{{ t('richText.alignmentGroup') }}</span>
        <BaseButton v-for="alignment in alignments" :key="alignment.name" variant="ghost" size="sm" icon-only :aria-label="t(`richText.${alignment.name}`)" :title="t(`richText.${alignment.name}`)" :aria-pressed="active({ textAlign: alignment.name })" :disabled="blocked" :disabled-reason="t('richText.readOnly')" :class="{ 'bg-surface-raised': active({ textAlign: alignment.name }) }" @mousedown.prevent @click="emit('run', 'setTextAlign', alignment.name)"><component :is="alignment.icon" class="h-5 w-5" aria-hidden="true" /></BaseButton>
      </div>
    </div>
    <div class="mt-2 flex flex-wrap items-center gap-2 border-t border-border-default pt-2">
      <label class="flex min-h-11 items-center gap-2 rounded-lg border border-border-default px-2 text-xs" :title="disabled ? t('richText.readOnly') : t('richText.color')">
        {{ t('richText.color') }}<input type="color" class="h-8 w-8 cursor-pointer bg-transparent" :value="colorInput('textStyle', 'color', [0, 0, 0])" :aria-label="t('richText.color')" :disabled="blocked" :title="disabled ? t('richText.readOnly') : t('richText.color')" @input="emit('run', 'setColor', inputValue($event))" />
      </label>
      <BaseButton variant="ghost" size="sm" :disabled="blocked || !attribute('textStyle', 'color')" :disabled-reason="disabled ? t('richText.readOnly') : t('richText.noColor')" @click="emit('run', 'unsetColor')">{{ t('richText.removeColor') }}</BaseButton>
      <label class="flex min-h-11 items-center gap-2 rounded-lg border border-border-default px-2 text-xs" :title="disabled ? t('richText.readOnly') : t('richText.highlight')">
        {{ t('richText.highlight') }}<input type="color" class="h-8 w-8 cursor-pointer bg-transparent" :value="colorInput('highlight', 'color', [255, 245, 157])" :aria-label="t('richText.highlight')" :disabled="blocked" :title="disabled ? t('richText.readOnly') : t('richText.highlight')" @input="emit('run', 'setHighlight', { color: inputValue($event) })" />
      </label>
      <BaseButton variant="ghost" size="sm" :disabled="blocked || !active('highlight')" :disabled-reason="disabled ? t('richText.readOnly') : t('richText.noHighlight')" @click="emit('run', 'unsetHighlight')">{{ t('richText.removeHighlight') }}</BaseButton>
      <BaseButton variant="ghost" size="sm" :disabled="blocked" :disabled-reason="t('richText.readOnly')" @click="emit('clear')">{{ t('richText.clear') }}</BaseButton>
      <div class="ml-auto shrink-0">
        <BaseActionMenu :label="t('richText.insert')" :items="insertItems" :disabled="blocked" :disabled-reason="t('richText.readOnly')" align="right" testid="document-insert-menu" />
      </div>
    </div>
    <div v-if="active('table')" class="mt-2 flex flex-wrap items-center gap-1 rounded-lg bg-surface-raised p-2" role="group" :aria-label="t('richText.tableGroup')">
      <span class="flex items-center gap-1 px-1 text-xs font-medium"><TableCellsIcon class="h-4 w-4" aria-hidden="true" />{{ t('richText.tableGroup') }}</span>
      <BaseButton v-for="command in tableCommands" :key="command" :variant="command.startsWith('delete') ? 'danger-ghost' : 'ghost'" size="sm" :disabled="!can(command)" :disabled-reason="reason(command)" @mousedown.prevent @click="emit('run', command)">{{ t(`richText.${command}`) }}</BaseButton>
    </div>
    <label v-if="active('editorialCallout')" class="mt-2 flex flex-wrap items-center gap-2 text-xs">
      {{ t('richText.calloutType') }}
      <select class="min-h-11 rounded-lg border border-border-default bg-input-bg px-2 text-input-text" :value="attribute('editorialCallout', 'kind')" :disabled="blocked" :title="disabled ? t('richText.readOnly') : t('richText.calloutType')" @change="emit('callout', inputValue($event))">
        <option v-for="kind in callouts" :key="kind" :value="kind">{{ t(`richText.callout${kind}`) }}</option>
        <option value="">{{ t('richText.removeCallout') }}</option>
      </select>
    </label>
  </div>
</template>
