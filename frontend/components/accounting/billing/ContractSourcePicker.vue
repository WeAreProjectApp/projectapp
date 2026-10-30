<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue'
import { MagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseFloatingListbox from '~/components/base/BaseFloatingListbox.vue'
import { INPUT_FIELD_BASE } from '~/components/base/inputClasses'
import { contractSourceKey, contractSourceParts, normalizeContractSource } from '~/utils/contractSourceSearch'

const props = defineProps({
  modelValue: { type: String, default: '' },
  sources: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const owner = ref(null)
const input = ref(null)
const open = ref(false)
const composing = ref(false)
const query = ref('')
const activeIndex = ref(-1)
const listboxId = `${useId()}-contract-sources`
const dateFormatter = new Intl.DateTimeFormat('es-CO', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota',
})
const selected = computed(() => props.sources.find(source => contractSourceKey(source) === props.modelValue))
const indexedSources = computed(() => props.sources.map(source => ({
  source, key: contractSourceKey(source), normalized: normalizeContractSource(source.title),
})))
const results = computed(() => {
  const needle = normalizeContractSource(query.value)
  const filtered = indexedSources.value.filter(row => row.normalized.includes(needle))
  return [true, false].flatMap(contractLike => filtered.filter(row => Boolean(row.source.is_contract_like) === contractLike))
    .map((row, index) => ({ ...row, index, parts: contractSourceParts(row.source.title, query.value) }))
})
const groups = computed(() => [
  { title: 'Contratos y otrosíes', contractLike: true },
  { title: 'Otros documentos del proyecto', contractLike: false },
].map(group => ({
  ...group, rows: results.value.filter(row => Boolean(row.source.is_contract_like) === group.contractLike),
})).filter(group => group.rows.length))
const activeId = computed(() => open.value && activeIndex.value >= 0 ? `${listboxId}-${activeIndex.value}` : undefined)

function close() { open.value = false; query.value = ''; composing.value = false; activeIndex.value = -1 }
function show() { if (!props.disabled && !composing.value) open.value = true }
function search(value) { query.value = value; show(); activeIndex.value = results.value.length ? 0 : -1 }
function choose(source) { emit('update:modelValue', contractSourceKey(source)); close() }
function clear() { emit('update:modelValue', ''); query.value = ''; activeIndex.value = -1; input.value?.focus(); show() }
async function move(direction) {
  show()
  const count = results.value.length
  if (!count) return
  activeIndex.value = activeIndex.value < 0 ? (direction > 0 ? 0 : count - 1) : (activeIndex.value + direction + count) % count
  await nextTick()
  document.getElementById(activeId.value)?.scrollIntoView?.({ block: 'nearest' })
}
function enter() {
  if (!open.value) { show(); return }
  const row = results.value[activeIndex.value]
  if (row) choose(row.source)
}
function beginComposition() {
  composing.value = true
  // Hide the app popup while the native IME owns the keyboard (including Esc).
  open.value = false
  activeIndex.value = -1
}
function endComposition(event) { composing.value = false; search(event.target.value) }
function onKeydown(event) {
  if (composing.value || event.isComposing || event.keyCode === 229) {
    event.stopPropagation()
    return
  }
  if (event.key === 'Tab') { close(); return }
  if (!['ArrowDown', 'ArrowUp', 'Enter', 'Escape'].includes(event.key)) return
  event.preventDefault()
  if (event.key === 'ArrowDown') move(1)
  else if (event.key === 'ArrowUp') move(-1)
  else if (event.key === 'Enter') enter()
  else { event.stopPropagation(); close() }
}
function dateLabel(value) {
  if (!value) return 'Fecha no disponible'
  if (Number.isNaN(new Date(value).getTime())) return 'Fecha no disponible'
  return dateFormatter.format(new Date(value))
}
function location(source) { return source.proposal_title ? `Propuesta: ${source.proposal_title}` : source.folder_path || 'Sin carpeta' }
watch(() => props.sources, close)
watch(() => props.disabled, value => { if (value) close() })
watch(() => props.modelValue, () => { if (!open.value) query.value = '' })
</script>

<template>
  <div ref="owner" class="relative min-w-0">
    <MagnifyingGlassIcon aria-hidden="true" class="pointer-events-none absolute left-3 top-3 h-4 w-4 text-text-subtle" />
    <input
      ref="input"
      type="text"
      role="combobox"
      aria-label="Contrato existente del proyecto"
      aria-autocomplete="list"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-controls="open ? listboxId : undefined"
      :aria-activedescendant="activeId"
      :value="open || composing ? query : selected?.title || ''"
      :disabled="disabled"
      :title="disabled ? 'Espera a que termine la vinculación del documento.' : undefined"
      :class="[INPUT_FIELD_BASE, 'py-2.5 pl-9 pr-10 text-sm']"
      placeholder="Buscar documento…"
      autocomplete="off"
      data-testid="billing-link-contract-source"
      @focus="show"
      @click="show"
      @input="search($event.target.value)"
      @compositionstart="beginComposition"
      @compositionend="endComposition"
      @keydown="onKeydown"
      @blur="close"
    >
    <BaseButton
      v-if="!disabled && (modelValue || query)"
      unstyled icon-only type="button"
      class="absolute right-0 top-0 flex h-full items-center px-3 text-text-subtle hover:text-text-default"
      aria-label="Quitar documento seleccionado"
      title="Quitar documento seleccionado"
      data-testid="billing-link-contract-source-clear"
      @mousedown.prevent
      @click="clear"
    ><BaseActionIcon action="clear" /></BaseButton>
    <BaseFloatingListbox :id="listboxId" :open="open" :anchor="input" :owner="owner" aria-label="Documentos del proyecto" @close="close">
      <div v-for="(group, groupIndex) in groups" :key="group.title" role="group" :aria-labelledby="`${listboxId}-group-${groupIndex}`">
        <p :id="`${listboxId}-group-${groupIndex}`" class="border-b border-border-muted px-4 py-2 text-xs font-semibold text-text-muted">{{ group.title }}</p>
        <div
          v-for="row in group.rows" :id="`${listboxId}-${row.index}`" :key="row.key"
          role="option" :aria-selected="row.key === modelValue"
          :data-testid="`billing-contract-source-option-${row.key}`"
          :class="['cursor-pointer break-words px-4 py-2.5 text-sm', activeIndex === row.index ? 'bg-primary-soft' : 'hover:bg-surface-raised']"
          @mousedown.prevent
          @mouseenter="activeIndex = row.index"
          @click="choose(row.source)"
        >
          <p class="text-text-default"><template v-for="(part, index) in row.parts" :key="index"><mark v-if="part.match" class="rounded bg-primary-soft font-semibold text-text-brand">{{ part.text }}</mark><span v-else>{{ part.text }}</span></template></p>
          <p class="text-xs text-text-muted">{{ dateLabel(row.source.created_at) }} · {{ location(row.source) }}</p>
          <p class="text-xs text-text-subtle">{{ row.source.origin_label }}</p>
        </div>
      </div>
      <p v-if="!results.length" role="status" class="px-4 py-3 text-sm text-text-muted">Sin coincidencias. Prueba con otra parte del nombre.</p>
    </BaseFloatingListbox>
  </div>
</template>
