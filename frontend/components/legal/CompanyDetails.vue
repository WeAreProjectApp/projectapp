<script setup>
import { computed } from 'vue'
import { useMessages } from '~/composables/useMessages'
import { LEGAL_ENTITY as L } from '~/config/legalEntity'

// Company contact block for /contact: Meta's review requires the same name,
// address and phone as the verified business portfolio.
const { messages } = useMessages('waiter')
const company = computed(() => messages.value?.company || {})

const rows = computed(() => [
  { key: 'legal_name', label: company.value.legal_name, value: `${L.brand} — ${L.tradeName}` },
  { key: 'owner', label: company.value.owner, value: L.owner },
  { key: 'nit', label: company.value.nit, value: L.nit },
  { key: 'address', label: company.value.address, value: `${L.address}, ${L.city}, ${L.country}` },
  { key: 'phone', label: company.value.phone, value: L.phone, href: L.whatsappHref, external: true },
  { key: 'email', label: company.value.email, value: L.email, href: `mailto:${L.email}` },
  { key: 'hours', label: company.value.hours, value: company.value.hours_value },
])
</script>

<template>
  <section
    class="rounded-3xl border border-border-default bg-surface p-6 lg:p-8"
    aria-labelledby="company-details-title"
    data-testid="company-details"
  >
    <h2 id="company-details-title" class="text-2xl font-bold text-text-brand lg:text-3xl">
      {{ company.title || 'Company details' }}
    </h2>
    <dl class="mt-6 grid gap-x-8 gap-y-4 sm:grid-cols-2">
      <div v-for="row in rows" :key="row.key">
        <dt class="text-sm font-medium text-text-muted">{{ row.label }}</dt>
        <dd class="mt-1 break-words text-base font-light text-text-brand lg:text-lg">
          <a
            v-if="row.href"
            :href="row.href"
            class="underline-offset-4 hover:underline"
            v-bind="row.external ? { target: '_blank', rel: 'noopener noreferrer' } : {}"
          >
            {{ row.value }}
          </a>
          <template v-else>{{ row.value }}</template>
        </dd>
      </div>
    </dl>
  </section>
</template>
