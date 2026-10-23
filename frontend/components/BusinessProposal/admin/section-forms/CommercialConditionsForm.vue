<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="17" />
    <FieldInput v-model="form.title" label="Título" />
  </div>

  <!-- Paquetes de requerimientos -->
  <div class="mt-2">
    <FieldInput v-model="form.packagesTitle" label="Título de los paquetes" />
    <FieldTextarea v-model="form.packagesIntro" label="Intro de los paquetes" :rows="2" :isSingle="true" class="mt-2" />

    <p data-testid="hour-rate-tab-hint" class="text-[11px] text-text-subtle mt-3">
      Los paquetes, los cupos y los descuentos vienen del catálogo de Paquetes de requerimientos.
      La composición y el precio de esta propuesta se configuran en la pestaña
      <span class="font-medium text-text-muted">«Paquetes de requerimientos»</span>, que además
      muestra la tabla tal como se imprime en el PDF.
    </p>

    <FieldTextarea
      v-model="form.effortBadge"
      label="Tallas incluidas y condiciones"
      help="Aclara el uso de cupos XS/S/M, la cotización independiente de L/XL y las correcciones cubiertas por garantía."
      :rows="2"
      :isSingle="true"
      class="mt-3"
    />
  </div>

  <!-- Alcance -->
  <div class="mt-4 border-t border-border-default dark:border-white/[0.08] pt-3">
    <FieldInput v-model="form.scopeTitle" label="Título de alcance" />
    <FieldTextarea
      v-model="form.scopeParagraphs"
      label="Párrafos de alcance (uno por línea)"
      help="Cláusula que aclara que lo no descrito en el alcance no hace parte del trabajo aprobado."
      :rows="6"
      :isSingle="true"
      class="mt-2"
    />
  </div>
</template>

<script setup>
// Rates, currency and the package list are deliberately absent from this form:
// the catalog owns the package structure and the «Paquetes de requerimientos» tab owns the
// per-proposal rate. They still round-trip through buildFormFromJson/formToJson
// as untouched carry-through fields, so saving here never disturbs them.
import { FieldInput, FieldTextarea } from './fields.js';

defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});
</script>
