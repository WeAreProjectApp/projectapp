<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import BaseModal from '~/components/base/BaseModal.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseInput from '~/components/base/BaseInput.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import SecureLinkFields from '~/components/secureLinks/SecureLinkFields.vue'
import SecureLinkTypeField from '~/components/secureLinks/SecureLinkTypeField.vue'
import { usePlatformSecureLinksStore } from '~/stores/platform-secure-links'

const props = defineProps({ replaces: { type: Object, default: null } })
const emit = defineEmits(['close', 'created'])
const store = usePlatformSecureLinksStore()
const { t, locale } = useI18n()
const language = ref(locale.value.startsWith('en') ? 'en' : 'es')
const title = ref(props.replaces?.title || '')
const secretType = ref('credentials')
const fields = ref({})
const validityDays = ref(7)
const requestId = ref(globalThis.crypto.randomUUID())
const selectedType = computed(() => store.types.find(type => type.key === secretType.value))
const busy = ref(false)
const error = ref('')
const created = ref(null)
const url = ref('')
const copied = ref(false)
const formElement = ref(null)
let generation = 0
watch(secretType, () => { fields.value = {}; error.value = '' })
function clear() { generation += 1; fields.value = {}; url.value = ''; created.value = null }
function close() { clear(); emit('close') }
onBeforeUnmount(clear)

async function submit() {
  if (!formElement.value?.reportValidity() || busy.value) return
  const attempt = generation
  busy.value = true
  error.value = ''
  const result = await store.create({
    request_id: requestId.value, title: title.value, secret_type: secretType.value, fields: { ...fields.value },
    validity_days: Number(validityDays.value), language: language.value, replaces: props.replaces?.id || null,
  })
  if (attempt !== generation) return
  busy.value = false
  if (!result.success) { error.value = result.code || 'failed'; return }
  fields.value = {}
  created.value = result.data.link
  url.value = result.data.url || ''
  emit('created')
}
async function copy() {
  copied.value = false
  try { await navigator.clipboard.writeText(url.value); copied.value = true } catch { error.value = 'clipboard' }
}
function newRequest() { requestId.value = globalThis.crypto.randomUUID(); error.value = '' }
</script>

<template>
  <BaseModal :model-value="true" kind="form" padding="md" @update:model-value="close">
    <h2 class="mb-3 text-lg font-semibold text-text-default">{{ t(replaces ? 'platformSecureLinks.replaceTitle' : 'platformSecureLinks.create') }}</h2>
    <p class="mb-4 text-sm text-text-muted">{{ t('platformSecureLinks.teamOnly') }}</p>
    <BaseAlert v-if="created" variant="success" data-testid="platform-secure-created">{{ t('platformSecureLinks.created') }}</BaseAlert>
    <form v-else ref="formElement" class="space-y-4" autocomplete="off" data-testid="platform-secure-form" @submit.prevent="submit">
      <BaseFormField :label="t('platformSecureLinks.label')" for="platform-secure-title" required>
        <BaseInput id="platform-secure-title" v-model="title" required maxlength="160" data-testid="platform-secure-title" />
      </BaseFormField>
      <SecureLinkTypeField v-model="secretType" v-model:custom-name="fields.custom_name" :types="store.types" :language="language" />
      <SecureLinkFields :key="secretType" v-model="fields" :type="selectedType" :language="language" :exclude-keys="['custom_name']" id-prefix="platform-secure" />
      <BaseFormField :label="t('platformSecureLinks.validity')" for="platform-secure-validity">
        <BaseSelect id="platform-secure-validity" v-model="validityDays" :options="[1, 3, 7].map(value => ({ value, label: t('platformSecureLinks.days', { count: value }) }))" />
      </BaseFormField>
      <BaseFormField :label="t('platformSecureLinks.language')" for="platform-secure-language">
        <BaseSelect id="platform-secure-language" v-model="language" :options="[{ value: 'es', label: 'Español' }, { value: 'en', label: 'English' }]" />
      </BaseFormField>
      <BaseButton type="submit" :loading="busy" data-testid="platform-secure-submit">{{ t('platformSecureLinks.create') }}</BaseButton>
    </form>
    <div v-if="created" class="mt-4 space-y-3">
      <p class="text-sm text-text-muted">{{ t('platformSecureLinks.noSecretRead') }}</p>
      <BaseInput v-if="url" :model-value="url" readonly :aria-label="t('platformSecureLinks.url')" data-testid="platform-secure-url" />
      <BaseButton v-if="url" data-testid="platform-secure-copy" @click="copy">{{ t(copied ? 'platformSecureLinks.copied' : 'platformSecureLinks.copy') }}</BaseButton>
      <p v-else class="text-sm text-text-muted">{{ t('platformSecureLinks.replayed') }}</p>
    </div>
    <BaseAlert v-if="error" variant="danger" class="mt-4" data-testid="platform-secure-form-error">{{ t(`platformSecureLinks.errors.${error}`) }}</BaseAlert>
    <BaseButton v-if="error === 'request_id_conflict'" variant="secondary" class="mt-3" @click="newRequest">{{ t('platformSecureLinks.newRequest') }}</BaseButton>
    <BaseButton variant="ghost" class="mt-4" data-testid="platform-secure-close" @click="close">{{ t('platformSecureLinks.close') }}</BaseButton>
  </BaseModal>
</template>
