<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="11" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.introMessage" :format="form.text_formats?.['/introMessage'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/introMessage': $event }" label="Mensaje de introducción" :rows="3" :isSingle="true" />
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Pasos</label>
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
          <FieldInput v-model="step.title" label="Título" class="mb-1" />
          <FieldInput v-model="step.description" label="Descripción" />
        </div>
      </template>
    </draggable>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="form.steps.push({ title: '', description: '' })"><BaseActionIcon action="create" /> Agregar paso</button>
  </div>
  <FieldTextarea v-model="form.ctaMessage" :format="form.text_formats?.['/ctaMessage'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/ctaMessage': $event }" label="Mensaje CTA" :rows="2" :isSingle="true" />
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <div class="bg-surface-raised rounded-xl p-3 border border-border-muted">
      <p class="text-xs text-text-subtle mb-2">CTA Primario</p>
      <FieldInput v-model="form.primaryCTA.text" label="Texto" class="mb-1" />
      <FieldInput v-model="form.primaryCTA.link" label="Link" />
    </div>
    <div class="bg-surface-raised rounded-xl p-3 border border-border-muted">
      <p class="text-xs text-text-subtle mb-2">CTA Secundario</p>
      <FieldInput v-model="form.secondaryCTA.text" label="Texto" class="mb-1" />
      <FieldInput v-model="form.secondaryCTA.link" label="Link" />
    </div>
  </div>
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Métodos de contacto</label>
    <draggable v-model="form.contactMethods" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
      <template #item="{ element: method, index: idx }">
        <div class="mb-3 bg-surface-raised rounded-xl p-3 border border-border-muted">
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-2">
              <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
              <span class="text-xs text-text-subtle">Método {{ idx + 1 }}</span>
            </div>
            <BaseButton variant="danger-ghost" size="sm" @click="form.contactMethods.splice(idx, 1)">Eliminar</BaseButton>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
            <EmojiIconField v-model="method.icon" label="Icono" placeholder="📧" />
            <FieldInput v-model="method.title" label="Título" />
            <FieldInput v-model="method.value" label="Valor" />
            <FieldInput v-model="method.link" label="Link" />
          </div>
        </div>
      </template>
    </draggable>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="form.contactMethods.push({ icon: '', title: '', value: '', link: '' })"><BaseActionIcon action="create" /> Agregar método</button>
  </div>
  <FieldTextarea v-model="form.validityMessage" :format="form.text_formats?.['/validityMessage'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/validityMessage': $event }" label="Mensaje de vigencia" :rows="2" :isSingle="true" />
  <FieldTextarea v-model="form.thankYouMessage" :format="form.text_formats?.['/thankYouMessage'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/thankYouMessage': $event }" label="Mensaje de agradecimiento" :rows="2" :isSingle="true" />
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
