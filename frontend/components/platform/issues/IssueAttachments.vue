<template>
  <div v-if="attachments.length" class="mt-2 space-y-1">
    <BaseButton v-for="item in attachments" :key="item.id" variant="ghost" size="sm" :disabled="busy === item.id" @click="download(item)">{{ t('platformIssues.download', { title: item.title }) }}</BaseButton>
    <p v-if="error" role="alert" class="text-xs text-error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { usePlatformApi } from '~/composables/usePlatformApi'
defineProps({ attachments: { type: Array, default: () => [] } })
const { t } = useI18n()
const busy = ref(null)
const error = ref('')
async function download(item) {
  busy.value = item.id
  error.value = ''
  try {
    const { get } = usePlatformApi()
    const response = await get(`issue-reports/attachments/${item.id}/`, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${item.title}.pdf`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch {
    error.value = t('platformIssues.downloadError')
  } finally {
    busy.value = null
  }
}
</script>
