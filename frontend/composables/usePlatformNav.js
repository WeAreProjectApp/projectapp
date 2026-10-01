import { computed } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformNotificationsStore } from '~/stores/platform-notifications'

/**
 * Fuente única de la navegación de la plataforma.
 *
 * El sidebar de desktop (`PlatformSidebar.vue`) y el drawer móvil
 * (`PlatformMobileDrawer.vue`) consumen estos mismos items para que ambas
 * superficies no vuelvan a desincronizarse, como pasó tras el refactor de IA
 * (los módulos globales Tablero/Solicitudes/Bugs/etc. ahora viven dentro de
 * cada proyecto y las rutas globales quedaron como redirects).
 */
export function usePlatformNav() {
  const localePath = useLocalePath()
  const { t } = useI18n()
  const route = useRoute()
  const authStore = usePlatformAuthStore()
  const notifStore = usePlatformNotificationsStore()
  const lp = (path) => localePath(path)

  const primaryItems = computed(() => {
    const items = [
      { label: 'Notificaciones', href: lp('/platform/notifications'), icon: 'bell', badge: notifStore.unreadCount },
      { label: 'Proyectos',      href: lp('/platform/projects'),      icon: 'folder' },
      { label: t('platformBilling.accounts'), href: lp('/platform/collection-accounts'), icon: 'file' },
      { label: t('platformBilling.hosting'), href: lp('/platform/payments'), icon: 'credit-card' },
    ]
    if (authStore.isClient) {
      // Client-facing document portal (view/download/sign). Admins use /panel/documents.
      items.push({ label: 'Documentos', href: lp('/platform/documents'), icon: 'file' })
    }
    if (authStore.isAdmin) {
      items.push({ label: 'Clientes', href: lp('/platform/clients'), icon: 'users' })
    }
    return items
  })

  const accountItems = computed(() => [
    { label: 'Configuración', href: lp('/platform/profile'), icon: 'settings' },
  ])

  const adminItems = computed(() => [
    { label: 'Panel admin', href: '/panel', icon: 'external', external: true },
  ])

  function isActive(href) {
    const cleanPath = route.path.replace(/^\/[a-z]{2}-[a-z]{2}/, '')
    const cleanHref = href.replace(/^\/[a-z]{2}-[a-z]{2}/, '')
    return cleanPath === cleanHref || cleanPath.startsWith(`${cleanHref}/`)
  }

  return { primaryItems, accountItems, adminItems, isActive }
}
