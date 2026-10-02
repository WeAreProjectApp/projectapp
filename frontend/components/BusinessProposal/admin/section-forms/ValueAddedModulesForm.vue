<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="9" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.intro" label="Intro (por qué se incluyen sin costo)" :rows="3" :isSingle="true" />

  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Módulos a destacar</label>
    <p class="text-[11px] text-text-muted mb-3">
      Selecciona qué módulos base aparecerán en esta sección de "incluido sin costo". Los datos completos
      (icono, título, items) viven en la sección Requerimientos funcionales.
    </p>
    <div class="space-y-3">
      <div v-for="id in valueAddedAvailableIds" :key="id"
           class="border border-border-default dark:border-white/[0.08] rounded-xl p-3 bg-surface-raised">
        <label class="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            :checked="form.module_ids.includes(id)"
            class="rounded border-input-border text-text-brand focus:ring-focus-ring/30"
            @change="toggleValueAddedId(id, $event.target.checked)"
          />
          <span class="text-sm font-medium text-text-default">
            {{ valueAddedModuleLabel(id) }}
          </span>
        </label>
        <template v-if="form.module_ids.includes(id)">
          <FieldTextarea
            :modelValue="form.justifications[id] || ''"
            label="Justificación corta"
            help="Máx ~180 caracteres. Una oración explicando por qué este módulo aporta valor."
            :rows="2"
            :isSingle="true"
            class="mt-2"
            @update:modelValue="form.justifications[id] = $event"
          />

          <!-- Condiciones del módulo (Req 3) -->
          <div class="mt-3 border-t border-border-default dark:border-white/[0.08] pt-3 space-y-2">
            <p class="text-[11px] text-text-muted uppercase tracking-wider">Condiciones del beneficio</p>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <FieldCurrency
                :modelValue="getCond(id, 'min_price_usd')"
                label="Precio mínimo (USD)"
                placeholder="0 = sin mínimo"
                @update:modelValue="setCondNum(id, 'min_price_usd', $event)"
              />
              <FieldCurrency
                :modelValue="getCond(id, 'min_price_cop')"
                label="Precio mínimo (COP)"
                placeholder="0 = sin mínimo"
                @update:modelValue="setCondNum(id, 'min_price_cop', $event)"
              />
              <FieldInput
                :modelValue="getCond(id, 'duration_months')"
                label="Duración (meses)"
                placeholder="vacío = sin límite"
                @update:modelValue="setCondNum(id, 'duration_months', $event)"
              />
            </div>
            <FieldTextarea
              :modelValue="getCond(id, 'discretionary_note')"
              label="Nota discrecional"
              help="Ej: se implementa si la lógica de negocio lo permite y tiene sentido medir/automatizar."
              :rows="2"
              :isSingle="true"
              @update:modelValue="setCond(id, 'discretionary_note', $event)"
            />
            <!-- Cláusulas legales categorizadas (fuente única web + PDF) -->
            <div class="space-y-2">
              <div class="flex items-center justify-between gap-2">
                <label class="block text-xs font-medium text-text-muted uppercase tracking-wider">
                  Términos y condiciones
                </label>
                <button
                  type="button"
                  class="text-[11px] font-medium text-text-brand hover:underline"
                  @click="addClause(id)"
                >
                  <BaseActionIcon action="create" />
                  Añadir cláusula
                </button>
              </div>
              <p class="text-[11px] text-text-muted">
                Cada cláusula lleva una categoría (Elegibilidad, Alcance, Vigencia…). Se muestran
                igual en el modal de la vista pública y en el anexo del PDF. Usa
                <code>**negrilla**</code> para resaltar.
              </p>

              <div
                v-for="(clause, idx) in getClauses(id)"
                :key="idx"
                class="border border-border-default dark:border-white/[0.08] rounded-lg p-2 bg-surface space-y-2"
              >
                <div class="flex items-start gap-2">
                  <div class="flex-1">
                    <FieldInput
                      :modelValue="clause.label"
                      label="Categoría"
                      placeholder="Ej: Elegibilidad"
                      @update:modelValue="setClauseField(id, idx, 'label', $event)"
                    />
                  </div>
                  <div class="flex items-center gap-1 pt-6">
                    <BaseActionButton
                      action="move-up"
                      label="Subir cláusula"
                      :disabled="idx === 0"
                      disabled-reason="Esta cláusula ya es la primera."
                      @click="moveClause(id, idx, -1)"
                    />
                    <BaseActionButton
                      action="move-down"
                      label="Bajar cláusula"
                      :disabled="idx === getClauses(id).length - 1"
                      disabled-reason="Esta cláusula ya es la última."
                      @click="moveClause(id, idx, 1)"
                    />
                    <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar cláusula" size="sm" @click="removeClause(id, idx)" />
                  </div>
                </div>
                <FieldTextarea
                  :modelValue="clause.text"
                  label="Texto de la cláusula"
                  :rows="3"
                  :isSingle="true"
                  @update:modelValue="setClauseField(id, idx, 'text', $event)"
                />
              </div>

              <p v-if="!getClauses(id).length" class="text-[11px] text-text-muted italic">
                Sin cláusulas. Añade al menos una para que el módulo muestre términos.
              </p>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>

  <!-- Disposiciones generales de la sección (web + anexo PDF) -->
  <div class="border border-border-default dark:border-white/[0.08] rounded-xl p-3 bg-surface-raised space-y-2">
    <div class="flex items-center justify-between gap-2">
      <label class="block text-xs font-medium text-text-muted uppercase tracking-wider">
        Disposiciones generales
      </label>
      <button
        type="button"
        class="text-[11px] font-medium text-text-brand hover:underline"
        @click="addGeneralClause"
      >
        <BaseActionIcon action="create" />
        Añadir cláusula
      </button>
    </div>
    <p class="text-[11px] text-text-muted">
      Cláusulas transversales a todos los módulos incluidos. Se muestran al cierre de la sección
      pública y como bloque final del anexo del PDF.
    </p>

    <FieldInput
      :modelValue="form.general_terms?.title || ''"
      label="Título del bloque"
      placeholder="Disposiciones generales aplicables a los módulos incluidos"
      @update:modelValue="setGeneralTitle"
    />

    <div
      v-for="(clause, idx) in generalClauses"
      :key="idx"
      class="border border-border-default dark:border-white/[0.08] rounded-lg p-2 bg-surface space-y-2"
    >
      <div class="flex items-start gap-2">
        <div class="flex-1">
          <FieldInput
            :modelValue="clause.label"
            label="Categoría"
            placeholder="Ej: Fuerza mayor y caso fortuito"
            @update:modelValue="setGeneralClauseField(idx, 'label', $event)"
          />
        </div>
        <div class="flex items-center gap-1 pt-6">
          <BaseActionButton
            action="move-up"
            label="Subir cláusula general"
            :disabled="idx === 0"
            disabled-reason="Esta cláusula ya es la primera."
            @click="moveGeneralClause(idx, -1)"
          />
          <BaseActionButton
            action="move-down"
            label="Bajar cláusula general"
            :disabled="idx === generalClauses.length - 1"
            disabled-reason="Esta cláusula ya es la última."
            @click="moveGeneralClause(idx, 1)"
          />
          <BaseActionButton action="delete" variant="danger-ghost" label="Eliminar cláusula general" size="sm" @click="removeGeneralClause(idx)" />
        </div>
      </div>
      <FieldTextarea
        :modelValue="clause.text"
        label="Texto de la cláusula"
        :rows="3"
        :isSingle="true"
        @update:modelValue="setGeneralClauseField(idx, 'text', $event)"
      />
    </div>
  </div>

  <FieldTextarea v-model="form.footer_note" label="Nota de cierre" :rows="2" :isSingle="true" />
</template>

<script setup>
import { computed } from 'vue';
import { FieldCurrency, FieldInput, FieldTextarea } from './fields.js';
import { VALUE_ADDED_DEFAULT_MODULE_IDS } from '~/components/BusinessProposal/admin/sectionEditorUtils.js';

const props = defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
  /** All sections in the proposal (used to discover available group ids). */
  allSections: { type: Array, default: () => [] },
});

const valueAddedFreeGroups = computed(() => {
  const fr = (props.allSections || []).find((s) => s.section_type === 'functional_requirements');
  const groups = fr?.content_json?.groups || [];
  return groups.filter((g) => g && g.id && (g.is_always_included ?? !g.is_calculator_module));
});

const valueAddedLabelById = computed(() => {
  const map = new Map();
  for (const g of valueAddedFreeGroups.value) {
    map.set(g.id, `${g.icon || ''} ${g.title || g.id}`.trim());
  }
  return map;
});

const valueAddedAvailableIds = computed(() => {
  const fromGroups = valueAddedFreeGroups.value.map((g) => g.id);
  if (fromGroups.length) return fromGroups;
  return [...VALUE_ADDED_DEFAULT_MODULE_IDS];
});

function valueAddedModuleLabel(id) {
  return valueAddedLabelById.value.get(id) || id;
}

function toggleValueAddedId(id, checked) {
  if (!Array.isArray(props.form.module_ids)) props.form.module_ids = [];
  if (!props.form.justifications) props.form.justifications = {};
  const idx = props.form.module_ids.indexOf(id);
  if (checked && idx === -1) {
    props.form.module_ids.push(id);
    if (!(id in props.form.justifications)) props.form.justifications[id] = '';
  } else if (!checked && idx !== -1) {
    props.form.module_ids.splice(idx, 1);
  }
}

function getCond(id, key) {
  const value = props.form.conditions?.[id]?.[key];
  return value == null ? '' : value;
}

function ensureCond(id) {
  if (!props.form.conditions) props.form.conditions = {};
  if (!props.form.conditions[id]) props.form.conditions[id] = {};
  return props.form.conditions[id];
}

function setCond(id, key, value) {
  ensureCond(id)[key] = value;
}

function setCondNum(id, key, value) {
  // Empty → null (no minimum / no limit); otherwise store a Number.
  const cond = ensureCond(id);
  cond[key] = value === '' || value == null ? null : Number(value);
}

// --- Legal clauses (terms_clauses) -----------------------------------------
// `terms_clauses` is canonical; `terms` is kept in sync as the flattened
// legacy string so proposals rendered by older code keep the same content.
function getClauses(id) {
  const clauses = props.form.conditions?.[id]?.terms_clauses;
  return Array.isArray(clauses) ? clauses : [];
}

function flattenClauses(clauses) {
  return clauses
    .filter((c) => String(c.text || '').trim())
    .map((c) => {
      const label = String(c.label || '').trim();
      const text = String(c.text).trim();
      return label ? `**${label}.** ${text}` : text;
    })
    .join('\n');
}

function writeClauses(id, clauses) {
  const cond = ensureCond(id);
  cond.terms_clauses = clauses;
  cond.terms = flattenClauses(clauses);
}

function addClause(id) {
  writeClauses(id, [...getClauses(id), { label: '', text: '' }]);
}

function removeClause(id, idx) {
  const next = [...getClauses(id)];
  next.splice(idx, 1);
  writeClauses(id, next);
}

function moveClause(id, idx, delta) {
  const next = [...getClauses(id)];
  const target = idx + delta;
  if (target < 0 || target >= next.length) return;
  [next[idx], next[target]] = [next[target], next[idx]];
  writeClauses(id, next);
}

function setClauseField(id, idx, key, value) {
  const next = getClauses(id).map((c, i) => (i === idx ? { ...c, [key]: value } : c));
  writeClauses(id, next);
}

// --- Section-level general provisions --------------------------------------
function ensureGeneral() {
  if (!props.form.general_terms || typeof props.form.general_terms !== 'object') {
    props.form.general_terms = { title: '', clauses: [] };
  }
  if (!Array.isArray(props.form.general_terms.clauses)) {
    props.form.general_terms.clauses = [];
  }
  return props.form.general_terms;
}

const generalClauses = computed(() => {
  const clauses = props.form.general_terms?.clauses;
  return Array.isArray(clauses) ? clauses : [];
});

function setGeneralTitle(value) {
  ensureGeneral().title = value;
}

function addGeneralClause() {
  ensureGeneral().clauses.push({ label: '', text: '' });
}

function removeGeneralClause(idx) {
  ensureGeneral().clauses.splice(idx, 1);
}

function moveGeneralClause(idx, delta) {
  const clauses = ensureGeneral().clauses;
  const target = idx + delta;
  if (target < 0 || target >= clauses.length) return;
  [clauses[idx], clauses[target]] = [clauses[target], clauses[idx]];
}

function setGeneralClauseField(idx, key, value) {
  const clause = ensureGeneral().clauses[idx];
  if (clause) clause[key] = value;
}
</script>
