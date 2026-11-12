<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useProcurementStore } from '~/stores/procurement'
import { useProposalStore } from '~/stores/proposals'
import { PAGE_MAX_WIDTH } from '~/utils/tableLayout'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })
const { t, locale } = useI18n()
const tr = key => t(`procurement.${key}`)
const lp = useLocalePath()
const route = useRoute()
const store = useProcurementStore()
const auth = useProposalStore()
const state = ref('interesting')
const notes = ref('')
const loading = ref(false)
const error = ref('')
const saved = ref(false)
const mine = computed(() => store.detail?.classifications?.find(item => item.owner === auth.adminUser?.id))
const states = computed(() => ['interesting', 'reviewing', 'applied', 'discarded'].map(value => ({ value, label: tr(value) })))
const date = value => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota' }).format(new Date(value)) : tr('unknown')
async function load() {
  error.value = ''; loading.value = true; store.close()
  try { await store.open(route.params.id); state.value = mine.value?.state || 'interesting'; notes.value = mine.value?.notes || '' }
  catch { error.value = tr('loadError') }
  finally { loading.value = false }
}
async function save(restore = false) {
  error.value = ''; saved.value = false
  if (!restore && state.value === 'discarded' && !notes.value.trim()) { error.value = tr('reasonRequired'); return }
  try {
    if (restore) await store.restore(route.params.id)
    else await store.classify(route.params.id, { state: state.value, notes: notes.value })
    state.value = mine.value?.state || state.value; notes.value = mine.value?.notes || ''; saved.value = true
  } catch { error.value = tr('saveError') }
}
onMounted(load)
watch(() => route.params.id, load)
onBeforeUnmount(() => store.close())
</script>

<template>
  <div :class="PAGE_MAX_WIDTH" data-testid="procurement-detail">
    <NuxtLink :to="lp('/panel/procurement')" class="text-sm text-text-subtle"><BaseActionIcon action="back" />{{ tr('back') }}</NuxtLink>
    <p v-if="loading" role="status" class="mt-4">{{ tr('loading') }}</p>
    <p v-if="error" role="alert" class="my-4">{{ error }}</p>
    <BaseButton v-if="error && !store.detail" variant="secondary" @click="load"><BaseActionIcon action="retry" />{{ tr('retry') }}</BaseButton>
    <template v-if="store.detail">
      <header class="my-5"><h1 class="break-words text-2xl font-light text-text-default">{{ store.detail.title || store.detail.reference }}</h1><p class="mt-2 text-text-subtle">{{ store.detail.entity_name }} · {{ store.detail.reference }}</p></header>
      <dl class="grid gap-4 rounded-xl border border-input-border bg-surface p-4 sm:grid-cols-2 lg:grid-cols-3"><div><dt class="text-sm text-text-subtle">{{ tr('budget') }}</dt><dd>{{ store.detail.budget ?? tr('unknown') }}</dd></div><div><dt class="text-sm text-text-subtle">{{ tr('department') }}</dt><dd>{{ store.detail.department }} · {{ store.detail.city }}</dd></div><div><dt class="text-sm text-text-subtle">{{ tr('closing') }}</dt><dd>{{ date(store.detail.closing_at) }}</dd><dd v-if="store.detail.days_remaining !== null" :class="store.detail.days_remaining <= 3 ? 'text-danger-strong' : 'text-text-default'">{{ store.detail.days_remaining }} {{ tr('days') }}</dd></div><div><dt class="text-sm text-text-subtle">{{ tr('status') }}</dt><dd>{{ store.detail.source_status }}</dd></div><div><dt class="text-sm text-text-subtle">{{ tr('methods') }}</dt><dd>{{ store.detail.method }}</dd></div><div><dt class="text-sm text-text-subtle">{{ tr('unspsc_codes') }}</dt><dd>{{ store.detail.unspsc_code }}</dd></div></dl>
      <p class="my-4 whitespace-pre-wrap break-words text-text-default">{{ store.detail.description }}</p>
      <BaseButton v-if="store.detail.source_url" as="a" :href="store.detail.source_url" target="_blank" rel="noopener noreferrer" variant="secondary">{{ tr('official') }}</BaseButton>
      <form class="my-6 max-w-3xl space-y-4 rounded-xl border border-input-border p-4" data-testid="procurement-classification-form" @submit.prevent="save()"><h2 class="text-xl">{{ tr('classification') }}</h2><p class="text-sm text-text-subtle">{{ tr('notesHelp') }}</p><BaseFormField :label="tr('status')" for="classification-state"><BaseSelect id="classification-state" v-model="state" :options="states" /></BaseFormField><BaseFormField :label="tr('notes')" for="classification-notes"><BaseTextarea id="classification-notes" v-model="notes" rows="5" maxlength="12000" /></BaseFormField><p v-if="saved" role="status">{{ tr('saved') }}</p><div class="flex flex-wrap gap-2"><BaseButton data-testid="procurement-save-classification" type="submit" :loading="store.saving">{{ tr('save') }}</BaseButton><BaseButton v-if="mine?.state === 'discarded'" variant="secondary" :loading="store.saving" data-testid="procurement-restore-classification" @click="save(true)"><BaseActionIcon action="restore" />{{ tr('restore') }}</BaseButton></div></form>
      <section class="my-6"><h2 class="mb-3 text-xl">{{ tr('team') }}</h2><ul class="space-y-3"><li v-for="item in store.detail.classifications" :key="item.id" class="rounded-xl border border-input-border p-4"><strong>{{ item.owner_name }} · {{ tr(item.state) }}</strong><p class="mt-2 whitespace-pre-wrap break-words">{{ item.notes }}</p></li></ul></section>
      <section><h2 class="mb-3 text-xl">{{ tr('history') }}</h2><ul class="space-y-3"><li v-for="item in store.detail.activities" :key="item.id" class="rounded-xl border border-input-border p-4"><p class="text-sm text-text-subtle">{{ item.actor }} · {{ date(item.created_at) }} · {{ tr(item.snapshot.state) }}</p><p class="mt-2 whitespace-pre-wrap break-words">{{ item.snapshot.notes }}</p></li></ul></section>
    </template>
  </div>
</template>
