/**
 * Admin panel navigation: section definitions. Paths are i18n keys; resolve with localePath().
 * @param {(path: string) => string} localePath - Nuxt i18n localePath composable
 * @param {{ includeSuperuserOnly?: boolean }} [options] - pass the viewer's
 *   superuser flag to hide gated sections; defaults to including everything
 *   (label lookups in the admin layout need the full list).
 * @returns {Array<{ id: string, label: string, muted?: boolean, superuserOnly?: boolean, items: Array<NavItem> }>}
 */

/**
 * @typedef {Object} NavItem
 * @property {string} label
 * @property {string} href - Resolved URL (pass through localePath)
 * @property {string} icon - SidebarIcon name
 * @property {boolean} [matchExact] - Only exact path match (e.g. dashboard)
 * @property {boolean} [external] - Use <a> instead of NuxtLink
 * @property {boolean} [openInNewTab]
 * @property {boolean} [superuserOnly] - Hide this single item from non-superusers
 *   (for a link into a superuser-gated page inside an otherwise open section)
 */

export function getPanelNavSections(localePath, { includeSuperuserOnly = true } = {}) {
  const lp = localePath
  const sections = [
    {
      id: 'overview',
      label: 'General',
      items: [
        {
          label: 'Dashboard',
          href: lp('/panel'),
          icon: 'dashboard',
          matchExact: true,
        },
      ],
    },
    {
      id: 'tasks',
      label: 'Tareas',
      items: [
        { label: 'Kanban', href: lp('/panel/tasks'), icon: 'board' },
      ],
    },
    {
      id: 'commercial',
      label: 'Comercial',
      items: [
        { label: 'Defaults', href: lp('/panel/defaults'), icon: 'settings' },
        { label: 'Paquetes de horas', href: lp('/panel/hour-packages'), icon: 'package' },
        { label: 'Clientes', href: lp('/panel/clients'), icon: 'users' },
        { label: 'Entregabilidad email', href: lp('/panel/proposals/email-deliverability'), icon: 'mail' },
        { label: 'Propuestas', href: lp('/panel/proposals'), icon: 'money-bag' },
        { label: 'Nueva propuesta', href: lp('/panel/proposals/create'), icon: 'plus' },
        { label: 'Módulos adicionales', href: lp('/panel/additional-modules'), icon: 'puzzle' },
        { label: 'Programa de Alianza', href: lp('/panel/partnership-program'), icon: 'credit-card' },
        { divider: true },
        { label: 'Diagnósticos', href: lp('/panel/diagnostics'), icon: 'file' },
        { label: 'Nuevo diagnóstico', href: lp('/panel/diagnostics/create'), icon: 'plus' },
      ],
    },
    {
      id: 'site',
      label: 'Contenido ProjectApp',
      items: [
        { label: 'Blog', href: lp('/panel/blog'), icon: 'blog' },
        { label: 'Calendario del blog', href: lp('/panel/blog/calendar'), icon: 'calendar' },
        { label: 'Portafolio', href: lp('/panel/portfolio'), icon: 'portfolio' },
        { label: 'Tarjetas QR', href: lp('/panel/qr-cards'), icon: 'qrcode' },
        { label: 'Linktrees', href: lp('/panel/linktrees'), icon: 'link' },
        { label: 'LinkedIn', href: lp('/panel/linkedin'), icon: 'linkedin' },
      ],
    },
    {
      id: 'communications',
      label: 'Comunicaciones',
      items: [
        { label: 'Hilos con clientes', href: lp('/panel/communications'), icon: 'mail' },
        { label: 'Enviar emails', href: lp('/panel/emails'), icon: 'send' },
        { label: 'Enlaces seguros', href: lp('/panel/secure-links'), icon: 'key' },
      ],
    },
    {
      id: 'documents',
      label: 'Gestor Documental',
      items: [
        { label: 'Gestor Documental', href: lp('/panel/documents'), icon: 'file' },
      ],
    },
    {
      id: 'accounting',
      label: 'Contabilidad',
      superuserOnly: true,
      items: [
        { label: 'Resumen', href: lp('/panel/accounting'), icon: 'credit-card', matchExact: true },
        { label: 'Ingresos', href: lp('/panel/accounting/incomes'), icon: 'plus' },
        { label: 'Gastos', href: lp('/panel/accounting/expenses'), icon: 'file' },
        { label: 'Hostings', href: lp('/panel/accounting/hostings'), icon: 'database' },
        { label: 'Bolsillo', href: lp('/panel/accounting/pocket'), icon: 'folder' },
        { label: 'Recurrentes', href: lp('/panel/accounting/recurring'), icon: 'refresh' },
        { label: 'Cuentas de cobro', href: lp('/panel/accounting/collections'), icon: 'file' },
        { label: 'Tarjetas', href: lp('/panel/accounting/cards'), icon: 'credit-card' },
        { divider: true },
        { label: 'Historial', href: lp('/panel/accounting/history'), icon: 'calendar' },
        { label: 'Configuración', href: lp('/panel/accounting/settings'), icon: 'settings' },
      ],
    },
    {
      // After `accounting` on purpose: the Hostings entry below points at
      // the accounting page, and the breadcrumb resolver walks sections in
      // order — hostings must keep resolving under Contabilidad.
      id: 'platform',
      label: 'Plataforma',
      items: [
        { label: 'Proyectos', href: lp('/panel/projects'), icon: 'folder' },
        { label: 'Monitoreo', href: lp('/panel/monitoring'), icon: 'search' },
        // The same accounting view, doubled here deliberately: hostings are
        // also part of the delivered product. Item-level gate because the
        // target page is superuser-only while Proyectos is open to admins.
        {
          label: 'Hostings',
          href: lp('/panel/accounting/hostings'),
          icon: 'database',
          superuserOnly: true,
        },
      ],
    },
    {
      id: 'integrations',
      label: 'Integraciones',
      superuserOnly: true,
      items: [
        { label: 'MCPs', href: lp('/panel/mcps'), icon: 'settings' },
      ],
    },
    {
      id: 'reference',
      label: 'Referencia',
      items: [
        { label: 'Mapa de vistas', href: lp('/panel/views'), icon: 'sitemap' },
      ],
    },
    {
      id: 'system',
      label: 'Sistema',
      muted: true,
      items: [
        { label: 'Admins del panel', href: lp('/panel/admins'), icon: 'shield' },
        {
          label: 'Django Admin',
          href: '/admin/',
          icon: 'external',
          external: true,
          openInNewTab: true,
        },
        {
          label: 'Sitemap',
          href: '/sitemap.xml',
          icon: 'sitemap',
          external: true,
          openInNewTab: true,
        },
      ],
    },
  ]
  if (includeSuperuserOnly) return sections
  return sections
    .filter((section) => !section.superuserOnly)
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => !item.superuserOnly),
    }))
}
