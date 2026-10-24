<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="6" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.intro" :format="form.text_formats?.['/intro'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/intro': $event }" label="Texto introductorio" :rows="2" :isSingle="true" />
  <FieldInput v-model="form.currentLabel" label="Etiqueta de etapa actual" placeholder="Actual" />
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Etapas</label>
    <draggable v-model="form.stages" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
      <template #item="{ element: stage, index: idx }">
        <div class="mb-4 bg-surface-raised rounded-xl p-4 border border-border-muted">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
              <span class="text-xs text-text-subtle">Etapa {{ idx + 1 }}</span>
            </div>
            <BaseButton variant="danger-ghost" size="sm" @click="form.stages.splice(idx, 1)">Eliminar</BaseButton>
          </div>
          <div class="grid grid-cols-[100px_1fr] gap-3 mb-2">
            <EmojiIconField v-model="stage.icon" label="Icono" placeholder="✉️" />
            <FieldInput v-model="stage.title" label="Título" />
          </div>
          <FieldTextarea v-model="stage.description" :format="stage.text_formats?.['/description'] || 'plain'" @update:format="stage.text_formats = { ...stage.text_formats, '/description': $event }" label="Descripción" :rows="2" :isSingle="true" />
          <label class="flex items-center gap-2 mt-2 text-xs">
            <input type="checkbox" v-model="stage.current" class="rounded border-input-border text-text-brand" />
            <span class="text-text-muted/60">Etapa actual</span>
          </label>
        </div>
      </template>
    </draggable>
    <button type="button" class="text-xs text-text-brand hover:text-text-brand font-medium" @click="form.stages.push({ icon: '', title: '', description: '', current: false })">
      <BaseActionIcon action="create" />
      Agregar etapa
    </button>
  </div>
</template>

<script setup>
import { FieldInput, FieldTextarea } from './fields.js';
import EmojiIconField from '~/components/BusinessProposal/admin/EmojiIconField.vue';
import draggable from 'vuedraggable';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
