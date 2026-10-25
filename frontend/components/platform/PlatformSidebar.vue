<template>
  <aside
    :class="[
      'fixed inset-y-0 left-0 z-30 flex flex-col border-r transition-all duration-300 ease-in-out',
      'border-input-border/[0.06] bg-surface dark:border-white/[0.06] dark:bg-primary-strong',
      isCollapsed ? 'w-[64px]' : 'w-[240px]',
    ]"
  >
    <!-- Logo header -->
    <div
      :class="[
        'flex h-16 shrink-0 items-center border-b border-input-border/[0.06] dark:border-white/[0.06]',
        isCollapsed ? 'justify-center px-2' : 'gap-3 px-5',
      ]"
    >
      <span
        v-if="!isCollapsed"
        class="text-xl font-bold tracking-tight text-text-brand dark:text-white"
      >
        Project<span class="text-text-brand dark:text-accent">App.</span>
      </span>
      <span
        v-else
        class="text-base font-bold tracking-tight text-text-brand dark:text-white"
      >
        P<span class="text-text-brand dark:text-accent">A</span>
      </span>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto px-3 py-4">
      <!-- Navegación -->
      <div class="mb-5">
        <p
          v-if="!isCollapsed"
          class="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-green-light/60"
        >
          Navegación
        </p>
        <SidebarItem
          v-for="item in primaryItems"
          :key="item.href"
          :item="item"
          :is-collapsed="isCollapsed"
          :is-active="isActive(item.href)"
          :disabled="item.disabled"
        />
      </div>

      <!-- Configuration section -->
      <div class="mb-5">
        <p
          v-if="!isCollapsed"
          class="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-green-light/60"
        >
          Cuenta
        </p>
        <SidebarItem
          v-for="item in accountItems"
          :key="item.href"
          :item="item"
          :is-collapsed="isCollapsed"
          :is-active="isActive(item.href)"
          :disabled="item.disabled"
        />
        <PlatformHelpMenu :collapsed="isCollapsed" />
        <!-- Personaliza button (opens theme picker, not a route) -->
        <BaseButton
          unstyled
          icon-only
          type="button"
          aria-label="Personalizar apariencia"
          :class="[
            'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150',
            isCollapsed ? 'justify-center' : '',
            'text-green-light hover:bg-primary-soft hover:text-text-brand dark:hover:bg-surface/[0.06] dark:hover:text-white',
          ]"
          :title="isCollapsed ? 'Personaliza' : undefined"
          @click="showThemePicker = true"
        >
          <svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="13.5" cy="6.5" r="2.5" /><circle cx="17.5" cy="10.5" r="2.5" /><circle cx="8.5" cy="7.5" r="2.5" /><circle cx="6.5" cy="12.5" r="2.5" />
            <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 011.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
          </svg>
          <span v-if="!isCollapsed" class="truncate">Personaliza</span>
        </BaseButton>
      </div>

      <!-- Admin section -->
      <div v-if="authStore.isAdmin" class="mb-5">
        <p
          v-if="!isCollapsed"
          class="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-green-light/60"
        >
          Administración
        </p>
        <SidebarItem
          v-for="item in adminItems"
          :key="item.href"
          :item="item"
          :is-collapsed="isCollapsed"
          :is-active="isActive(item.href)"
          :disabled="item.disabled"
        />
      </div>
    </nav>

    <!-- User footer -->
    <div class="shrink-0 border-t border-input-border/[0.06] p-3 dark:border-white/[0.06]">
      <div
        :class="[
          'flex items-center rounded-xl transition',
          isCollapsed ? 'justify-center p-2' : 'gap-3 p-2',
        ]"
      >
        <div class="h-9 w-9 shrink-0 overflow-hidden rounded-full">
          <img
            v-if="authStore.user?.avatar_display_url"
            :src="authStore.user.avatar_display_url"
            alt="Avatar"
            class="h-full w-full object-cover"
          />
          <div v-else class="flex h-full w-full items-center justify-center bg-primary text-xs font-bold text-white dark:bg-accent-soft dark:text-text-brand">
            {{ authStore.userInitials }}
          </div>
        </div>
        <div v-if="!isCollapsed" class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium text-text-brand dark:text-white">{{ authStore.displayName }}</p>
          <p class="truncate text-xs text-green-light">{{ userSubtitle }}</p>
        </div>
      </div>

      <!-- Action buttons -->
      <div
        :class="[
          'mt-2 flex',
          isCollapsed ? 'flex-col items-center gap-1' : 'items-center gap-1',
        ]"
      >
        <!-- Color theme -->
        <BaseButton
          unstyled
          icon-only
          type="button"
          aria-label="Personalizar apariencia"
          :class="sidebarActionClass"
          :title="isCollapsed ? 'Personalizar' : undefined"
          @click="showThemePicker = true"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="13.5" cy="6.5" r="2.5" />
            <circle cx="17.5" cy="10.5" r="2.5" />
            <circle cx="8.5" cy="7.5" r="2.5" />
            <circle cx="6.5" cy="12.5" r="2.5" />
            <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 011.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
          </svg>
        </BaseButton>

        <BaseButton
          unstyled
          icon-only
          type="button"
          aria-label="Cerrar sesión"
          :class="sidebarActionClass"
          :title="isCollapsed ? 'Salir' : undefined"
          @click="$emit('logout')"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
        </BaseButton>

        <BaseButton
          unstyled
          icon-only
          type="button"
          :aria-label="isCollapsed ? 'Expandir barra lateral' : 'Colapsar barra lateral'"
          :class="[sidebarActionClass, 'ml-auto']"
          :title="isCollapsed ? 'Expandir' : 'Colapsar'"
          @click="toggleSidebar"
        >
          <svg
            class="h-4 w-4 transition-transform duration-300"
            :class="isCollapsed ? 'rotate-180' : ''"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </BaseButton>
      </div>
    </div>
  </aside>
</template>

<script setup>
import PlatformHelpMenu from '~/components/platform/PlatformHelpMenu.vue'
import { computed, inject, onMounted, onUnmounted } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformNotificationsStore } from '~/stores/platform-notifications'
import SidebarItem from '~/components/platform/SidebarItem.vue'
import { usePlatformNav } from '~/composables/usePlatformNav'

defineEmits(['logout'])

const props = defineProps({
  isCollapsed: { type: Boolean, default: false },
  isDark: { type: Boolean, default: true },
})

const toggleSidebar = inject('toggleSidebar')
const toggleTheme = inject('toggleTheme')
const showThemePicker = inject('showThemePicker')

const authStore = usePlatformAuthStore()
const notifStore = usePlatformNotificationsStore()

const { primaryItems, accountItems, adminItems, isActive } = usePlatformNav()

onMounted(() => { notifStore.startPolling(30000) })
onUnmounted(() => { notifStore.stopPolling() })

const userSubtitle = computed(() =>
  authStore.user?.company_name || authStore.user?.email || 'Portal ProjectApp',
)

const sidebarActionClass = computed(() => [
  'flex h-8 w-8 items-center justify-center rounded-lg text-green-light transition',
  'hover:bg-primary-soft hover:text-text-brand',
  'dark:hover:bg-surface/[0.06] dark:hover:text-white',
])

</script>
