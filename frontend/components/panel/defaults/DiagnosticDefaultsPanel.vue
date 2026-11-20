<template>
  <div>
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />

    <p class="text-sm text-text-muted mb-6">
      Configura los valores iniciales que se aplicarán a los nuevos diagnósticos.
    </p>

    <BaseTabs v-model="activeTab" :tabs="tabs" />

    <!-- ═══ TAB: Vista General ═══ -->
    <section v-show="activeTab === 'general'" class="max-w-5xl mx-auto">
      <p class="text-sm text-text-muted mb-6">
        Estos valores se aplican al crear cada nuevo diagnóstico. Puedes seguir ajustándolos por diagnóstico.
      </p>
      <form
        class="bg-surface rounded-xl shadow-sm border border-border-muted p-4 sm:p-8 space-y-6"
        @submit.prevent="handleSaveGeneral"
      >
        <BaseFormRow :cols="2" :gap="4">
          <BaseFormField label="Idioma" for="defaults-language">
            <BaseChoiceSelect
              id="defaults-language"
              :model-value="generalForm.language"
              :disabled="isSaving"
              data-testid="defaults-language"
              :options="[{ value: 'es', label: 'Español' }, { value: 'en', label: 'English' }]"
              @update:model-value="onLanguageChange"
            />
          </BaseFormField>
          <BaseFormField label="Moneda" for="defaults-currency">
            <BaseChoiceSelect
              id="defaults-currency"
              v-model="generalForm.default_currency"
              data-testid="defaults-currency"
              :options="[{ value: 'COP', label: 'COP' }, { value: 'USD', label: 'USD' }]"
            />
          </BaseFormField>
        </BaseFormRow>

        <BaseFormRow :cols="2" :gap="4">
          <BaseFormField label="Inversión por defecto">
            <BaseCurrencyInput
              v-model="generalForm.default_investment_amount"
              :decimals="2"
              data-testid="defaults-investment"
            />
          </BaseFormField>
          <BaseFormField label="Duración por defecto">
            <BaseInput
              v-model="generalForm.default_duration_label"
              type="text"
              maxlength="80"
              placeholder="ej. 4 semanas"
              data-testid="defaults-duration-label"
            />
          </BaseFormField>
        </BaseFormRow>

        <fieldset class="border border-border-muted rounded-xl p-4">
          <legend class="px-2 text-sm font-medium text-text-default">Distribución de pagos</legend>
          <BaseFormRow :cols="2" :gap="4">
            <BaseFormField label="% Pago inicial">
              <div class="flex items-center gap-3">
                <BaseInput
                  v-model.number="generalForm.payment_initial_pct"
                  type="number"
                  min="0"
                  max="100"
                  class="w-32"
                  data-testid="defaults-payment-initial"
                  @input="syncPaymentFinal"
                />
                <span class="text-sm text-text-muted">%</span>
              </div>
            </BaseFormField>
            <BaseFormField label="% Pago final">
              <div class="flex items-center gap-3">
                <BaseInput
                  v-model.number="generalForm.payment_final_pct"
                  type="number"
                  min="0"
                  max="100"
                  class="w-32"
                  data-testid="defaults-payment-final"
                  @input="syncPaymentInitial"
                />
                <span class="text-sm text-text-muted">%</span>
              </div>
            </BaseFormField>
          </BaseFormRow>
          <p
            v-if="!isPaymentValid"
            class="text-xs text-danger-strong mt-2"
            data-testid="defaults-payment-warning"
          >La suma debe ser exactamente 100% (actual: {{ paymentSum }}%).</p>
          <p v-else class="text-xs text-text-subtle mt-2">Suma: {{ paymentSum }}%.</p>
        </fieldset>

        <BaseFormRow :cols="3" :gap="4">
          <BaseFormField label="Días de recordatorio">
            <BaseInput
              v-model.number="generalForm.reminder_days"
              type="number"
              min="1"
              max="60"
              data-testid="defaults-reminder-days"
            />
          </BaseFormField>
          <BaseFormField label="Días de urgencia">
            <BaseInput
              v-model.number="generalForm.urgency_reminder_days"
              type="number"
              min="1"
              max="60"
              data-testid="defaults-urgency-days"
            />
          </BaseFormField>
          <BaseFormField label="Días de expiración">
            <BaseInput
              v-model.number="generalForm.expiration_days"
              type="number"
              min="1"
              max="365"
              data-testid="defaults-expiration-days"
            />
          </BaseFormField>
        </BaseFormRow>

        <div>
          <label class="flex items-center gap-2 text-sm font-medium text-text-default mb-1">
            Patrón de URL personalizada
            <BaseTooltip position="right" width="max-w-xs">
              <div class="space-y-2 text-left">
                <p>Puedes usar <strong>texto libre</strong> o combinarlo con placeholders.</p>
                <p>
                  Placeholders disponibles:
                  <code>{client_name}</code>, <code>{year}</code>.
                </p>
                <p class="text-xs opacity-80">Reglas (se aplican automáticamente):</p>
                <ul class="list-disc pl-4 text-xs opacity-80 space-y-0.5">
                  <li>Se convierte a minúsculas</li>
                  <li>Los espacios se reemplazan por guiones <code>-</code></li>
                  <li>Se eliminan tildes y caracteres especiales</li>
                </ul>
                <p class="text-xs opacity-80">
                  Ejemplos: <code>mi-diagnostico</code>, <code>{client_name}-2026</code>.
                </p>
              </div>
            </BaseTooltip>
          </label>
          <BaseInput
            v-model="generalForm.default_slug_pattern"
            type="text"
            class="font-mono"
            data-testid="diagnostic-defaults-slug-pattern"
            placeholder="{client_name}"
          />
          <p class="text-xs text-text-subtle mt-1">
            Texto libre permitido. Se aplica al crear un diagnóstico si el admin no escribe una URL manualmente.
          </p>
          <p class="text-xs text-text-muted mt-1">
            Vista previa: <span class="font-mono text-text-brand">/diagnostic/{{ slugPatternPreview }}</span>
          </p>
        </div>

        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-4 border-t border-border-muted">
          <BaseButton
            variant="ghost"
            size="md"
            class="!text-text-muted hover:!text-danger-strong"
            data-testid="defaults-reset-btn"
            @click="confirmReset"
          >
            Restablecer a valores del sistema
          </BaseButton>
          <BaseButton
            type="submit"
            variant="primary"
            size="lg"
            :loading="isSaving"
            :disabled="!isPaymentValid || isSaving || isLoading"
            data-testid="defaults-save-btn"
          >{{ isSaving ? 'Guardando…' : 'Guardar cambios' }}</BaseButton>
        </div>
      </form>
    </section>

    <!-- ═══ TAB: Secciones ═══ -->
    <section v-show="activeTab === 'sections'" class="max-w-7xl mx-auto">
      <p class="text-sm text-text-muted mb-6">
        Lista de las secciones que se sembrarán en cada nuevo diagnóstico para el idioma seleccionado.
        Para editar el contenido detallado, abre un diagnóstico real y modifícalo allí — el editor por
        defecto se gestiona desde el JSON de cada sección.
      </p>
      <p v-if="isLoading" role="status" class="text-sm text-text-muted">Cargando configuración…</p>
      <BaseBadge v-if="systemSections && !isLoading" class="mb-3">Plantilla del sistema</BaseBadge>
      <div v-if="!isLoading" class="bg-surface rounded-xl shadow-card border border-border-muted divide-y divide-border-muted">
        <div
          v-for="section in sectionsList"
          :key="section.section_type"
          class="px-4 py-3 flex items-center justify-between gap-3"
          data-testid="defaults-section-row"
        >
          <div>
            <p class="text-sm font-medium text-text-default">{{ section.title }}</p>
            <p class="text-xs text-text-subtle mt-0.5">
              {{ section.section_type }} · orden {{ section.order }} · visibilidad {{ section.visibility }}
            </p>
          </div>
          <BaseBadge :variant="section.is_enabled ? 'success' : 'neutral'" size="sm">
            {{ section.is_enabled ? 'Activa' : 'Desactivada' }}
          </BaseBadge>
        </div>
        <div
          v-if="!sectionsList.length"
          class="px-4 py-6 text-sm text-text-muted text-center"
        >No hay secciones configuradas.</div>
      </div>
    </section>

    <!-- ═══ TAB: Plantillas de Email ═══ -->
    <section v-show="activeTab === 'emails'" class="max-w-3xl">
      <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-6 space-y-3">
        <h2 class="text-base font-medium text-text-default">Plantillas de email del diagnóstico</h2>
        <p class="text-sm text-text-muted">
          Las plantillas <code class="text-xs">diagnostic_initial_sent</code>, <code class="text-xs">diagnostic_final_sent</code>,
          <code class="text-xs">diagnostic_custom_email</code> y <code class="text-xs">diagnostic_documents_sent</code> se
          editan desde el panel central de plantillas de email.
        </p>
        <BaseButton
          as="NuxtLink"
          variant="primary"
          size="md"
          :to="localePath('/panel/defaults') + '?mode=proposal&tab=emails'"
        ><BaseActionIcon action="forward" /> Ir a Plantillas de Email</BaseButton>
      </div>
    </section>

    <!-- ═══ TAB: Diagnostic Prompt ═══ -->
    <section v-show="activeTab === 'prompt'" class="max-w-3xl">
      <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-6 space-y-3">
        <h2 class="text-base font-medium text-text-default">Diagnostic Prompt (IA)</h2>
        <p class="text-sm text-text-muted">
          El panel de prompts de IA del diagnóstico se gestiona por diagnóstico desde la pestaña
          “Prompt” del editor. Aquí no hay todavía un prompt por defecto compartido.
        </p>
      </div>
    </section>

    <!-- ═══ TAB: JSON ═══ -->
    <section v-show="activeTab === 'json'" class="max-w-7xl mx-auto">
      <div class="flex items-center justify-between mb-2">
        <h2 class="text-sm text-text-muted">JSON crudo del config activo</h2>
        <span v-if="rawConfig?.updated_at" class="text-xs text-text-subtle">
          Actualizado: {{ formatDate(rawConfig.updated_at) }}
        </span>
      </div>
      <pre
        class="bg-primary-strong text-white rounded-xl p-4 text-xs overflow-x-auto"
        data-testid="defaults-json-view"
      >{{ rawConfigPretty }}</pre>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useDiagnosticsStore } from '~/stores/diagnostics';
import { toSlug } from '~/utils/slugify';
import { formatDateTime } from '~/utils/formatDate';

const localePath = useLocalePath();
const route = useRoute();
const store = useDiagnosticsStore();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const notify = usePanelNotify();

const tabs = [
  { id: 'general', label: 'Vista General' },
  { id: 'sections', label: 'Secciones' },
  { id: 'emails', label: 'Plantillas de Email' },
  { id: 'prompt', label: 'Prompt' },
  { id: 'json', label: 'JSON' },
];
const activeTab = ref(
  ['general', 'sections', 'emails', 'prompt', 'json'].includes(route.query.tab)
    ? route.query.tab
    : 'general'
);

const generalForm = ref({
  language: 'es',
  default_currency: 'COP',
  default_investment_amount: 0,
  default_duration_label: '',
  payment_initial_pct: 60,
  payment_final_pct: 40,
  reminder_days: 7,
  urgency_reminder_days: 14,
  expiration_days: 21,
  default_slug_pattern: '{client_name}',
});

const slugPatternPreview = computed(() => {
  const pattern = (generalForm.value.default_slug_pattern || '').trim() || '{client_name}';
  const sample = {
    '{client_name}': 'María López',
    '{year}': String(new Date().getFullYear()),
  };
  let rendered = pattern;
  for (const [key, val] of Object.entries(sample)) rendered = rendered.split(key).join(val);
  return toSlug(rendered, { fallback: 'diagnostico' });
});

const sectionsList = ref([]);
const systemSections = ref(false);
const rawConfig = ref(null);
const isSaving = ref(false);
const isLoading = ref(false);
let defaultsRequest = 0;

const paymentSum = computed(
  () => Number(generalForm.value.payment_initial_pct || 0)
       + Number(generalForm.value.payment_final_pct || 0)
);
const isPaymentValid = computed(() => paymentSum.value === 100);

const rawConfigPretty = computed(() => {
  if (!rawConfig.value) return '{}';
  try {
    return JSON.stringify(rawConfig.value, null, 2);
  } catch (_) {
    return String(rawConfig.value);
  }
});

function formatDate(iso) {
  return formatDateTime(iso, { fallback: '' });
}

function applyConfig(data) {
  const { effective_sections_json: effectiveSections, ...config } = data;
  rawConfig.value = config;
  const fallback = Array.isArray(effectiveSections);
  systemSections.value = config.id === null || fallback;
  sectionsList.value = fallback ? effectiveSections : config.sections_json || [];
  generalForm.value = {
    language: data.language || generalForm.value.language,
    default_currency: data.default_currency || 'COP',
    default_investment_amount: data.default_investment_amount ?? 0,
    default_duration_label: data.default_duration_label || '',
    payment_initial_pct: Number(data.payment_initial_pct ?? 60),
    payment_final_pct: Number(data.payment_final_pct ?? 40),
    reminder_days: Number(data.reminder_days ?? 7),
    urgency_reminder_days: Number(data.urgency_reminder_days ?? 14),
    expiration_days: Number(data.expiration_days ?? 21),
    default_slug_pattern: typeof data.default_slug_pattern === 'string'
      ? data.default_slug_pattern
      : '{client_name}',
  };
}

function syncPaymentFinal() {
  const initial = Number(generalForm.value.payment_initial_pct || 0);
  if (initial >= 0 && initial <= 100) {
    generalForm.value.payment_final_pct = 100 - initial;
  }
}

function syncPaymentInitial() {
  const final = Number(generalForm.value.payment_final_pct || 0);
  if (final >= 0 && final <= 100) {
    generalForm.value.payment_initial_pct = 100 - final;
  }
}

async function loadDefaults(lang) {
  const request = ++defaultsRequest;
  isLoading.value = true;
  const result = await store.fetchDiagnosticDefaults(lang);
  if (request !== defaultsRequest) return;
  isLoading.value = false;
  if (!result.success) {
    generalForm.value.language = rawConfig.value?.language || 'es';
    notify.error('No se pudieron cargar los valores por defecto.');
    return;
  }
  applyConfig(result.data || {});
}

async function onLanguageChange(language) {
  generalForm.value.language = language;
  await loadDefaults(language);
}

async function handleSaveGeneral() {
  if (isLoading.value || isSaving.value) return;
  if (!isPaymentValid.value) {
    notify.error('La distribución de pagos debe sumar 100%.');
    return;
  }
  isSaving.value = true;
  try {
    const result = await store.saveDiagnosticDefaults(
      generalForm.value.language,
      null,
      generalForm.value,
    );
    if (result.success) {
      applyConfig(result.data || {});
      notify.success('Valores guardados correctamente.');
    } else {
      const detail = result.errors?.detail
        || Object.values(result.errors || {}).flat().join(' ')
        || 'Error al guardar.';
      notify.error(detail);
    }
  } finally {
    isSaving.value = false;
  }
}

function confirmReset() {
  requestConfirm({
    title: 'Restablecer valores por defecto',
    message: '¿Eliminar el config personalizado y volver a los valores del sistema (60/40, COP, 21 días)?',
    confirmText: 'Restablecer',
    cancelText: 'Cancelar',
    variant: 'danger',
    onConfirm: async () => {
      const result = await store.resetDiagnosticDefaults(generalForm.value.language);
      if (result.success) {
        await loadDefaults(generalForm.value.language);
        notify.success('Valores restablecidos.');
      } else {
        notify.error('No se pudo restablecer.');
      }
    },
  });
}

onMounted(() => {
  loadDefaults(generalForm.value.language);
});

usePanelRefresh(() => loadDefaults(generalForm.value.language));
</script>
