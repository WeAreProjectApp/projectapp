<template>
  <Teleport to="body">
    <Transition name="drawer-overlay">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
        @click="$emit('close')"
      />
    </Transition>
    <Transition name="drawer-slide">
      <aside
        v-if="isOpen"
        :class="[
          'fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r md:hidden',
          'border-input-border/[0.06] bg-surface dark:border-white/[0.06] dark:bg-primary-strong',
        ]"
      >
        <!-- Header -->
        <div class="flex h-16 shrink-0 items-center justify-between border-b border-input-border/[0.06] px-5 dark:border-white/[0.06]">
          <div class="flex items-center gap-3">
            <span class="text-xl font-bold tracking-tight text-text-brand dark:text-white">
              Project<span class="text-text-brand dark:text-accent">App.</span>
            </span>
          </div>
          <BaseButton
            unstyled
            icon-only
            type="button"
            aria-label="Cerrar navegación"
            class="flex h-9 w-9 items-center justify-center rounded-full text-green-light transition hover:bg-primary-soft hover:text-text-brand dark:hover:bg-surface/[0.06] dark:hover:text-white"
            @click="$emit('close')"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </BaseButton>
        </div>

        <!-- Navigation (reuse sidebar items) -->
        <nav class="flex-1 overflow-y-auto px-3 py-4">
          <div class="mb-5">
            <p class="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-green-light/60">Navegación</p>
            <SidebarItem
              v-for="item in primaryItems"
              :key="item.href"
              :item="item"
              :is-collapsed="false"
              :is-active="isActive(item.href)"
              :disabled="item.disabled"
              @click="$emit('close')"
            />
          </div>

          <div class="mb-5">
            <p class="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-green-light/60">Cuenta</p>
            <SidebarItem
              v-for="item in accountItems"
              :key="item.href"
              :item="item"
              :is-collapsed="false"
              :is-active="isActive(item.href)"
              :disabled="item.disabled"
              @click="$emit('close')"
            />
            <PlatformHelpMenu />
            <BaseButton variant="secondary" size="md" class="w-full" @click="$emit('close'); $emit('openThemePicker')">
              <svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="13.5" cy="6.5" r="2.5" /><circle cx="17.5" cy="10.5" r="2.5" /><circle cx="8.5" cy="7.5" r="2.5" /><circle cx="6.5" cy="12.5" r="2.5" />
                <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 011.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
              </svg>
              <span class="truncate">Personaliza</span>
            </BaseButton>
          </div>

          <div v-if="authStore.isAdmin" class="mb-5">
            <p class="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-green-light/60">Administración</p>
            <SidebarItem
              v-for="item in adminItems"
              :key="item.href"
              :item="item"
              :is-collapsed="false"
              :is-active="isActive(item.href)"
              :disabled="item.disabled"
              @click="$emit('close')"
            />
          </div>
        </nav>

        <!-- User footer -->
        <div class="shrink-0 border-t border-input-border/[0.06] p-4 dark:border-white/[0.06]">
          <div class="flex items-center gap-3 rounded-xl p-2">
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
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-text-brand dark:text-white">{{ authStore.displayName }}</p>
              <p class="truncate text-xs text-green-light">{{ userSubtitle }}</p>
            </div>
          </div>

          <div class="mt-2 flex items-center gap-1">
            <!-- Theme customization -->
            <BaseButton
              unstyled
              icon-only
              type="button"
              aria-label="Personalizar apariencia"
              class="flex h-9 w-9 items-center justify-center rounded-lg text-green-light transition hover:bg-primary-soft hover:text-text-brand dark:hover:bg-surface/[0.06] dark:hover:text-white"
              @click="$emit('close'); $emit('openThemePicker')"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="13.5" cy="6.5" r="2.5" />
                <circle cx="17.5" cy="10.5" r="2.5" />
                <circle cx="8.5" cy="7.5" r="2.5" />
                <circle cx="6.5" cy="12.5" r="2.5" />
                <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 011.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
              </svg>
            </BaseButton>

            <BaseButton variant="ghost" size="md" class="ml-auto" @click="$emit('logout')">
              Salir
            </BaseButton>
          </div>
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>

<script setup>
import PlatformHelpMenu from '~/components/platform/PlatformHelpMenu.vue'
import { computed } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import SidebarItem from '~/components/platform/SidebarItem.vue'
import { usePlatformNav } from '~/composables/usePlatformNav'

defineEmits(['close', 'logout', 'toggleTheme', 'openThemePicker'])

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  isDark: { type: Boolean, default: true },
})

const authStore = usePlatformAuthStore()

const { primaryItems, accountItems, adminItems, isActive } = usePlatformNav()

const userSubtitle = computed(() =>
  authStore.user?.company_name || authStore.user?.email || 'Portal ProjectApp',
)
</script>

<style scoped>
.drawer-overlay-enter-active,
.drawer-overlay-leave-active {
  transition: opacity 0.25s ease;
}
.drawer-overlay-enter-from,
.drawer-overlay-leave-to {
  opacity: 0;
}

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(-100%);
}
</style>
