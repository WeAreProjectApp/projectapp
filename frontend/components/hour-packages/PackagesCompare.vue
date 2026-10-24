<template>
  <!-- pt-3 gives the -top-2.5 badge room inside the overflow-x-auto clip box -->
  <div class="flex gap-4 overflow-x-auto pt-3 pb-2">
    <article
      v-for="pkg in packages"
      :key="pkg.id"
      class="relative flex-1 min-w-[210px] max-w-[280px] bg-surface rounded-xl shadow-sm border p-5 flex flex-col"
      :class="[
        pkg.id === bestValueId ? 'border-primary ring-1 ring-primary' : 'border-border-muted',
        { 'opacity-60': !pkg.is_active },
      ]"
      :data-testid="`hour-package-tier-${pkg.id}`"
    >
      <span
        v-if="pkg.id === bestValueId"
        class="absolute -top-2.5 left-1/2 -translate-x-1/2 text-[10px] px-2.5 py-0.5 rounded-full font-medium bg-primary text-white whitespace-nowrap"
      >
        Mayor descuento
      </span>

      <h3 class="text-sm font-medium text-text-default">{{ pkg.name_es }}</h3>
      <p class="text-xs text-text-subtle mb-4">{{ pkg.name_en }}</p>

      <p class="text-lg font-medium text-text-default">{{ composition(pkg) }}</p>
      <p class="mt-1 text-xs text-text-muted">{{ pkg.validity_months }} meses desde el pago</p>
      <p class="mt-3 text-xs text-text-subtle line-through">{{ money(pkg.reference_price, pkg.currency) }}</p>
      <p class="mt-1 text-sm font-medium text-text-brand">-{{ pkg.discount_percent }} % · Ahorra {{ money(pkg.savings, pkg.currency) }}</p>
      <p class="mt-3 border-t border-border-muted pt-3 text-lg font-medium text-text-default">
        {{ money(totalPrice(pkg), pkg.currency) }} <span class="text-xs">{{ pkg.currency === 'COP' ? '+ IVA' : '+ Tax' }}</span>
      </p>

      <p v-if="pkg.note_es" class="mt-2 text-xs text-text-subtle flex-1">{{ pkg.note_es }}</p>
      <span v-else class="flex-1" />

      <div class="mt-4 flex items-center gap-3">
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
import { computed } from 'vue';
import {
  bestValuePackageId,
  composition,
  totalPrice,
  formatPackageMoney as money,
} from '~/utils/hourPackagePricing';

const props = defineProps({
  packages: { type: Array, required: true },
});

defineEmits(['delete']);

const localePath = useLocalePath();
const bestValueId = computed(() => bestValuePackageId(props.packages));
</script>
