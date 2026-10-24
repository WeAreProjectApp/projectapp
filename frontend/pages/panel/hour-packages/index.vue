<template>
  <div>
    <!-- Before ConfirmModal: modals stack in template order, so the
         confirmation an entry opens lands above this fading menu. -->
    <BaseRowActionsModal
      :open="actionsRow !== null"
      :title="actionsRow?.name_es || ''"
      :items="actionsRow ? packageActionItems(actionsRow) : []"
      testid="hour-package-actions-modal"
      @close="actionsRow = null"
    />
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
    <div class="mb-6 flex flex-col gap-4 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
      <h1 class="text-2xl font-light text-text-default">Paquetes de requerimientos</h1>
      <BaseButton
        v-if="activeSection === 'catalog'"
        as="NuxtLink"
        variant="primary"
        size="md"
        :to="localePath({ path: '/panel/hour-packages/create', query: { nationality: selectedNationality } })"
      >
        <BaseActionIcon action="create" />
        Nuevo paquete
      </BaseButton>
    </div>

    <div class="mb-6">
      <BaseSegmented v-model="activeSection" :options="sectionOptions" />
    </div>

    <!-- ══════════════ Catálogo ══════════════ -->
    <template v-if="activeSection === 'catalog'">
      <div class="mb-6 flex flex-col gap-3 panel-portrait:flex-row panel-portrait:items-start panel-portrait:justify-between">
        <div>
          <!-- Nationality tabs: prices switch per country -->
          <BaseSegmented v-model="selectedNationality" :options="nationalityOptions" nowrap />
          <p class="text-xs text-text-subtle mt-2">
            Los paquetes {{ nationalityLabel }} se cotizan en {{ currentCurrency }}.
          </p>
        </div>
        <BaseSegmented v-model="viewMode" :options="viewModeOptions" />
      </div>

      <!-- Loading -->
      <div v-if="hourPackagesStore.isLoading" class="flex justify-center py-12">
        <div class="w-6 h-6 border-2 border-focus-ring/30 border-t-focus-ring rounded-full animate-spin" />
      </div>

      <div v-else>
        <div v-if="packages.length === 0" class="bg-surface rounded-xl shadow-sm border border-border-muted px-6 py-12 text-center text-text-subtle text-sm">
          Sin paquetes para este mercado. Crea uno o restaura los valores por defecto.
        </div>

        <!-- Cards mode -->
        <HourPackagesCards
          v-else-if="viewMode === 'cards'"
          :packages="packages"
          @delete="handleDelete"
        />

        <!-- Compare mode -->
        <HourPackagesCompare
          v-else-if="viewMode === 'compare'"
          :packages="packages"
          @delete="handleDelete"
        />

        <template v-else>
          <BaseExploratoryList
            :columns="packageColumns"
            :rows="pagedPackages"
            caption="Paquetes de requerimientos y precios"
            card-test-id-prefix="hour-package-row"
            table-min-width="64rem"
            row-actions-layout="menu-start"
          >
            <template #cell-name_es="{ row: pkg }">
              <NuxtLink :to="localePath(`/panel/hour-packages/${pkg.id}/edit`)" class="block min-w-0 max-w-full text-sm font-medium leading-tight text-text-default [overflow-wrap:anywhere] transition-colors hover:text-text-brand">{{ pkg.name_es }}</NuxtLink>
              <p class="mt-0.5 min-w-0 max-w-full text-xs text-text-subtle [overflow-wrap:anywhere]">{{ pkg.name_en }} · Orden {{ pkg.order }}</p>
            </template>
            <template #cell-composition="{ row: pkg }">{{ composition(pkg) }}<p class="text-xs text-text-subtle">{{ pkg.validity_months }} meses</p></template>
            <template #cell-reference="{ row: pkg }"><span class="line-through">{{ formatMoney(pkg.reference_price, pkg.currency) }}</span></template>
            <template #cell-discount_percent="{ row: pkg }">
              <span v-if="Number(pkg.discount_percent) > 0" class="inline-flex rounded-full bg-primary-soft px-2 py-0.5 text-xs font-medium text-text-brand">-{{ pkg.discount_percent }}%</span>
              <span v-else>—</span>
            </template>
            <template #cell-savings="{ row: pkg }">{{ formatMoney(pkg.savings, pkg.currency) }}</template>
            <template #cell-total="{ row: pkg }"><span class="font-medium">{{ formatMoney(totalPrice(pkg), pkg.currency) }} {{ pkg.currency === 'COP' ? '+ IVA' : '+ Tax' }}</span></template>
            <template #cell-status="{ row: pkg }"><span class="inline-flex rounded-full px-2.5 py-1 text-xs font-medium" :class="statusBadgeClass(pkg)">{{ pkg.is_active ? 'Activo' : 'Inactivo' }}</span></template>
            <template #row-actions="{ row: pkg }">
              <BaseActionButton
                action="more"
                class="h-11 w-11 shrink-0"
                :label="`Acciones de ${pkg.name_es}`"
                :data-testid="`hour-package-actions-${pkg.id}`"
                @click.stop="actionsRow = pkg"
              />
            </template>
          </BaseExploratoryList>

          <BasePagination
            v-if="packages.length > 0"
            :current-page="packagesPage"
            :total-pages="packagesTotalPages"
            :total-items="packagesTotalItems"
            :range-from="packagesRangeFrom"
            :range-to="packagesRangeTo"
            class="mt-4"
            @prev="packagesPrev"
            @next="packagesNext"
            @go="packagesGoTo"
          />
        </template>
      </div>
    </template>

    <!-- ══════════════ Configuración ══════════════ -->
    <template v-else>
      <div class="space-y-6 max-w-2xl">
        <section class="bg-surface rounded-xl shadow-sm border border-border-muted p-6">
          <h2 class="text-sm font-medium text-text-default mb-1">Vista por defecto</h2>
          <p class="text-xs text-text-subtle mb-4">
            Modo con el que abre el catálogo al entrar a esta página.
          </p>
          <BaseSegmented
            :model-value="defaultViewMode"
            :options="viewModeOptions"
            data-testid="hour-packages-default-view"
            @update:model-value="saveDefaultViewMode"
          />
        </section>

        <section class="bg-surface rounded-xl shadow-sm border border-border-muted p-6 space-y-4">
          <h2 class="text-sm font-medium text-text-default">Valores internos y mercados</h2>
          <p class="text-xs text-text-subtle">Los precios por talla son internos. Las nuevas ofertas toman estos valores; las ofertas emitidas conservan sus condiciones.</p>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label v-for="field in pricingFields" :key="field.key" class="block text-sm text-text-default">
              {{ field.label }}
              <input v-model.number="pricingSettings[field.key]" type="number" min="0.001" :step="field.step"
                :data-testid="`packages-setting-${field.key}`"
                class="bg-input-bg mt-1 w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text" />
            </label>
          </div>
          <p class="text-xs text-text-muted">Tasa de Contabilidad: {{ hourPackagesStore.settings?.exchange_rate }} COP por USD. Precio USD = referencia COP ÷ tasa × factor × (1 − descuento).</p>
          <h3 class="text-sm font-medium text-text-default">Cupo mensual del Programa de Alianza</h3>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <label v-for="size in ['xs', 's', 'm']" :key="size" class="block text-sm text-text-default">Cupos {{ size.toUpperCase() }}
              <input v-model.number="pricingSettings[`alliance_${size}_count`]" type="number" min="0" step="1"
                :data-testid="`packages-alliance-${size}`" class="bg-input-bg mt-1 w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text" />
            </label>
          </div>
          <p class="text-xs text-text-subtle">Sólo alianza a cinco años, vigente y al día. Renovación mensual sin acumulación y sin intercambio entre tallas.</p>
          <BaseButton variant="primary" size="sm" :disabled="hourPackagesStore.isUpdating" data-testid="hour-packages-save-base-rates" @click="saveBaseRates">Guardar configuración</BaseButton>
        </section>

        <section class="bg-surface rounded-xl shadow-sm border border-border-muted p-6">
          <h2 class="text-sm font-medium text-text-default mb-1">Restablecer paquetes por defecto</h2>
          <p class="text-xs text-text-subtle mb-4">
            Restaura Ágil (30 XS, −10 %), Pro (30 XS + 20 S, −15 %) y Premium
            (30 XS + 20 S + 10 M, −25 %), con vigencia de 12 meses.
            Conserva los valores internos configurados y los documentos históricos.
          </p>
          <div class="flex flex-col sm:flex-row sm:items-center gap-3">
            <BaseSegmented v-model="restoreNationality" :options="nationalityOptions" nowrap />
            <BaseButton
              variant="danger"
              size="sm"
              :disabled="hourPackagesStore.isUpdating"
              data-testid="hour-packages-restore-defaults"
              @click="confirmRestore"
            >
              Restablecer
            </BaseButton>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useHourPackagesStore } from '~/stores/hour_packages';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { usePanelNotify } from '~/composables/usePanelNotify';
import BasePagination from '~/components/base/BasePagination.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import BaseRowActionsModal from '~/components/base/BaseRowActionsModal.vue';
import HourPackagesCards from '~/components/hour-packages/PackagesCards.vue';
import HourPackagesCompare from '~/components/hour-packages/PackagesCompare.vue';
import { usePagination } from '~/composables/usePagination';
import { composition, totalPrice, formatPackageMoney as formatMoney } from '~/utils/hourPackagePricing';

const localePath = useLocalePath();

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const CURRENCY_BY_NATIONALITY = { COL: 'COP', EXT: 'USD', USA: 'USD' };

const nationalityOptions = [
  { value: 'COL', label: 'Colombia (COP)', testId: 'hour-packages-tab-col' },
  { value: 'EXT', label: 'Extranjeros (USD)', testId: 'hour-packages-tab-ext' },
  { value: 'USA', label: 'USA (USD)', testId: 'hour-packages-tab-usa' },
];

const sectionOptions = [
  { value: 'catalog', label: 'Catálogo', testId: 'hour-packages-section-catalog' },
  { value: 'config', label: 'Configuración', testId: 'hour-packages-section-config' },
];

const viewModeOptions = [
  { value: 'table', label: 'Tabla', testId: 'hour-packages-view-table' },
  { value: 'cards', label: 'Tarjetas', testId: 'hour-packages-view-cards' },
  { value: 'compare', label: 'Comparativa', testId: 'hour-packages-view-compare' },
];
const packageColumns = [
  { key: 'name_es', label: 'Paquete', mobile: 'primary' },
  { key: 'composition', label: 'Cupos', mobile: 'secondary' },
  { key: 'reference', label: 'Referencia', mobile: 'secondary' },
  { key: 'discount_percent', label: 'Desc.', mobile: 'meta' },
  { key: 'savings', label: 'Ahorro', mobile: 'secondary' },
  { key: 'total', label: 'Total', mobile: 'secondary' },
  { key: 'status', label: 'Estado', mobile: 'meta' },
];

const hourPackagesStore = useHourPackagesStore();
const notify = usePanelNotify();
const packages = computed(() => hourPackagesStore.packages);
const selectedNationality = ref('COL');
const activeSection = ref('catalog');
const viewMode = ref('table');
const restoreNationality = ref('COL');
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const actionsRow = ref(null);

function packageActionItems(pkg) {
  return [
    { action: 'edit', label: 'Editar', to: localePath(`/panel/hour-packages/${pkg.id}/edit`), testid: `hour-package-edit-${pkg.id}` },
    { divider: true },
    { action: 'delete', label: 'Eliminar', danger: true, onClick: () => handleDelete(pkg), testid: `hour-package-delete-${pkg.id}` },
  ];
}

const defaultViewMode = computed(() => hourPackagesStore.settings?.default_view_mode ?? 'table');

const pricingSettings = ref({});
const pricingFields = [
  { key: 'xs_price_cop', label: 'Valor XS (COP)', step: '1' },
  { key: 's_price_cop', label: 'Valor S (COP)', step: '1' },
  { key: 'm_price_cop', label: 'Valor M (COP)', step: '1' },
  { key: 'foreign_multiplier', label: 'Factor extranjeros', step: '0.001' },
  { key: 'usa_multiplier', label: 'Factor EE. UU.', step: '0.001' },
];
watch(() => hourPackagesStore.settings, (settings) => {
  if (!settings) return;
  pricingSettings.value = Object.fromEntries([
    ...pricingFields.map((field) => field.key),
    'alliance_xs_count', 'alliance_s_count', 'alliance_m_count',
  ].map((key) => [key, Number(settings[key])]));
}, { immediate: true });

const nationalityLabel = computed(() =>
  ({ COL: 'de Colombia', EXT: 'del extranjero', USA: 'de Estados Unidos' }[selectedNationality.value]));
const currentCurrency = computed(() => CURRENCY_BY_NATIONALITY[selectedNationality.value]);

const {
  currentPage: packagesPage,
  totalPages: packagesTotalPages,
  totalItems: packagesTotalItems,
  rangeFrom: packagesRangeFrom,
  rangeTo: packagesRangeTo,
  paginatedItems: pagedPackages,
  goTo: packagesGoTo,
  next: packagesNext,
  prev: packagesPrev,
} = usePagination(packages, { pageSize: 10 });

onMounted(async () => {
  hourPackagesStore.fetchAdminPackages(selectedNationality.value);
  const result = await hourPackagesStore.fetchSettings();
  if (result.success) viewMode.value = result.data.default_view_mode;
});
watch(selectedNationality, (nationality) => {
  hourPackagesStore.fetchAdminPackages(nationality);
});
usePanelRefresh(() => hourPackagesStore.fetchAdminPackages(selectedNationality.value));

function statusBadgeClass(pkg) {
  return pkg.is_active
    ? 'bg-primary-soft text-text-brand'
    : 'bg-surface-raised text-text-muted';
}

async function saveBaseRates() {
  const result = await hourPackagesStore.updateSettings({ ...pricingSettings.value });
  if (!result.success) {
    notify.error('No se pudo guardar. Revisa valores positivos, cupos enteros y al menos un cupo para Alianza.');
    return;
  }
  notify.success('Configuración guardada. Las ofertas emitidas conservan sus condiciones.');
  await hourPackagesStore.fetchAdminPackages(selectedNationality.value);
}

async function saveDefaultViewMode(mode) {
  const result = await hourPackagesStore.updateSettings({ default_view_mode: mode });
  if (result.success) {
    notify.success('Vista por defecto guardada.');
  } else {
    notify.error('No se pudo guardar la vista por defecto.');
  }
}

function confirmRestore() {
  const label = { COL: 'Colombia', EXT: 'Extranjeros', USA: 'Estados Unidos' }[restoreNationality.value];
  requestConfirm({
    title: 'Restablecer paquetes',
    message: `¿Reemplazar el catálogo de ${label} con los paquetes por defecto? Los paquetes actuales de ese país se eliminan.`,
    variant: 'danger',
    confirmText: 'Restablecer',
    onConfirm: async () => {
      const result = await hourPackagesStore.restoreDefaults(restoreNationality.value);
      if (!result.success) {
        notify.error('No se pudo restablecer el catálogo.');
        return;
      }
      notify.success(`Catálogo de ${label} restablecido.`);
      // The restore also resets that nationality's base rate in settings.
      await hourPackagesStore.fetchSettings();
      if (restoreNationality.value === selectedNationality.value) {
        await hourPackagesStore.fetchAdminPackages(selectedNationality.value);
      }
    },
  });
}

function handleDelete(pkg) {
  requestConfirm({
    title: 'Eliminar paquete',
    message: `¿Eliminar "${pkg.name_es}"? El PDF de las propuestas en modo automático dejará de mostrarlo; las propuestas en modo manual no se modifican.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    onConfirm: async () => {
      const result = await hourPackagesStore.deletePackage(pkg.id);
      if (result.success) {
        notify.success('Paquete eliminado.');
      } else {
        notify.error('No se pudo eliminar el paquete.');
      }
    },
  });
}
</script>
