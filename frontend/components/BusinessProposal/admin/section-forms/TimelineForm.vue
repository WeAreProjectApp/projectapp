<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="8" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.introText" :format="form.text_formats?.['/introText'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/introText': $event }" label="Texto introductorio" :rows="3" :isSingle="true" />
  <FieldInput v-model="form.totalDuration" label="Duración total" placeholder="Aproximadamente 1 mes" />
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Fases</label>
    <draggable v-model="form.phases" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
      <template #item="{ element: phase, index: idx }">
        <div class="mb-4 bg-surface-raised rounded-xl p-4 border border-border-muted">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
              <span class="text-xs text-text-subtle">Fase {{ idx + 1 }}</span>
            </div>
            <BaseButton variant="danger-ghost" size="sm" @click="form.phases.splice(idx, 1)">Eliminar</BaseButton>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-2">
            <FieldInput v-model="phase.title" label="Título" />
            <FieldInput v-model="phase.duration" label="Duración" placeholder="2 semanas" />
          </div>
          <FieldTextarea v-model="phase.description" :format="phase.text_formats?.['/description'] || 'plain'" @update:format="phase.text_formats = { ...phase.text_formats, '/description': $event }" label="Descripción" :rows="2" :isSingle="true" />
          <FieldTextarea v-model="phase.tasks" :lines="true" format-path="/tasks" :formats="phase.text_formats || {}" @update:formats="phase.text_formats = $event" label="Tareas" help="Una por línea" :rows="3" />
          <FieldInput v-model="phase.milestone" label="Hito / Milestone" class="mt-2" />
        </div>
      </template>
    </draggable>
    <button type="button" class="text-xs text-text-brand hover:text-text-brand font-medium" @click="form.phases.push({ title: '', duration: '', description: '', tasks: '', milestone: '' })">
      <BaseActionIcon action="create" />
      Agregar fase
    </button>
  </div>
</template>

<script setup>
import { FieldInput, FieldTextarea } from './fields.js';
import draggable from 'vuedraggable';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
