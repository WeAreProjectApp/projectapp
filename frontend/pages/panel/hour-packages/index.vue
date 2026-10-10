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
      <h1 class="text-2xl font-light text-text-default">Paquetes de horas</h1>
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
          Sin paquetes para esta nacionalidad — las propuestas nuevas usarán los paquetes por defecto.
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
            caption="Paquetes de horas y precios"
            card-test-id-prefix="hour-package-row"
            table-min-width="64rem"
            row-actions-layout="menu-start"
          >
            <template #cell-name_es="{ row: pkg }">
              <NuxtLink :to="localePath(`/panel/hour-packages/${pkg.id}/edit`)" class="block min-w-0 max-w-full text-sm font-medium leading-tight text-text-default [overflow-wrap:anywhere] transition-colors hover:text-text-brand">{{ pkg.name_es }}</NuxtLink>
              <p class="mt-0.5 min-w-0 max-w-full text-xs text-text-subtle [overflow-wrap:anywhere]">{{ pkg.name_en }} · Orden {{ pkg.order }}</p>
            </template>
            <template #cell-hours="{ row: pkg }">{{ pkg.hours }} h</template>
            <template #cell-hourly_rate="{ row: pkg }">{{ formatMoney(pkg.hourly_rate, pkg.currency) }}/h</template>
            <template #cell-discount_percent="{ row: pkg }">
              <span v-if="Number(pkg.discount_percent) > 0" class="inline-flex rounded-full bg-primary-soft px-2 py-0.5 text-xs font-medium text-text-brand">-{{ pkg.discount_percent }}%</span>
              <span v-else>—</span>
            </template>
            <template #cell-effective_rate="{ row: pkg }">{{ formatMoney(effectiveRate(pkg), pkg.currency) }}/h</template>
            <template #cell-total="{ row: pkg }"><span class="font-medium">{{ formatMoney(totalPrice(pkg), pkg.currency) }}</span></template>
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

        <section class="bg-surface rounded-xl shadow-sm border border-border-muted p-6">
          <h2 class="text-sm font-medium text-text-default mb-1">Tarifa base por hora</h2>
          <p class="text-xs text-text-subtle mb-4">
            Al guardar, la tarifa se aplica a <strong>todos</strong> los paquetes de esa
            nacionalidad (incluidos los inactivos y los que tenían tarifa personalizada).
            Las propuestas en modo automático toman el catálogo al generar su PDF;
            las que están en modo manual no se modifican.
          </p>
          <div class="mb-4 grid grid-cols-1 gap-4 panel-portrait:grid-cols-3">
            <div>
              <label for="hp-base-rate-col" class="block text-sm font-medium text-text-default mb-1">Colombia (COP)</label>
              <input
                id="hp-base-rate-col"
                v-model.number="baseRates.COL"
                type="number"
                min="1"
                step="1"
                data-testid="hour-packages-base-rate-col"
                class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all"
              />
            </div>
            <div>
              <label for="hp-base-rate-ext" class="block text-sm font-medium text-text-default mb-1">Extranjeros (USD)</label>
              <input
                id="hp-base-rate-ext"
                v-model.number="baseRates.EXT"
                type="number"
                min="0.01"
                step="0.01"
                data-testid="hour-packages-base-rate-ext"
                class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all"
              />
            </div>
            <div>
              <label for="hp-base-rate-usa" class="block text-sm font-medium text-text-default mb-1">USA (USD)</label>
              <input
                id="hp-base-rate-usa"
                v-model.number="baseRates.USA"
                type="number"
                min="0.01"
                step="0.01"
                data-testid="hour-packages-base-rate-usa"
                class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all"
              />
            </div>
          </div>
          <BaseButton
            variant="primary"
            size="sm"
            :disabled="hourPackagesStore.isUpdating"
            data-testid="hour-packages-save-base-rates"
            @click="saveBaseRates"
          >
            Guardar tarifas
          </BaseButton>
        </section>

        <section class="bg-surface rounded-xl shadow-sm border border-border-muted p-6">
          <h2 class="text-sm font-medium text-text-default mb-1">Restablecer paquetes por defecto</h2>
          <p class="text-xs text-text-subtle mb-4">
            Reemplaza el catálogo del país elegido con la escalera por defecto:
            1&nbsp;h, 20&nbsp;h (-10%), 60&nbsp;h (-20%) y 180&nbsp;h (-30%)
            sobre la tarifa base (COL $30.000&nbsp;COP/h · EXT $18&nbsp;USD/h · USA $30&nbsp;USD/h).
            Los paquetes actuales de ese país se eliminan.
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
import { effectiveRate, totalPrice, formatPackageMoney as formatMoney } from '~/utils/hourPackagePricing';

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
  { key: 'hours', label: 'Horas', mobile: 'secondary' },
  { key: 'hourly_rate', label: 'Tarifa/h', mobile: 'secondary' },
  { key: 'discount_percent', label: 'Desc.', mobile: 'meta' },
  { key: 'effective_rate', label: 'Tarifa efectiva', mobile: 'secondary' },
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

const baseRates = ref({ COL: null, EXT: null, USA: null });
// DRF serializes decimals as strings — normalize to numbers for the inputs.
watch(
  () => hourPackagesStore.settings,
  (settings) => {
    if (!settings) return;
    baseRates.value = {
      COL: Number(settings.base_rate_col),
      EXT: Number(settings.base_rate_ext),
      USA: Number(settings.base_rate_usa),
    };
  },
  { immediate: true },
);

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
  const rates = baseRates.value;
  const invalid = Object.values(rates).some(
    (rate) => !Number.isFinite(rate) || rate <= 0,
  );
  if (invalid) {
    notify.error('Las tarifas base deben ser números mayores a 0.');
    return;
  }
  const result = await hourPackagesStore.updateSettings({
    base_rate_col: rates.COL,
    base_rate_ext: rates.EXT,
    base_rate_usa: rates.USA,
  });
  if (!result.success) {
    notify.error('No se pudieron guardar las tarifas base.');
    return;
  }
  const updatedCount = Object.values(result.data?.updated_packages ?? {})
    .reduce((sum, count) => sum + count, 0);
  notify.success(
    updatedCount > 0
      ? `Tarifas base guardadas. ${updatedCount} paquete${updatedCount === 1 ? '' : 's'} actualizado${updatedCount === 1 ? '' : 's'}.`
      : 'Tarifas base guardadas. Sin cambios en los paquetes.',
  );
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
