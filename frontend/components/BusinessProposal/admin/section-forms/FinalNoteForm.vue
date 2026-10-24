<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="10" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.message" :format="form.text_formats?.['/message'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/message': $event }" label="Mensaje" :rows="5" :isSingle="true" />
  <FieldTextarea v-model="form.personalNote" :format="form.text_formats?.['/personalNote'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/personalNote': $event }" label="Nota personal" :rows="3" :isSingle="true" />
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <FieldInput v-model="form.teamName" label="Nombre del equipo" />
    <FieldInput v-model="form.teamRole" label="Rol" />
    <FieldInput v-model="form.contactEmail" label="Email de contacto" />
  </div>
  <FieldInput v-model="form.signature" label="URL de la firma (imagen)" />
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Badges de compromiso</label>
    <draggable v-model="form.commitmentBadges" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
      <template #item="{ element: badge, index: idx }">
        <div class="mb-3 bg-surface-raised rounded-xl p-3 border border-border-muted">
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-2">
              <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
              <span class="text-xs text-text-subtle">Badge {{ idx + 1 }}</span>
            </div>
            <BaseButton variant="danger-ghost" size="sm" @click="form.commitmentBadges.splice(idx, 1)">Eliminar</BaseButton>
          </div>
          <div class="grid grid-cols-[100px_1fr] gap-2 mb-1">
            <EmojiIconField v-model="badge.icon" label="Icono" placeholder="🤝" />
            <FieldInput v-model="badge.title" label="Título" />
          </div>
          <FieldInput v-model="badge.description" label="Descripción" />
        </div>
      </template>
    </draggable>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="form.commitmentBadges.push({ icon: '', title: '', description: '' })"><BaseActionIcon action="create" /> Agregar badge</button>
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
