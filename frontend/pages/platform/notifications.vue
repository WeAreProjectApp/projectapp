<template>
  <div id="platform-notifications">
    <!-- Header -->
    <div class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between" data-enter>
      <div>
        <h1 class="text-2xl font-bold text-text-default">Notificaciones</h1>
        <p class="mt-1 text-sm text-green-light">
          {{ notifStore.unreadCount > 0 ? `${notifStore.unreadCount} sin leer` : 'Todo al día' }}
        </p>
      </div>
      <div class="flex items-center gap-3">
        <BaseButton variant="secondary" size="sm" v-if="notifStore.unreadCount > 0" @click="handleMarkAllRead">
          Marcar todas como leídas
        </BaseButton>
        <div class="flex gap-1.5">
          <button
            v-for="tab in filterTabs"
            :key="tab.value"
            type="button"
            class="rounded-full px-3.5 py-1.5 text-xs font-medium transition"
            :class="activeFilter === tab.value
              ? 'bg-primary text-white dark:bg-accent dark:text-text-default'
              : 'text-green-light hover:bg-surface-muted/50 dark:hover:bg-white/10'"
            @click="activeFilter = tab.value"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="notifStore.isLoading" class="py-20 text-center">
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
    </div>

    <!-- Empty -->
    <div v-else-if="filteredNotifications.length === 0" class="py-16 text-center" data-enter>
      <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-muted/50 dark:bg-white/5">
        <svg class="h-8 w-8 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
      </div>
      <p class="text-sm text-green-light">
        {{ activeFilter === 'all' ? 'No tienes notificaciones.' : activeFilter === 'unread' ? 'No tienes notificaciones sin leer.' : 'No tienes notificaciones leídas.' }}
      </p>
    </div>

    <!-- List -->
    <div v-else class="space-y-2" data-enter>
      <div
        v-for="notif in filteredNotifications"
        :key="notif.id"
        class="group flex cursor-pointer items-start gap-4 rounded-2xl border p-4 transition"
        :class="notif.is_read
          ? 'border-border-muted bg-surface hover:border-border-default  dark:hover:border-white/10'
          : 'border-border-default bg-surface-muted/30 hover:border-border-default dark:bg-white/5 dark:hover:border-white/15'"
        @click="handleNotifClick(notif)"
      >
        <!-- Icon -->
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" :class="typeIconBg(notif.type)">
          <svg class="h-5 w-5" :class="typeIconColor(notif.type)" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <template v-if="notif.type === 'bug_reported' || notif.type === 'bug_status_changed'">
              <path d="M8 2l1.88 1.88M14.12 3.88L16 2M9 7.13v-1a3.003 3.003 0 116 0v1" />
              <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 014-4h4a4 4 0 014 4v3c0 3.3-2.7 6-6 6z" />
              <path d="M12 20v-9M6.53 9C4.6 8.8 3 7.1 3 5M6 13H2M6 17l-4 1M17.47 9c1.93-.2 3.53-1.9 3.53-4M18 13h4M18 17l4 1" />
            </template>
            <template v-else-if="notif.type === 'cr_created' || notif.type === 'cr_status_changed'">
              <path d="M1 4v6h6" />
              <path d="M23 20v-6h-6" />
              <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" />
            </template>
            <template v-else-if="notif.type === 'cr_converted'">
              <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </template>
            <template v-else-if="notif.type === 'deliverable_uploaded' || notif.type === 'deliverable_new_version'">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14,2 14,8 20,8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </template>
            <template v-else-if="notif.type === 'comment_added'">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
            </template>
            <template v-else>
              <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 01-3.46 0" />
            </template>
          </svg>
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <div class="flex items-start justify-between gap-2">
            <h4 class="text-sm font-medium" :class="notif.is_read ? 'text-green-light' : 'text-text-default'">
              {{ notif.title }}
            </h4>
            <span v-if="!notif.is_read" class="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent" />
          </div>
          <p v-if="notif.message" class="mt-0.5 text-xs text-green-light/70">{{ notif.message }}</p>
          <div class="mt-2 flex items-center gap-3 text-[10px] text-green-light/50">
            <span v-if="notif.project_name" class="font-medium">{{ notif.project_name }}</span>
            <span>{{ formatTimeAgo(notif.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformNotificationsStore } from '~/stores/platform-notifications'

definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
usePageEntrance('#platform-notifications')

const notifStore = usePlatformNotificationsStore()
const activeFilter = ref('all')

const filterTabs = [
  { value: 'all', label: 'Todas' },
  { value: 'unread', label: 'Sin leer' },
  { value: 'read', label: 'Leídas' },
]

const filteredNotifications = computed(() => {
  if (activeFilter.value === 'unread') return notifStore.unreadNotifications
  if (activeFilter.value === 'read') return notifStore.readNotifications
  return notifStore.notifications
})

function typeIconColor(type) {
  const map = {
    bug_reported: 'text-red-500', bug_status_changed: 'text-red-500',
    cr_created: 'text-amber-500', cr_status_changed: 'text-amber-500', cr_converted: 'text-emerald-500',
    deliverable_uploaded: 'text-purple-500', deliverable_new_version: 'text-purple-500',
    comment_added: 'text-blue-500', general: 'text-text-muted',
  }
  return map[type] || 'text-text-muted'
}

function typeIconBg(type) {
  const map = {
    bug_reported: 'bg-red-500/10', bug_status_changed: 'bg-red-500/10',
    cr_created: 'bg-amber-500/10', cr_status_changed: 'bg-amber-500/10', cr_converted: 'bg-emerald-500/10',
    deliverable_uploaded: 'bg-purple-500/10', deliverable_new_version: 'bg-purple-500/10',
    comment_added: 'bg-blue-500/10', general: 'bg-surface-raised',
  }
  return map[type] || 'bg-surface-raised'
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return ''
  const now = new Date()
  const d = new Date(dateStr)
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Ahora'
  if (diffMin < 60) return `Hace ${diffMin} min`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `Hace ${diffHours}h`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `Hace ${diffDays}d`
  return d.toLocaleDateString('es-CO', { day: '2-digit', month: 'short' })
}

const localePath = useLocalePath()

function getNotifRoute(notif) {
  if (!notif.project) return null
  const base = `/platform/projects/${notif.project}`
  if (notif.related_object_type === 'delivery_stage') return localePath(`${base}/delivery?stage=${notif.related_object_id}`)
  const typeRoutes = {
    bug_reported: '/bugs', bug_status_changed: '/bugs',
    cr_created: '/changes', cr_status_changed: '/changes', cr_converted: '/changes',
    delivery_published: '/delivery', delivery_reviewed: '/delivery', delivery_message: '/delivery',
    deliverable_uploaded: '/deliverables', deliverable_new_version: '/deliverables',
  }
  return localePath(base + (typeRoutes[notif.type] || ''))
}

async function handleNotifClick(notif) {
  if (!notif.is_read) {
    await notifStore.markRead(notif.id)
  }
  const route = getNotifRoute(notif)
  if (route) navigateTo(route)
}

async function handleMarkAllRead() {
  await notifStore.markAllRead()
}

onMounted(async () => {
  await notifStore.fetchNotifications()
  notifStore.fetchUnreadCount()
})

onUnmounted(() => {
  notifStore.stopPolling()
})
</script>
