<template>
  <div class="admin-layout min-h-screen bg-surface-muted transition-colors duration-200 dark:bg-primary-strong" :style="layoutStyle">
    <div class="hidden panel-landscape:block">
      <PanelSidebar
        :is-collapsed="isCollapsed"
        :is-dark="isDark"
        @toggle-theme="toggle"
      />
    </div>

    <div
      class="mobile-topbar sticky top-0 z-30 flex h-14 items-center justify-between border-b border-input-border px-4 panel-landscape:hidden"
      :class="isDark ? 'bg-primary-strong/95 backdrop-blur-xl' : 'bg-surface/90 backdrop-blur-xl'"
    >
      <BaseActionButton
        action="open-navigation"
        label="Abrir menú"
        tooltip-position="right"
        variant="secondary"
        size="md"
        class="h-11 w-11 rounded-full"
        @click="openMobile"
      />

      <span v-if="_panelViewLabel && route.path !== localePath('/panel')" class="text-sm font-medium text-text-brand dark:text-white truncate max-w-[180px]">
        {{ _panelViewLabel }}
      </span>
      <NuxtLink
        v-else
        :to="localePath('/panel')"
        class="text-base font-bold tracking-tight text-text-brand dark:text-white"
      >
        Project<span class="text-green-light dark:text-accent">App.</span>
      </NuxtLink>

      <BaseActionButton
        :action="isDark ? 'enable-light-theme' : 'enable-dark-theme'"
        :label="themeToggleLabel(isDark)"
        tooltip-position="left"
        variant="secondary"
        size="md"
        class="h-11 w-11 rounded-full"
        @click="toggle"
      />
    </div>

    <PanelMobileDrawer
      :is-open="isMobileOpen"
      :is-dark="isDark"
      @close="closeMobile"
      @toggle-theme="toggle"
    />

    <main
      :class="[
        'relative z-10 transition-all duration-300 ease-in-out',
        // pb clears the fixed refresh button (48px + bottom-6): without it
        // the last row of a table that just overflows the viewport ends up
        // under the FAB, which swallows its action clicks.
        'px-4 pt-6 pb-24 panel-portrait:px-6 panel-desktop:px-8',
        'panel-landscape:ml-[var(--panel-sidebar-width,240px)]',
        isResizing ? 'transition-none select-none' : '',
        'text-base text-text-default',
      ]"
    >
      <!--
        Oculta por debajo de `md`: en un celular el nombre de la vista ya
        aparece en la barra superior (que además es sticky, así que sobrevive al
        scroll) y otra vez en el título de la propia vista. La miga era la
        tercera copia del mismo dato, y el alto vertical es justo lo que se está
        tratando de devolverle al contenido. En escritorio no cambia nada.
      -->
      <div
        v-if="_panelSectionLabel && _panelViewLabel"
        data-testid="panel-breadcrumb"
        class="mb-5 hidden items-center gap-1.5 text-xs text-text-muted panel-landscape:flex"
      >
        <span>{{ _panelSectionLabel }}</span>
        <span aria-hidden="true" class="text-text-subtle">›</span>
        <span class="text-text-muted">{{ _panelViewLabel }}</span>
      </div>
      <BasePageShell width="panel">
        <PanelPwaHost />
        <slot />
      </BasePageShell>
    </main>

    <PanelRefreshButton
      v-if="refreshStore.hasHandler"
      :loading="refreshStore.isRefreshing"
      @click="refreshStore.trigger()"
    />

    <PanelNotificationHost />
  </div>
</template>

<script setup>
import { provide, watch, computed, onMounted, onUnmounted } from 'vue'
import { useDarkMode, themeToggleLabel } from '~/composables/useDarkMode'
import { usePanelSidebar } from '~/composables/usePanelSidebar'
import { getPanelNavSections } from '~/config/panelNav'
import { resolvePanelBreadcrumb } from '~/utils/panelBreadcrumbs'
import { usePanelRefreshStore } from '~/stores/panel_refresh'
import PanelSidebar from '~/components/panel/PanelSidebar.vue'
import PanelMobileDrawer from '~/components/panel/PanelMobileDrawer.vue'
import PanelRefreshButton from '~/components/panel/PanelRefreshButton.vue'
import PanelNotificationHost from '~/components/panel/PanelNotificationHost.vue'
import BasePageShell from '~/components/base/BasePageShell.vue'
import PanelPwaHost from '~/components/pwa/PanelPwaHost.vue'

const refreshStore = usePanelRefreshStore()

const localePath = useLocalePath()
const route = useRoute()
const { isDark, toggle } = useDarkMode()

const {
  isCollapsed,
  isMobileOpen,
  isResizing,
  layoutStyle,
  hydrate: hydratePanelSidebar,
  toggle: togglePanelSidebar,
  openMobile,
  closeMobile,
  setupResizeListener,
  cleanupResizeListener,
} = usePanelSidebar()

onMounted(() => {
  hydratePanelSidebar()
  setupResizeListener()
})

onUnmounted(() => {
  cleanupResizeListener()
})

provide('togglePanelSidebar', togglePanelSidebar)

watch(() => route.fullPath, () => {
  closeMobile()
})

const _panelBreadcrumb = computed(() =>
  resolvePanelBreadcrumb(route.path, getPanelNavSections(localePath)),
)
const _panelViewLabel = computed(() => _panelBreadcrumb.value?.label ?? null)
const _panelSectionLabel = computed(() => _panelBreadcrumb.value?.section ?? null)

useHead(() => ({
  title: _panelViewLabel.value ? `Project App (${_panelViewLabel.value})` : 'Project App',
}))
</script>
