<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseInput from '~/components/base/BaseInput.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import PlatformSecureLinkForm from './PlatformSecureLinkForm.vue'
import PlatformSecureLinkDetail from './PlatformSecureLinkDetail.vue'
import { usePlatformSecureLinksStore } from '~/stores/platform-secure-links'
import { usePlatformAuthStore } from '~/stores/platform-auth'

const props = defineProps({ projectId: { type: Number, required: true } })
const store = usePlatformSecureLinksStore()
const auth = usePlatformAuthStore()
const { t } = useI18n()
const search = ref('')
const status = ref('')
const creating = ref(false)
const selected = ref(null)
const replaces = ref(null)
const catalogError = ref(false)
async function refresh(page = store.page) {
  if (auth.isClient) await store.fetchLinks(props.projectId, { page, search: search.value, ...(status.value ? { status: status.value } : {}) })
}
async function load() {
  creating.value = false; selected.value = null; replaces.value = null
  store.clear()
  if (!auth.isClient) return
  await refresh(1)
  const result = await store.fetchTypes()
  catalogError.value = !result.success
}
watch(() => props.projectId, load, { immediate: true })
watch(() => [auth.isClient, auth.user?.id], load)
onBeforeUnmount(() => store.clear())
function replace(link) { selected.value = null; replaces.value = link; creating.value = true }
function closeForm() { creating.value = false; replaces.value = null }
</script>

<template>
  <section class="min-w-0 space-y-5" data-testid="platform-secure-workspace">
    <h2 class="text-xl font-semibold text-text-default">{{ t('platformSecureLinks.title') }}</h2>
    <BaseAlert v-if="!auth.isClient" variant="info">{{ t('platformSecureLinks.clientOnly') }}</BaseAlert>
    <template v-else>
      <p class="text-sm text-text-muted">{{ t('platformSecureLinks.teamOnly') }}</p>
      <p class="text-sm text-text-muted">{{ t('platformSecureLinks.noFiles') }}</p>
      <BaseAlert v-if="catalogError" variant="danger">{{ t('platformSecureLinks.errors.failed') }} <BaseButton variant="ghost" @click="load">{{ t('platformSecureLinks.retry') }}</BaseButton></BaseAlert>
      <BaseButton v-if="store.types.length" data-testid="platform-secure-new" @click="creating = true">{{ t('platformSecureLinks.create') }}</BaseButton>
      <form class="flex flex-wrap items-end gap-3" @submit.prevent="refresh(1)">
        <BaseFormField class="min-w-0 flex-1" :label="t('platformSecureLinks.search')" for="platform-secure-search">
          <BaseInput id="platform-secure-search" v-model="search" maxlength="160" data-testid="platform-secure-search" />
        </BaseFormField>
        <BaseFormField :label="t('platformSecureLinks.state')" for="platform-secure-state">
          <BaseSelect id="platform-secure-state" v-model="status" :options="['', 'active', 'consumed', 'expired', 'revoked'].map(value => ({ value, label: t(`platformSecureLinks.status.${value || 'all'}`) }))" />
        </BaseFormField>
        <BaseButton type="submit" variant="secondary" :loading="store.loading" data-testid="platform-secure-filter">{{ t('platformSecureLinks.filter') }}</BaseButton>
      </form>
      <BaseAlert v-if="store.error" variant="danger" data-testid="platform-secure-list-error">{{ t(`platformSecureLinks.errors.${store.error}`) }} <BaseButton variant="ghost" @click="refresh(store.page)">{{ t('platformSecureLinks.retry') }}</BaseButton></BaseAlert>
      <p v-if="!store.loading && !store.links.length" class="text-sm text-text-muted" data-testid="platform-secure-empty">{{ t('platformSecureLinks.empty') }}</p>
      <ul class="space-y-3" data-testid="platform-secure-list">
        <li v-for="link in store.links" :key="link.id" class="rounded-xl border border-border-default p-4" :data-testid="`platform-secure-row-${link.id}`">
          <div class="flex min-w-0 flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1 break-words">
              <h3 class="font-semibold text-text-default">{{ link.title }}</h3>
              <p class="mt-1 text-sm text-text-muted">{{ link.type_label }} · {{ t(`platformSecureLinks.status.${link.status}`) }}</p>
              <p class="mt-1 text-sm text-text-muted">{{ t('platformSecureLinks.expires') }}: {{ link.expires_at }}</p>
            </div>
            <BaseButton variant="secondary" :data-testid="`platform-secure-manage-${link.id}`" @click="selected = link">{{ t('platformSecureLinks.manage') }}</BaseButton>
          </div>
        </li>
      </ul>
      <div class="flex flex-wrap gap-3">
        <BaseButton v-if="store.page > 1" variant="ghost" @click="refresh(store.page - 1)">{{ t('platformSecureLinks.previous') }}</BaseButton>
        <BaseButton v-if="store.page * 25 < store.count" variant="ghost" @click="refresh(store.page + 1)">{{ t('platformSecureLinks.next') }}</BaseButton>
      </div>
      <PlatformSecureLinkForm v-if="creating" :replaces="replaces" @close="closeForm" @created="refresh(1)" />
      <PlatformSecureLinkDetail v-if="selected" :key="selected.id" :link="selected" @close="selected = null" @updated="refresh" @replace="replace" />
    </template>
  </section>
</template>
