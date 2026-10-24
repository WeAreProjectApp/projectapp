<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="2" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.paragraphs" :lines="true" format-path="/paragraphs" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Párrafos" help="Un párrafo por línea" :rows="6" />
  <FieldInput v-model="form.issuesTitle" label="Título de problemas" />
  <FieldTextarea v-model="form.issues" :lines="true" format-path="/issues" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Problemas" help="Un problema por línea" :rows="4" />
  <FieldInput v-model="form.opportunityTitle" label="Título de oportunidad" />
  <FieldTextarea v-model="form.opportunity" :format="form.text_formats?.['/opportunity'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/opportunity': $event }" label="Oportunidad" :rows="3" :isSingle="true" />
</template>

<script setup>
import { FieldInput, FieldTextarea } from './fields.js';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
