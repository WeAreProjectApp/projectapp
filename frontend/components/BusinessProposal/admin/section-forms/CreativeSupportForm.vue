<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="5" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.paragraphs" :lines="true" format-path="/paragraphs" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Párrafos" help="Un párrafo por línea" :rows="6" />
  <FieldInput v-model="form.includesTitle" label="Título de incluye" />
  <FieldTextarea v-model="form.includes" :lines="true" format-path="/includes" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Incluye" help="Un item por línea" :rows="4" />
  <FieldTextarea v-model="form.closing" :format="form.text_formats?.['/closing'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/closing': $event }" label="Cierre" :rows="3" :isSingle="true" />
</template>

<script setup>
import { FieldInput, FieldTextarea } from './fields.js';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
