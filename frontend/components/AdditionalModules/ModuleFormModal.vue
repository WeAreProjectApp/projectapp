<script setup>
import { useId, reactive, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  module: { type: Object, default: null },
  categories: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'save'])
const { t } = useI18n()
const languageTab = ref('es')

const requiredFieldMessages = {
  category: 'Selecciona una categoría.',
  slug: 'Escribe el identificador del módulo.',
  name_es: 'Escribe el nombre en español.',
  name_en: 'Escribe el nombre en inglés.',
  summary_es: 'Escribe el resumen en español.',
  summary_en: 'Escribe el resumen en inglés.',
  what_is_es: 'Explica qué es el módulo en español.',
  what_is_en: 'Explica qué es el módulo en inglés.',
  purpose_es: 'Explica para qué sirve en español.',
  purpose_en: 'Explica para qué sirve en inglés.',
  problems_solved_es: 'Agrega al menos un problema en español.',
  problems_solved_en: 'Agrega al menos un problema en inglés.',
  integrations_es: 'Agrega al menos una integración en español.',
  integrations_en: 'Agrega al menos una integración en inglés.',
  implementation_requirements_es: 'Agrega al menos un requisito en español.',
  implementation_requirements_en: 'Agrega al menos un requisito en inglés.',
}
const listFields = new Set([
  'problems_solved_es', 'problems_solved_en',
  'integrations_es', 'integrations_en',
  'implementation_requirements_es', 'implementation_requirements_en',
])
const fieldErrors = reactive(Object.fromEntries(
  Object.keys(requiredFieldMessages).map((field) => [field, '']),
))

const form = reactive({
  category: '',
  slug: '',
  icon: '',
  name_es: '',
  name_en: '',
  summary_es: '',
  summary_en: '',
  what_is_es: '',
  what_is_en: '',
  purpose_es: '',
  purpose_en: '',
  problems_solved_es: '',
  problems_solved_en: '',
  integrations_es: '',
  integrations_en: '',
  implementation_requirements_es: '',
  implementation_requirements_en: '',
})

const listText = (value) => (Array.isArray(value) ? value.join('\n') : '')
const parseLines = (value) => value.split('\n').map((item) => item.trim()).filter(Boolean)

function clearFieldErrors() {
  for (const field of Object.keys(fieldErrors)) fieldErrors[field] = ''
}

function clearFieldError(field) {
  fieldErrors[field] = ''
}

function resetForm() {
  const module = props.module
  form.category = module?.category || props.categories.find((item) => item.is_active)?.id || ''
  form.slug = module?.slug || ''
  form.icon = module?.icon || ''
  for (const field of ['name', 'summary', 'what_is', 'purpose']) {
    form[`${field}_es`] = module?.[`${field}_es`] || ''
    form[`${field}_en`] = module?.[`${field}_en`] || ''
  }
  for (const field of ['problems_solved', 'integrations', 'implementation_requirements']) {
    form[`${field}_es`] = listText(module?.[`${field}_es`])
    form[`${field}_en`] = listText(module?.[`${field}_en`])
  }
  languageTab.value = 'es'
  clearFieldErrors()
}

watch(() => props.modelValue, (open) => {
  if (open) resetForm()
})

function close() {
  emit('update:modelValue', false)
}

function submit() {
  clearFieldErrors()
  for (const [field, message] of Object.entries(requiredFieldMessages)) {
    const missing = listFields.has(field)
      ? parseLines(form[field]).length === 0
      : !String(form[field]).trim()
    if (missing) fieldErrors[field] = message
  }
  const missingFields = Object.keys(fieldErrors).filter((field) => fieldErrors[field])
  if (missingFields.length) {
    if (missingFields.some((field) => field.endsWith('_en'))) languageTab.value = 'en'
    else languageTab.value = 'es'
    return
  }
  emit('save', {
    category: Number(form.category),
    slug: form.slug.trim(),
    icon: form.icon.trim(),
    name_es: form.name_es.trim(),
    name_en: form.name_en.trim(),
    summary_es: form.summary_es.trim(),
    summary_en: form.summary_en.trim(),
    what_is_es: form.what_is_es.trim(),
    what_is_en: form.what_is_en.trim(),
    purpose_es: form.purpose_es.trim(),
    purpose_en: form.purpose_en.trim(),
    problems_solved_es: parseLines(form.problems_solved_es),
    problems_solved_en: parseLines(form.problems_solved_en),
    integrations_es: parseLines(form.integrations_es),
    integrations_en: parseLines(form.integrations_en),
    implementation_requirements_es: parseLines(form.implementation_requirements_es),
    implementation_requirements_en: parseLines(form.implementation_requirements_en),
  })
}

const modalFormId = useId();
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    kind="form-wide"
    padding="none"
    @update:model-value="emit('update:modelValue', $event)"
    @close="close"
  >
    <form :id="modalFormId" class="flex min-h-0 flex-col" data-testid="additional-module-form" @submit.prevent="submit">
      <header class="border-b border-border-default px-5 py-5 sm:px-7">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h2 class="text-xl font-medium text-text-brand">
              {{ module ? t('additionalModules.moduleEditTitle') : t('additionalModules.moduleCreateTitle') }}
            </h2>
            <p class="mt-1 text-sm text-text-muted">{{ t('additionalModules.noPriceNotice') }}</p>
          </div>
          <BaseButton variant="ghost" icon-only :aria-label="t('additionalModules.close')" @click="close">
            <span aria-hidden="true" class="text-xl">×</span>
          </BaseButton>
        </div>
      </header>

      <div class="space-y-5 px-5 py-5 sm:px-7">
        <div class="grid gap-4 sm:grid-cols-[1fr_1fr_7rem]">
          <BaseFormField :label="t('additionalModules.category')" for="additional-module-category" required :error="fieldErrors.category">
            <BaseSelect
              id="additional-module-category"
              v-model="form.category"
              :options="categories.map((category) => ({ value: category.id, label: category.name_es }))"
              :error="!!fieldErrors.category"
              data-testid="additional-module-category"
              @update:model-value="clearFieldError('category')"
            />
          </BaseFormField>
          <BaseFormField :label="t('additionalModules.slug')" for="additional-module-slug" required :error="fieldErrors.slug">
            <BaseInput id="additional-module-slug" v-model="form.slug" :error="!!fieldErrors.slug" data-testid="additional-module-slug" @update:model-value="clearFieldError('slug')" />
          </BaseFormField>
          <BaseFormField :label="t('additionalModules.icon')" for="additional-module-icon">
            <BaseInput id="additional-module-icon" v-model="form.icon" data-testid="additional-module-icon" />
          </BaseFormField>
        </div>

        <BaseSegmented
          v-model="languageTab"
          :options="[
            { value: 'es', label: t('additionalModules.spanish') },
            { value: 'en', label: t('additionalModules.english') },
          ]"
          data-testid="additional-module-language-tabs"
        />

        <div v-show="languageTab === 'es'" class="space-y-4">
          <BaseFormField :label="t('additionalModules.name')" for="additional-module-name-es" required :error="fieldErrors.name_es">
            <BaseInput id="additional-module-name-es" v-model="form.name_es" :error="!!fieldErrors.name_es" data-testid="additional-module-name-es" @update:model-value="clearFieldError('name_es')" />
          </BaseFormField>
          <BaseFormField :label="t('additionalModules.summary')" for="additional-module-summary-es" required :error="fieldErrors.summary_es">
            <BaseTextarea id="additional-module-summary-es" v-model="form.summary_es" rows="2" :error="!!fieldErrors.summary_es" data-testid="additional-module-summary-es" @update:model-value="clearFieldError('summary_es')" />
          </BaseFormField>
          <div class="grid gap-4 sm:grid-cols-2">
            <BaseFormField :label="t('additionalModules.whatIsField')" for="additional-module-what-es" required :error="fieldErrors.what_is_es">
              <BaseTextarea id="additional-module-what-es" v-model="form.what_is_es" rows="5" :error="!!fieldErrors.what_is_es" data-testid="additional-module-what-es" @update:model-value="clearFieldError('what_is_es')" />
            </BaseFormField>
            <BaseFormField :label="t('additionalModules.purposeField')" for="additional-module-purpose-es" required :error="fieldErrors.purpose_es">
              <BaseTextarea id="additional-module-purpose-es" v-model="form.purpose_es" rows="5" :error="!!fieldErrors.purpose_es" data-testid="additional-module-purpose-es" @update:model-value="clearFieldError('purpose_es')" />
            </BaseFormField>
          </div>
          <BaseFormField :label="t('additionalModules.problemsField')" for="additional-module-problems-es" required :error="fieldErrors.problems_solved_es">
            <BaseTextarea id="additional-module-problems-es" v-model="form.problems_solved_es" rows="4" :error="!!fieldErrors.problems_solved_es" data-testid="additional-module-problems-es" @update:model-value="clearFieldError('problems_solved_es')" />
          </BaseFormField>
          <BaseFormField :label="t('additionalModules.integrationsField')" for="additional-module-integrations-es" required :error="fieldErrors.integrations_es">
            <BaseTextarea id="additional-module-integrations-es" v-model="form.integrations_es" rows="4" :error="!!fieldErrors.integrations_es" data-testid="additional-module-integrations-es" @update:model-value="clearFieldError('integrations_es')" />
          </BaseFormField>
          <BaseFormField :label="t('additionalModules.requirementsField')" for="additional-module-requirements-es" required :error="fieldErrors.implementation_requirements_es">
            <BaseTextarea id="additional-module-requirements-es" v-model="form.implementation_requirements_es" rows="4" :error="!!fieldErrors.implementation_requirements_es" data-testid="additional-module-requirements-es" @update:model-value="clearFieldError('implementation_requirements_es')" />
          </BaseFormField>
        </div>

        <div v-show="languageTab === 'en'" class="space-y-4">
          <BaseFormField :label="t('additionalModules.name')" for="additional-module-name-en" required :error="fieldErrors.name_en">
            <BaseInput id="additional-module-name-en" v-model="form.name_en" :error="!!fieldErrors.name_en" data-testid="additional-module-name-en" @update:model-value="clearFieldError('name_en')" />
          </BaseFormField>
          <BaseFormField :label="t('additionalModules.summary')" for="additional-module-summary-en" required :error="fieldErrors.summary_en">
            <BaseTextarea id="additional-module-summary-en" v-model="form.summary_en" rows="2" :error="!!fieldErrors.summary_en" data-testid="additional-module-summary-en" @update:model-value="clearFieldError('summary_en')" />
          </BaseFormField>
          <div class="grid gap-4 sm:grid-cols-2">
            <BaseFormField :label="t('additionalModules.whatIsField')" for="additional-module-what-en" required :error="fieldErrors.what_is_en">
              <BaseTextarea id="additional-module-what-en" v-model="form.what_is_en" rows="5" :error="!!fieldErrors.what_is_en" data-testid="additional-module-what-en" @update:model-value="clearFieldError('what_is_en')" />
            </BaseFormField>
            <BaseFormField :label="t('additionalModules.purposeField')" for="additional-module-purpose-en" required :error="fieldErrors.purpose_en">
              <BaseTextarea id="additional-module-purpose-en" v-model="form.purpose_en" rows="5" :error="!!fieldErrors.purpose_en" data-testid="additional-module-purpose-en" @update:model-value="clearFieldError('purpose_en')" />
            </BaseFormField>
          </div>
          <BaseFormField :label="t('additionalModules.problemsField')" for="additional-module-problems-en" required :error="fieldErrors.problems_solved_en">
            <BaseTextarea id="additional-module-problems-en" v-model="form.problems_solved_en" rows="4" :error="!!fieldErrors.problems_solved_en" data-testid="additional-module-problems-en" @update:model-value="clearFieldError('problems_solved_en')" />
          </BaseFormField>
          <BaseFormField :label="t('additionalModules.integrationsField')" for="additional-module-integrations-en" required :error="fieldErrors.integrations_en">
            <BaseTextarea id="additional-module-integrations-en" v-model="form.integrations_en" rows="4" :error="!!fieldErrors.integrations_en" data-testid="additional-module-integrations-en" @update:model-value="clearFieldError('integrations_en')" />
          </BaseFormField>
          <BaseFormField :label="t('additionalModules.requirementsField')" for="additional-module-requirements-en" required :error="fieldErrors.implementation_requirements_en">
            <BaseTextarea id="additional-module-requirements-en" v-model="form.implementation_requirements_en" rows="4" :error="!!fieldErrors.implementation_requirements_en" data-testid="additional-module-requirements-en" @update:model-value="clearFieldError('implementation_requirements_en')" />
          </BaseFormField>
        </div>

        <BaseAlert v-if="errorMessage" variant="danger">
          {{ errorMessage }}
        </BaseAlert>
      </div>

    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="ghost" @click="close">{{ t('additionalModules.cancel') }}</BaseButton>
        <BaseButton type="submit" :form="modalFormId" :loading="saving" data-testid="additional-module-save">
          {{ t('additionalModules.save') }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
