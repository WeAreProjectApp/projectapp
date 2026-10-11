<script setup>
import { computed } from 'vue'
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import { listOf } from '~/utils/buildingWithUs'
import { priceForTerm, tierWhatsappUrl } from '~/utils/buildingOnDemand'
import { formatMoney } from '~/utils/formatMoney'

const props = defineProps({
  tier: { type: Object, required: true },
  term: { type: Object, default: () => ({ id: 'monthly', months: 1 }) },
  offer: { type: Object, default: () => ({}) },
  whatsappBaseUrl: { type: String, default: '' },
  language: { type: String, default: 'es' },
})
const { t } = useI18n()
const label = (key, params = {}) => t(`buildingOnDemand.${key}`, params, {
  locale: props.language === 'en' ? 'en-us' : 'es-co',
})
const price = computed(() => priceForTerm(props.tier, props.term.id))
const isLongTerm = computed(() => Number(price.value?.months) > 1)
const whatsappUrl = computed(() => tierWhatsappUrl(props.whatsappBaseUrl, label('tierWhatsappMessage', {
  name: props.tier.name,
  term: props.term.label || label('monthlyTerm'),
})))
</script>

<template>
  <article
    class="flex h-full min-w-0 flex-col gap-6 rounded-2xl border bg-surface p-6 text-text-default shadow-card [overflow-wrap:anywhere]"
    :class="tier.recommended ? 'border-primary ring-2 ring-primary/20' : 'border-border-default'"
    :data-testid="`building-on-demand-tier-${tier.id}`"
    :data-recommended="tier.recommended ? 'true' : 'false'"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <h3 class="min-w-0 text-2xl font-semibold">{{ tier.name }}</h3>
      <BaseBadge :variant="tier.recommended ? 'success' : 'neutral'" v-bind="{ textPolicy: 'wrap' }">
        {{ tier.badge }}
      </BaseBadge>
    </div>

    <div class="space-y-2">
      <p class="text-sm font-semibold uppercase tracking-wide text-text-brand">{{ tier.pace_label }}</p>
      <p class="text-base text-text-muted">{{ tier.pace_summary }}</p>
      <p class="text-sm text-text-muted">
        {{ label('dailyPace', { hours: tier.daily_hours, days: offer.days_per_week }) }}
      </p>
    </div>

    <div class="space-y-3 rounded-xl bg-surface-raised p-4">
      <p class="text-3xl font-semibold text-text-brand">{{ label('bagHours', { hours: tier.bag_hours }) }}</p>
      <BaseBadge variant="neutral" v-bind="{ textPolicy: 'wrap' }">{{ label('bagCondition') }}</BaseBadge>
    </div>

    <div class="space-y-2">
      <h4 class="text-sm font-semibold">{{ label('idealFor') }}</h4>
      <p class="text-base text-text-muted">{{ tier.ideal_for }}</p>
    </div>

    <div class="space-y-3">
      <h4 class="text-sm font-semibold">{{ label('rolesLabel') }}</h4>
      <ul class="space-y-2 text-sm text-text-muted">
        <li v-for="role in listOf(tier.roles)" :key="role" class="flex min-w-0 gap-2">
          <span aria-hidden="true" class="shrink-0 text-success-strong">✓</span>
          <span class="min-w-0">{{ role }}</span>
        </li>
      </ul>
    </div>

    <div v-if="tier.server" class="space-y-2 rounded-xl border border-border-muted p-4">
      <p class="text-base font-semibold">{{ label('serverRam', { ram: tier.server.ram_gb }) }}</p>
      <p class="text-sm text-text-muted">
        {{ label('serverSpecs', { vcpu: tier.server.vcpu, disk: tier.server.disk_gb, transfer: tier.server.transfer_tb }) }}
      </p>
    </div>

    <ul class="space-y-2 text-sm text-text-muted">
      <li v-for="highlight in listOf(tier.highlights)" :key="highlight" class="flex min-w-0 gap-2">
        <span aria-hidden="true" class="shrink-0 text-success-strong">✓</span>
        <span class="min-w-0">{{ highlight }}</span>
      </li>
    </ul>

    <div class="mt-auto space-y-4 border-t border-border-muted pt-5">
      <template v-if="price">
        <p :data-testid="`building-on-demand-price-${tier.id}`" class="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span class="text-2xl font-semibold">{{ formatMoney(price.monthly_price, 'COP') }}</span>
          <span class="text-sm text-text-muted">{{ label('perMonth') }}</span>
          <span v-if="offer.prices_include_vat === false" class="text-sm text-text-muted">{{ label('vatSuffix') }}</span>
        </p>
        <div v-if="isLongTerm" class="space-y-3">
          <BaseBadge variant="success" v-bind="{ textPolicy: 'wrap' }">
            {{ label('discountLabel', { discount: price.discount_percent }) }}
          </BaseBadge>
          <dl class="space-y-2 text-sm">
            <div class="flex flex-wrap justify-between gap-x-3 gap-y-1" :data-testid="`building-on-demand-total-${tier.id}`">
              <dt class="text-text-muted">{{ label('termTotal') }}</dt>
              <dd class="font-semibold">{{ formatMoney(price.total, 'COP') }}</dd>
            </div>
            <div class="flex flex-wrap justify-between gap-x-3 gap-y-1">
              <dt class="text-text-muted">{{ label('termSavings') }}</dt>
              <dd class="font-semibold text-success-strong">{{ formatMoney(price.savings, 'COP') }}</dd>
            </div>
          </dl>
        </div>
      </template>
      <p v-else class="text-sm text-text-muted">{{ label('priceUnavailable') }}</p>
      <BaseButton
        as="a"
        :to="whatsappUrl"
        target="_blank"
        rel="noopener noreferrer"
        variant="primary"
        v-bind="{ textPolicy: 'wrap' }"
        class="min-h-11 w-full"
        :data-testid="`building-on-demand-tier-cta-${tier.id}`"
      >
        {{ tier.cta_label }}
      </BaseButton>
    </div>
  </article>
</template>
