<script setup>
import { onMounted, ref } from 'vue';
import { SERVICE_CONTRACT_FIELDS } from '~/stores/proposals_constants';
import { formatServiceTerm, serviceTermNumber, validServiceContractSettings } from '~/utils/serviceContractTerms';

const { t } = useI18n();
const store = useProposalStore();
const config = ref(null);
const loading = ref(false);
const saving = ref(false);
const error = ref('');
const errors = ref({});
const saved = ref(false);
const catalogs = ['duration_options', 'notice_options'];

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const result = await store.fetchCompanySettings();
    const settings = result.data?.service_contract_settings;
    if (!result.success || !validServiceContractSettings(settings)) throw new Error('Invalid settings');
    config.value = JSON.parse(JSON.stringify(settings));
  } catch {
    error.value = t('serviceContract.loadError');
  } finally {
    loading.value = false;
  }
}

function optionsFor(field) {
  return [...new Set(config.value[field.optionsKey].map(serviceTermNumber).filter(n => n !== null))]
    .sort((a, b) => a - b)
    .map(value => ({ value, label: formatServiceTerm(value, field.duration) }));
}

function errorText(key) {
  const value = errors.value[key];
  return Array.isArray(value) ? value.join(' ') : typeof value === 'string' ? value : value ? t('serviceContract.invalidNumber') : '';
}

async function save() {
  if (saving.value) return;
  saved.value = false;
  errors.value = {};
  error.value = '';
  const value = {};
  for (const key of catalogs) {
    value[key] = config.value[key].map(serviceTermNumber);
    if (!value[key].length) errors.value[key] = t('serviceContract.emptyList');
    else if (value[key].includes(null)) errors.value[key] = t('serviceContract.invalidNumber');
    else if (new Set(value[key]).size !== value[key].length) errors.value[key] = t('serviceContract.duplicates');
    value[key].sort((a, b) => a - b);
  }
  for (const field of SERVICE_CONTRACT_FIELDS) {
    value[field.defaultKey] = serviceTermNumber(config.value[field.defaultKey]);
    if (value[field.defaultKey] === null || !value[field.optionsKey].includes(value[field.defaultKey])) {
      errors.value[field.defaultKey] = t('serviceContract.chooseDefault');
    }
  }
  if (Object.keys(errors.value).length) return;
  saving.value = true;
  try {
    const result = await store.saveServiceContractSettings(value);
    if (!result.success) {
      errors.value = result.errors || {};
      error.value = t('serviceContract.saveError');
      return;
    }
    config.value = JSON.parse(JSON.stringify(result.data.service_contract_settings));
    saved.value = true;
  } catch {
    error.value = t('serviceContract.saveError');
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="bg-surface border border-border-muted rounded-xl shadow-sm p-5 sm:p-6" data-testid="service-contract-settings">
    <h2 class="text-lg font-bold text-text-default">{{ t('serviceContract.settingsTitle') }}</h2>
    <p class="mt-1 mb-4 text-sm text-text-muted">{{ t('serviceContract.settingsHint') }}</p>
    <p v-if="loading" role="status" class="text-sm text-text-muted">{{ t('serviceContract.loading') }}</p>
    <p v-if="error" role="alert" class="mb-3 text-sm text-danger-strong">{{ error }}</p>
    <BaseButton v-if="!config && !loading" size="sm" variant="secondary" @click="load">{{ t('serviceContract.retry') }}</BaseButton>
    <form v-if="config" class="space-y-5" novalidate @submit.prevent="save" @input="saved = false" @change="saved = false">
      <fieldset :disabled="saving" class="space-y-5">
        <div class="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <fieldset v-for="key in catalogs" :key="key" class="min-w-0 space-y-3">
            <legend class="text-sm font-semibold text-text-default">{{ t(`serviceContract.${key}`) }}</legend>
            <div v-for="(value, index) in config[key]" :key="index" class="flex items-end gap-2">
              <BaseFormField
                class="min-w-0 flex-1"
                :label="t('serviceContract.optionLabel', { index: index + 1, catalog: t(`serviceContract.${key}`) })"
                :for="`service-${key}-${index}`"
                size="sm"
                label-policy="wrap"
              >
                <BaseInput :id="`service-${key}-${index}`" v-model="config[key][index]" type="number" min="1" max="999" step="1" size="sm" />
              </BaseFormField>
              <BaseButton
                size="sm"
                variant="ghost"
                :aria-label="t('serviceContract.removeOption', { index: index + 1, catalog: t(`serviceContract.${key}`) })"
                @click="config[key].splice(index, 1); saved = false"
              >{{ t('serviceContract.remove') }}</BaseButton>
            </div>
            <p v-if="errorText(key)" role="alert" class="text-sm text-danger-strong">{{ errorText(key) }}</p>
            <BaseButton size="sm" variant="secondary" textPolicy="wrap" class="max-w-full" @click="config[key].push(''); saved = false">
              {{ t('serviceContract.addOption', { catalog: t(`serviceContract.${key}`) }) }}
            </BaseButton>
          </fieldset>
        </div>
        <div class="space-y-4">
          <BaseFormField
            v-for="field in SERVICE_CONTRACT_FIELDS"
            :key="field.defaultKey"
            :label="t('serviceContract.defaultLabel', { field: t(`serviceContract.fields.${field.key}`) })"
            :for="`service-${field.defaultKey}`"
            :error="errorText(field.defaultKey)"
            label-policy="wrap"
            size="sm"
          >
            <BaseSelect :id="`service-${field.defaultKey}`" v-model="config[field.defaultKey]" :options="optionsFor(field)" :placeholder="t('serviceContract.select')" size="sm" />
          </BaseFormField>
        </div>
      </fieldset>
      <p v-if="saved" role="status" class="text-sm text-success-strong">{{ t('serviceContract.saved') }}</p>
      <BaseButton type="submit" size="sm" :loading="saving" :disabled="saving" :disabled-reason="t('serviceContract.saving')">{{ t('serviceContract.save') }}</BaseButton>
    </form>
  </section>
</template>
