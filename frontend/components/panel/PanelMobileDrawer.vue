<template>
  <Teleport to="body">
    <Transition name="drawer-overlay">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm panel-landscape:hidden"
        @click="$emit('close')"
      />
    </Transition>
    <Transition name="drawer-slide">
      <aside
        v-if="isOpen"
        ref="drawerRef"
        tabindex="-1"
        role="dialog"
        aria-modal="true"
        aria-label="Menú principal"
        :class="[
          'fixed inset-y-0 left-0 z-50 flex w-[min(280px,calc(100vw-32px))] flex-col border-r panel-landscape:hidden focus:outline-none',
          'border-border-muted bg-surface',
        ]"
      >
        <div class="flex h-16 shrink-0 items-center justify-between border-b border-border-muted px-5">
          <span class="text-xl font-bold tracking-tight text-text-default">
            Project<span class="text-text-brand">App.</span>
          </span>
          <BaseActionButton action="close" label="Cerrar menú" size="md" @click="$emit('close')" />
        </div>

        <nav class="flex-1 overflow-y-auto px-3 py-4">
          <div
            v-for="section in sections"
            :key="section.id"
            class="mb-5"
          >
            <p
              class="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest"
              :class="section.muted ? 'text-green-light/40 dark:text-text-subtle/60' : 'text-green-light/60 dark:text-text-subtle/80'"
            >
              {{ section.label }}
            </p>
            <template
              v-for="(item, idx) in section.items"
              :key="item.divider ? `div-${section.id}-${idx}` : item.href + item.label"
            >
              <div
                v-if="item.divider"
                aria-hidden="true"
                class="my-2 mx-3 h-px bg-border-muted"
              />
              <SidebarItem
                wrap-label
                v-else
                :item="item"
                :is-collapsed="false"
                :is-active="isItemActive(item)"
                :disabled="item.disabled"
              />
            </template>
          </div>
        </nav>

        <div class="shrink-0 border-t border-border-muted p-4">
          <div class="mb-3 flex items-center gap-2">
            <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-text-brand">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <p class="truncate text-xs text-green-light dark:text-text-muted">Internal admin</p>
          </div>

          <BaseButton variant="secondary" size="md" class="w-full" :disabled="isBridging" @click="goToPlatform('/platform/dashboard')">
            <BaseActionIcon action="open-platform" />
            {{ isBridging ? 'Abriendo...' : 'Plataforma' }}
          </BaseButton>

          <PanelPwaInstallButton class="mt-2" @install="$emit('close')" />

          <BaseButton variant="secondary" size="md" class="mt-2 w-full" @click="$emit('close'); $emit('toggle-theme')">
            <BaseActionIcon :action="isDark ? 'enable-light-theme' : 'enable-dark-theme'" />
            {{ isDark ? 'Modo claro' : 'Modo oscuro' }}
          </BaseButton>
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, toRef, watch } from 'vue'
import { getPanelNavSections } from '~/config/panelNav'
import { isPanelNavItemActive } from '~/utils/panelNavActive'
import { usePanelToPlatformBridge } from '~/composables/usePanelToPlatformBridge'
import { useProposalStore } from '~/stores/proposals'
import SidebarItem from '~/components/platform/SidebarItem.vue'
import PanelPwaInstallButton from '~/components/pwa/PanelPwaInstallButton.vue'
import { useFocusTrap } from '~/composables/useFocusTrap'

const emit = defineEmits(['close', 'toggle-theme'])

const { goToPlatform, isBridging } = usePanelToPlatformBridge()

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  isDark: { type: Boolean, default: false },
})

const drawerRef = ref(null)
useFocusTrap(drawerRef, { active: toRef(props, 'isOpen') })

function onKeydown(event) {
  if (event.key === 'Escape' && props.isOpen) emit('close')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (typeof document !== 'undefined') document.body.style.overflow = ''
})

watch(
  () => props.isOpen,
  (open) => {
    if (typeof document !== 'undefined') document.body.style.overflow = open ? 'hidden' : ''
  },
  { immediate: true },
)

const localePath = useLocalePath()
const route = useRoute()

const proposalStore = useProposalStore()
const sections = computed(() =>
  getPanelNavSections(localePath, {
    includeSuperuserOnly: proposalStore.isSuperuser,
  }),
)

function isItemActive(item) {
  return isPanelNavItemActive(route.path, item)
}
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
