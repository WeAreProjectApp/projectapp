<template>
  <aside class="w-full shrink-0 self-start rounded-3xl border border-border-default bg-surface px-3 py-3 shadow-sm lg:w-56 lg:py-4">
    <div
      ref="scrollerRef"
      class="scrollbar-hide flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible"
      @scroll="updateScrollState"
    >
      <template v-for="item in items" :key="item.disabled ? item.label : item.href">
        <span
          v-if="item.disabled"
          class="flex shrink-0 cursor-not-allowed items-center justify-between gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium opacity-40"
        >
          {{ item.label }}
          <span class="rounded-full bg-surface-muted px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-text-muted">Pronto</span>
        </span>
        <NuxtLink
          v-else
          :to="item.href"
          :data-active="isActive(item.href)"
          :class="[
            'flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition',
            isActive(item.href)
              ? 'bg-primary-soft text-text-brand dark:bg-lemon/10 dark:text-accent'
              : 'text-green-light hover:bg-primary-soft hover:text-text-brand dark:hover:text-accent',
          ]"
        >
          {{ item.label }}
        </NuxtLink>
      </template>
    </div>

    <!-- Barrita indicadora de scroll (solo móvil, solo si hay overflow) -->
    <div
      v-show="hasOverflow"
      class="mt-2 h-1 w-full overflow-hidden rounded-full bg-surface-muted lg:hidden"
      aria-hidden="true"
    >
      <div class="h-full rounded-full bg-green-light/40" :style="thumbStyle"></div>
    </div>
  </aside>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'

const props = defineProps({
  projectId: { type: [String, Number], required: true },
})

const localePath = useLocalePath()
const route = useRoute()
const authStore = usePlatformAuthStore()
const { t } = useI18n()

const items = computed(() => {
  const base = `/platform/projects/${props.projectId}`
  const navigationItems = [
    { label: 'Resumen',           href: localePath(base) },
    { label: t('platformDelivery.navigation'), href: localePath(`${base}/delivery`) },
    { label: 'Solicitudes',       href: localePath(`${base}/changes`) },
    { label: 'Bugs',              href: localePath(`${base}/bugs`) },
    { label: 'Recursos',          href: localePath(`${base}/deliverables`) },
    { label: 'Hosting',           href: localePath(`${base}/payments`) },
    { label: 'Cuentas de cobro',  href: localePath(`${base}/collection-accounts`), disabled: true },
    { label: 'Modelo de datos',   href: localePath(`${base}/data-model`), disabled: true },
  ]
  if (authStore.isAdmin) {
    navigationItems.push({
      label: t('projectAccess.navigation'),
      href: localePath(`${base}/access`),
    })
  }
  return navigationItems
})

function isActive(href) {
  const stripped = (p) => p.replace(/^\/[a-z]{2}-[a-z]{2}/, '')
  return stripped(route.path) === stripped(href)
}

// --- Indicadores de scroll horizontal (móvil) ---
const scrollerRef = ref(null)
const hasOverflow = ref(false)
const thumbWidthPct = ref(100)
const thumbLeftPct = ref(0)

const thumbStyle = computed(() => ({
  width: `${thumbWidthPct.value}%`,
  marginLeft: `${thumbLeftPct.value}%`,
}))

function updateScrollState() {
  const el = scrollerRef.value
  if (!el) return
  const { scrollLeft, scrollWidth, clientWidth } = el
  const max = scrollWidth - clientWidth
  hasOverflow.value = max > 2
  thumbWidthPct.value = scrollWidth > 0 ? Math.min(100, (clientWidth / scrollWidth) * 100) : 100
  thumbLeftPct.value = scrollWidth > 0 ? (scrollLeft / scrollWidth) * 100 : 0
}

function scrollActiveIntoView() {
  const el = scrollerRef.value
  if (!el) return
  const active = el.querySelector('[data-active="true"]')
  if (!active) return
  // Solo ajusta el scroll horizontal del contenedor; no toca el scroll de la página.
  const target = active.offsetLeft - (el.clientWidth - active.clientWidth) / 2
  el.scrollLeft = Math.max(0, target)
}

let resizeObserver = null

onMounted(() => {
  nextTick(() => {
    scrollActiveIntoView()
    updateScrollState()
  })
  if (typeof ResizeObserver !== 'undefined' && scrollerRef.value) {
    resizeObserver = new ResizeObserver(() => updateScrollState())
    resizeObserver.observe(scrollerRef.value)
  }
})

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
})

watch(() => route.path, () => {
  nextTick(() => {
    scrollActiveIntoView()
    updateScrollState()
  })
})
</script>

<style scoped>
/* Oculta la scrollbar nativa: dejamos solo la barrita indicadora propia. */
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>
