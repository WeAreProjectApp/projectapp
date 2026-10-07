<template>
<section class="rounded-xl border border-border-muted bg-surface p-5" data-testid="proposal-email-settings">
    <div class="space-y-3 pt-2 border-t border-input-border">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h4 class="text-sm font-medium text-text-default">Configuración del correo (diseño nuevo)</h4>
          <p class="text-xs text-text-muted mt-1">
            Estos campos llenan los bloques del correo comercial: lista "Qué incluye", card "Método en 3 fases" y firma. Si los dejas vacíos se omiten o se usa el método estándar de marca.
          </p>
        </div>
        <BaseButton variant="secondary" size="sm" class="shrink-0" data-testid="edit-email-preview-btn" @click="emit('open-email-preview')">
          <BaseActionIcon action="view" /> Vista previa
        </BaseButton>
      </div>

      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Firmado por</label>
        <BaseSelect v-model="form.email_signed_by" data-testid="edit-email-signed-by">
          <option value="gustavo">Gustavo Pérez · CEO</option>
          <option value="carlos">Carlos Blanco · CTO</option>
        </BaseSelect>
        <p class="text-xs text-text-subtle mt-1">Nombre y cargo que firman al pie del correo.</p>
      </div>

      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-text-default">Qué incluye (bullets)</label>
          <button
            type="button"
            class="text-xs text-primary hover:underline disabled:opacity-50"
            :disabled="form.email_features.length >= MAX_EMAIL_FEATURES"
            :title="form.email_features.length >= MAX_EMAIL_FEATURES ? `Ya alcanzaste el máximo de ${MAX_EMAIL_FEATURES} ítems.` : undefined"
            data-testid="edit-add-feature"
            @click="addEmailFeature"
          >
            <BaseActionIcon action="create" />
            Agregar ítem
          </button>
        </div>
        <p class="text-xs text-text-muted mb-2">
          Hasta 8 ítems. Si queda vacío el bloque no se renderiza.
        </p>
        <div v-if="form.email_features.length === 0" class="text-xs text-text-subtle italic">
          Sin ítems — el bloque no aparecerá en el correo.
        </div>
        <div
          v-for="(_, idx) in form.email_features"
          :key="`feature-${idx}`"
          class="flex items-start gap-2 mb-2"
        >
          <span class="text-xs font-medium text-text-muted pt-2 w-6">
            {{ String(idx + 1).padStart(2, '0') }}
          </span>
          <BaseTextarea
            v-model="form.email_features[idx]"
            :rows="2"
            size="sm"
            class="flex-1"
            placeholder="Ej. Dashboard en tiempo real con filtros por ruta, conductor y estado."
          />
          <BaseButton variant="danger-ghost" size="sm" @click="removeEmailFeature(idx)">
            Quitar
          </BaseButton>
        </div>
      </div>

      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-text-default">Método en 3 fases</label>
          <button
            type="button"
            class="text-xs text-primary hover:underline"
            @click="ensureMethodPhases"
          >
            Restaurar método estándar
          </button>
        </div>
        <p class="text-xs text-text-muted mb-2">
          Card oscura del correo. Si lo dejas con los valores estándar usa los textos de marca; puedes personalizarlos por propuesta.
        </p>
        <div
          v-for="(phase, idx) in form.email_method_phases"
          :key="`phase-${idx}`"
          class="grid grid-cols-1 sm:grid-cols-[60px,1fr,90px,1fr] gap-2 mb-2 items-start"
        >
          <BaseInput
            v-model="form.email_method_phases[idx].number"
            size="sm"
            placeholder="01"
            class="text-center"
          />
          <BaseInput
            v-model="form.email_method_phases[idx].title"
            size="sm"
            placeholder="Diagnóstico"
          />
          <BaseInput
            v-model="form.email_method_phases[idx].duration"
            size="sm"
            placeholder="5 días"
          />
          <BaseTextarea
            v-model="form.email_method_phases[idx].description"
            :rows="2"
            size="sm"
            placeholder="Mapeo de procesos y alcance final."
          />
        </div>
        <p class="text-xs text-text-subtle">Orden de columnas: número · título · duración · descripción.</p>
      </div>
    </div>

<div class="mt-4 flex justify-end"><BaseButton variant="primary" size="sm" :loading="saving" @click="emit('save')">Guardar configuración del correo</BaseButton></div>
</section>
</template>

<script setup>
import { DEFAULT_METHOD_PHASES } from '~/stores/proposals_constants';
const props = defineProps({ form: { type: Object, required: true }, saving: { type: Boolean, default: false } });
const emit = defineEmits(['save', 'open-email-preview']);
const form = props.form;
const MAX_EMAIL_FEATURES = 8;
function addEmailFeature() {
  if (form.email_features.length >= MAX_EMAIL_FEATURES) return;
  form.email_features = [...form.email_features, ''];
}
function removeEmailFeature(idx) {
  form.email_features = form.email_features.filter((_, i) => i !== idx);
}
function ensureMethodPhases() {
  if (!form.email_method_phases || form.email_method_phases.length === 0) {
    form.email_method_phases = DEFAULT_METHOD_PHASES.map((p) => ({ ...p }));
  }
}

</script>
