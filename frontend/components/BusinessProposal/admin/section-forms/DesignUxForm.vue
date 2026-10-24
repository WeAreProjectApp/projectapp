<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="4" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.paragraphs" :lines="true" format-path="/paragraphs" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Párrafos" help="Un párrafo por línea" :rows="6" />
  <FieldInput v-model="form.focusTitle" label="Título de enfoque" />
  <FieldTextarea v-model="form.focusItems" :lines="true" format-path="/focusItems" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Items de enfoque" help="Un item por línea" :rows="4" />
  <FieldInput v-model="form.objectiveTitle" label="Título del objetivo" />
  <FieldTextarea v-model="form.objective" :format="form.text_formats?.['/objective'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/objective': $event }" label="Objetivo" :rows="3" :isSingle="true" />
</template>

<script setup>
import { FieldInput, FieldTextarea } from './fields.js';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
