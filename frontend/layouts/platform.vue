<template>
  <div
    :class="[
      { dark: isDark },
      hasCover ? 'platform-cover' : '',
      hasCover && isCoverDark ? 'platform-cover-dark' : '',
      hasTheme && !hasCover ? 'platform-color-only' : '',
    ]"
    class="relative min-h-screen"
  >
    <!-- Background: cover image fixed behind everything -->
    <div
      v-if="hasCover"
      class="fixed inset-0 z-0 bg-cover bg-center bg-no-repeat"
      :style="coverBgStyle"
    />
    <!-- Default solid background when no cover -->
    <div v-if="!hasCover && !hasTheme" class="fixed inset-0 z-0 bg-surface-muted" />

    <!-- Desktop sidebar (hidden on mobile) -->
    <div class="hidden md:block">
      <PlatformSidebar
        :is-collapsed="isCollapsed"
        :is-dark="isDark"
        @logout="handleLogout"
      />
    </div>

    <!-- Mobile top bar -->
    <div
      class="mobile-topbar sticky top-0 z-30 flex h-14 items-center justify-between border-b border-input-border/[0.06] px-4 md:hidden"
      :class="hasCover ? '' : 'bg-surface/80 backdrop-blur-xl dark:bg-primary-strong/90'"
    >
      <BaseButton
        unstyled
        icon-only
        type="button"
        aria-label="Abrir navegación"
        class="flex h-10 w-10 items-center justify-center rounded-full bg-primary-soft text-text-brand dark:bg-primary dark:text-white"
        @click="openMobile"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </BaseButton>
      <NuxtLink :to="localePath('/platform/projects')" class="text-base font-bold tracking-tight text-text-brand dark:text-white">
        Project<span class="text-green-light dark:text-accent">App.</span>
      </NuxtLink>
      <div class="h-8 w-8 shrink-0 overflow-hidden rounded-full">
        <img v-if="authStore.user?.avatar_display_url" :src="authStore.user.avatar_display_url" alt="Avatar" class="h-full w-full object-cover" />
        <div v-else class="flex h-full w-full items-center justify-center bg-primary text-xs font-bold text-white dark:bg-accent-soft dark:text-text-brand">
          {{ authStore.userInitials }}
        </div>
      </div>
    </div>

    <!-- Mobile drawer -->
    <PlatformMobileDrawer
      :is-open="isMobileOpen"
      :is-dark="isDark"
      @close="closeMobile"
      @logout="handleLogout"
      @toggle-theme="toggle"
      @open-theme-picker="showThemePicker = true"
    />

    <!-- Main content -->
    <main
      :class="[
        'relative z-10 transition-all duration-300 ease-in-out',
        'px-4 py-6 sm:px-6 lg:px-8',
        isCollapsed ? 'md:ml-[64px]' : 'md:ml-[240px]',
      ]"
    >
      <div class="mx-auto max-w-screen-2xl">
        <slot />
      </div>
    </main>

    <ClientOnly><AppiWidget /></ClientOnly>

    <!-- Theme picker popover -->
    <Teleport to="body">
      <Transition name="theme-popover">
        <div
          v-if="showThemePicker"
          class="fixed inset-0 z-50 flex items-end justify-center bg-black/30 px-4 pb-4 backdrop-blur-sm sm:items-center sm:pb-0"
          @click.self="showThemePicker = false"
        >
          <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-3xl border border-input-border/[0.06] bg-surface p-6 shadow-2xl dark:border-white/[0.06] dark:bg-primary sm:p-8">
            <div class="mb-5 flex items-center justify-between">
              <div>
                <h3 class="text-lg font-semibold text-text-brand dark:text-white">Personalizar interfaz</h3>
                <p class="mt-1 text-xs text-green-light">Escoge un color y una imagen para hacer tuyo este espacio.</p>
              </div>
              <BaseButton
                unstyled
                icon-only
                type="button"
                aria-label="Cerrar personalización"
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-green-light transition hover:bg-primary-soft hover:text-text-brand dark:hover:bg-surface/[0.06] dark:hover:text-white"
                @click="showThemePicker = false"
              >
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </BaseButton>
            </div>
            <ThemePicker />
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { provide, watch, onMounted, onUnmounted, ref, computed } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformTheme } from '~/composables/usePlatformTheme'
import { usePlatformSidebar } from '~/composables/usePlatformSidebar'
import { usePlatformCustomTheme } from '~/composables/usePlatformCustomTheme'
import PlatformSidebar from '~/components/platform/PlatformSidebar.vue'
import AppiWidget from '~/components/platform/AppiWidget.vue'
import PlatformMobileDrawer from '~/components/platform/PlatformMobileDrawer.vue'
import ThemePicker from '~/components/platform/ThemePicker.vue'

const route = useRoute()
const localePath = useLocalePath()
const authStore = usePlatformAuthStore()
const { isDark, toggle, hydrate: hydrateTheme } = usePlatformTheme()
const {
  isCollapsed,
  isMobileOpen,
  hydrate: hydrateSidebar,
  toggle: toggleSidebar,
  openMobile,
  closeMobile,
  setupResizeListener,
  cleanupResizeListener,
} = usePlatformSidebar()

const {
  themeColor,
  coverImage,
  customCoverImageUrl,
  hasTheme,
  hasCover,
  isCoverDark,
  hydrate: hydrateCustomTheme,
} = usePlatformCustomTheme()

const showThemePicker = ref(false)

const coverBgStyle = computed(() => {
  const url = customCoverImageUrl.value || (coverImage.value ? `/static/cover_gallery/${coverImage.value}` : '')
  return url ? { backgroundImage: `url(${encodeURI(url)})` } : {}
})

authStore.hydrate()

onMounted(() => {
  hydrateTheme()
  hydrateSidebar()
  hydrateCustomTheme()
  setupResizeListener()
})

onUnmounted(() => {
  cleanupResizeListener()
})

provide('toggleSidebar', toggleSidebar)
provide('toggleTheme', toggle)
provide('showThemePicker', showThemePicker)

watch(() => route.fullPath, () => {
  closeMobile()
})

async function handleLogout() {
  authStore.logout()
  await navigateTo(localePath('/platform/login'))
}

const _platformRouteMap = [
  { path: localePath('/platform/collection-accounts'), label: 'Cuentas cobro' },
  { path: localePath('/platform/complete-profile'), label: 'Completar perfil' },
  { path: localePath('/platform/notifications'), label: 'Notificaciones' },
  { path: localePath('/platform/deliverables'), label: 'Recursos' },
  { path: localePath('/platform/dashboard'), label: 'Dashboard' },
  { path: localePath('/platform/payments'), label: 'Hosting' },
  { path: localePath('/platform/projects'), label: 'Proyectos' },
  { path: localePath('/platform/clients'), label: 'Clientes' },
  { path: localePath('/platform/changes'), label: 'Cambios' },
  { path: localePath('/platform/profile'), label: 'Perfil' },
  { path: localePath('/platform/board'), label: 'Tablero' },
  { path: localePath('/platform/bugs'), label: 'Bugs' },
]

const _platformDynamic = [
  { re: /\/platform\/projects\/[^/]+\/collection-accounts/, label: 'Cuentas cobro' },
  { re: /\/platform\/projects\/[^/]+\/data-model/, label: 'Modelo datos' },
  { re: /\/platform\/projects\/[^/]+\/deliverables\/[^/]+/, label: 'Recurso' },
  { re: /\/platform\/projects\/[^/]+\/deliverables/, label: 'Recursos' },
  { re: /\/platform\/projects\/[^/]+\/payments/, label: 'Hosting' },
  { re: /\/platform\/projects\/[^/]+\/changes/, label: 'Cambios' },
  { re: /\/platform\/projects\/[^/]+\/board/, label: 'Tablero' },
  { re: /\/platform\/projects\/[^/]+\/bugs/, label: 'Bugs' },
  { re: /\/platform\/projects\/[^/]+/, label: 'Proyecto' },
  { re: /\/platform\/collection-accounts\/[^/]+/, label: 'Cuenta cobro' },
  { re: /\/platform\/clients\/[^/]+/, label: 'Cliente' },
]

const _platformViewLabel = computed(() => {
  const p = route.path
  for (const { re, label } of _platformDynamic) {
    if (re.test(p)) return label
  }
  for (const { path, label, exact } of _platformRouteMap) {
    if (exact ? p === path : p === path || p.startsWith(path + '/')) return label
  }
  return null
})

useHead(() => ({
  title: _platformViewLabel.value ? `Project App (${_platformViewLabel.value})` : 'Project App',
}))
</script>

<style scoped>
.theme-popover-enter-active,
.theme-popover-leave-active {
  transition: opacity 0.25s ease;
}
.theme-popover-enter-from,
.theme-popover-leave-to {
  opacity: 0;
}
</style>
