<script setup>
import { ref } from 'vue'
import { useDiagnosticDarkMode } from '~/composables/useDiagnosticDarkMode'
import { PANEL_ACTIONS } from '~/config/panelActions'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })

const { isDark, toggle } = useDiagnosticDarkMode()

// Demo state for components
const sampleText = ref('Texto de ejemplo')
const sampleNumber = ref(42)
const sampleSelect = ref('a')
const sampleTextarea = ref('Una nota corta\ncon dos líneas.')
const toggleA = ref(true)
const toggleB = ref(false)
const checkA = ref(false)
// BaseFormRow demo
const sampleRowA = ref('')
const sampleRowB = ref('')
const sampleRowC = ref('')
const sampleRowD = ref('')
const modalOpen = ref(false)
const modalLongContent = ref(false)
const workspaceModalOpen = ref(false)
const fieldError = ref(false)

const segmented = ref('editor')
const filterOpen = ref(false)
const filterCount = ref(2)
const baseTab = ref('a')
const alertVisible = ref(true)
const dropdownLog = ref('')
const collapseOpen = ref(false)
const responsiveTab = ref('overview')
const responsiveFilterTab = ref('all')
const responsiveBulkCount = ref(3)

const responsiveFilterTabs = ref([
  { id: 'pending', name: 'Pendientes de revisión', builtin: true },
  { id: 'negotiating', name: 'En negociación', builtin: true },
  { id: 'follow-up', name: 'Seguimiento comercial', builtin: true },
  { id: 'archived', name: 'Archivadas', builtin: true },
])

const responsiveTableColumns = [
  {
    key: 'project',
    label: 'Proyecto',
    size: 'name',
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
    columnWidth: { min: 176, default: 240, max: 400, resizable: true },
  },
  {
    key: 'owner',
    label: 'Responsable',
    responsive: { compact: 'group', portrait: 'keep', landscape: 'keep' },
    columnWidth: { min: 128, default: 160, max: 240, shrinkPriority: 2, fillPriority: 2 },
  },
  {
    key: 'amount',
    label: 'Valor',
    format: 'money',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
    columnWidth: { min: 144, default: 144, max: 144, fixed: true },
  },
  {
    key: 'updated',
    label: 'Actualizado',
    format: 'date',
    responsive: { compact: 'hide', portrait: 'hide', landscape: 'hide' },
    columnWidth: { min: 112, default: 128, max: 176, shrinkPriority: 1, fillPriority: 1 },
  },
  {
    key: 'status',
    label: 'Estado',
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
    columnWidth: { min: 112, default: 112, max: 640, shrinkPriority: 3, fillPriority: 3 },
  },
]

const responsiveTableRows = [
  {
    id: 1,
    project: 'Sitio institucional Aurora',
    owner: 'María Gómez',
    amount: 4250000,
    updated: '2026-08-20',
    status: 'En curso',
  },
  {
    id: 2,
    project: 'Portal de clientes Boreal',
    owner: 'Carlos Ruiz',
    amount: 7800000,
    updated: '2026-08-18',
    status: 'Revisión',
  },
]

const responsiveActions = [
  { action: 'edit', label: 'Editar selección', onClick: () => { dropdownLog.value = 'editar selección' } },
  { action: 'export', label: 'Exportar', onClick: () => { dropdownLog.value = 'exportar selección' } },
  { divider: true },
  { action: 'archive', label: 'Archivar', danger: true, onClick: () => { dropdownLog.value = 'archivar selección' } },
]

const tokenSwatches = [
  { group: 'Surface', items: ['bg-surface', 'bg-surface-muted', 'bg-surface-raised'] },
  { group: 'Border', items: ['border-border-default', 'border-border-muted'] },
  { group: 'Text', items: ['text-text-default', 'text-text-muted', 'text-text-subtle', 'text-text-brand'] },
  { group: 'Brand', items: ['bg-primary', 'bg-primary-strong', 'bg-primary-soft', 'bg-accent', 'bg-accent-soft'] },
  { group: 'Form', items: ['bg-input-bg', 'border-input-border', 'text-input-text', 'ring-focus-ring'] },
  {
    group: 'Status',
    items: [
      'bg-success-soft', 'text-success-strong',
      'bg-warning-soft', 'text-warning-strong',
      'bg-danger-soft', 'text-danger-strong',
      'bg-info-soft', 'text-info-strong',
    ],
  },
]

// Elevation contract: the only three shadows the UI uses. Surfaces that rely
// on shadow for separation must also carry border-border-default (in dark the
// shadow fades against the wash and the border keeps the edge readable).
const shadowScale = [
  { cls: 'shadow-card', role: 'Cards / paneles en reposo' },
  { cls: 'shadow-raised', role: 'Dropdowns, popovers, botones flotantes, sticky bars' },
  { cls: 'shadow-overlay', role: 'Modales y drawers' },
]

const canonicalActionEntries = Object.entries(PANEL_ACTIONS).map(([key, definition]) => ({
  key,
  ...definition,
}))
</script>

<template>
  <div class="space-y-10" data-testid="styleguide-page">
    <header class="flex flex-col items-start gap-4 panel-portrait:flex-row panel-portrait:justify-between">
      <div>
        <h1 class="text-panel-title font-light text-text-default">Design System — Styleguide</h1>
        <p class="text-sm text-text-muted mt-1">
          Catálogo visual de tokens y componentes base. Úsalo como referencia al construir vistas nuevas y para validar
          dark mode antes de publicar.
        </p>
      </div>
      <BaseButton variant="secondary" size="sm" @click="toggle">
        <BaseActionIcon :action="isDark ? 'enable-light-theme' : 'enable-dark-theme'" />
        {{ isDark ? 'Modo claro' : 'Modo oscuro' }}
      </BaseButton>
    </header>

    <!-- Tokens -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">1. Tokens</h2>
      <p class="text-sm text-text-muted">
        Cada chip muestra cómo resuelve el token en el modo activo. Cambia entre claro/oscuro arriba para verificar.
      </p>
      <div v-for="group in tokenSwatches" :key="group.group" class="space-y-2">
        <h3 class="text-xs font-semibold text-text-brand uppercase tracking-wider">{{ group.group }}</h3>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          <div
            v-for="cls in group.items"
            :key="cls"
            class="rounded-xl border border-border-muted p-3 bg-surface flex items-center gap-3"
          >
            <span
              class="block w-10 h-10 rounded-lg border border-border-muted"
              :class="cls.startsWith('text-') ? `${cls} flex items-center justify-center font-bold` : cls.startsWith('ring-') ? `ring-2 ${cls}` : cls"
            >
              <template v-if="cls.startsWith('text-')">Aa</template>
            </span>
            <code class="text-xs text-text-muted">{{ cls }}</code>
          </div>
        </div>
      </div>
    </section>

    <!-- Buttons -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">2. BaseButton</h2>
      <BaseCard padding="md">
        <div class="flex flex-wrap items-center gap-3">
          <BaseButton variant="primary">Primary</BaseButton>
          <BaseButton variant="secondary">Secondary</BaseButton>
          <BaseButton variant="ghost">Ghost</BaseButton>
          <BaseButton variant="danger">Danger</BaseButton>
          <BaseButton variant="danger-ghost">Danger ghost</BaseButton>
          <BaseButton variant="link">Link</BaseButton>
          <BaseButton variant="accent">Accent</BaseButton>
          <BaseButton variant="primary" loading>Loading</BaseButton>
          <BaseButton variant="primary" disabled disabled-reason="Ejemplo visual de un botón no disponible.">Disabled</BaseButton>
        </div>
        <div class="flex flex-wrap items-center gap-3 mt-4">
          <BaseButton size="sm">Small</BaseButton>
          <BaseButton size="md">Medium</BaseButton>
          <BaseButton size="lg">Large</BaseButton>
        </div>
        <!-- Icon-only: square padding, aria-label is required -->
        <div class="flex flex-wrap items-center gap-3 mt-4">
          <BaseActionButton action="close" size="sm" />
          <BaseActionButton action="delete" variant="danger-ghost" size="sm" />
          <BaseActionButton action="edit" variant="secondary" size="md" />
        </div>
        <p class="mt-4 text-xs text-text-muted">
          One variant per kind of action: <code>danger</code> for confirmed destruction
          (modal footer), <code>danger-ghost</code> for inline destruction (row trash).
          See <code>components/base/README.md</code> → Button variants.
        </p>
      </BaseCard>
    </section>

    <!-- Canonical action catalog -->
    <section class="space-y-4" aria-labelledby="canonical-actions-title">
      <div>
        <h2 id="canonical-actions-title" class="text-lg font-semibold text-text-default">
          2a. Catálogo canónico de acciones
        </h2>
        <p class="mt-1 text-sm text-text-muted">
          Un solo símbolo de Heroicons 24 Outline por acción. Cada botón expone el mismo nombre al cursor,
          al foco y al lector de pantalla.
        </p>
      </div>
      <BaseCard padding="md">
        <ul class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" role="list">
          <li
            v-for="entry in canonicalActionEntries"
            :key="entry.key"
            class="flex min-w-0 items-center gap-3 rounded-lg border border-border-muted bg-surface-muted p-2"
          >
            <BaseActionButton :action="entry.key" :label="entry.label" />
            <span class="min-w-0">
              <span class="block truncate text-sm font-medium text-text-default">{{ entry.label }}</span>
              <code class="block truncate text-xs text-text-muted">{{ entry.key }} · {{ entry.iconName }}</code>
            </span>
          </li>
        </ul>
      </BaseCard>
    </section>

    <!-- Badges -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">3. BaseBadge</h2>
      <BaseCard padding="md">
        <div class="flex flex-wrap items-center gap-2">
          <BaseBadge variant="neutral">Neutral</BaseBadge>
          <BaseBadge variant="primary">Primary</BaseBadge>
          <BaseBadge variant="accent">Accent</BaseBadge>
          <BaseBadge variant="success">Success</BaseBadge>
          <BaseBadge variant="warning">Warning</BaseBadge>
          <BaseBadge variant="danger">Danger</BaseBadge>
          <BaseBadge variant="info">Info</BaseBadge>
          <BaseBadge variant="success" size="sm">Small</BaseBadge>
          <BaseBadge variant="danger" size="sm" data-testid="sg-atomic-state-badge">
            <span aria-hidden="true">⚠</span>
            <span>Solucionar bug</span>
          </BaseBadge>
        </div>
      </BaseCard>
    </section>

    <!-- Form controls -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">4. Form controls</h2>
      <BaseCard padding="md">
        <BaseFormRow
          :cols="2"
          :gap="4"
          help="Texto: hint de ayuda. Textarea: soporta múltiples líneas."
        >
          <BaseFormField label="Texto" for="sg-text">
            <BaseInput id="sg-text" v-model="sampleText" placeholder="Escribe algo…" />
          </BaseFormField>
          <BaseFormField label="Número" required for="sg-num">
            <BaseInput id="sg-num" v-model.number="sampleNumber" type="number" min="0" />
          </BaseFormField>
          <BaseFormField
            label="Con error"
            :error="fieldError ? 'Este campo es obligatorio.' : ''"
            for="sg-err"
          >
            <BaseInput id="sg-err" v-model="sampleText" :error="fieldError" />
          </BaseFormField>
          <BaseFormField label="Select" for="sg-sel">
            <BaseSelect
              id="sg-sel"
              v-model="sampleSelect"
              :options="[
                { value: 'a', label: 'Opción A' },
                { value: 'b', label: 'Opción B' },
                { value: 'c', label: 'Opción C' },
              ]"
            />
          </BaseFormField>
          <BaseFormField label="Textarea" class="panel-portrait:col-span-2">
            <BaseTextarea v-model="sampleTextarea" :rows="3" />
          </BaseFormField>
          <!-- Not fields: they claim the three bands so they line up beside them. -->
          <div class="space-y-3 panel-portrait:row-span-3">
            <BaseCheckbox v-model="checkA">Acepto los términos</BaseCheckbox>
            <BaseCheckbox v-model="fieldError">Mostrar estado de error en el campo de arriba</BaseCheckbox>
          </div>
          <div class="space-y-3 panel-portrait:row-span-3">
            <div class="flex items-center gap-3">
              <BaseToggle v-model="toggleA" aria-label="Activar A" />
              <span class="text-sm text-text-default">Toggle A — {{ toggleA ? 'on' : 'off' }}</span>
            </div>
            <div class="flex items-center gap-3">
              <BaseToggle v-model="toggleB" size="sm" aria-label="Activar B" />
              <span class="text-sm text-text-default">Toggle B (sm) — {{ toggleB ? 'on' : 'off' }}</span>
            </div>
            <div class="flex items-center gap-3">
              <BaseToggle :model-value="false" disabled disabled-reason="Ejemplo visual de un interruptor no disponible." aria-label="Disabled" />
              <span class="text-sm text-text-muted">Toggle disabled</span>
            </div>
          </div>
        </BaseFormRow>
      </BaseCard>

      <!-- BaseFormRow: short UI labels stay atomic; its shared bands remain the
           safety net for explicitly long, sentence-like labels. -->
      <BaseCard padding="md">
        <h3 class="text-sm font-semibold text-text-default">BaseFormRow — bandas compartidas</h3>
        <p class="text-xs text-text-muted mt-1 mb-4">
          La fila comparte etiqueta, campo y error. La ayuda sale debajo del grupo completo;
          una acción compañera ocupa la banda del campo y nunca se centra contra todo el bloque.
        </p>

        <div class="max-w-2xl space-y-5" data-testid="styleguide-form-rows">
          <div class="space-y-2">
            <p class="text-xs text-text-muted">Etiquetas reales en una sola línea y ayuda del grupo</p>
            <BaseFormRow
              help="Estos datos se usan al emitir cuentas de cobro."
              help-testid="sg-row-help"
              data-testid="sg-row-atomic"
            >
              <BaseFormField label="C.C. / NIT">
                <BaseInput v-model="sampleRowA" data-testid="sg-row-one-a" />
              </BaseFormField>
              <BaseFormField label="Código de facturación">
                <BaseInput v-model="sampleRowB" data-testid="sg-row-one-b" />
              </BaseFormField>
            </BaseFormRow>
          </div>

          <div class="max-w-xs space-y-2">
            <p class="text-xs text-text-muted">Fallback: etiquetas de frase explícitamente envolventes</p>
            <BaseFormRow data-testid="sg-row-wrapped-fallback">
              <BaseFormField
                label="Nombre completo que aparecerá en la cuenta de cobro"
                label-policy="wrap"
              >
                <BaseInput v-model="sampleRowC" data-testid="sg-row-both-a" />
              </BaseFormField>
              <BaseFormField
                label="Correo destinatario que recibirá la cuenta de cobro"
                label-policy="wrap"
              >
                <BaseInput v-model="sampleRowD" data-testid="sg-row-both-b" />
              </BaseFormField>
            </BaseFormRow>
          </div>

          <div class="max-w-lg space-y-2">
            <p class="text-xs text-text-muted">Acción compañera alineada con el campo</p>
            <BaseFormRow
              layout="field-action"
              help="Filtra por un proyecto o incluye los documentos sin proyecto."
              data-testid="sg-row-action"
            >
              <BaseFormField label="Proyecto">
                <BaseInput v-model="sampleRowA" data-testid="sg-row-action-input" />
              </BaseFormField>
              <BaseFormRowAction>
                <BaseButton variant="secondary" data-testid="sg-row-action-button">
                  Sin proyecto
                </BaseButton>
              </BaseFormRowAction>
            </BaseFormRow>
          </div>
        </div>
      </BaseCard>
    </section>

    <!-- Card and surfaces -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">5. BaseCard / Surfaces</h2>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <BaseCard padding="md">
          <h3 class="text-sm font-semibold text-text-default">bg-surface</h3>
          <p class="text-xs text-text-muted mt-1">Tarjeta principal.</p>
        </BaseCard>
        <div class="rounded-xl border border-border-muted p-5 bg-surface-muted">
          <h3 class="text-sm font-semibold text-text-default">bg-surface-muted</h3>
          <p class="text-xs text-text-muted mt-1">Wash de fondo de página.</p>
        </div>
        <div class="rounded-xl border border-border-muted p-5 bg-surface-raised">
          <h3 class="text-sm font-semibold text-text-default">bg-surface-raised</h3>
          <p class="text-xs text-text-muted mt-1">Panel interior elevado.</p>
        </div>
      </div>
      <div class="pt-2">
        <h3 class="text-xs font-semibold text-text-brand uppercase tracking-wider mb-2">Elevación (escala de sombras)</h3>
        <p class="text-xs text-text-muted mb-3">
          Las únicas tres sombras del sistema. Toda superficie con sombra lleva también
          <code>border-border-default</code>: en dark la sombra se pierde contra el wash y el borde mantiene el contorno.
        </p>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-6 py-2">
          <div
            v-for="s in shadowScale"
            :key="s.cls"
            class="rounded-xl border border-border-default bg-surface p-5"
            :class="s.cls"
          >
            <code class="text-xs text-text-brand">{{ s.cls }}</code>
            <p class="text-xs text-text-muted mt-1">{{ s.role }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Segmented -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">6. BaseSegmented</h2>
      <BaseCard padding="md">
        <BaseSegmented
          v-model="segmented"
          class="max-w-xs"
          full-width
          :options="[
            { value: 'editor', label: 'Todos (9999)', testId: 'sg-segmented-all' },
            { value: 'json', label: 'Esperados (9999)', testId: 'sg-segmented-expected' },
            { value: 'preview', label: 'Líquidos (9999)', testId: 'sg-segmented-liquid' },
          ]"
          data-testid="sg-segmented-counts"
        />
        <p class="text-xs text-text-muted mt-3">Selección actual: <code>{{ segmented }}</code></p>
      </BaseCard>
    </section>

    <!-- Tabs -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">7. BaseResponsiveTabs</h2>
      <BaseCard padding="md">
        <p class="text-xs text-text-muted mb-3">Variant: underline (default)</p>
        <BaseResponsiveTabs
          v-model="baseTab"
          :tabs="[
            { id: 'a', label: 'General' },
            { id: 'b', label: 'Pendientes', badge: 4 },
            { id: 'c', label: 'Archivado', disabled: true, disabledReason: 'Ejemplo de una sección no disponible.' },
          ]"
        />
        <p class="text-xs text-text-muted mb-3">Variant: pill</p>
        <BaseResponsiveTabs
          v-model="baseTab"
          variant="pill"
          full-width
          :tabs="[
            { id: 'a', label: 'A' },
            { id: 'b', label: 'B' },
            { id: 'c', label: 'C' },
          ]"
        />
      </BaseCard>
    </section>

    <!-- Responsive foundations -->
    <section
      class="space-y-4"
      data-testid="responsive-foundations"
      aria-labelledby="responsive-foundations-title"
    >
      <div>
        <h2 id="responsive-foundations-title" class="text-panel-section font-semibold text-text-default">
          8. Fundamentos responsivos del panel
        </h2>
        <p class="mt-1 text-sm text-text-muted">
          Cambia el ancho del navegador: cada ejemplo usa el mismo contrato que las vistas de producto.
        </p>
        <p class="mt-2 text-xs font-semibold uppercase tracking-wider text-text-brand" data-testid="responsive-profile">
          Perfil activo:
          <span data-responsive-profile="compact" class="panel-portrait:hidden">compact · &lt;640</span>
          <span data-responsive-profile="portrait" class="hidden panel-portrait:inline panel-landscape:hidden">portrait · 640–1023</span>
          <span data-responsive-profile="landscape" class="hidden panel-landscape:inline panel-desktop:hidden">landscape · 1024–1279</span>
          <span data-responsive-profile="desktop" class="hidden panel-desktop:inline panel-wide:hidden">desktop · 1280–1919</span>
          <span data-responsive-profile="wide" class="hidden panel-wide:inline">wide · ≥1920</span>
        </p>
      </div>

      <BaseCard padding="md" data-testid="responsive-tabs-example">
        <h3 class="text-sm font-semibold text-text-default">Tabs de módulo</h3>
        <p class="mb-3 mt-1 text-xs text-text-muted">
          Selector nativo en compact/portrait; tira visible y reordenable desde landscape.
        </p>
        <BaseResponsiveTabs
          v-model="responsiveTab"
          aria-label="Sección de ejemplo"
          :tabs="[
            { id: 'overview', label: 'Resumen general' },
            { id: 'deliverables', label: 'Entregables pendientes', badge: 4 },
            { id: 'activity', label: 'Actividad reciente' },
            { id: 'settings', label: 'Configuración del módulo' },
          ]"
        />

        <h3 class="mt-2 text-sm font-semibold text-text-default">Filtros guardados</h3>
        <p class="mb-3 mt-1 text-xs text-text-muted">
          Mismo quiebre, wrap sin recortes y reordenamiento accesible por menú/teclado.
        </p>
        <BaseFilterTabs
          :tabs="responsiveFilterTabs"
          :active-tab-id="responsiveFilterTab"
          :is-tab-limit-reached="false"
          @select="responsiveFilterTab = $event"
        />
      </BaseCard>

      <BaseCard padding="none" data-testid="responsive-table-example">
        <div class="border-b border-border-muted px-4 py-3 panel-portrait:px-6">
          <h3 class="text-sm font-semibold text-text-default">Tabla con prioridad declarada</h3>
          <p class="mt-1 text-xs text-text-muted">
            Proyecto se ajusta desde su borde y se recuerda; doble clic restablece. Estado se conserva,
            responsable/valor se agrupan y actualizado se oculta hasta desktop.
          </p>
        </div>
        <div class="p-3 panel-portrait:p-4">
          <BaseResponsiveTable
            :columns="responsiveTableColumns"
            :rows="responsiveTableRows"
            :show-actions="false"
            column-widths-key="projectapp-table-widths:styleguide-responsive-table"
          />
        </div>
      </BaseCard>

      <BaseCard padding="md" data-testid="responsive-actions-example">
        <h3 class="text-sm font-semibold text-text-default">Acciones de fila y selección múltiple</h3>
        <p class="mt-1 text-xs text-text-muted">
          Un menú agrupa lo que no cabe; en táctil, botones e ítems mantienen un área mínima de 44 px.
        </p>
        <div class="mt-3 flex items-center gap-3">
          <BaseActionMenu :items="responsiveActions" label="Acciones de fila" />
          <span class="text-xs text-text-muted">Última acción: {{ dropdownLog || '—' }}</span>
        </div>
        <BaseBulkActionBar
          :selected-count="responsiveBulkCount"
          :outside-count="1"
          :filtered-count="8"
          :all-filtered-selected="false"
          :actions="responsiveActions"
          testid-prefix="styleguide"
          @clear="responsiveBulkCount = 0"
          @select-all="responsiveBulkCount = 8"
        />
      </BaseCard>
    </section>

    <!-- Alert + EmptyState -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">9. BaseAlert / BaseEmptyState</h2>
      <BaseCard padding="md">
        <div class="space-y-3">
          <BaseAlert v-if="alertVisible" variant="info" title="Información" dismissible @dismiss="alertVisible = false">
            Este es un alerta dismissible. Soporta título, body via slot y un dismiss button.
          </BaseAlert>
          <BaseAlert variant="success" title="Listo">Operación completada con éxito.</BaseAlert>
          <BaseAlert variant="warning">Aviso sin título — el body va en el slot default.</BaseAlert>
          <BaseAlert variant="danger" title="Error crítico">Algo salió mal.</BaseAlert>
        </div>
        <div class="mt-6">
          <BaseEmptyState title="Sin propuestas" description="Cuando crees tu primera propuesta aparecerá aquí.">
            <template #actions>
              <BaseButton variant="primary" size="md">Crear propuesta</BaseButton>
              <BaseButton variant="ghost" size="md">Ver demo</BaseButton>
            </template>
          </BaseEmptyState>
        </div>
      </BaseCard>
    </section>

    <!-- Dropdown -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">10. BaseDropdown</h2>
      <BaseCard padding="md">
        <BaseDropdown
          :items="[
            { action: 'edit', label: 'Editar', onClick: () => (dropdownLog = 'editar') },
            { action: 'duplicate', label: 'Duplicar', onClick: () => (dropdownLog = 'duplicar') },
            { divider: true },
            { action: 'archive', label: 'Archivar', onClick: () => (dropdownLog = 'archivar') },
            { action: 'delete', label: 'Eliminar', danger: true, onClick: () => (dropdownLog = 'eliminar') },
          ]"
        >
          <template #trigger>
            <BaseButton variant="secondary" size="md"><BaseActionIcon action="more" /> Acciones</BaseButton>
          </template>
        </BaseDropdown>
        <p class="text-xs text-text-muted mt-3">Última acción: <code>{{ dropdownLog || '—' }}</code></p>
      </BaseCard>
    </section>

    <!-- Existing UI components on tokens -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">11. UI components on tokens</h2>
      <BaseCard padding="md">
        <h3 class="text-sm font-semibold text-text-default mb-3">FilterToggleButton</h3>
        <div class="flex items-center gap-3">
          <UiFilterToggleButton :open="filterOpen" :count="filterCount" @click="filterOpen = !filterOpen" />
          <BaseButton variant="ghost" size="sm" @click="filterCount = (filterCount + 1) % 4">
            Cambiar count ({{ filterCount }})
          </BaseButton>
        </div>
      </BaseCard>
    </section>

    <!-- Modal -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">12. BaseModal</h2>
      <BaseCard padding="md">
        <div class="flex flex-wrap items-center gap-3">
          <BaseButton variant="primary" @click="modalLongContent = false; modalOpen = true">Abrir modal</BaseButton>
          <BaseButton variant="secondary" @click="modalLongContent = true; modalOpen = true">Abrir modal largo</BaseButton>
          <BaseButton variant="secondary" @click="workspaceModalOpen = true">
            Abrir modal full-height
          </BaseButton>
          <span class="text-xs text-text-muted">El modal cierra con backdrop o tecla Esc.</span>
        </div>
      </BaseCard>
      <BaseModal v-model="modalOpen" kind="form">
        <div class="space-y-4 p-4 panel-portrait:p-6">
          <h3 class="text-lg font-semibold text-text-default">Demo modal</h3>
          <p class="text-sm text-text-muted">
            Renderizado por <code>BaseModal</code> con tokens semánticos. Prueba abrirlo en light y dark.
          </p>
          <BaseFormField label="Campo dentro del modal">
            <BaseInput v-model="sampleText" />
          </BaseFormField>
          <div v-if="modalLongContent" class="space-y-4">
            <BaseFormField v-for="index in 16" :key="index" :label="`Observación ${index}`">
              <BaseTextarea :rows="3" :aria-label="`Observación ${index}`" />
            </BaseFormField>
          </div>
        </div>
        <template #footer>
          <BaseModalActions>
            <BaseButton variant="ghost" @click="modalOpen = false">Cancelar</BaseButton>
            <BaseButton variant="primary" @click="modalOpen = false">Aceptar</BaseButton>
          </BaseModalActions>
        </template>
      </BaseModal>

      <!-- size="full" + full-height: para modales que sostienen documentos
           (previsualizaciones, PDFs) en vez de un formulario. El panel no
           scrollea; cada columna trae su propio scroll. -->
      <BaseModal v-model="workspaceModalOpen" kind="workspace" full-height>
        <div class="shrink-0 px-6 pt-6 pb-3">
          <h3 class="text-lg font-semibold text-text-default">Modal de trabajo</h3>
          <p class="text-sm text-text-muted">
            Cabecera y pie fijos; el scroll vive en cada columna, no en el modal.
          </p>
        </div>
        <div class="flex-1 min-h-0 px-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div class="min-h-0 overflow-y-auto rounded-xl border border-border-default p-4">
            <p v-for="n in 40" :key="`l-${n}`" class="text-sm text-text-muted">
              Columna izquierda · línea {{ n }}
            </p>
          </div>
          <div class="min-h-0 overflow-y-auto rounded-xl border border-border-default p-4">
            <p v-for="n in 40" :key="`r-${n}`" class="text-sm text-text-muted">
              Columna derecha · línea {{ n }}
            </p>
          </div>
        </div>
        <template #footer>
          <BaseModalActions>
            <BaseButton variant="primary" @click="workspaceModalOpen = false">Cerrar</BaseButton>
          </BaseModalActions>
        </template>
      </BaseModal>
    </section>

    <!-- Tooltip -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">13. BaseTooltip</h2>
      <BaseCard padding="md">
        <div class="flex items-center gap-3">
          <BaseTooltip position="right" width="max-w-xs" min-width="min-w-[200px]">
            <template #trigger>
              <BaseButton variant="secondary" size="sm">Hover / tap</BaseButton>
            </template>
            Spec de tooltip: <code>bg-primary-strong</code> + <code>text-white</code> — oscuro de marca, legible sobre ambos washes.
          </BaseTooltip>
          <span class="text-xs text-text-muted">Mismo fondo en claro y oscuro; nunca <code>bg-gray-900</code>.</span>
        </div>
      </BaseCard>
    </section>

    <!-- Collapse + Skeleton -->
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">14. BaseCollapse / BaseSkeleton</h2>
      <BaseCard padding="md">
        <!-- panel-action-icons: allow-content-glyph — 0fr→1fr documents the demonstrated CSS transition. -->
        <button
          type="button"
          class="flex items-center gap-2 text-sm font-medium text-text-default focus:outline-none focus:ring-2 focus:ring-focus-ring/40 rounded-lg px-2 py-1"
          :aria-expanded="collapseOpen"
          aria-controls="styleguide-collapse"
          @click="collapseOpen = !collapseOpen"
        >
          <BaseActionIcon :action="collapseOpen ? 'collapse' : 'expand'" />
          Acordeón animado (grid 0fr→1fr, sin medir altura; se congela bajo reduced-motion)
        </button>
        <BaseCollapse id="styleguide-collapse" :open="collapseOpen">
          <p class="text-sm text-text-muted px-2 pt-2">
            El trigger vive en el consumidor y debe ser un <code>&lt;button aria-expanded aria-controls&gt;</code>.
            El cuerpo cerrado queda <code>inert</code> (fuera del orden de tabulación).
          </p>
        </BaseCollapse>
        <div class="mt-6 space-y-2 max-w-sm">
          <BaseSkeleton variant="line" class="w-3/4" />
          <BaseSkeleton variant="line" class="w-1/2" />
          <div class="flex items-center gap-3 mt-3">
            <BaseSkeleton variant="circle" />
            <BaseSkeleton variant="card" class="flex-1" />
          </div>
        </div>
      </BaseCard>
    </section>
  </div>
</template>
