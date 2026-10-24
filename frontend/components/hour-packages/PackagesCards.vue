<template>
  <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
    <article
      v-for="pkg in packages"
      :key="pkg.id"
      class="bg-surface rounded-xl shadow-sm border border-border-muted p-5 flex flex-col"
      :class="{ 'opacity-60': !pkg.is_active }"
      :data-testid="`hour-package-card-${pkg.id}`"
    >
      <div class="flex items-start justify-between gap-3">
        <div>
          <NuxtLink
            :to="localePath(`/panel/hour-packages/${pkg.id}/edit`)"
            class="text-sm font-medium text-text-default hover:text-text-brand transition-colors"
          >
            {{ pkg.name_es }}
          </NuxtLink>
          <p class="text-xs text-text-subtle">{{ pkg.name_en }}</p>
        </div>
        <span
          class="text-[10px] px-2 py-0.5 rounded-full font-medium flex-shrink-0"
          :class="pkg.is_active ? 'bg-primary-soft text-text-brand' : 'bg-surface-raised text-text-muted'"
        >
          {{ pkg.is_active ? 'Activo' : 'Inactivo' }}
        </span>
      </div>

      <p class="mt-4 text-lg font-medium text-text-default">{{ composition(pkg) }}</p>
      <p class="mt-1 text-xs text-text-muted">Vigencia: {{ pkg.validity_months }} meses desde el pago</p>
      <dl class="mt-3 space-y-2 text-sm flex-1">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <dt class="text-text-muted">Referencia</dt>
          <dd class="text-text-muted line-through">{{ money(pkg.reference_price, pkg.currency) }}</dd>
        </div>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <dt class="text-text-muted">Descuento</dt>
          <dd class="font-medium text-text-brand">-{{ pkg.discount_percent }} %</dd>
        </div>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <dt class="text-text-muted">Ahorro</dt>
          <dd class="font-medium text-text-brand">{{ money(pkg.savings, pkg.currency) }}</dd>
        </div>
        <div class="flex flex-wrap items-center justify-between gap-2 border-t border-border-muted pt-2">
          <dt class="text-text-muted">Total</dt>
          <dd class="font-medium text-text-default">{{ money(totalPrice(pkg), pkg.currency) }} {{ pkg.currency === 'COP' ? '+ IVA' : '+ Tax' }}</dd>
        </div>
      </dl>

      <BaseRichTextContent v-if="pkg.note_es" :source="pkg.note_es" :format="pkg.text_formats?.['/note_es'] || 'plain'" class="mt-3 text-xs text-text-subtle" />

      <div class="mt-4 pt-3 border-t border-border-muted flex items-center gap-3">
        <NuxtLink
          :to="localePath(`/panel/hour-packages/${pkg.id}/edit`)"
          class="text-xs text-text-brand font-medium"
        >
          Editar
        </NuxtLink>
        <BaseButton variant="danger-ghost" size="sm" @click="$emit('delete', pkg)">
          Eliminar
        </BaseButton>
      </div>
    </article>
  </div>
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import { composition, totalPrice, formatPackageMoney as money } from '~/utils/hourPackagePricing';

defineProps({
  packages: { type: Array, required: true },
});

defineEmits(['delete']);

const localePath = useLocalePath();
</script>
