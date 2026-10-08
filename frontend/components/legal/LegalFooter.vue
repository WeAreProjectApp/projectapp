<script setup>
import { computed } from 'vue'
import { useMessages } from '~/composables/useMessages'
import { LEGAL_ENTITY as L, WAITER_LEGAL_ROUTES as R } from '~/config/legalEntity'

// Legal strip required by Meta's app review: the same legal name, ID,
// address and phone as the verified business portfolio, plus the public
// Waiter legal pages. "page" closes the legal pages; "overlay" sits inside
// the dark video footer of the marketing pages.
const props = defineProps({
  variant: { type: String, default: 'page' },
})

const localePath = useLocalePath()
const { messages } = useMessages('waiter')
const footer = computed(() => messages.value?.footer || {})

const links = computed(() => [
  { key: 'product', label: footer.value.product || 'Waiter', to: R.product },
  { key: 'privacy', label: footer.value.privacy || 'Waiter privacy policy', to: R.privacy },
  { key: 'terms', label: footer.value.terms || 'Waiter terms of service', to: R.terms },
  { key: 'deletion', label: footer.value.data_deletion || 'Data deletion', to: R.dataDeletion },
  ...(props.variant === 'page'
    ? [{ key: 'contact', label: footer.value.contact || 'Contact', to: '/contact' }]
    : []),
])

const isOverlay = computed(() => props.variant === 'overlay')
</script>

<template>
  <div
    :class="isOverlay
      ? 'text-white'
      : 'border-t border-border-default bg-surface px-4 py-8 text-text-brand sm:px-6 lg:px-32'"
    data-testid="legal-footer"
  >
    <div :class="isOverlay ? '' : 'mx-auto max-w-4xl'">
      <nav
        :aria-label="footer.nav_label || 'Waiter legal pages'"
        class="flex flex-wrap gap-x-4 gap-y-1"
      >
        <NuxtLink
          v-for="link in links"
          :key="link.key"
          :to="localePath(link.to)"
          :class="isOverlay
            ? 'text-xs font-regular opacity-60 transition-opacity hover:opacity-90 lg:text-sm'
            : 'text-sm font-medium underline-offset-4 hover:underline'"
          :data-testid="`legal-footer-link-${link.key}`"
        >
          {{ link.label }}
        </NuxtLink>
      </nav>
      <p
        :class="isOverlay ? 'mt-2 text-xs font-light opacity-60' : 'mt-4 text-sm font-light text-text-muted'"
        data-testid="legal-footer-identity"
      >
        <strong class="font-semibold">{{ L.brand }}</strong>
        · {{ L.tradeName }} — {{ L.owner }} · NIT {{ L.nit }}
        · {{ L.address }}, {{ L.city }}, {{ L.country }}
        · {{ footer.phone_label || 'Phone' }}
        <a :href="L.phoneHref" class="hover:underline">{{ L.phone }}</a>
        · <a :href="`mailto:${L.email}`" class="hover:underline">{{ L.email }}</a>
      </p>
      <p
        v-if="!isOverlay"
        class="mt-2 text-sm font-light text-text-muted"
      >
        {{ footer.copyright || '© 2026 ProjectApp. Waiter is a ProjectApp product.' }}
      </p>
    </div>
  </div>
</template>
