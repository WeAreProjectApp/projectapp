<template>
  <div>
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
  <!-- F10: Section completeness indicator -->
  <div v-if="allSections.length" class="mb-4 bg-surface rounded-xl shadow-sm border border-border-muted px-5 py-4">
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-1">
        <span class="text-xs font-semibold text-text-muted uppercase tracking-wider">Completitud de secciones</span>
        <BaseTooltip position="right">
          <template #trigger>
            <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
          </template>
          {{ tt.sectionCompleteness }}
        </BaseTooltip>
      </div>
      <span class="text-sm font-bold" :class="sectionCompleteness >= 80 ? 'text-text-brand' : sectionCompleteness >= 50 ? 'text-warning-strong' : 'text-danger-strong'">
        {{ sectionCompleteness }}%
      </span>
    </div>
    <div class="w-full h-2 bg-surface-raised rounded-full overflow-hidden">
      <div
        class="h-full rounded-full transition-all duration-500"
        :class="sectionCompleteness >= 80 ? 'bg-primary' : sectionCompleteness >= 50 ? 'bg-warning-strong' : 'bg-danger-strong'"
        :style="{ width: sectionCompleteness + '%' }"
      />
    </div>
    <p class="text-[11px] text-text-subtle mt-1.5">
      {{ sectionsWithContent }}/{{ enabledSectionsCount }} secciones comerciales habilitadas tienen contenido (sin contar «Det. técnico» — pestaña dedicada).
    </p>
  </div>

  <div class="mb-3 flex justify-end">
    <BaseButton
      variant="secondary"
      size="sm"
      data-testid="add-section-button"
      @click="showAddSectionModal = true"
    >
      <BaseActionIcon action="create" />
      Agregar sección
    </BaseButton>
  </div>

  <BaseModal v-model="showAddSectionModal" kind="form">
    <div class="p-5">
      <h3 class="text-sm font-semibold text-text-default mb-1">Agregar sección</h3>
      <p class="text-xs text-text-subtle mb-4">
        La sección se crea con el contenido por defecto del idioma de la propuesta y se agrega al final.
      </p>
      <BaseEmptyState
        v-if="!availableSectionTypes.length"
        title="Nada por agregar"
        description="La propuesta ya tiene todas las secciones disponibles."
      />
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <BaseButton variant="secondary" size="md" v-for="option in availableSectionTypes" :key="option.type" :data-testid="`add-section-option-${option.type}`" :disabled="proposalStore.isUpdating" @click="handleAddSection(option.type)">
          {{ option.label }}
          <span class="block text-[11px] text-text-subtle">{{ option.type }}</span>
        </BaseButton>
      </div>
    </div>
  </BaseModal>

  <draggable
    v-model="localSections"
    item-key="id"
    handle=".section-drag-handle"
    ghost-class="opacity-30"
    :disabled="proposalStore.isUpdating"
    class="space-y-3"
    @end="onSectionReorderEnd"
  >
    <template #item="{ element: section }">
    <div
      class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden"
    >
      <!-- Section header -->
      <div
        :data-testid="`section-header-${section.section_type}`"
        class="px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-2 cursor-pointer hover:bg-surface-raised transition-colors"
        @click="toggleSection(section.id)"
      >
        <div class="flex items-center gap-4">
          <span
            class="section-drag-handle cursor-grab select-none text-text-subtle"
            :data-testid="`section-drag-handle-${section.section_type}`"
            title="Arrastra para reordenar"
            @click.stop
          >⠿</span>
          <span class="text-xs text-text-subtle font-mono w-6">{{ section.order + 1 }}</span>
          <span class="text-sm font-medium text-text-default">{{ section.title }}</span>
          <BaseBadge
            v-if="sectionDirty.isDirty(section.id)"
            variant="warning"
            :data-testid="`section-dirty-badge-${section.section_type}`"
          >Sin guardar</BaseBadge>
          <span class="text-xs text-text-subtle">({{ section.section_type }})</span>
        </div>
        <div class="flex items-center gap-3">
          <label class="flex items-center gap-2 text-xs" @click.stop>
            <input
              type="checkbox"
              :checked="section.is_enabled"
              class="rounded border-input-border text-text-brand focus:ring-focus-ring/30"
              @change="toggleEnabled(section)"
            />
            <span class="text-text-muted">Visible</span>
          </label>
          <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar sección" :data-testid="`section-delete-${section.section_type}`" title="Eliminar sección" @click.stop="handleDeleteSection(section)">
              <BaseActionIcon action="delete" />
          </BaseButton>
          <BaseActionIcon
            :action="expandedSections.has(section.id) ? 'collapse' : 'expand'"
            class="text-text-subtle"
          />
        </div>
      </div>

      <!-- Section content editor (expanded) -->
      <div v-if="expandedSections.has(section.id)" class="border-t border-border-muted px-3 sm:px-6 py-4 sm:py-6">
        <SectionEditor
          :section="section"
          :proposalData="proposal"
          :module-link-options="moduleLinkOptions"
          :item-link-options="itemLinkOptions"
          :all-sections="allSections"
          @save="saveCommercialSection"
          @syncHostingPercent="emit('sync-hosting-percent', $event)"
          @dirty-change="sectionDirty.setDirty(section.id, $event)"
        />
      </div>
    </div>
    </template>
  </draggable>

  <!-- Sticky send bar for sections tab -->
  <div v-if="proposal.client_email" class="sticky bottom-0 mt-4 bg-surface/95 backdrop-blur-sm border border-border-muted rounded-xl shadow-lg px-5 py-3 flex items-center justify-between gap-3 z-10">
    <div class="flex items-center gap-2 text-xs text-text-muted">
      <a :href="'/proposal/' + proposal.uuid + '?preview=1'" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-text-brand hover:underline"><BaseActionIcon action="open-external" /> Preview</a>
    </div>
    <div class="flex items-center gap-3">
      <BaseButton
        v-if="proposal.status === 'draft'"
        variant="primary"
        size="md"
        class="!bg-info-strong hover:!bg-info-strong/90"
        @click="emit('send')"
      >
        <BaseActionIcon action="send" /> Enviar al Cliente
      </BaseButton>
      <BaseButton
        v-else-if="['sent', 'viewed'].includes(proposal.status)"
        variant="primary"
        size="md"
        class="!bg-info-strong hover:!bg-info-strong/90"
        @click="emit('resend')"
      >
        <BaseActionIcon action="resend" /> Re-enviar al Cliente
      </BaseButton>
    </div>
  </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { QuestionMarkCircleIcon } from '@heroicons/vue/24/outline';
import draggable from 'vuedraggable';
import SectionEditor from '~/components/BusinessProposal/admin/SectionEditor.vue';
import { SECTION_TYPE_OPTIONS } from '~/components/BusinessProposal/admin/section-forms/index.js';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { useDirtyTracker } from '~/composables/useDirtyTracker';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useProposalStore } from '~/stores/proposals';
import { useTooltipTexts } from '~/composables/useTooltipTexts';

const props = defineProps({
  proposal: { type: Object, required: true },
  /** { id, label }[] for technical_document linked_module_ids */
  moduleLinkOptions: { type: Array, default: () => [] },
  /** { groupId, groupLabel, items }[] for technical_document linked_item_ids */
  itemLinkOptions: { type: Array, default: () => [] },
});

const emit = defineEmits(['send', 'resend', 'sync-hosting-percent', 'dirty-state-change']);

const proposalStore = useProposalStore();
const notify = usePanelNotify();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const { proposalEdit: tt } = useTooltipTexts();

function notifyProposalFailure(result, fallbackTitle) {
  notify.error({
    title: result?.message || fallbackTitle,
    detail: result?.hint || '',
  });
}

// --- Section collections ---
const allSections = computed(() =>
  [...(props.proposal?.sections || [])].sort((a, b) => a.order - b.order)
);

const commercialSections = computed(() =>
  allSections.value.filter(s => s.section_type !== 'technical_document')
);

// --- Completeness ---
const enabledSectionsCount = computed(() =>
  commercialSections.value.filter(s => s.is_enabled).length
);

const sectionsWithContent = computed(() => {
  return commercialSections.value.filter(s => {
    if (!s.is_enabled) return false;
    let cj = s.content_json;
    if (typeof cj === 'string') {
      try { cj = JSON.parse(cj); } catch { cj = null; }
    }
    return cj && typeof cj === 'object' && Object.keys(cj).length > 0;
  }).length;
});

const sectionCompleteness = computed(() => {
  if (enabledSectionsCount.value === 0) return 0;
  return Math.round(sectionsWithContent.value / enabledSectionsCount.value * 100);
});

// --- Expand / collapse + dirty tracking ---
const expandedSections = ref(new Set());
const sectionDirty = useDirtyTracker();

// The page owns the route/unload/refresh guards; it only needs the boolean.
watch(sectionDirty.hasDirty, (dirty) => emit('dirty-state-change', dirty));

async function toggleSection(id) {
  if (expandedSections.value.has(id)) {
    // Collapsing unmounts the editor and discards unsaved edits.
    if (sectionDirty.isDirty(id)) {
      const ok = await requestConfirm({
        title: 'Cambios sin guardar',
        message: 'Si cierras esta sección perderás los cambios que no guardaste.',
        variant: 'warning',
        confirmText: 'Cerrar sin guardar',
        cancelText: 'Seguir editando',
      });
      if (!ok) return;
      sectionDirty.setDirty(id, false);
    }
    expandedSections.value.delete(id);
  } else {
    expandedSections.value.add(id);
  }
  expandedSections.value = new Set(expandedSections.value);
}

function collapseSection(id) {
  sectionDirty.setDirty(id, false);
  expandedSections.value.delete(id);
  expandedSections.value = new Set(expandedSections.value);
}

async function toggleEnabled(section) {
  const result = await proposalStore.updateSection(section.id, { is_enabled: !section.is_enabled });
  if (!result.success) {
    notifyProposalFailure(result, 'No se pudo actualizar la sección');
  }
}

// commercialSections never contains technical_document, so the sync-preview
// flow (accepted proposals) is unreachable here — it stays on the page's
// technical tab.
async function saveCommercialSection({ sectionId, payload }) {
  const r = await proposalStore.updateSection(sectionId, payload);
  if (r.success) {
    collapseSection(sectionId);
  } else {
    notifyProposalFailure(r, 'No se pudo guardar la sección');
  }
}

// --- Reorder (drag & drop) ---
// Mutable mirror of commercialSections for vuedraggable's v-model.
const localSections = ref([]);
watch(commercialSections, (list) => {
  localSections.value = [...list];
}, { immediate: true });

async function onSectionReorderEnd() {
  // Permute within the commercial sections' own order slots so the hidden
  // technical_document section keeps its place in the global sequence.
  const slots = localSections.value.map((s) => s.order).sort((a, b) => a - b);
  const payload = localSections.value.map((s, i) => ({ id: s.id, order: slots[i] }));
  const changed = payload.some((p, i) => localSections.value[i].order !== p.order);
  if (!changed) return;

  const result = await proposalStore.reorderSections(props.proposal.id, payload);
  if (!result?.success) {
    // Snap back to the store's canonical order.
    localSections.value = [...commercialSections.value];
    notifyProposalFailure(result || {}, 'No se pudo reordenar las secciones');
  }
}

// --- Add / delete sections ---
const showAddSectionModal = ref(false);

const availableSectionTypes = computed(() => {
  const present = new Set((props.proposal?.sections || []).map((s) => s.section_type));
  return SECTION_TYPE_OPTIONS.filter((o) => !present.has(o.type));
});

async function handleAddSection(sectionType) {
  const result = await proposalStore.createSection(props.proposal.id, sectionType);
  if (result.success) {
    showAddSectionModal.value = false;
    notify.success({ title: 'Sección agregada.' });
    if (result.data?.id) {
      expandedSections.value.add(result.data.id);
      expandedSections.value = new Set(expandedSections.value);
    }
  } else {
    notifyProposalFailure(result, 'No se pudo agregar la sección');
  }
}

function handleDeleteSection(section) {
  requestConfirm({
    title: 'Eliminar sección',
    message: `¿Eliminar la sección «${section.title}»? Esta acción no se puede deshacer.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    cancelText: 'Cancelar',
    onConfirm: async () => {
      const result = await proposalStore.deleteSection(section.id);
      if (result.success) {
        sectionDirty.setDirty(section.id, false);
        expandedSections.value.delete(section.id);
        expandedSections.value = new Set(expandedSections.value);
        notify.success({ title: 'Sección eliminada.' });
      } else {
        notifyProposalFailure(result, 'No se pudo eliminar la sección');
      }
    },
  });
}
</script>
