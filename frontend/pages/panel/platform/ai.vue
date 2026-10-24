<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { usePlatformAIAdminStore } from '~/stores/platform_ai_admin'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })
const { t } = useI18n()
const store = usePlatformAIAdminStore()
const tab = ref('activation'), busy = ref(false), error = ref(''), saved = ref(false), search = ref('')
const form = reactive({}), keys = reactive({ anthropic: '', openai: '', jev: '' })
const selectedTemplateId = ref(''), family = ref('report'), templateContent = ref(''), preview = ref(''), versions = ref([])
const fields = ['chatbot_enabled', 'voice_reporting_enabled', 'chatbot_model', 'voice_report_model', 'monthly_audio_limit', 'daily_user_audio_limit', 'ai_request_limit', 'ai_window_minutes', 'max_output_tokens', 'report_cache_enabled', 'chatbot_cache_enabled', 'report_cache_hours', 'chatbot_cache_hours']
const quotaOverrides = reactive({})
const tabs = computed(() => ['activation', 'providers', 'templates', 'usage'].map((id) => ({ id, label: t(`platformAI.tabs.${id}`) })))
const modelOptions = [{ value: 'claude-haiku-5-5', label: 'Claude Haiku 5.5' }, { value: 'gpt-6-luna', label: 'GPT-6 Luna' }]
const providers = ['anthropic', 'openai', 'jev']
const familyOptions = computed(() => ['report', 'chatbot'].map((value) => ({ value, label: t(`platformAI.family.${value}`) })))
const templateOptions = computed(() => store.templates.filter((item) => item.family === family.value).map((item) => ({ value: String(item.id), label: `${t(`platformAI.scenarios.${item.scenario}`)} · ${item.language.toUpperCase()}` })))
const selectedTemplate = computed(() => store.templates.find((item) => String(item.id) === String(selectedTemplateId.value)))
function resetForm() { fields.forEach((field) => { form[field] = store.settings[field] }) }
function resetClientQuotas() { Object.keys(quotaOverrides).forEach((key) => { delete quotaOverrides[key] }) }
async function run(action) {
  busy.value = true; error.value = ''; saved.value = false
  try { await action(); saved.value = true }
  catch { error.value = t('platformAI.adminError') }
  finally { busy.value = false }
}
onMounted(() => run(async () => { await store.load(); resetForm(); await store.loadClients(); await store.loadTemplates(); await store.loadUsage() }))
watch(family, () => { selectedTemplateId.value = '' })
watch(selectedTemplate, (item) => { templateContent.value = item?.content || ''; preview.value = ''; versions.value = [] })
function saveSettings() { return run(async () => { await store.saveSettings({ ...form, expected_version: store.settings.version }); resetForm() }) }
function saveKey(provider) { return run(async () => { try { await store.saveKey(provider, keys[provider]) } finally { keys[provider] = '' } }) }
function reload() { return run(async () => { await store.load(); resetForm(); await store.loadClients(search.value); resetClientQuotas(); await store.loadTemplates(); await store.loadUsage() }) }
function clientQuota(client) { return quotaOverrides[client.user_id] || (quotaOverrides[client.user_id] = { limit: client.ai_request_limit ?? '', minutes: client.ai_window_minutes ?? '' }) }
function saveClientQuota(client, inherit = false) { return run(async () => {
  await store.saveClientQuota(client, inherit ? null : Number(clientQuota(client).limit), inherit ? null : Number(clientQuota(client).minutes))
  delete quotaOverrides[client.user_id]
}) }
</script>

<template>
  <BasePageShell data-testid="platform-ai-settings">
    <header class="mb-6 space-y-2">
      <h1 class="text-2xl font-semibold text-text-default">{{ t('platformAI.title') }}</h1>
      <p class="text-sm text-text-muted">{{ t('platformAI.adminHint') }}</p>
    </header>
    <BaseAlert v-if="error" variant="danger" role="alert">{{ error }}</BaseAlert>
    <BaseAlert v-else-if="saved" variant="success" role="status">{{ t('platformAI.saved') }}</BaseAlert>
    <BaseButton variant="ghost" :loading="busy" @click="reload">{{ t('platformAI.reload') }}</BaseButton>
    <BaseResponsiveTabs v-model="tab" :tabs="tabs" :aria-label="t('platformAI.title')" />
    <p v-if="!store.settings" class="py-8 text-text-muted" role="status">{{ t('platformAI.loading') }}</p>
    <div v-else class="mt-5 min-w-0 space-y-5">
      <template v-if="tab === 'activation'">
        <section class="space-y-4 rounded-xl border border-border-muted bg-surface p-4">
          <h2 class="text-lg font-semibold text-text-default">{{ t('platformAI.global') }}</h2>
          <p class="text-sm text-text-muted">{{ t('platformAI.switchHint') }}</p>
          <div v-for="field in ['chatbot_enabled', 'voice_reporting_enabled']" :key="field" class="flex items-center justify-between gap-3">
            <span class="text-sm text-text-default">{{ t(`platformAI.settings.${field}`) }}</span>
            <BaseToggle v-model="form[field]" :aria-label="t(`platformAI.settings.${field}`)" :data-testid="`ai-global-${field}`" />
          </div>
          <BaseButton :loading="busy" data-testid="ai-save-settings" @click="saveSettings">{{ t('platformAI.save') }}</BaseButton>
        </section>
        <section class="space-y-4">
          <h2 class="text-lg font-semibold text-text-default">{{ t('platformAI.clients') }}</h2>
          <form class="flex flex-wrap gap-2" @submit.prevent="run(() => store.loadClients(search))">
            <BaseInput v-model="search" :aria-label="t('platformAI.search')" :placeholder="t('platformAI.search')" />
            <BaseButton type="submit" :loading="busy" variant="secondary">{{ t('platformAI.search') }}</BaseButton>
          </form>
          <article v-for="client in store.clients.results" :key="client.user_id" class="space-y-3 rounded-xl border border-border-muted bg-surface p-4">
            <h3 class="break-words font-medium text-text-default">{{ client.name }}</h3>
            <div v-for="field in ['chatbot_enabled', 'voice_reporting_enabled']" :key="field" class="flex items-center justify-between gap-3">
              <span class="text-sm text-text-default">{{ t(`platformAI.settings.${field}`) }}</span>
              <BaseToggle :model-value="client[field]" :aria-label="`${client.name}: ${t(`platformAI.settings.${field}`)}`" :disabled="busy" @update:model-value="run(() => store.saveClient(client, field, $event))" />
            </div>
            <p class="text-sm text-text-muted">{{ t(client.ai_request_limit ? 'platformAI.customQuota' : 'platformAI.inheritedQuota') }}</p>
            <div class="grid gap-3 panel-portrait:grid-cols-2">
              <BaseFormField :label="t('platformAI.settings.ai_request_limit')"><BaseInput v-model="clientQuota(client).limit" type="number" min="1" max="1000" /></BaseFormField>
              <BaseFormField :label="t('platformAI.settings.ai_window_minutes')"><BaseInput v-model="clientQuota(client).minutes" type="number" min="1" max="10080" /></BaseFormField>
            </div>
            <div class="flex flex-wrap gap-2"><BaseButton variant="secondary" :loading="busy" @click="saveClientQuota(client)">{{ t('platformAI.saveQuota') }}</BaseButton><BaseButton variant="ghost" :loading="busy" @click="saveClientQuota(client, true)">{{ t('platformAI.inheritQuota') }}</BaseButton></div>
          </article>
          <p v-if="!store.clients.results.length" class="text-sm text-text-muted">{{ t('platformAI.noClients') }}</p>
          <div class="flex flex-wrap items-center gap-3">
            <BaseButton variant="ghost" :disabled="busy || store.clients.page <= 1" :disabled-reason="t('platformAI.firstPage')" @click="run(() => store.loadClients(search, store.clients.page - 1))">{{ t('platformAI.previous') }}</BaseButton>
            <span class="text-sm text-text-muted">{{ store.clients.page }} · {{ store.clients.count }}</span>
            <BaseButton variant="ghost" :disabled="busy || store.clients.page * 20 >= store.clients.count" :disabled-reason="t('platformAI.lastPage')" @click="run(() => store.loadClients(search, store.clients.page + 1))">{{ t('platformAI.next') }}</BaseButton>
          </div>
        </section>
      </template>
      <template v-else-if="tab === 'providers'">
        <section class="space-y-4 rounded-xl border border-border-muted bg-surface p-4">
          <BaseFormField v-for="field in ['chatbot_model', 'voice_report_model']" :key="field" :label="t(`platformAI.settings.${field}`)"><BaseSelect v-model="form[field]" :options="modelOptions" /></BaseFormField>
          <BaseButton :loading="busy" @click="saveSettings">{{ t('platformAI.save') }}</BaseButton>
          <p class="text-sm text-text-muted">{{ t('platformAI.providerHint') }}</p>
        </section>
        <article v-for="provider in providers" :key="provider" class="space-y-3 rounded-xl border border-border-muted bg-surface p-4">
          <h2 class="font-semibold text-text-default">{{ provider === 'jev' ? 'Jev' : provider === 'openai' ? 'OpenAI' : 'Anthropic' }}</h2>
          <p class="text-sm text-text-muted">{{ t(store.settings.credentials[provider].configured ? 'platformAI.keyConfigured' : 'platformAI.keyMissing') }} · {{ store.settings.credentials[provider].last_test_status || t('platformAI.notTested') }}</p>
          <BaseFormField :label="t('platformAI.apiKey')"><BaseInput v-model="keys[provider]" type="password" autocomplete="new-password" :data-testid="`ai-key-${provider}`" /></BaseFormField>
          <div class="flex flex-wrap gap-2">
            <BaseButton :loading="busy" :disabled="!keys[provider].trim()" :disabled-reason="t('platformAI.keyRequired')" @click="saveKey(provider)">{{ t('platformAI.saveKey') }}</BaseButton>
            <BaseButton variant="secondary" :disabled="busy || !store.settings.credentials[provider].configured" :disabled-reason="t('platformAI.keyRequired')" @click="run(() => store.testKey(provider))">{{ t('platformAI.testKey') }}</BaseButton>
            <BaseButton variant="danger-ghost" :disabled="busy || !store.settings.credentials[provider].configured" :disabled-reason="t('platformAI.keyRequired')" @click="run(() => store.deleteKey(provider))">{{ t('platformAI.deleteKey') }}</BaseButton>
          </div>
        </article>
      </template>
      <template v-else-if="tab === 'templates'">
        <section class="space-y-4 rounded-xl border border-border-muted bg-surface p-4">
          <BaseFormField :label="t('platformAI.templateFamily')"><BaseSelect v-model="family" :options="familyOptions" /></BaseFormField>
          <BaseFormField :label="t('platformAI.template')"><BaseSelect v-model="selectedTemplateId" :options="[{ value: '', label: t('platformAI.chooseTemplate') }, ...templateOptions]" /></BaseFormField>
          <template v-if="selectedTemplate">
            <p class="text-sm text-text-muted">{{ t('platformAI.version') }} {{ selectedTemplate.version }} · {{ t('platformAI.placeholders') }}: {{ selectedTemplate.placeholders.join(', ') || '—' }}</p>
            <BaseFormField :label="t('platformAI.templateContent')"><BaseTextarea v-model="templateContent" :rows="10" maxlength="12000" data-testid="ai-template-content" /></BaseFormField>
            <p class="text-sm text-text-muted">{{ t('platformAI.templateHint') }}</p>
            <div class="flex flex-wrap gap-2">
              <BaseButton :loading="busy" @click="run(() => store.saveTemplate(selectedTemplate, templateContent))">{{ t('platformAI.saveVersion') }}</BaseButton>
              <BaseButton variant="secondary" :loading="busy" @click="run(async () => { preview = await store.previewTemplate(selectedTemplate, templateContent) })">{{ t('platformAI.preview') }}</BaseButton>
              <BaseButton variant="ghost" :loading="busy" @click="run(async () => { versions = await store.versions(selectedTemplate) })">{{ t('platformAI.history') }}</BaseButton>
            </div>
            <p v-if="preview" class="whitespace-pre-wrap break-words rounded-xl bg-surface-raised p-4 text-text-default" data-testid="ai-template-preview">{{ preview }}</p>
            <div v-for="version in versions" :key="version.version" class="flex flex-wrap items-center gap-3">
              <span class="text-sm text-text-muted">{{ t('platformAI.version') }} {{ version.version }}</span>
              <BaseButton variant="secondary" :loading="busy" @click="run(() => store.restoreTemplate(selectedTemplate, version.version))">{{ t('platformAI.restore') }}</BaseButton>
            </div>
          </template>
        </section>
      </template>
      <template v-else>
        <section class="space-y-4 rounded-xl border border-border-muted bg-surface p-4">
          <h2 class="text-lg font-semibold text-text-default">{{ t('platformAI.limits') }}</h2>
          <p class="text-sm text-text-muted">{{ t('platformAI.sharedQuotaHint') }}</p>
          <BaseFormField v-for="field in ['ai_request_limit', 'ai_window_minutes', 'monthly_audio_limit', 'daily_user_audio_limit', 'max_output_tokens', 'report_cache_hours', 'chatbot_cache_hours']" :key="field" :label="t(`platformAI.settings.${field}`)"><BaseInput :model-value="form[field]" type="number" min="1" @update:model-value="form[field] = Number($event)" /></BaseFormField>
          <div v-for="field in ['report_cache_enabled', 'chatbot_cache_enabled']" :key="field" class="flex items-center justify-between gap-3"><span class="text-sm text-text-default">{{ t(`platformAI.settings.${field}`) }}</span><BaseToggle v-model="form[field]" :aria-label="t(`platformAI.settings.${field}`)" /></div>
          <BaseButton :loading="busy" @click="saveSettings">{{ t('platformAI.save') }}</BaseButton>
          <div class="flex flex-wrap gap-2"><BaseButton v-for="fn in ['voice_report', 'chatbot', 'all']" :key="fn" variant="secondary" :loading="busy" @click="run(() => store.invalidate(fn))">{{ t('platformAI.invalidate') }} · {{ t(`platformAI.functions.${fn}`) }}</BaseButton></div>
        </section>
        <section class="space-y-3">
          <h2 class="text-lg font-semibold text-text-default">{{ t('platformAI.monthlyUsage') }} · {{ store.usage?.month }}</h2>
          <p class="text-sm text-text-muted">{{ t('platformAI.costHint') }}</p>
          <article v-for="(group, index) in store.usage?.groups || []" :key="index" class="space-y-1 rounded-xl border border-border-muted bg-surface p-4 text-sm text-text-default">
            <p class="break-words font-medium">{{ group.model }} · {{ group.purpose }} · {{ group.status }}</p>
            <p>{{ t('platformAI.requests') }}: {{ group.requests }} · {{ t('platformAI.audioSeconds') }}: {{ Number(group.audio_seconds).toFixed(1) }}</p>
            <p>{{ t('platformAI.tokens') }}: {{ group.input_tokens }} / {{ group.output_tokens }} · {{ t('platformAI.cacheTokens') }}: {{ group.cache_read_tokens }} / {{ group.cache_write_tokens }}</p>
            <p>USD {{ Number(group.estimated_cost).toFixed(6) }}</p>
          </article>
        </section>
      </template>
    </div>
  </BasePageShell>
</template>
