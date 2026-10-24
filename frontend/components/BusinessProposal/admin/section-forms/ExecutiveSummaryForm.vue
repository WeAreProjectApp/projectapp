<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="1" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.paragraphs" :lines="true" format-path="/paragraphs" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Párrafos" help="Un párrafo por línea" :rows="6" />
  <FieldInput v-model="form.highlightsTitle" label="Título de highlights" />
  <FieldTextarea v-model="form.highlights" :lines="true" format-path="/highlights" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Highlights / Incluye" help="Un item por línea" :rows="4" />
</template>

<script setup>
import { FieldInput, FieldTextarea } from './fields.js';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
