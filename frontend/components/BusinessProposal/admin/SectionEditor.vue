<template>
  <div class="section-editor" data-testid="section-editor">
    <!-- Section title -->
    <label class="block mb-5">
      <span class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1">Título de la sección</span>
      <input
        v-model="sectionTitle"
        type="text"
        class="bg-input-bg w-full px-4 py-2.5 border border-border-default rounded-xl text-sm
               focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none
               dark:border-white/[0.08]"
      />
    </label>

    <TechnicalDocumentEditor
      v-if="sectionType === 'technical_document'"
      :section="section"
      :module-link-options="moduleLinkOptions"
      :item-link-options="itemLinkOptions"
      @save="emit('save', $event)"
    />

    <!-- Paste mode toggle -->
    <div v-else-if="hasPasteSupport" class="mb-5">
      <div class="flex items-center gap-3 mb-3">
        <button
          type="button"
          class="text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors"
          :class="!pasteMode
            ? 'bg-primary text-on-primary border-primary'
            : 'bg-surface text-text-muted/60 border-border-default dark:border-white/[0.08] hover:border-text-muted'"
          @click="onTogglePasteMode(false)"
        >Formulario</button>
        <button
          type="button"
          class="text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors"
          :class="pasteMode
            ? 'bg-primary text-on-primary border-primary'
            : 'bg-surface text-text-muted/60 border-border-default dark:border-white/[0.08] hover:border-text-muted'"
          @click="onTogglePasteMode(true)"
        >Pegar contenido</button>
        <BaseActionButton action="view" label="Previsualizar" @click="showPreview = true" />
      </div>

      <div v-if="pasteMode" class="space-y-3">
        <p class="text-[11px] text-text-muted">
          El contenido de este campo se mostrará directamente en la propuesta del cliente.
          Puedes usar formato Markdown (negritas, listas, etc.).
        </p>
        <textarea
          v-model="pasteText"
          rows="18"
          data-testid="paste-textarea"
          placeholder="Escribe o pega aquí el contenido de esta sección..."
          class="bg-input-bg w-full px-4 py-3 border border-border-default rounded-xl text-sm font-mono
                 focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-y
                 dark:border-white/[0.08]"
        />
      </div>
    </div>

    <!-- Dynamic form fields based on section_type -->
    <div v-show="!pasteMode && sectionType !== 'technical_document'" class="space-y-5">
      <component
        :is="activeFormComponent"
        v-if="activeFormComponent && sectionType !== 'functional_requirements'"
        :form="form"
        :proposal-data="proposalData"
        v-bind="sectionType === 'value_added_modules' ? { allSections } : {}"
      />
    </div>

    <!-- Functional requirements render outside the paste-mode wrapper:
         their groups/modules stay visible regardless of paste mode -->
    <component
      :is="activeFormComponent"
      v-if="activeFormComponent && sectionType === 'functional_requirements'"
      :form="form"
      :proposal-data="proposalData"
      :paste-mode="pasteMode"
      @preview-sub="onPreviewSub"
    />

    <!-- Raw JSON toggle -->
    <div v-if="sectionType !== 'technical_document'" class="mt-6 border-t border-border-muted pt-4">
      <button type="button" class="text-xs text-text-subtle hover:text-text-muted" @click="showRawJson = !showRawJson">
        {{ showRawJson ? 'Ocultar' : 'Mostrar' }} JSON crudo
      </button>
      <div v-if="showRawJson" class="mt-2">
        <textarea
          v-model="rawJsonText"
          rows="10"
          class="w-full px-4 py-3 border border-border-default dark:border-white/[0.08] rounded-xl text-xs font-mono bg-surface-raised dark:text-white resize-y outline-none"
          readonly
        />
      </div>
    </div>

    <!-- Save button -->
    <div v-if="sectionType !== 'technical_document'" class="flex flex-wrap items-center gap-3 mt-5">
      <BaseButton variant="primary" size="md" :disabled="isSaving" @click="handleSave">
        {{ isSaving ? 'Guardando...' : 'Guardar Sección' }}
      </BaseButton>
      <BaseButton variant="secondary" size="md" @click="showPreview = true">
        <span class="flex items-center gap-1.5">
          <BaseActionIcon action="view" />
          Previsualizar
        </span>
      </BaseButton>
    </div>
    <p v-if="sectionType !== 'technical_document' && validationError" class="mt-2 text-sm text-danger-strong bg-danger-soft border border-danger-strong/30 rounded-lg px-4 py-2">{{ validationError }}</p>

    <!-- Section preview modal -->
    <SectionPreviewModal
      :visible="showPreview"
      :section="previewSection"
      :proposalData="proposalData"
      @close="showPreview = false"
    />

    <!-- Sub-section preview modal -->
    <SectionPreviewModal
      :visible="showSubPreview"
      :section="previewSection"
      :proposalData="proposalData"
      :subSection="subPreviewData"
      @close="showSubPreview = false"
    />
  </div>
</template>

<script setup>
import { resolveEditorialContent, withoutEditorialPrefix } from '~/utils/editorialMetadata';
import { reactive, ref, computed, watch } from 'vue';
import SectionPreviewModal from '~/components/BusinessProposal/admin/SectionPreviewModal.vue';
import TechnicalDocumentEditor from '~/components/BusinessProposal/admin/TechnicalDocumentEditor.vue';
import { sectionFormRegistry } from '~/components/BusinessProposal/admin/section-forms/index.js';
import {
  buildFormFromJson as _buildFormFromJson,
  formToJson as _formToJson,
  formToReadableText as _formToReadableText,
} from '~/components/BusinessProposal/admin/sectionEditorUtils.js';

const props = defineProps({
  section: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
  /** { id, label }[] for technical_document linked_module_ids */
  moduleLinkOptions: { type: Array, default: () => [] },
  /** { groupId, groupLabel, items }[] for technical_document linked_item_ids */
  itemLinkOptions: { type: Array, default: () => [] },
  /** All sections in the proposal (used by value_added_modules to discover available group ids). */
  allSections: { type: Array, default: () => [] },
});

const emit = defineEmits(['save', 'syncHostingPercent', 'dirty-change']);
// emit exposed for TechnicalDocumentEditor @save in template

const sectionType = computed(() => props.section.section_type);
const sectionTitle = ref(props.section.title);
const isSaving = ref(false);
const showPreview = ref(false);
const showSubPreview = ref(false);
const subPreviewData = ref(null);

/** Per-type form component resolved from the section-forms registry. */
const activeFormComponent = computed(() => sectionFormRegistry[sectionType.value]?.component || null);

const previewSection = computed(() => {
  const contentJson = formToJson(form, sectionType.value);
  if (pasteMode.value) {
    contentJson._editMode = 'paste';
    contentJson.rawText = pasteText.value;
  }
  return {
    id: props.section.id,
    section_type: sectionType.value,
    title: sectionTitle.value,
    content_json: contentJson,
  };
});
const validationError = ref('');
const showRawJson = ref(false);
const initialContent = props.section.content_json || {};
const pasteMode = ref(initialContent._editMode === 'paste');
const pasteText = ref(initialContent.rawText || '');

const hasPasteSupport = computed(() => true);

function formToReadableText() {
  return _formToReadableText(form, sectionType.value);
}

function onTogglePasteMode(on) {
  pasteMode.value = on;
  if (on) {
    pasteText.value = formToReadableText();
  }
}

function onPreviewSub(payload) {
  subPreviewData.value = payload;
  showSubPreview.value = true;
}

// --- Build form state from content_json ---
const form = reactive(buildFormFromJson(resolveEditorialContent(props.section.content_json, props.section.text_formats, '/content_json'), props.section.section_type));

watch(() => props.section, (s) => {
  sectionTitle.value = s.title;
  Object.assign(form, buildFormFromJson(resolveEditorialContent(s.content_json, s.text_formats, '/content_json'), s.section_type));
  // A store refresh (save success, panel refresh) is the new clean state.
  baselineSignature.value = dirtySignature();
}, { deep: true });

// Auto-sync paste text from form data (keeps paste area current while editing in form mode)
watch(
  () => _formToReadableText(form, sectionType.value),
  (newText) => {
    if (!pasteMode.value) pasteText.value = newText;
  },
);

// --- Dirty tracking ---
// Paste text only participates while in paste mode: in form mode the
// auto-sync watch above mutates it constantly, which would false-flag.
function dirtySignature() {
  return JSON.stringify({
    title: sectionTitle.value,
    json: formToJson(form, sectionType.value),
    paste: pasteMode.value ? pasteText.value : null,
  });
}
const baselineSignature = ref(dirtySignature());
const isDirty = computed(() => dirtySignature() !== baselineSignature.value);
watch(isDirty, (dirty) => emit('dirty-change', dirty));

defineExpose({ save: handleSave, isDirty });

// --- Helpers: JSON ↔ form conversion (delegated to sectionEditorUtils.js) ---

function buildFormFromJson(json, type) {
  return _buildFormFromJson(json, type, props.proposalData);
}

function formToJson(formData, type) {
  return _formToJson(formData, type);
}

const rawJsonText = computed(() => {
  try {
    return JSON.stringify(formToJson(form, sectionType.value), null, 2);
  } catch { return '{}'; }
});

function validateOptionalPrices() {
  const missing = [];
  const type = sectionType.value;

  if (type === 'investment') {
    const modules = form.modules || [];
    for (const mod of modules) {
      if (mod.is_required === false && !mod.price) {
        missing.push(mod.name || 'Módulo sin nombre');
      }
    }
  } else if (type === 'functional_requirements') {
    const allGroups = [...(form.groups || []), ...(form.additionalModules || [])];
    for (const group of allGroups) {
      for (const item of (group.items || [])) {
        if (item.is_required === false && !item.price) {
          missing.push(item.name || 'Elemento sin nombre');
        }
      }
    }
  }

  return missing;
}

function handleSave() {
  isSaving.value = true;
  validationError.value = '';
  try {
    // Hard validation: optional items must have a price
    const missingPrices = validateOptionalPrices();
    if (missingPrices.length > 0) {
      validationError.value = `No se puede guardar: los siguientes elementos opcionales (Obligatorio = No) no tienen precio asignado: ${missingPrices.join(', ')}`;
      isSaving.value = false;
      return;
    }

    const contentJson = formToJson(form, sectionType.value);
    if (pasteMode.value) {
      contentJson._editMode = 'paste';
      contentJson.rawText = pasteText.value;
    } else {
      contentJson._editMode = 'form';
      delete contentJson.rawText;
    }
    emit('save', {
      sectionId: props.section.id,
      payload: {
        ...(props.section.proposal_source_hash ? { source_hash: props.section.proposal_source_hash } : {}),
        title: sectionTitle.value,
        is_wide_panel: props.section.is_wide_panel,
        content_json: contentJson,
        ...(props.section.text_formats ? { text_formats: withoutEditorialPrefix(props.section.text_formats, '/content_json') } : {}),
      },
    });
    // Sync hostingPercent back to General tab when saving the investment section
    if (sectionType.value === 'investment' && form.hostingPlan?.hostingPercent != null) {
      emit('syncHostingPercent', form.hostingPlan.hostingPercent);
    }
    // Success/failure feedback is owned by the parent (collapse on success,
    // notification on error) — the save request is still in flight here.
  } finally {
    isSaving.value = false;
  }
}
</script>
