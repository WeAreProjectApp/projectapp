<template>
  <a
    v-if="!disabled && item.external"
    :href="item.href"
    :target="item.openInNewTab ? '_blank' : undefined"
    :rel="item.openInNewTab ? 'noopener noreferrer' : undefined"
    :class="itemClasses"
    :title="isCollapsed ? item.label : undefined"
  >
    <SidebarIcon :name="item.icon" class="h-5 w-5 shrink-0" />
    <span v-if="!isCollapsed" class="truncate">{{ item.label }}</span>
  </a>
  <NuxtLink
    v-else-if="!disabled"
    :to="item.href"
    :data-tour="item.tourTarget"
    :class="itemClasses"
    :title="isCollapsed ? item.label : undefined"
    :aria-current="isActive ? 'page' : undefined"
  >
    <SidebarIcon :name="item.icon" class="h-5 w-5 shrink-0" />
    <span v-if="!isCollapsed" class="truncate">{{ item.label }}</span>
    <span
      v-if="!isCollapsed && item.badge"
      class="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500/15 px-1.5 text-[10px] font-semibold text-red-400"
    >
      {{ item.badge }}
    </span>
  </NuxtLink>
  <div
    v-else
    :class="[itemClasses, 'cursor-default opacity-40']"
    :title="isCollapsed ? `${item.label} (próximamente)` : undefined"
  >
    <SidebarIcon :name="item.icon" class="h-5 w-5 shrink-0" />
    <span v-if="!isCollapsed" class="truncate">{{ item.label }}</span>
    <span
      v-if="!isCollapsed"
      class="ml-auto text-[9px] font-medium uppercase tracking-wider text-green-light/40 dark:text-text-subtle/70"
    >
      pronto
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SidebarIcon from '~/components/platform/SidebarIcon.vue'

const props = defineProps({
  item: { type: Object, required: true },
  isCollapsed: { type: Boolean, default: false },
  isActive: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const itemClasses = computed(() => [
  'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150',
  props.isCollapsed ? 'justify-center' : '',
  props.isActive && !props.disabled
    ? 'bg-primary text-white dark:bg-white/10 dark:text-white'
    : 'text-green-light dark:text-text-muted hover:bg-primary-soft hover:text-text-brand dark:hover:bg-surface/[0.06] dark:hover:text-white',
])
</script>
