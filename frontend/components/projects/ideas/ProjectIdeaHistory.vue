<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import { onBeforeUnmount, ref, watch } from 'vue'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
import { formatDateTime } from '~/utils/formatDate'
const props = defineProps({ api: { type: Object, required: true }, ideaId: { type: Number, required: true } })
const emit = defineEmits(['close'])
const { t } = useI18n()
const revisions = ref([])
const count = ref(0)
const page = ref(1)
const error = ref('')
let generation = 0
async function load(selectedPage = 1) {
  const current = ++generation
  revisions.value = []
  error.value = ''
  try {
    const result = await props.api.revisions(props.ideaId, selectedPage)
    if (current !== generation) return
    revisions.value = result.results
    count.value = result.count
    page.value = result.page
  } catch (failure) { if (current === generation) error.value = normalizeApiError(failure).message }
}
watch(() => props.ideaId, () => load(), { immediate: true })
onBeforeUnmount(() => { generation += 1 })
</script>

<template>
  <section class="space-y-3 rounded-xl border border-border-default bg-surface-muted p-4" data-testid="project-idea-history">
    <div class="flex items-center justify-between gap-3">
      <h3 class="font-medium">{{ t('projectIdeas.revisions') }}</h3>
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" type="button" @click="emit('close')">{{ t('projectIdeas.close') }}</BaseButton>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <article v-for="revision in revisions" :key="revision.number" class="space-y-2 border-t border-border-muted py-3">
      <p class="text-sm text-text-subtle">{{ revision.editor }} · {{ formatDateTime(revision.created_at) }} · #{{ revision.number }}</p>
      <p class="whitespace-pre-wrap break-words text-sm">{{ revision.text }}</p>
    </article>
    <div v-if="count > 20" class="flex gap-3">
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="page > 1" type="button" @click="load(page - 1)">{{ t('projectIdeas.previous') }}</BaseButton>
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="page * 20 < count" type="button" @click="load(page + 1)">{{ t('projectIdeas.next') }}</BaseButton>
    </div>
  </section>
</template>
