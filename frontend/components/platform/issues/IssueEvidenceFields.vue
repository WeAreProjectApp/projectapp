<template>
  <div class="space-y-3">
    <p v-if="loading" class="text-xs text-text-muted">{{ t('platformIssues.loading') }}</p>
    <p v-if="error" role="alert" class="text-xs text-danger-strong">{{ error }}</p>
    <div v-if="admin">
      <label :for="`${id}-contract`" class="mb-1 block text-xs text-text-muted">{{ t('platformIssues.contract') }}</label>
      <select :id="`${id}-contract`" :value="modelValue.contract_id ?? ''" class="w-full rounded-xl border border-border-default bg-surface px-3 py-2 text-sm text-text-default" @change="selectContract">
        <option value="">{{ t('platformIssues.noContract') }}</option>
        <option v-for="contract in options.contracts" :key="contract.id" :value="contract.id">{{ contract.title }}</option>
      </select>
    </div>
    <fieldset class="space-y-1" :disabled="loading">
      <legend class="mb-1 text-xs font-medium text-text-muted">{{ t('platformIssues.documents') }}</legend>
      <label v-for="doc in options.documents" :key="doc.id" class="flex items-center gap-2 text-xs text-text-default">
        <input type="checkbox" :checked="modelValue.document_ids?.includes(doc.id)" @change="toggleDocument(doc.id, $event.target.checked)" />{{ doc.title }}
      </label>
      <p v-if="!options.documents?.length && !loading" class="text-xs text-text-muted">{{ t('platformIssues.noDocuments') }}</p>
    </fieldset>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { usePlatformIssueReportsStore } from '~/stores/platform-issue-reports'
const props = defineProps({ modelValue: { type: Object, required: true }, projectId: { type: [String, Number], required: true }, kind: { type: String, required: true }, ticketId: { type: Number, required: true }, admin: Boolean, id: { type: String, default: 'issue-evidence' } })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const store = usePlatformIssueReportsStore()
const loading = ref(false)
const error = ref('')
const options = ref({ contracts: [], documents: [] })
let generation = 0
async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  const result = await store.contextOptions(props.projectId, { kind: props.kind, ticket_id: props.ticketId, ...(props.modelValue.contract_id ? { contract_id: props.modelValue.contract_id } : {}) })
  if (current !== generation) return
  loading.value = false
  if (result.success) options.value = result.data
  else error.value = result.message
}
function selectContract(event) {
  emit('update:modelValue', { ...props.modelValue, contract_id: event.target.value ? Number(event.target.value) : null, document_ids: [] })
}
function toggleDocument(id, checked) {
  const selected = props.modelValue.document_ids || []
  emit('update:modelValue', { ...props.modelValue, document_ids: checked ? [...selected, id] : selected.filter((item) => item !== id) })
}
watch(() => [props.projectId, props.ticketId, props.modelValue.contract_id], load, { immediate: true })
</script>
