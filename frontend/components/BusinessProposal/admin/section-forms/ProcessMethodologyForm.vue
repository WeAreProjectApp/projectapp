<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="5" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.intro" :format="form.text_formats?.['/intro'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/intro': $event }" label="Introducción" :rows="3" :isSingle="true" />
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Pasos del proceso</label>
    <draggable v-model="form.steps" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
      <template #item="{ element: step, index: idx }">
        <div class="mb-3 bg-surface-raised rounded-xl p-3 border border-border-muted">
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-2">
              <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
              <span class="text-xs text-text-subtle">Paso {{ idx + 1 }}</span>
            </div>
            <BaseButton variant="danger-ghost" size="sm" @click="form.steps.splice(idx, 1)">Eliminar</BaseButton>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <EmojiIconField v-model="step.icon" label="Icono" placeholder="🔍" />
            <FieldInput v-model="step.title" label="Título" />
          </div>
          <FieldInput v-model="step.description" label="Descripción" class="mt-1" />
          <FieldInput v-model="step.clientAction" label="Acción del cliente" class="mt-1" />
        </div>
      </template>
    </draggable>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="form.steps.push({ icon: '', title: '', description: '', clientAction: '' })"><BaseActionIcon action="create" /> Agregar paso</button>
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
