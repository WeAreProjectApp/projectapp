<script setup>
import { useId, reactive, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  categories: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'save', 'status'])
const { t } = useI18n()
const editingId = ref(null)
const formOpen = ref(false)
const fieldErrors = reactive({ slug: '', name_es: '', name_en: '' })
const form = reactive({ slug: '', name_es: '', name_en: '' })

function clearFieldErrors() {
  fieldErrors.slug = ''
  fieldErrors.name_es = ''
  fieldErrors.name_en = ''
}

watch(() => props.modelValue, (open) => {
  if (!open) return
  formOpen.value = false
  editingId.value = null
  clearFieldErrors()
})

function openCreate() {
  editingId.value = null
  form.slug = ''
  form.name_es = ''
  form.name_en = ''
  formOpen.value = true
  clearFieldErrors()
}

function openEdit(category) {
  editingId.value = category.id
  form.slug = category.slug
  form.name_es = category.name_es
  form.name_en = category.name_en
  formOpen.value = true
  clearFieldErrors()
}

function submit() {
  clearFieldErrors()
  if (!form.slug.trim()) fieldErrors.slug = `Completa ${String(t('additionalModules.slug')).toLocaleLowerCase()}.`
  if (!form.name_es.trim()) fieldErrors.name_es = `Completa ${String(t('additionalModules.categoryNameEs')).toLocaleLowerCase()}.`
  if (!form.name_en.trim()) fieldErrors.name_en = `Completa ${String(t('additionalModules.categoryNameEn')).toLocaleLowerCase()}.`
  if (Object.values(fieldErrors).some(Boolean)) return
  emit('save', {
    id: editingId.value,
    payload: {
      slug: form.slug.trim(),
      name_es: form.name_es.trim(),
      name_en: form.name_en.trim(),
    },
  })
}

function closeForm() {
  formOpen.value = false
  editingId.value = null
  clearFieldErrors()
}

defineExpose({ closeForm })
const modalFormId = useId()
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    kind="form-wide"
    padding="none"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="flex min-h-0 flex-col">
      <header class="flex items-start justify-between gap-4 border-b border-border-default px-5 py-5 sm:px-7">
        <div>
          <h2 class="text-xl font-medium text-text-brand">{{ t('additionalModules.categoryFormTitle') }}</h2>
          <p class="mt-1 text-sm text-text-muted">{{ t('additionalModules.orderHelp') }}</p>
        </div>
        <BaseButton variant="ghost" icon-only :aria-label="t('additionalModules.close')" @click="emit('update:modelValue', false)">
          <span aria-hidden="true" class="text-xl">×</span>
        </BaseButton>
      </header>

      <div class="space-y-4 px-5 py-5 sm:px-7">
        <div class="flex justify-end">
          <BaseButton variant="secondary" size="sm" data-testid="additional-category-add" @click="openCreate">
            {{ t('additionalModules.addCategory') }}
          </BaseButton>
        </div>

        <form :id="modalFormId" v-if="formOpen" class="rounded-xl border border-border-default bg-surface-raised p-4" @submit.prevent="submit">
          <h3 class="mb-4 font-medium text-text-brand">
            {{ editingId ? t('additionalModules.editCategory') : t('additionalModules.addCategory') }}
          </h3>
          <div class="grid gap-4 sm:grid-cols-3">
            <BaseFormField :label="t('additionalModules.slug')" for="additional-category-slug" required :error="fieldErrors.slug">
              <BaseInput id="additional-category-slug" v-model="form.slug" :error="!!fieldErrors.slug" data-testid="additional-category-slug" @update:model-value="fieldErrors.slug = ''" />
            </BaseFormField>
            <BaseFormField :label="t('additionalModules.categoryNameEs')" for="additional-category-name-es" required :error="fieldErrors.name_es">
              <BaseInput id="additional-category-name-es" v-model="form.name_es" :error="!!fieldErrors.name_es" data-testid="additional-category-name-es" @update:model-value="fieldErrors.name_es = ''" />
            </BaseFormField>
            <BaseFormField :label="t('additionalModules.categoryNameEn')" for="additional-category-name-en" required :error="fieldErrors.name_en">
              <BaseInput id="additional-category-name-en" v-model="form.name_en" :error="!!fieldErrors.name_en" data-testid="additional-category-name-en" @update:model-value="fieldErrors.name_en = ''" />
            </BaseFormField>
          </div>
          <BaseAlert v-if="errorMessage" class="mt-4" variant="danger">
            {{ errorMessage }}
          </BaseAlert>

        </form>

        <ul class="space-y-3" data-testid="additional-category-list">
          <li
            v-for="category in categories"
            :key="category.id"
            class="flex flex-col gap-3 rounded-xl border border-border-default bg-surface p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-medium text-text-brand">{{ category.name_es }}</span>
                <BaseBadge :variant="category.is_active ? 'success' : 'neutral'">
                  {{ category.is_active ? t('additionalModules.active') : t('additionalModules.retired') }}
                </BaseBadge>
              </div>
              <p class="mt-1 text-sm text-text-muted">{{ category.name_en }} · {{ category.slug }}</p>
              <p class="mt-1 text-xs text-text-subtle">
                {{ category.active_module_count }} / {{ category.module_count }} {{ t('additionalModules.title').toLowerCase() }}
              </p>
            </div>
            <div class="flex flex-wrap gap-2">
              <BaseButton variant="secondary" size="sm" @click="openEdit(category)">{{ t('additionalModules.edit') }}</BaseButton>
              <BaseButton
                v-if="category.is_active"
                variant="danger-ghost"
                size="sm"
                :disabled="category.active_module_count > 0"
                :disabled-reason="category.active_module_count > 0 ? t('additionalModules.retireCategoryBlocked') : ''"
                @click="emit('status', { category, action: 'retire' })"
              >
                {{ t('additionalModules.retire') }}
              </BaseButton>
              <BaseButton
                v-else
                variant="secondary"
                size="sm"
                @click="emit('status', { category, action: 'restore' })"
              >
                {{ t('additionalModules.restore') }}
              </BaseButton>
            </div>
          </li>
        </ul>
      </div>
    </div>
    <template #footer>
      <BaseModalActions v-if="formOpen">
        <BaseButton type="button" variant="ghost" size="sm" @click="closeForm">{{ t('additionalModules.cancel') }}</BaseButton>
        <BaseButton type="submit" :form="modalFormId" size="sm" :loading="saving">{{ t('additionalModules.save') }}</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
