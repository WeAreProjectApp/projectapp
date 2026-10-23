<template>
  <div class="bg-surface rounded-2xl shadow-card border border-border-muted">
    <!-- Header (keyboard-accessible accordion trigger) -->
    <button
      type="button"
      class="w-full flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-left select-none rounded-2xl focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
      :class="expanded ? 'border-b border-border-muted rounded-b-none' : ''"
      :aria-expanded="expanded"
      :aria-controls="bodyId"
      @click="expanded = !expanded"
    >
      <div class="flex items-center gap-2 min-w-0">
        <span class="text-base" aria-hidden="true">{{ meta.icon }}</span>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-text-default truncate">
            {{ section.title || meta.label }}
          </div>
          <div class="text-xs text-text-subtle">
            {{ meta.label }} · orden {{ section.order }}
          </div>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="px-2 py-0.5 rounded-full text-2xs font-medium uppercase tracking-wide"
          :class="section.is_enabled
            ? 'bg-primary-soft text-text-brand'
            : 'bg-surface-raised text-text-muted'"
        >
          {{ section.is_enabled ? 'Activa' : 'Oculta' }}
        </span>
        <span
          class="px-2 py-0.5 rounded-full text-2xs font-medium uppercase tracking-wide bg-surface-raised text-text-muted"
        >
          {{ visibilityLabel }}
        </span>
        <BaseActionIcon :action="expanded ? 'collapse' : 'expand'" />
      </div>
    </button>

    <!-- Body -->
    <BaseCollapse :id="bodyId" :open="expanded">
      <div class="p-5 space-y-4">
        <!-- Meta bar -->
        <BaseFormRow :cols="3" :gap="3" class="text-sm">
          <BaseFormField label="Título">
            <BaseInput
              v-model="localSection.title"
              @change="onMetaChange"
            />
          </BaseFormField>
          <BaseFormField label="Visibilidad">
            <BaseSelect
              v-model="localSection.visibility"
              :options="visibilityOptions"
              @update:model-value="onMetaChange"
            />
          </BaseFormField>
          <!-- Not a field: it has to claim the three bands itself to sit
               alongside them instead of dropping into the label band. -->
          <div class="flex items-center gap-3 sm:row-span-3 sm:self-center">
            <label class="inline-flex items-center gap-2 text-sm text-text-muted">
              <BaseCheckbox v-model="localSection.is_enabled" @update:model-value="onMetaChange" />
              Activa en la vista pública
            </label>
          </div>
        </BaseFormRow>

        <!-- Per-type form -->
        <component
          :is="FormComponent"
          v-model="form"
          @update:modelValue="onFormChange"
        />

        <!-- Footer -->
        <div class="flex items-center justify-between pt-3 border-t border-border-muted">
          <BaseButton variant="link" size="sm" @click="$emit('reset')">
            Restaurar contenido por defecto
          </BaseButton>
          <div class="text-xs" :class="saveError ? 'text-danger-strong' : 'text-text-subtle'">
            <span v-if="isSaving">Guardando…</span>
            <template v-else-if="saveError">
              <span role="alert">⚠ No se guardó: {{ saveError }}</span>
              <button
                type="button"
                class="ml-2 underline font-medium rounded focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
                @click="$emit('retry')"
              >Reintentar</button>
            </template>
            <span v-else-if="lastSavedAt">Guardado {{ lastSavedAt }}</span>
          </div>
        </div>
      </div>
    </BaseCollapse>
  </div>
</template>

<script setup>
import { resolveEditorialContent } from '~/utils/editorialMetadata';
import { ref, reactive, computed, watch, shallowRef } from 'vue';
import BaseCollapse from '~/components/base/BaseCollapse.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import BaseCheckbox from '~/components/base/BaseCheckbox.vue';
import {
  SECTION_META,
  VISIBILITY_OPTIONS,
  buildFormFromJson,
  formToJson,
} from './diagnosticSectionEditorUtils';
import PurposeForm from './sections/PurposeForm.vue';
import RadiographyForm from './sections/RadiographyForm.vue';
import CategoriesForm from './sections/CategoriesForm.vue';
import DeliveryStructureForm from './sections/DeliveryStructureForm.vue';
import ExecutiveSummaryForm from './sections/ExecutiveSummaryForm.vue';
import CostForm from './sections/CostForm.vue';
import TimelineForm from './sections/TimelineForm.vue';
import ScopeForm from './sections/ScopeForm.vue';

const props = defineProps({
  section: { type: Object, required: true },
  isSaving: { type: Boolean, default: false },
  lastSavedAt: { type: String, default: '' },
  /** Persistent autosave failure for this section ('' = healthy). */
  saveError: { type: String, default: '' },
});

const emit = defineEmits(['update:section', 'update:content', 'reset', 'retry']);

const expanded = ref(false);
const visibilityOptions = VISIBILITY_OPTIONS;
const bodyId = computed(() => `diagnostic-section-body-${props.section.id}`);

const meta = computed(() => SECTION_META[props.section.section_type] || { label: props.section.section_type, icon: '📄' });
const visibilityLabel = computed(() =>
  visibilityOptions.find((o) => o.value === props.section.visibility)?.label ?? props.section.visibility,
);

const FORM_COMPONENTS = {
  purpose: PurposeForm,
  radiography: RadiographyForm,
  categories: CategoriesForm,
  delivery_structure: DeliveryStructureForm,
  executive_summary: ExecutiveSummaryForm,
  cost: CostForm,
  timeline: TimelineForm,
  scope: ScopeForm,
};

const FormComponent = shallowRef(FORM_COMPONENTS[props.section.section_type] || null);

const localSection = reactive({
  title: props.section.title,
  visibility: props.section.visibility,
  is_enabled: props.section.is_enabled,
});

const form = ref(buildFormFromJson(props.section.section_type, resolveEditorialContent(props.section.content_json, props.section.text_formats, '/content_json')));

// Rehydrate only when the incoming section row swaps (different id/type) —
// not on every inbound save merge, otherwise in-flight keystrokes are
// clobbered by the parent's merge after the debounced save returns.
watch(
  () => [props.section.id, props.section.section_type],
  () => {
    localSection.title = props.section.title;
    localSection.visibility = props.section.visibility;
    localSection.is_enabled = props.section.is_enabled;
    FormComponent.value = FORM_COMPONENTS[props.section.section_type] || null;
    form.value = buildFormFromJson(props.section.section_type, resolveEditorialContent(props.section.content_json, props.section.text_formats, '/content_json'));
  },
);

function onMetaChange() {
  emit('update:section', { ...localSection });
}

function onFormChange(next) {
  form.value = next;
  const contentJson = formToJson(props.section.section_type, next);
  emit('update:content', contentJson);
}
</script>
