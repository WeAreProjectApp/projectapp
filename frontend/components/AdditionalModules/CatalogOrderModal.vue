<script setup>
import { ref, watch } from 'vue'
import draggable from 'vuedraggable'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  categories: { type: Array, default: () => [] },
  modules: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'save'])
const { t } = useI18n()
const groups = ref([])

function rebuild() {
  groups.value = props.categories.map((category) => ({
    ...category,
    modules: props.modules
      .filter((module) => module.category === category.id)
      .map((module) => ({ ...module })),
  }))
}

watch(() => props.modelValue, (open) => {
  if (open) rebuild()
})

function move(list, index, direction) {
  const next = index + direction
  if (next < 0 || next >= list.length) return
  const [item] = list.splice(index, 1)
  list.splice(next, 0, item)
}

function save() {
  emit('save', {
    category_ids: groups.value.map((category) => category.id),
    module_groups: groups.value.map((category) => ({
      category_id: category.id,
      module_ids: category.modules.map((module) => module.id),
    })),
  })
}
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
          <h2 class="text-xl font-medium text-text-brand">{{ t('additionalModules.orderTitle') }}</h2>
          <p class="mt-1 text-sm text-text-muted">{{ t('additionalModules.orderHelp') }}</p>
        </div>
        <BaseButton variant="ghost" icon-only :aria-label="t('additionalModules.close')" @click="emit('update:modelValue', false)">
          <span aria-hidden="true" class="text-xl">×</span>
        </BaseButton>
      </header>

      <div class="px-5 py-5 sm:px-7">
        <draggable
          v-model="groups"
          item-key="id"
          handle=".category-drag-handle"
          ghost-class="opacity-30"
          class="space-y-4"
          data-testid="additional-catalog-order-groups"
        >
          <template #item="{ element: category, index: categoryIndex }">
            <section class="rounded-xl border border-border-default bg-surface">
              <header class="flex items-center gap-2 border-b border-border-default bg-surface-raised px-3 py-3">
                <BaseButton
                  unstyled
                  icon-only
                  class="category-drag-handle min-h-11 min-w-11 cursor-grab rounded-lg text-text-muted hover:bg-surface"
                  :aria-label="`${t('additionalModules.reorder')}: ${category.name_es}`"
                >
                  <span aria-hidden="true">⋮⋮</span>
                </BaseButton>
                <h3 class="min-w-0 flex-1 font-medium text-text-brand">{{ category.name_es }}</h3>
                <BaseButton
                  variant="ghost"
                  icon-only
                  size="sm"
                  :disabled="categoryIndex === 0"
                  :disabled-reason="t('additionalModules.moveUp')"
                  :aria-label="`${t('additionalModules.moveUp')}: ${category.name_es}`"
                  @click="move(groups, categoryIndex, -1)"
                >↑</BaseButton>
                <BaseButton
                  variant="ghost"
                  icon-only
                  size="sm"
                  :disabled="categoryIndex === groups.length - 1"
                  :disabled-reason="t('additionalModules.moveDown')"
                  :aria-label="`${t('additionalModules.moveDown')}: ${category.name_es}`"
                  @click="move(groups, categoryIndex, 1)"
                >↓</BaseButton>
              </header>

              <draggable
                v-model="category.modules"
                item-key="id"
                group="additional-module-catalog"
                handle=".module-drag-handle"
                ghost-class="opacity-30"
                class="min-h-12 space-y-2 p-3"
              >
                <template #item="{ element: module, index: moduleIndex }">
                  <div class="flex items-center gap-2 rounded-lg border border-border-default bg-surface px-2 py-2">
                    <BaseButton
                      unstyled
                      icon-only
                      class="module-drag-handle min-h-11 min-w-11 cursor-grab rounded-lg text-text-muted hover:bg-surface-raised"
                      :aria-label="`${t('additionalModules.reorder')}: ${module.name_es}`"
                    >
                      <span aria-hidden="true">⋮⋮</span>
                    </BaseButton>
                    <span aria-hidden="true" class="text-lg">{{ module.icon }}</span>
                    <span class="min-w-0 flex-1 text-sm text-text-default">{{ module.name_es }}</span>
                    <BaseBadge v-if="!module.is_active" variant="neutral" size="sm">{{ t('additionalModules.retired') }}</BaseBadge>
                    <BaseButton
                      variant="ghost"
                      icon-only
                      size="sm"
                      :disabled="moduleIndex === 0"
                      :disabled-reason="t('additionalModules.moveUp')"
                      :aria-label="`${t('additionalModules.moveUp')}: ${module.name_es}`"
                      @click="move(category.modules, moduleIndex, -1)"
                    >↑</BaseButton>
                    <BaseButton
                      variant="ghost"
                      icon-only
                      size="sm"
                      :disabled="moduleIndex === category.modules.length - 1"
                      :disabled-reason="t('additionalModules.moveDown')"
                      :aria-label="`${t('additionalModules.moveDown')}: ${module.name_es}`"
                      @click="move(category.modules, moduleIndex, 1)"
                    >↓</BaseButton>
                  </div>
                </template>
              </draggable>
            </section>
          </template>
        </draggable>

        <BaseAlert v-if="errorMessage" class="mt-4" variant="danger">{{ errorMessage }}</BaseAlert>
      </div>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton variant="ghost" @click="emit('update:modelValue', false)">{{ t('additionalModules.cancel') }}</BaseButton>
        <BaseButton :loading="saving" data-testid="additional-catalog-order-save" @click="save">
          {{ t('additionalModules.saveOrder') }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
