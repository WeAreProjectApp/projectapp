<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';

const props = defineProps({
  economics: { type: Object, default: null },
  isLoading: { type: Boolean, default: false },
  error: { type: String, default: '' },
});
defineEmits(['retry']);

const { t, locale } = useI18n();
const language = computed(() => locale.value.startsWith('en') ? 'en' : 'es');
const unavailable = computed(() => t('buildingOnDemandAdmin.metadata.unavailable'));
const currency = computed(() => props.economics?.currency || 'COP');
const referenceUrl = computed(() => {
  try {
    const url = new URL(props.economics?.reference_url);
    return url.protocol === 'https:' ? url.href : '';
  } catch {
    return '';
  }
});
const consultedOn = computed(() => formatDate(props.economics?.consulted_on, {
  locale: language.value,
  fallback: unavailable.value,
}));
const columns = computed(() => [
  { key: 'tier_name', label: t('buildingOnDemandAdmin.economics.tier'), mobile: 'primary' },
  { key: 'monthly_price', label: t('buildingOnDemandAdmin.economics.monthlyPrice'), mobile: 'secondary', textPolicy: 'atomic' },
  { key: 'hosting_cost_monthly', label: t('buildingOnDemandAdmin.economics.hostingCost'), mobile: 'secondary', textPolicy: 'atomic' },
  { key: 'net_monthly', label: t('buildingOnDemandAdmin.economics.net'), mobile: 'secondary', textPolicy: 'atomic' },
  { key: 'breakeven_hours', label: t('buildingOnDemandAdmin.economics.breakeven'), mobile: 'secondary', textPolicy: 'atomic' },
  { key: 'bag_share_percent', label: t('buildingOnDemandAdmin.economics.bagShare'), mobile: 'secondary', textPolicy: 'atomic' },
  { key: 'bag_hours', label: t('buildingOnDemandAdmin.economics.bagHours'), mobile: 'secondary', textPolicy: 'atomic' },
]);
const termGroups = computed(() => {
  const tiers = Array.isArray(props.economics?.tiers) ? props.economics.tiers : [];
  const rows = Array.isArray(props.economics?.rows) ? props.economics.rows : [];
  const groups = new Map();
  for (const row of rows) {
    if (!groups.has(row.term)) {
      const knownTerm = ['monthly', 'quarterly', 'semiannual', 'nine-month'].includes(row.term);
      groups.set(row.term, {
        id: row.term,
        label: knownTerm
          ? t(`buildingOnDemandAdmin.economics.terms.${row.term}`)
          : t('buildingOnDemandAdmin.economics.termMonths', { months: row.months }),
        rows: [],
      });
    }
    groups.get(row.term).rows.push({
      ...row,
      id: `${row.tier}-${row.term}`,
      tier_name: tiers.find((tier) => tier.id === row.tier)?.name || row.tier || unavailable.value,
    });
  }
  return [...groups.values()];
});

function money(value) {
  return formatMoney(value, currency.value) || unavailable.value;
}

function number(value, decimals = 0) {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return unavailable.value;
  return new Intl.NumberFormat(language.value === 'en' ? 'en-US' : 'es-CO', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(value));
}

function percent(value) {
  const formatted = number(value);
  return formatted === unavailable.value ? formatted : `${formatted} %`;
}

function hours(value, decimals = 0) {
  const formatted = number(value, decimals);
  return formatted === unavailable.value ? formatted : t('buildingOnDemandAdmin.economics.hours', { hours: formatted });
}
</script>

<template>
  <section
    class="min-w-0 max-w-full rounded-2xl border border-border-default bg-surface p-5 shadow-card panel-portrait:p-6"
    data-testid="building-on-demand-admin-economics"
    aria-labelledby="building-on-demand-admin-economics-title"
    :aria-busy="isLoading ? 'true' : undefined"
  >
    <h2 id="building-on-demand-admin-economics-title" class="text-xl font-medium text-text-brand">{{ t('buildingOnDemandAdmin.economics.title') }}</h2>
    <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{{ t('buildingOnDemandAdmin.economics.description') }}</p>

    <BaseAlert v-if="error" class="mt-4" variant="danger" data-testid="building-on-demand-admin-economics-error">
      <p>{{ t('buildingOnDemandAdmin.economics.error') }}</p>
      <BaseButton
        class="mt-3"
        variant="secondary"
        :loading="isLoading"
        data-testid="building-on-demand-admin-economics-retry"
        @click="$emit('retry')"
      >{{ t('buildingOnDemandAdmin.retry') }}</BaseButton>
    </BaseAlert>
    <p v-if="isLoading" class="mt-4 text-sm text-text-subtle" role="status" data-testid="building-on-demand-admin-economics-loading">{{ t('buildingOnDemandAdmin.loading') }}</p>

    <template v-if="economics">
      <div class="mt-5 min-w-0 rounded-xl border border-border-default bg-surface-raised p-4" data-testid="building-on-demand-admin-economics-inputs">
        <h3 class="text-base font-medium text-text-default">{{ t('buildingOnDemandAdmin.economics.inputsTitle') }}</h3>
        <dl class="mt-3 grid min-w-0 gap-4 text-sm panel-portrait:grid-cols-2 panel-desktop:grid-cols-3">
          <div class="min-w-0">
            <dt class="text-text-subtle">{{ t('buildingOnDemandAdmin.economics.hourCost') }}</dt>
            <dd class="mt-1 text-text-default" data-testid="building-on-demand-admin-economics-hour-cost">{{ money(economics.hour_cost) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-text-subtle">{{ t('buildingOnDemandAdmin.economics.vat') }}</dt>
            <dd class="mt-1 text-text-default" data-testid="building-on-demand-admin-economics-vat">{{ percent(economics.vat_percent) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-text-subtle">{{ t('buildingOnDemandAdmin.economics.provider') }}</dt>
            <dd class="mt-1 max-w-full text-text-default [overflow-wrap:anywhere]" data-testid="building-on-demand-admin-economics-provider">{{ economics.provider || unavailable }}</dd>
          </div>
          <div class="min-w-0 panel-portrait:col-span-2">
            <dt class="text-text-subtle">{{ t('buildingOnDemandAdmin.economics.reference') }}</dt>
            <dd class="mt-1 min-w-0 max-w-full text-text-default [overflow-wrap:anywhere]">
              <BaseButton
                v-if="referenceUrl"
                as="a"
                variant="link"
                :textPolicy="'wrap'"
                :to="referenceUrl"
                target="_blank"
                rel="noopener noreferrer"
                data-testid="building-on-demand-admin-economics-reference"
              >{{ referenceUrl }}</BaseButton>
              <span v-else data-testid="building-on-demand-admin-economics-reference-unavailable">{{ unavailable }}</span>
            </dd>
          </div>
          <div class="min-w-0">
            <dt class="text-text-subtle">{{ t('buildingOnDemandAdmin.economics.consultedOn') }}</dt>
            <dd class="mt-1 text-text-default" data-testid="building-on-demand-admin-economics-consulted-on">{{ consultedOn }}</dd>
          </div>
        </dl>
      </div>

      <div class="mt-5 min-w-0 space-y-5">
        <section
          v-for="group in termGroups"
          :key="group.id"
          class="min-w-0 max-w-full"
          :data-testid="`building-on-demand-admin-economics-term-${group.id}`"
          :aria-labelledby="`building-on-demand-admin-economics-term-title-${group.id}`"
        >
          <h3 :id="`building-on-demand-admin-economics-term-title-${group.id}`" class="mb-3 text-base font-medium text-text-brand">{{ group.label }}</h3>
          <BaseExploratoryList
            :columns="columns"
            :rows="group.rows"
            :caption="group.label"
            :show-actions="false"
            card-test-id-prefix="building-on-demand-admin-economics-row"
          >
            <template #cell-monthly_price="{ value }">{{ money(value) }}</template>
            <template #cell-hosting_cost_monthly="{ value }">{{ money(value) }}</template>
            <template #cell-net_monthly="{ value }">{{ money(value) }}</template>
            <template #cell-breakeven_hours="{ value }">{{ hours(value, 1) }}</template>
            <template #cell-bag_share_percent="{ value }">{{ percent(value) }}</template>
            <template #cell-bag_hours="{ value }">{{ hours(value) }}</template>
          </BaseExploratoryList>
        </section>
      </div>
      <p class="mt-5 max-w-3xl text-sm leading-6 text-text-muted" data-testid="building-on-demand-admin-economics-note">{{ t('buildingOnDemandAdmin.economics.note') }}</p>
    </template>
    <p v-if="!termGroups.length && !isLoading && !error" class="mt-4 text-sm text-text-subtle" data-testid="building-on-demand-admin-economics-empty">{{ t('buildingOnDemandAdmin.economics.empty') }}</p>
  </section>
</template>
