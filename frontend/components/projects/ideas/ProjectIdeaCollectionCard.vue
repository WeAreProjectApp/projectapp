<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import { onBeforeUnmount, ref, watch } from 'vue'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
import { formatDateTime } from '~/utils/formatDate'
const props = defineProps({ collection: { type: Object, required: true }, api: { type: Object, required: true }, initialDetail: { type: Object, default: null } })
const { t } = useI18n()
const detail = ref(null)
const error = ref('')
const feedback = ref('')
const busy = ref(false)
let generation = 0
watch(() => [props.collection.id, props.initialDetail], () => {
  generation += 1
  detail.value = props.initialDetail?.id === props.collection.id ? props.initialDetail : null
  error.value = ''
  feedback.value = ''
  busy.value = false
}, { immediate: true })
async function load() {
  const current = ++generation
  busy.value = true
  error.value = ''
  try {
    const result = await props.api.collection(props.collection.id)
    if (current === generation) detail.value = result
  } catch (failure) { if (current === generation) error.value = normalizeApiError(failure).message }
  finally { if (current === generation) busy.value = false }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(detail.value.items.map((item) => `${item.author}\n${item.text}`).join('\n\n'))
    feedback.value = t('projectIdeas.copied')
  } catch { feedback.value = t('projectIdeas.copyError') }
}
onBeforeUnmount(() => { generation += 1 })
</script>

<template>
  <article class="space-y-3 rounded-xl border border-border-default p-4" data-testid="idea-collection">
    <h4 class="font-medium">{{ collection.title }}</h4>
    <p class="text-sm text-text-subtle">{{ collection.created_by }} · {{ formatDateTime(collection.created_at) }}</p>
    <p class="text-sm text-text-subtle">{{ t('projectIdeas.selected') }}: {{ collection.item_count }}</p>
    <BaseButton v-if="!detail" variant="secondary" size="md" textPolicy="wrap" class="min-h-11" :disabled="busy" type="button" data-testid="idea-collection-open" @click="load">{{ t('projectIdeas.viewCollection') }}</BaseButton>
    <p v-for="(item, position) in detail?.items || []" :key="position" class="whitespace-pre-wrap break-words text-sm">{{ item.author }}: {{ item.text }}</p>
    <BaseButton v-if="detail" variant="secondary" size="md" textPolicy="wrap" class="min-h-11" type="button" @click="copy">{{ t('projectIdeas.copy') }}</BaseButton>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="feedback" role="status">{{ feedback }}</p>
  </article>
</template>
