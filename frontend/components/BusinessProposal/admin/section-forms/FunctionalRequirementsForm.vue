<template>
  <!-- Intro fields: hidden while the section-level paste mode is active -->
  <div v-show="!pasteMode" class="space-y-5">
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <FieldInput v-model="form.index" label="Índice" placeholder="7" />
      <FieldInput v-model="form.title" label="Título" />
    </div>
    <FieldTextarea v-model="form.intro" label="Introducción" :rows="3" :isSingle="true" />
  </div>

  <!-- Functional requirements groups: always visible regardless of paste mode -->
  <!-- Groups: collapsible -->
  <div v-for="(group, gIdx) in form.groups" :key="group.id || gIdx" :data-testid="`requirement-group-${group.id || gIdx}`" class="mt-4 border border-border-default dark:border-white/[0.08] rounded-xl overflow-hidden">
    <!-- Collapse header -->
    <div class="flex flex-wrap items-center justify-between gap-2 px-3 sm:px-4 py-3 bg-surface-raised cursor-pointer hover:bg-surface-raised transition-colors"
         @click="group._collapsed = !group._collapsed">
      <h4 class="text-sm font-semibold text-text-default flex items-center gap-2">
        <BaseActionIcon :action="group._collapsed ? 'expand' : 'collapse'" />
        <span>{{ group.icon }}</span> {{ group.title }}
        <span class="text-[10px] text-text-subtle font-normal">({{ (group.items || []).length }} elementos)</span>
      </h4>
      <div class="flex flex-wrap items-center gap-2" @click.stop>
        <button type="button" class="text-[10px] font-medium px-2 py-1 rounded border transition-colors"
          :class="!group._pasteMode ? 'bg-primary text-on-primary border-primary' : 'bg-surface text-text-muted border-border-default'"
          @click="onToggleGroupPaste(group, false)">Formulario</button>
        <button type="button" class="text-[10px] font-medium px-2 py-1 rounded border transition-colors"
          :class="group._pasteMode ? 'bg-primary text-on-primary border-primary' : 'bg-surface text-text-muted border-border-default'"
          @click="onToggleGroupPaste(group, true)">Pegar contenido</button>
        <BaseActionButton action="view" label="Previsualizar módulo" size="sm" @click="openSubPreview(group, gIdx)" />
        <label class="flex items-center gap-1 cursor-pointer" title="Si está marcado, este módulo forma parte del alcance de la propuesta">
          <input type="checkbox" v-model="group.selected" class="rounded border-input-border text-text-brand focus:ring-focus-ring/30" />
          <span class="text-[10px] text-text-muted font-medium">Seleccionado</span>
        </label>
        <button type="button" class="text-[10px] font-medium px-2 py-1 rounded border transition-colors"
          :class="group.is_calculator_module ? 'bg-info-soft text-info-strong border-info-strong/30' : 'bg-surface-raised text-text-subtle border-border-default dark:border-white/[0.08]'"
          :title="group.is_calculator_module ? 'Módulo opcional: se incluye cuando está seleccionado' : 'Grupo base del alcance'"
          @click="group.is_calculator_module = !group.is_calculator_module">
          <BaseActionIcon action="calculate" /> {{ group.is_calculator_module ? 'Opcional' : 'Base' }}
        </button>
        <button type="button" class="text-[10px] font-medium px-2 py-1 rounded border transition-colors"
          :class="group.is_visible !== false ? 'bg-primary-soft text-text-brand border-emerald-300' : 'bg-danger-soft text-danger-strong border-danger-strong/30'"
          :title="group.is_visible !== false ? 'Este módulo se muestra en la propuesta del cliente' : 'Este módulo está oculto en la propuesta del cliente'"
          @click="group.is_visible = group.is_visible === false ? true : false">
          <BaseActionIcon :action="group.is_visible !== false ? 'view' : 'hide'" /> {{ group.is_visible !== false ? 'Visible' : 'Oculto' }}
        </button>
        <BaseButton variant="danger-ghost" size="sm" class="ml-2" v-if="!protectedGroupIds.has(group.id)" :data-testid="'delete-requirement-group-' + (group.id || gIdx)" title="Eliminar este grupo de la propuesta" @click="form.groups.splice(gIdx, 1)">Eliminar</BaseButton>
      </div>
    </div>

    <!-- Collapse content -->
    <div v-show="!group._collapsed" class="p-4">
      <!-- Paste mode for this group -->
      <div v-if="group._pasteMode" class="space-y-3">
        <p class="text-[11px] text-text-muted">Contenido Markdown para esta sub-sección.</p>
        <textarea v-model="group._pasteText" rows="10" data-testid="group-paste-textarea" placeholder="Escribe o pega aquí el contenido de este grupo..."
          class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm font-mono focus:ring-1 focus:ring-focus-ring/30 outline-none resize-y" />
      </div>

      <!-- Form mode for this group -->
      <div v-else class="space-y-3">
        <div class="grid grid-cols-[100px_1fr] gap-3 items-end">
          <EmojiIconField v-model="group.icon" label="Icono" placeholder="🖥️" />
          <FieldInput v-model="group.title" label="Título del grupo" />
        </div>
        <FieldTextarea v-model="group.description" label="Descripción" :rows="2" :isSingle="true" />
        <div>
          <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Elementos</label>
          <draggable v-model="group.items" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
            <template #item="{ element: item, index: iIdx }">
              <div class="mb-2 bg-surface-raised rounded-lg p-3 border border-border-muted">
                <div class="flex items-center justify-between mb-1">
                  <div class="flex items-center gap-2">
                    <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
                    <span class="text-[10px] text-text-subtle">{{ iIdx + 1 }}</span>
                  </div>
                  <BaseButton variant="danger-ghost" size="sm" @click="group.items.splice(iIdx, 1)">Eliminar</BaseButton>
                </div>
                <div class="grid grid-cols-[90px_1fr] gap-2 mb-1">
                  <EmojiIconField v-model="item.icon" label="Icono" placeholder="🏠" />
                  <FieldInput v-model="item.name" label="Nombre" />
                </div>
                <FieldTextarea v-model="item.description" label="Descripción" :rows="2" :isSingle="true" />
                <div class="mt-1" title="Identificador estable usado para enlazar requerimientos técnicos. Se genera automáticamente al guardar; no lo cambies si ya tiene requerimientos enlazados.">
                  <FieldInput v-model="item.id" label="ID (enlace técnico)" placeholder="auto al guardar" />
                </div>
              </div>
            </template>
          </draggable>
          <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="group.items.push({ id: '', icon: '', name: '', description: '' })"><BaseActionIcon action="create" /> Agregar elemento</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Additional Modules: collapsible -->
  <div class="mt-6">
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Módulos Adicionales</label>
    <div v-for="(mod, mIdx) in form.additionalModules" :key="mIdx" class="mb-4 border border-border-default dark:border-white/[0.08] rounded-xl overflow-hidden">
      <div class="flex flex-wrap items-center justify-between gap-2 px-3 sm:px-4 py-3 bg-surface-raised cursor-pointer hover:bg-surface-raised transition-colors"
           @click="mod._collapsed = !mod._collapsed">
        <h4 class="text-sm font-semibold text-text-default flex items-center gap-2">
          <BaseActionIcon :action="mod._collapsed ? 'expand' : 'collapse'" />
          <span>{{ mod.icon || '🧩' }}</span> {{ mod.title || 'Módulo adicional' }}
        </h4>
        <div class="flex flex-wrap items-center gap-2" @click.stop>
          <button type="button" class="text-[10px] font-medium px-2 py-1 rounded border transition-colors"
            :class="!mod._pasteMode ? 'bg-primary text-on-primary border-primary' : 'bg-surface text-text-muted border-border-default'"
            @click="onToggleGroupPaste(mod, false)">Formulario</button>
          <button type="button" class="text-[10px] font-medium px-2 py-1 rounded border transition-colors"
            :class="mod._pasteMode ? 'bg-primary text-on-primary border-primary' : 'bg-surface text-text-muted border-border-default'"
            @click="onToggleGroupPaste(mod, true)">Pegar contenido</button>
          <BaseActionButton action="view" label="Previsualizar funcionalidad" size="sm" @click="openSubPreview(mod, mIdx, true)" />
          <label class="flex items-center gap-1 cursor-pointer" title="Si está marcado, este módulo forma parte del alcance de la propuesta">
            <input type="checkbox" v-model="mod.selected" class="rounded border-input-border text-text-brand focus:ring-focus-ring/30" />
            <span class="text-[10px] text-text-muted font-medium">Seleccionado</span>
          </label>
          <button type="button" class="text-[10px] font-medium px-2 py-1 rounded border transition-colors"
            :class="mod.is_calculator_module ? 'bg-info-soft text-info-strong border-info-strong/30' : 'bg-surface-raised text-text-subtle border-border-default dark:border-white/[0.08]'"
            :title="mod.is_calculator_module ? 'Módulo opcional: se incluye cuando está seleccionado' : 'Grupo base del alcance'"
            @click="mod.is_calculator_module = !mod.is_calculator_module">
            <BaseActionIcon action="calculate" /> {{ mod.is_calculator_module ? 'Opcional' : 'Base' }}
          </button>
          <button type="button" class="text-[10px] font-medium px-2 py-1 rounded border transition-colors"
            :class="mod.is_visible !== false ? 'bg-primary-soft text-text-brand border-emerald-300' : 'bg-danger-soft text-danger-strong border-danger-strong/30'"
            :title="mod.is_visible !== false ? 'Este módulo se muestra en la propuesta del cliente' : 'Este módulo está oculto en la propuesta del cliente'"
            @click="mod.is_visible = mod.is_visible === false ? true : false">
            <BaseActionIcon :action="mod.is_visible !== false ? 'view' : 'hide'" /> {{ mod.is_visible !== false ? 'Visible' : 'Oculto' }}
          </button>
          <BaseButton variant="danger-ghost" size="sm" class="ml-2" title="Eliminar este módulo de la propuesta" @click="form.additionalModules.splice(mIdx, 1)">Eliminar</BaseButton>
        </div>
      </div>
      <div v-show="!mod._collapsed" class="p-4">
        <div v-if="mod._pasteMode" class="space-y-3">
          <p class="text-[11px] text-text-muted">Contenido Markdown para este módulo.</p>
          <textarea v-model="mod._pasteText" rows="8" placeholder="Escribe o pega aquí el contenido de este módulo..."
            class="w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm font-mono focus:ring-1 focus:ring-focus-ring/30 outline-none resize-y" />
        </div>
        <div v-else class="space-y-3">
          <div class="grid grid-cols-[100px_1fr] gap-3 items-end">
            <EmojiIconField v-model="mod.icon" label="Icono" placeholder="🧩" />
            <FieldInput v-model="mod.title" label="Título del módulo" />
          </div>
          <FieldTextarea v-model="mod.description" label="Descripción" :rows="2" :isSingle="true" />
          <div>
            <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Elementos</label>
            <draggable v-model="mod.items" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
              <template #item="{ element: item, index: iIdx }">
                <div class="mb-2 bg-surface-raised rounded-lg p-3 border border-border-muted">
                  <div class="flex items-center justify-between mb-1">
                    <div class="flex items-center gap-2">
                      <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
                      <span class="text-[10px] text-text-subtle">{{ iIdx + 1 }}</span>
                    </div>
                    <BaseButton variant="danger-ghost" size="sm" @click="mod.items.splice(iIdx, 1)">Eliminar</BaseButton>
                  </div>
                  <div class="grid grid-cols-[90px_1fr] gap-2 mb-1">
                    <EmojiIconField v-model="item.icon" label="Icono" />
                    <FieldInput v-model="item.name" label="Nombre" />
                  </div>
                  <FieldTextarea v-model="item.description" label="Descripción" :rows="2" :isSingle="true" />
                  <div class="mt-1" title="Identificador estable usado para enlazar requerimientos técnicos. Se genera automáticamente al guardar; no lo cambies si ya tiene requerimientos enlazados.">
                    <FieldInput v-model="item.id" label="ID (enlace técnico)" placeholder="auto al guardar" />
                  </div>
                </div>
              </template>
            </draggable>
            <BaseButton variant="link" size="sm" @click="mod.items.push({ id: '', icon: '', name: '', description: '' })"><BaseActionIcon action="create" /> Agregar elemento</BaseButton>
          </div>
        </div>
      </div>
    </div>
    <BaseButton variant="link" size="sm" @click="addAdditionalModule">
      <BaseActionIcon action="create" /> Agregar módulo adicional
    </BaseButton>
  </div>
</template>

<script setup>
import { watch } from 'vue';
import { FieldInput, FieldTextarea } from './fields.js';
import EmojiIconField from '~/components/BusinessProposal/admin/EmojiIconField.vue';
import draggable from 'vuedraggable';
import { groupToReadableText as _groupToReadableText } from '~/components/BusinessProposal/admin/sectionEditorUtils.js';

const protectedGroupIds = new Set([
  'views',
  'components',
  'features',
  'cross_cutting_features',
]);

const props = defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
  /** Section-level paste mode owned by SectionEditor; gates only the intro fields. */
  pasteMode: { type: Boolean, default: false },
});

const emit = defineEmits(['preview-sub']);

function groupToReadableText(group) {
  return _groupToReadableText(group);
}

function onToggleGroupPaste(group, on) {
  group._pasteMode = on;
  if (on) {
    group._pasteText = groupToReadableText(group);
  }
}

function openSubPreview(group, idx, isAdditional = false) {
  const baseIndex = props.form.index || '7';
  const offset = isAdditional ? props.form.groups.length + idx + 1 : idx + 1;
  emit('preview-sub', {
    group: { ...group, items: [...(group.items || [])] },
    subIndex: `${baseIndex}.${offset}`,
  });
}

function addAdditionalModule() {
  form.additionalModules.push({
    id: `module_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    icon: '🧩',
    title: '',
    description: '',
    is_visible: true,
    selected: false,
    is_calculator_module: false,
    default_selected: false,
    is_invite: false,
    invite_note: '',
    items: [],
    _pasteMode: false,
    _pasteText: '',
    _collapsed: false,
  });
}

// Auto-sync group/module paste text for functional_requirements subsections
watch(
  () => {
    return [...props.form.groups, ...props.form.additionalModules].map(g => {
      const itemsSig = (g.items || []).map(i =>
        `${i.icon}|${i.name}|${i.description}`
      ).join('~');
      return `${g.title}|${g.icon}|${g.description}|${itemsSig}`;
    }).join('||');
  },
  () => {
    for (const g of props.form.groups) {
      if (!g._pasteMode) g._pasteText = _groupToReadableText(g);
    }
    for (const m of props.form.additionalModules) {
      if (!m._pasteMode) m._pasteText = _groupToReadableText(m);
    }
  },
);
</script>
