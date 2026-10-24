<template>
  <FieldInput v-model="form.proposalTitle" label="Título de la propuesta" />
  <p v-if="!form.proposalTitle && proposalData?.title" class="text-xs text-warning-strong -mt-3">
    ⚠ Vacío — se usará "{{ proposalData.title }}" del título de la propuesta.
  </p>
  <FieldInput v-model="form.clientName" label="Nombre del cliente" />
  <p v-if="!form.clientName && proposalData?.client_name" class="text-xs text-warning-strong -mt-3">
    ⚠ Vacío — se usará "{{ proposalData.client_name }}" de los datos generales.
  </p>
  <FieldTextarea v-model="form.inspirationalQuote" :format="form.text_formats?.['/inspirationalQuote'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/inspirationalQuote': $event }" label="Frase inspiracional" :rows="2" />
</template>

<script setup>
import { FieldInput, FieldTextarea } from './fields.js';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
