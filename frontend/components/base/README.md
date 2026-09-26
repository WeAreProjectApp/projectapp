# Base Components & Design Tokens

A thin design-system layer for ProjectApp's frontend. Components in this folder
wrap native HTML elements with semantic theme tokens so dark mode resolves
automatically — no `dark:` variants needed in consumer markup.

## Tokens

Defined in `frontend/assets/styles/theme.css` and exposed as Tailwind colors
(`frontend/tailwind.config.js`). Values flip with the `.dark` class on `<html>`
(toggled by `useDiagnosticDarkMode`).

| Token (Tailwind class)            | Use for                                  |
| --------------------------------- | ---------------------------------------- |
| `bg-surface`                      | primary card / panel background          |
| `bg-surface-muted`                | soft container (page-level wash)         |
| `bg-surface-raised`               | inner panels, chips, segmented controls  |
| `border-border-default`           | default border color                     |
| `border-border-muted`             | subtle dividers                          |
| `text-text-default`               | body / heading text                      |
| `text-text-muted`                 | labels, secondary copy                   |
| `text-text-subtle`                | placeholders, very faint copy            |
| `text-text-brand`                 | brand-tinted legends/headings (flips light/dark) |
| `bg-primary` / `text-primary`     | brand primary (esmerald — constant)      |
| `bg-accent`                       | brand accent (lemon — constant)          |
| `bg-input-bg` / `text-input-text` | form control fill / text                 |
| `border-input-border`             | form control border                      |
| `placeholder-input-placeholder`   | form control placeholder color           |
| `ring-focus-ring`                 | focus ring                               |
| `text-on-primary`                 | foreground (text/icon) on `bg-primary`   |
| `text-on-danger`                  | foreground (text/icon) on `bg-danger-strong` |
| `bg-success-soft / text-success-strong`, `warning-*`, `danger-*`, `info-*` | status pairs |

The legacy hex tokens (`esmerald`, `lemon`, `bone`, `gray-*`, etc.) keep working
unchanged. New work should prefer semantic tokens.

## Element-role contract

The normative map from UI role to canonical classes. One class set per role —
tokens flip automatically, so following this table standardizes light AND dark
at once. `/panel/styleguide` renders each row as its executable spec.

| Role | Canonical classes |
| --- | --- |
| Page wash | `bg-surface-muted` (the layout paints it; pages don't repaint) |
| Card / panel | `bg-surface border border-border-default rounded-xl shadow-card` |
| Raised chip / inner panel / table header | `bg-surface-raised` |
| Row / list hover | `hover:bg-surface-raised` (never `hover:bg-gray-*`) |
| Table borders / dividers | `border-border-muted`, `divide-border-muted` |
| Modal panel | `bg-surface border border-border-default rounded-2xl shadow-overlay` |
| Modal backdrop | `bg-black/50` in both modes (`BaseModal` is the reference) |
| Dropdown / popover / floating button | `bg-surface border border-border-default shadow-raised` |
| Tooltip | `bg-primary-strong text-white` (never `bg-gray-900`) |
| Empty state | `BaseEmptyState` or `bg-surface-raised text-text-muted` |
| Row that leads to a detail | `<BaseRowLink :to>` on the title cell (`relative` on the `<td>` + `stretch`), and the row's own `@click` routed through `useRowNavigation` |

### Navigable rows

**Si una fila lleva a un detalle, el detalle tiene dirección y la fila la
publica en un `<a href>`.**

1. **Dirección primero.** No hay fila navegable sin URL. Ruta propia si el
   detalle es una pantalla (`/panel/x/{id}/edit`); parámetro sobre la vista
   actual (`?income=123`) si el detalle es un modal.
2. **El título es el enlace.** `<BaseRowLink :to>` en la celda del título,
   estirado a *su* celda (`relative` en el `<td>` + `stretch`). Nunca sobre el
   `<tr>` entero: taparía la casilla, el kebab y los selectores de la fila, y
   se llevaría por delante la selección de texto.
3. **Botón lo que actúa, enlace lo que va.** Un `<a>` nunca envuelve `<td>`s ni
   contiene un `<button>`.
4. **El clic de fila es un atajo, no la navegación.** Pasa siempre por
   `useRowNavigation`, que decide según de dónde nació el clic y qué teclas hay
   pulsadas. Escuchá también `@auxclick.middle`: la rueda no dispara `click`.
5. **Cero `ctrlKey` en las pantallas.** El único archivo que lee modificadores
   es `utils/rowNavigation.js`. Si ramificás por `ctrlKey`/`metaKey` en una
   página, estás reimplementando un `<a>` — y sólo uno de los cinco gestos.
6. **El menú de la fila trae «Abrir en pestaña nueva»** como
   `<a target="_blank" rel="noopener noreferrer">` con el mismo href, no un
   botón que llame a `window.open`. En una pantalla táctil es la única vía.
7. **Los controles van antes del contenido.** Cuando la acción es un único
   kebab, la fila usa Checkbox → Acciones → Identidad. La celda del menú detiene
   `click`/`auxclick` para no activar la fila, pero no cancela el movimiento
   táctil que permite desplazar horizontalmente la tabla.

Cuando el clic simple no puede ser el del navegador — entrar a una carpeta pasa
por el store, y en plena búsqueda significa otra cosa — el enlace igual existe
por los gestos, y la página se queda el clic simple con `isPlainActivation`.

Nunca escribas `<component :is="'NuxtLink'">`: Nuxt resuelve los componentes en
compilación, así que un nombre en string se renderiza como el elemento
desconocido `<nuxtlink>`, con `to` en vez de `href` y sin navegar. Usá la
etiqueta estática, o `resolveComponent('NuxtLink')` si el tag es dinámico.

Los cinco gestos a probar en cada listado: clic simple, ctrl/cmd + clic, clic
con la rueda, clic derecho → «abrir en pestaña nueva», y copiar la dirección.

### Status color convention

All status UI routes through the paired tokens — components never pick raw
Tailwind hues or write their own dark alphas (the token bakes the dark alpha):

| Semantic | Absorbs (legacy drift) | Soft chip/badge | Strong text/icon |
| --- | --- | --- | --- |
| success | `green-*`, `emerald-*`, `teal-*` | `bg-success-soft` | `text-success-strong` |
| warning | `amber-*`, `yellow-*` | `bg-warning-soft` | `text-warning-strong` |
| danger | `red-*`, `rose-*` | `bg-danger-soft` | `text-danger-strong` |
| info | informational `blue-*` | `bg-info-soft` | `text-info-strong` |

Soft chips carry no status border by default; alert boxes may use
`border-success-strong/30` etc. (`*-strong` tokens are solid, so `/N` is safe).

### Elevation scale

Three shadows only, bound to CSS vars that strengthen in dark mode
(`--shadow-card/raised/overlay` in `theme.css`):

- `shadow-card` — cards / panels at rest
- `shadow-raised` — dropdowns, popovers, floating buttons, sticky bars
- `shadow-overlay` — modals and drawers

Any surface that relies on shadow for separation must also carry
`border border-border-default`: in dark mode shadows fade against the wash and
the border keeps the edge readable. Don't stack heavier shadows (`shadow-2xl`)
on nested cards.

### `dark:` variant policy

- **Panel:** prefer tokens; `dark:` only for genuinely mode-specific design
  (rare — leave a comment). Never a `dark:` gray.
- **Public proposal (`components/BusinessProposal/`, non-admin):** `dark:` is
  forbidden and non-functional — the viewer toggles `data-theme="dark"` on a
  wrapper, which `darkMode: 'class'` never matches. Use tokens, or scoped
  `[data-theme="dark"]` CSS for genuinely bespoke looks.

### Opacity modifiers

Semantic tokens are wired through an RGB-triplet bridge
(`rgb(var(--color-X-rgb) / <alpha-value>)`), so Tailwind opacity modifiers
work on every semantic color. Examples:

```html
<div class="bg-primary/40 text-text-brand/60 ring-focus-ring/30" />
<button class="bg-accent/80 hover:bg-accent" />
<span class="border border-border-default/50" />
```

**Caveat — dark-mode tokens with intrinsic alpha.** `surface-raised`,
`border-default`, `border-muted`, `input-border`, and the status `*-soft`
variants are intrinsically `rgba(...)` in dark mode. Their triplet variables
fall back to the underlying solid hue, so an opacity modifier in dark mode
*replaces* the baked alpha rather than composing with it — the result is
unlikely to match design intent.

Recommendation: use opacity modifiers on the "solid" tokens (`primary*`,
`accent*`, `text-*`, `input-text`, `focus-ring`, status `*-strong`,
light-mode soft backgrounds). For the alpha-baked tokens listed above,
prefer the bare class without `/N`.

## Components

| Component       | Props                                                                                  |
| --------------- | -------------------------------------------------------------------------------------- |
| `BaseInput`     | `modelValue`, `type`, `size` (`sm`/`md`), `error`, `placeholder`, `disabled`, `disabledReason` |
| `BaseCurrencyInput` | `modelValue` (Number/null), `decimals` (0 = COP; 2 allows a decimal comma), `size`, `error`, `placeholder`, `disabled` — money input that live-formats es-CO thousands (`1234567` → `1.234.567`) and emits the numeric value |
| `BaseSelect`    | `modelValue`, `options` (array or default slot), `size`, `error`, `placeholder`, `disabled`, `disabledReason` |
| `BaseTextarea`  | `modelValue`, `rows`, `size`, `error`, `placeholder`, `disabled`, `disabledReason` |
| `BaseButton`    | `variant` (`primary`/`secondary`/`ghost`/`danger`/`danger-ghost`/`link`/`accent`), `size` (`sm`/`md`/`lg`), `textPolicy` (`atomic` default / `wrap`), `loading`, `disabled`, `disabledReason`, `nativeTitle` (internal tooltip-owner escape hatch), `iconOnly`, `unstyled` (bespoke branded controls only), `as` — see [Button variants](#button-variants) |
| `BaseActionIcon` | `action` — renders the canonical 16 px Heroicons 24 Outline glyph from `config/panelActions.js`; consumers cannot replace it |
| `BaseActionButton` | `action`, `label`, `tooltip`, `statusLabel`, `statusTone` (`info`/`success`/`danger`), `variant`, `size`, `loading`, `disabled`, `disabledReason`, `as`, `to` — canonical icon-only action with one short viewport-aware hover/focus tooltip, no native duplicate, a separately contextual accessible name and visible transient status |
| `BaseControlGate` | `reasons`, `label`, `visible`, `reserveSpace`, `align`, `position` — complete visible + hover/focus/touch explanation around a native disabled control |
| `BaseBadge`     | `variant` (`neutral`/`success`/`warning`/`danger`/`info`/`accent`/`primary`), `size`, `textPolicy` (`atomic` default / `wrap`); status icon + label never separate |
| `BaseCard`      | `padding` (`none`/`sm`/`md`/`lg`), `as`                                                |
| `BaseModal`     | `modelValue`, `kind` (`confirm`/`form`/`form-wide`/`wizard`/`detail`/`workspace`; preferred), legacy `size`, `closeOnBackdrop`, `closeOnEsc`, `padding`, `fullHeight` — fullscreen below 640 px |
| `BaseFloatingListbox` | `open`, `anchor`, `owner`, `id`, `as`, `maxHeight`, `offset`, `viewportPadding` — portal de listbox que iguala el ancho del control, se voltea al lado con espacio y evita que un modal lo recorte |
| `BaseModalActions` | Responsive footer: full-width stacked actions below 640 px, right-aligned row above it |
| `BaseToggle`    | `modelValue`, `size` (`sm`/`md`), `disabled`, `disabledReason`, `ariaLabel`, `onClass` / `offClass` (override colors for status toggles, e.g. `on-class="bg-warning-strong"`) |
| `BaseCheckbox`  | `modelValue`, `value`, `disabled`, `disabledReason` — label via default slot |
| `BaseFormField` | `label`, `hint`, `error`, `required`, `for`, `size`, `standalone` — wrap any control in the default slot |
| `BaseFormRow`   | `cols` (`1`–`4`), `lg`, `gap`, `at`, `as`, `help`, `layout` (`equal`/`field-action`) — shared label/control/error bands plus group help; see [Form rows](#form-rows) |
| `BaseFormRowAction` | Companion action that occupies a `BaseFormRow` control band; use with `layout="field-action"` |
| `BaseSegmented` | `modelValue`, `options` (array of `{ value, label, testId?, disabled?, disabledReason? }` or strings), `size` (`sm`/`md`), `fullWidth`, `disabledReason` — atomic options; constrained groups reflow only between buttons |
| `BaseResponsiveTabs` | `modelValue`, `tabs` (array of `{ id, label, badge?, disabled?, disabledReason? }`), `variant` (`underline`/`pill`), `fullWidth`, `ariaLabel` — selector below 1024 px, wrapping strip from landscape up. `BaseTabs` remains as a compatibility alias |
| `BaseFilterTabs` | Saved-filter strip: same selector/strip breakpoint, wrapping, drag with touch delay, keyboard/menu reorder. `ProposalFilterTabs` remains as a compatibility alias |
| `BaseMobileTabSelect` | `modelValue`, `options` (array of `{ value, label, disabled? }`), `ariaLabel` (required), `testId`, `variant` (`nav`/`filter`) — hides from `panel-landscape` (1024 px), paired with `hidden panel-landscape:flex` |
| `BaseDropdown`  | `items` (array of `{ label, onClick?, to?, href?, testid?, icon?, disabled?, danger?, divider? }`), `align` (`left`/`right`), `width` — Headless UI Menu wrapper. Trigger via `#trigger` slot |
| `BaseActionMenu` | `items`, `label`, `disabled`, `placement`, `align`, `width`, `variant` — canonical row/action overflow menu |
| `BaseBulkActionBar` | `selectedCount`, `outsideCount`, `filteredCount`, `allFilteredSelected`, `actions`, `busy`, `testidPrefix`, `testid`; emits `clear`/`select-all` |
| `BaseResizeHandle` | Accessible, natively hinted vertical separator shared by panels and tables: pointer capture, Arrow/Home/End keyboard control and double-click reset |
| `BaseOverflowText` | `text`, `to`, `lines` (1/2), `stretch`, `expandable`, `testId`, `contentClasses`; measures real clipping (including after web-font readiness), adds one floating `BaseTooltip` only on overflow and exposes an in-place touch disclosure |
| `BaseResponsiveTable` | `columns`, `rows` plus legacy accounting-table props. Comparative tables declare explicit `responsive` `keep`/`group`/`hide` policy and exactly one `primary`; `textPolicy` is `wrap`/`truncate`/`atomic`; opt-in resizing uses `columnWidth` on every column plus `columnWidthsKey`; `rowActionsLayout="menu-start"` reserves a fixed leading kebab track (after selection) and sizes the data columns per viewport profile (auto layout below 1024 px, re-shared percentages from there up), while `inline-end` preserves loose-icon rows; supports `caption`, `testIdPrefix`, `rowClass` and custom-only actions |
| `BaseExploratoryList` | Exploratory CRUD list: one table from 1024 px and one stacked-card representation below it. Every column declares `mobile` as `primary`/`secondary`/`meta`/`hidden` and may opt into the same `textPolicy` contract |
| `BasePageShell` | `width` (`narrow`/`content`/`panel`/`full`), `as` — `panel` caps general content at 1400 px; the admin layout applies it globally |
| `BaseAlert`     | `variant` (`info`/`success`/`warning`/`danger`), `title`, `dismissible`. Icon via `#icon` slot, body via default slot |
| `BaseEmptyState` | `title`, `description`. Icon via `#icon`, custom body via default, CTA via `#actions` |
| `BaseTooltip`   | `position` (`top`/`bottom`/`left`/`right`), `backgroundColor`, `textColor`, `width`, `minWidth`, `rootClass`, `triggerClass`, `toggleOnClick`, `forceOpen`, `floating`, `viewportPadding`. Trigger via `#trigger`, body via default slot. `floating` teleports to `body`, flips/clamps inside the viewport and follows scroll/resize; `forceOpen` presents owned transient status without requiring hover/focus |

Components are auto-imported by Nuxt — use them directly in templates without
an explicit `import`.

### Panel action icons

Executable actions under `/panel/**` use an action key from
`config/panelActions.js`. The catalog is the only place that selects the icon
and default Spanish label, and every glyph comes from
`@heroicons/vue/24/outline`.

```vue
<BaseActionButton action="copy" label="Copiar enlace" @click="copyLink" />
<BaseActionIcon action="download" />
```

Use `BaseActionButton` for an icon-only control. It supplies one viewport-aware
hover/focus tooltip from the short catalog label and a separate accessible name
from `label`; it deliberately emits no native browser `title`. Pass `tooltip`
only when intentional visual copy should override the catalog label.
`statusLabel` forces that same tooltip visible and announces it; pair it with
`statusTone="success"` or `statusTone="danger"` when the action has a resolved
outcome. A verified copy success temporarily renders the canonical completion
check, then returns to the copy glyph when the status expires. Failed copies
keep the copy glyph available for retry.
Text buttons and menu items may render `BaseActionIcon` beside their visible
label. Do not import a Heroicon,
embed SVG, or use an emoji to represent an executable action. Run
`npm run check:panel-action-icons` to verify the contract. Informational,
decorative and content glyphs are outside the action vocabulary and need an
explicit guard comment when they appear inside a selectable row.

### Visible icon interaction contract

Every clickable icon across panel, platform and public views uses `BaseButton`
with `icon-only`, or `BaseActionButton` when the action belongs to the canonical
panel vocabulary. `BaseButton` owns the immediate 420 ms activation signal for
buttons and links: the glyph presses down 1 px, hops up at most 3 px with a
small scale overshoot, lands and settles without animating the control border.
Rapid clicks restart the hop. Pointer activation does not paint a focus ring;
the ring remains available through `focus-visible` for keyboard users. Coarse
pointers receive a minimum 44 px target; `prefers-reduced-motion` removes the
keyframes and briefly changes glyph contrast instead. Use `unstyled` only when
a branded control must retain bespoke chrome—the interaction, accessibility and
touch contract still remain active.

Immediate activation only confirms that the input was registered. Existing
`loading` state continues to represent pending asynchronous work. An outcome
that is not otherwise visible must use a nearby status; clipboard actions use
`useClipboardFeedback`, which exposes success for 2 seconds only after
`navigator.clipboard.writeText()` resolves and danger for 3 seconds when it
rejects. The owning screen still reports its actionable error through the
normal notification path.

Run `npm run check:icon-interaction-feedback` before delivery. The guard scans
application Vue files and rejects raw icon-only `button`, `a` and `NuxtLink`
controls unless an intentional custom exception is documented inline.

## Responsive panel contract

The source of truth shared by Tailwind, JavaScript and Playwright is
`config/responsive.js`. Do not introduce a breakpoint local to one screen.

| Profile | Range | Reference viewport | Canonical behavior |
| --- | ---: | ---: | --- |
| `compact` | `< 640px` | `412 × 915` | Drawer navigation, selectors for tabs/filters, stacked forms, fullscreen modal |
| `portrait` | `640–1023px` | `835 × 1195` | Same navigation/selectors, forms may use two columns, centered modal |
| `landscape` | `1024–1279px` | `1195 × 835` | Collapsed sidebar by default, wrapping strips, priority table may scroll |
| `desktop` | `1280–1919px` | `1440 × 900` | Expanded sidebar, all table columns available |
| `wide` | `≥ 1920px` | `2560 × 1440` | Same desktop behavior; `BasePageShell` stops general content at 1400 px |

### Table adoption

There is no automatic “least important” column. Every adopted table declares
what happens, and exactly one kept column owns grouped details:

```vue
<script setup>
const columns = [
  {
    key: 'project',
    label: 'Proyecto',
    responsive: {
      primary: true,
      compact: 'keep',
      portrait: 'keep',
      landscape: 'keep',
    },
  },
  {
    key: 'owner',
    label: 'Responsable',
    responsive: { compact: 'group', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'updated_at',
    label: 'Actualizado',
    format: 'date',
    responsive: { compact: 'hide', portrait: 'hide', landscape: 'hide' },
  },
]
</script>

<template>
  <BaseResponsiveTable :columns="columns" :rows="rows" />
</template>
```

- `keep`: remains a real column in that profile.
- `group`: disappears as a column and renders label/value beneath the primary
  cell, so the information stays reachable without horizontal hunting.
- `hide`: is intentionally absent at that profile.
- A table with no `responsive` declarations keeps the legacy horizontal-scroll
  behavior. A mixed declaration warns in development; partial automatic
  decisions are forbidden.

Every data-owned string also has an explicit containment policy. The default is
`wrap`: the inner value receives `min-w-0`, a bounded width and
`overflow-wrap:anywhere`, so an identifier without spaces cannot enlarge its
grid or table track. Use `truncate` only when the complete value is available
through a disclosure, tooltip or detail view. `atomic` is for bounded values
such as dates, money and percentages; it is inferred for those formats.

```js
const columns = [
  { key: 'name', label: 'Nombre' }, // wrap — safe default
  { key: 'reference', label: 'Referencia', textPolicy: 'truncate' },
  { key: 'amount', label: 'Total', format: 'money' }, // atomic
]
```

`break-words` alone is not the contract: it can leave a large intrinsic minimum
for strings without break opportunities. Custom slots and page-local flex/grid
wrappers must preserve `min-w-0` and `max-w-full`; badges and secondary metadata
belong on their own wrapping row when they would otherwise compete with a title.

Resizable tables opt in at the table contract, never with a page-local drag
handler. Every column declares `columnWidth`; the resizable track sets
`min/default/max/resizable`, fixed tracks set `fixed`, and flexible tracks set
the business order with `shrinkPriority`/`fillPriority`. `columnWidthsKey` is a
stable localStorage namespace. The chosen width is clamped and persisted, the
shared separator supports pointer and keyboard input, and double click removes
the preference. Donors reach their declared minima before the wrapper scrolls.

```vue
<BaseResponsiveTable
  :columns="[
    {
      key: 'name',
      label: 'Nombre',
      responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
      columnWidth: { min: 200, default: 280, max: 480, resizable: true },
    },
    {
      key: 'status',
      label: 'Estado',
      responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
      columnWidth: { min: 112, default: 112, max: 112, fixed: true },
    },
  ]"
  :rows="rows"
  :show-default-actions="false"
  row-actions-layout="menu-start"
  column-widths-key="projectapp-table-widths:example"
>
  <template #row-actions="{ row }">
    <BaseActionButton
      action="more"
      class="h-11 w-11 shrink-0"
      :label="`Acciones de ${row.name}`"
      @click.stop="actionsRow = row"
    />
  </template>
</BaseResponsiveTable>
```

`menu-start` is only for one overflow menu. It renders an accessible, visually
empty 56 px header/cell after the checkbox and before data, outside the
proportional width split. Pass `:show-default-actions="false"`: otherwise the
default Editar/Eliminar icons land next to the kebab and overflow the track.

Since 2026-09-26 this is the panel's row-actions standard, applied to every
accounting table and list: the kebab alone leads the row and opens an actions
modal (accounting uses `AccountingRowActionsModal` and
`AccountingRowActionsButton`) whose first entry is «Detalle e historial»,
followed by «Ver nota» when the record has a note. Nothing else sits beside the
kebab — a second button in the fixed 56 px track overflows onto the data. The
remaining `inline-end` tables outside accounting are pending migration.

A `<col>` is a column even when every cell under it is hidden, so a
`menu-start` table with a responsive policy emits `<col>` only for its control
tracks. Below 1024 px it uses auto layout with auto-width data columns (atomic
values keep their content width and the primary column takes the rest); from
1024 px it is fixed and each profile re-shares 100 % among the columns it
shows, with a landscape scroll floor that counts only those columns.

Exploratory CRUD lists use a different primitive because their mobile task is
scanning entities, not comparing columns. `BaseExploratoryList` renders only
one representation in the DOM and requires every field to declare its card
role explicitly:

```vue
<BaseExploratoryList :columns="[
  { key: 'name', label: 'Nombre', mobile: 'primary' },
  { key: 'status', label: 'Estado', mobile: 'secondary' },
  { key: 'internal_id', label: 'ID', mobile: 'hidden' },
]" :rows="rows">
  <template #row-actions="{ row }">
    <BaseActionMenu :items="actionsFor(row)" />
  </template>
</BaseExploratoryList>
```

### Tabs and filters

Use `BaseResponsiveTabs` for module sections and `BaseFilterTabs` for saved
filters. Both show a native selector below 1024 px and a wrapping strip above
it. Do not combine `overflow-hidden` with a one-line strip: it creates controls
that exist in the DOM but cannot be reached.

```vue
<BaseResponsiveTabs v-model="section" :tabs="sections" aria-label="Sección" />
<BaseFilterTabs :tabs="filters" :active-tab-id="filter" @select="filter = $event" />
```

### Modal and action adoption

Pick modal width by purpose, not a one-off pixel value. Put actions in
`BaseModalActions`; compact screens become fullscreen and stack the buttons in
document order.

| Kind | Maximum from 640 px | Purpose |
|---|---:|---|
| `confirm` | 28rem | Brief confirmation |
| `form` | 42rem | Simple / one-column form |
| `form-wide` | 64rem | Normal two-column form |
| `wizard` | 80rem | Multi-step assistant |
| `detail` | 64rem | Read-only detail |
| `workspace` | `min(90vw, 100rem)` | Preview or working surface |

```vue
<BaseModal v-model="open" kind="form">
  <div class="p-4 panel-portrait:p-6">…</div>
  <BaseModalActions>
    <BaseButton variant="ghost" @click="open = false">Cancelar</BaseButton>
    <BaseButton variant="primary" type="submit">Guardar</BaseButton>
  </BaseModalActions>
</BaseModal>
```

Use `BaseActionMenu` for row overflow and `BaseBulkActionBar` for selections;
do not lay an unbounded number of actions side by side. Accounting tables open
their row kebab into a modal instead (`AccountingRowActionsModal`): their
wrappers scroll horizontally and would clip a dropdown on the last rows. `BaseButton` and
`BaseDropdown` enforce a 44px target for coarse pointers.

Hover may enhance an action, never be the only way to discover it. A control
that is intentionally faded on mouse hover must also be keyboard-focusable and
carry `touch-reveal`; use `touch-target` for a non-BaseButton control that needs
the 44px coarse-pointer area.

### Form rows

Two fields side by side go in a `BaseFormRow`, never in a hand-written
`<div class="grid grid-cols-2 gap-3">`:

```vue
<BaseFormRow :cols="2" :gap="3">
  <BaseFormField label="NIT">…</BaseFormField>
  <BaseFormField label="Código de facturación">…</BaseFormField>
  <template #help>Estos datos aparecen en la cuenta de cobro.</template>
</BaseFormRow>
```

In a plain grid each column stacks on its own, so the taller label decides where
*its* control starts and the row comes out crooked — reliably, as soon as one
label wraps and the other does not. The row instead owns three shared bands
(label / control / error) that every field inherits through a subgrid, so each
band is as tall as the tallest cell and the controls line up. Explanatory help
is one block below the complete group; it never reserves an empty cell in the
other columns.

The semantic modal width prevents short labels from wrapping; the bands are the
safety net for genuinely long labels and validation errors. Short field labels
are atomic by default. A sentence-like label must opt into
`label-policy="wrap"` explicitly.

An action beside a field uses the control band too:

```vue
<BaseFormRow layout="field-action" help="Filtra por proyecto o incluye los que no tienen uno.">
  <BaseFormField label="Proyecto">…</BaseFormField>
  <BaseFormRowAction>
    <BaseButton variant="secondary">Sin proyecto</BaseButton>
  </BaseFormRowAction>
</BaseFormRow>
```

Notes:

- Below the breakpoint the fields stack in a single column, with no bands and
  no leftover reserved space.
- More fields than columns is fine — they wrap and each line aligns on its own.
- The fields must be **direct** children. A child that is not a field and should
  sit alongside them needs the bands too: `class="panel-portrait:row-span-3"` (plus
  `panel-portrait:col-span-2` to span the full width).
- A `BaseFormField` nested in a component may still align when that component's
  root is the field and remains a direct DOM child. Otherwise pass `standalone`.
- Hints inside aligned fields are intentionally not rendered: move that copy to
  the row's `help` prop or `#help` slot.

Live demo: `/panel/styleguide`, section 4.

### Modals that hold a workspace, not a form

By default the `BaseModal` panel is fullscreen below 640 px, then grows to its
content and scrolls as a whole (`panel-portrait:max-h-[90vh] overflow-y-auto`) — right for every form modal. A modal that
embeds documents (an email preview, a PDF, a diff) needs the opposite: pass
`full-height` and the panel becomes a fixed non-scrolling 90vh flex column, so
the slot can pin its own header/footer and let each pane scroll independently.
Nesting a panel scrollbar around scrollbars the embedded documents already
bring is what makes neither of them readable. Pair it with `size="full"`
only for legacy consumers; new work uses `kind="workspace"` (~90vw, capped at
1600px) when the content needs the width — see
`components/accounting/CollectionAccountFormModal.vue`.

## Button variants

Every button in the app is a `BaseButton`. Never hand-write button chrome
(`px-4 py-2 rounded-lg bg-…`) on a raw `<button>`: that is how the app ended up
with 43 different visual treatments for "delete" alone.

**Each kind of action maps to exactly one variant.** Pick by what the action
*is*, not by how prominent you want it to look:

| Action                                              | Variant        | Reads as                                  |
| --------------------------------------------------- | -------------- | ----------------------------------------- |
| Primary action (Guardar, Crear, Enviar, Confirmar)   | `primary`      | filled brand green                        |
| Secondary action (Duplicar, Exportar, Filtrar)       | `secondary`    | bordered, surface background              |
| Tertiary / Cancelar / Cerrar                         | `ghost`        | transparent, tint on hover                |
| Destructive **confirmed** (modal footer, confirm CTA)| `danger`       | filled red                                |
| Destructive **inline** (row trash icon, quitar ítem) | `danger-ghost` | red text, soft red wash on hover          |
| Text action inside prose or a list header            | `link`         | brand-coloured text, underline on hover   |
| Accent CTA — client platform, public site            | `accent`       | filled accent                             |

`accent` is not decoration: `pages/platform/**` uses accent-yellow as its
*primary* CTA, the way the panel uses `primary` green. Keep that split —
migrating a platform CTA to `primary` repaints the client-facing app.

A soft tint (`bg-primary-soft`) is low-emphasis chrome, so it maps to
`secondary`, not `primary`: promoting it changes the visual hierarchy of the
screen it lives on.

The destructive split is the one that matters: a filled red button in every
table row screams; a bare red word in a modal footer disappears. Confirmed
destruction is `danger`, inline destruction is `danger-ghost`.

What decides the split is the shape of the trigger, not whether a dialog
follows: a destructive action that carries a **text label** and sits in a row
of buttons next to a primary CTA — a bulk-action bar, a detail header — is
`danger`, because `danger-ghost` next to a filled CTA reads as plain text
until you hover it. `danger-ghost` is for the icon in a table row.

Sizes: `sm` (dense — tables, chips) · `md` (default — modals, forms) · `lg`
(prominent CTA). States come for free: hover, focus ring, `disabled`
(60% opacity + `not-allowed`) and `loading` (spinner, implies disabled).

```html
<BaseButton variant="primary" :loading="saving" type="submit">Guardar</BaseButton>
<BaseButton variant="ghost" @click="close">Cancelar</BaseButton>
<BaseButton variant="danger" @click="confirmDelete">Eliminar</BaseButton>

<!-- inline delete: icon-only needs an aria-label, BaseButton warns in dev if it is missing -->
<BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar tarea" @click="remove">
  <TrashIcon class="w-4 h-4" />
</BaseButton>
```

`iconOnly` swaps the rectangular padding for square padding so the glyph stays
centred. `link` drops padding and radius entirely — it is text, not a pill.

Filled variants use the `on-primary` / `on-danger` foreground tokens, never
`text-white`: `--color-danger-strong` flips to a light red in dark mode, so
hardcoded white text is unreadable there.

## Border-radius scale

Stick to the same three values across the system:

- `rounded-md` — small (chips, compact inputs)
- `rounded-xl` — default (cards, inputs, buttons)
- `rounded-full` — pills, avatars, badges

## Migration example

Before:

```html
<input
  v-model="form.email"
  type="email"
  class="w-full px-4 py-2.5 border border-gray-200 dark:border-white/[0.08]
         dark:bg-esmerald-dark dark:text-white dark:placeholder:text-green-light/40
         rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500
         outline-none bg-white"
/>
```

After:

```html
<BaseInput v-model="form.email" type="email" />
```

Dark mode is handled by the `bg-input-bg` / `border-input-border` tokens that
the component uses internally.

## Platform tenant theming

When a tenant has a custom `theme_color`, `usePlatformCustomTheme.applyTheme()`
overrides `--color-primary`, `--color-primary-strong`, `--color-primary-soft`,
`--color-text-brand`, and `--color-focus-ring` on `documentElement`. Base
components automatically reflect the tenant's brand color without needing any
component-level changes. When the tenant clears the theme, the overrides are
removed and the defaults from `assets/styles/theme.css` take over again.

## UI components migrated to tokens

These live in `frontend/components/ui/` (separate from base) but already use semantic
tokens, so they pair cleanly with the base layer:

- `FilterToggleButton` — `open`, `count`. Active state uses `bg-primary text-white`,
  inactive uses `bg-surface text-text-muted border-border-default`.

(`ResponsiveTabs` and `Tooltip` were deprecated and removed — use `BaseTabs`
and `BaseTooltip` instead.)

## Lint guard

`scripts/check-design-tokens.mjs` scans for forbidden color literals
(`bg-white`, `bg-esmerald`, `dark:bg-gray-700`, `text-gray-700`,
`bg-emerald-600`, etc.) and prints what to use instead.

It also guards the navigable-row contract above:

- **`MANUAL_MODIFIER_NAVIGATION`** — `ctrlKey`/`metaKey` within eight lines of
  `window.open` / `router.push` / `navigateTo` / `location.href`. Gates always;
  `utils/rowNavigation.js` is the one exempt file.
- **`ROW_LINK_MISSING`** — a tag with both `v-for` and `@click` whose block
  holds no `<a>` / `<NuxtLink>` / `<BaseRowLink>`. Warn-only until
  `--strict-rows`. A row that only expands in place is not a destination: mark
  it `design-tokens: allow-clickable-row` on or above the tag.

```bash
npm --prefix frontend run check:design-tokens          # full repo, warn-only
npm --prefix frontend run check:design-tokens:panel    # admin panel scope only
npm --prefix frontend run check:design-tokens:strict   # exit 1 on any offense (CI / pre-commit)
npm --prefix frontend run check:design-tokens:rows     # panel + the navigable-row gate
node frontend/scripts/check-design-tokens.mjs --files path/to/file.vue   # focused check on touched files
```

The script accepts `--scope=panel|proposal-public|public|full` and `--quiet`
(summary only). `proposal-public` is the public business-proposal viewer
(`pages/proposal/` + non-admin `components/BusinessProposal/`) carved out of
`public` so it can graduate to a hard CI gate once its token migration lands.
The base components (`components/base/`), the styleguide page, and decorative
UI components (`AnimatedTestimonials`, `BackgroundGradientAnimation`) are
allowlisted.

When you migrate a tab or component to tokens, run
`check:design-tokens --scope=panel --quiet` before and after to track progress.

### CI gating policy

The `design-tokens-guard` job in `.github/workflows/ci.yml` enforces three
distinct checks on every PR:

- **Per-PR (touched files): hard gate.** Files changed in the PR are run
  through `--strict --files <touched>`. Any new offense in a touched file
  fails the build. This keeps the migration incremental for legacy code that
  the PR does not touch.
- **Panel scope: hard gate.** `--scope=panel --strict` runs against the full
  panel surface on every PR (not just touched files). Now that panel sits at
  0 offenses, this prevents regressions introduced by new components added
  under `components/panel/` or imported indirectly into the panel without
  being modified by the PR.
- **Public scope: hard gate.** `--scope=public --strict` runs against the
  full public surface (proposal viewer, blog, portfolio, landings) on every
  PR. The scope sits at 0 offenses; the `proposal-public` sub-scope exists
  for tracking the public proposal viewer's deeper token migration (the
  `:deep` override block reduction) independently.

## Migration policy

- New views and components: use base components and semantic tokens.
- Legacy code: migrate when you are already touching the file. Coexistence is
  fine — old hex tokens stay valid.

### Legacy hex tokens (deprecated)

`esmerald`, `esmerald-dark`, `esmerald-light`, `lemon`, `bone`, `brown`,
`window-black`, `green-light` and bare `black`/`dark` are kept in
`tailwind.config.js` as raw hex for backwards compatibility. They are heavily
used (~3000 across the public site, ~360 in the panel) and many use opacity
modifiers like `bg-esmerald/40` which the current var-based semantic tokens
do not support cleanly.

**Do not introduce new uses.** The lint guard flags them. They will be
folded into the semantic system (`bg-esmerald` → `bg-primary`, etc.) once
the panel offense count drops low enough to coordinate the migration without
visual regressions on the public site.
- For pilots already migrated, see:
  - `components/panel/defaults/ProposalDefaultsPanel.vue` (general tab)
  - `pages/panel/proposals/[id]/edit.vue` (general tab + activity)
  - `components/BusinessProposal/admin/ContractParamsModal.vue`

## Visual regression

The styleguide page (`/panel/styleguide`) has full-page Playwright screenshot
coverage in light and dark mode. The spec lives at
`frontend/e2e/visual/styleguide.spec.js` and its baseline PNGs at
`frontend/e2e/visual/styleguide.spec.js-snapshots/`.

The intent is to catch unintended pixel changes when tokens, base components,
or shared layout chrome are touched — not to lock the design forever.

Run the visual specs:

```bash
npm --prefix frontend run e2e -- e2e/visual/styleguide.spec.js
```

Regenerate baselines (only after an *intentional* design change):

```bash
npm --prefix frontend run e2e -- e2e/visual/styleguide.spec.js --update-snapshots
```

When to regenerate:

- Yes: you changed tokens in `assets/styles/theme.css`, edited a base
  component on purpose, or added a new section to `pages/panel/styleguide.vue`.
- No: a test went red after an unrelated refactor or "harmless" tweak —
  inspect the diff (`e2e-results/` HTML report) and fix the regression
  instead of overwriting the baseline.

The first CI run on a fresh checkout has no baseline and will write the
PNGs on the spot. Commit the generated PNGs together with the change that
produced them so reviewers can eyeball the new look.
