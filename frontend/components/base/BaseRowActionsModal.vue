<script setup>
import { computed, nextTick, resolveComponent, shallowRef, watch } from 'vue'
import BaseActionIcon from './BaseActionIcon.vue'
import BaseButton from './BaseButton.vue'
import BaseModal from './BaseModal.vue'
import BaseModalActions from './BaseModalActions.vue'
import { getPanelAction } from '~/config/panelActions'

/**
 * The menu behind a list row's three-dot button.
 *
 * It takes the same entries as `BaseActionMenu` — `{ action, icon, label,
 * description, disabled, disabledReason, danger, divider, to, href, target,
 * testid, onClick }` — so a page that used the dropdown keeps its item builder
 * and its entry test ids. A modal rather than a dropdown: the lists scroll
 * inside an `overflow-x-auto` wrapper, which clips an absolutely positioned
 * menu on the last rows and on narrow screens.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  /** Test id of the menu body; each entry keeps its own `testid`. */
  testid: { type: String, required: true },
  /** Off when the menu opens above a modal that already locks the page. */
  lockScroll: { type: Boolean, default: true },
})

const emit = defineEmits(['close'])

// String names in <component :is> can't resolve Nuxt auto-imported components.
const NuxtLinkComponent = resolveComponent('NuxtLink')
const titleId = computed(() => `${props.testid}-title`)

// Owners clear the row on close; keep showing it while the modal fades out.
const shown = shallowRef({ title: props.title, subtitle: props.subtitle, items: props.items })
watch(
  () => [props.open, props.title, props.subtitle, props.items],
  () => {
    if (props.open) shown.value = { title: props.title, subtitle: props.subtitle, items: props.items }
  },
  { immediate: true },
)

function itemLabel(item) {
  if (item.label) return item.label
  return item.action ? getPanelAction(item.action).label : ''
}

function itemHint(item) {
  return item.description || (item.disabled && item.disabledReason) || ''
}

function hintId(index) {
  return `${props.testid}-entry-${index}-hint`
}

/** A disabled entry is always a disabled button: a dead link still navigates. */
function entryTag(item) {
  if (item.disabled) return 'button'
  if (item.href) return 'a'
  if (item.to) return NuxtLinkComponent
  return 'button'
}

function isLink(item) {
  return !item.disabled && Boolean(item.href || item.to)
}

/** Only the attributes of the element the entry renders as. */
function entryAttrs(item) {
  if (item.disabled) return { type: 'button', disabled: true }
  if (item.href) return { href: item.href, target: item.target || '_blank', rel: 'noopener noreferrer' }
  if (item.to) return { to: item.to }
  return { type: 'button' }
}

/**
 * Close first, act on the next tick. The owner opens the follow-up dialog
 * (confirmation, detail, form) from `onClick`; opening it in the same flush as
 * this close made the two dialogs trade focus traps and scroll locks. Links
 * only close: the router or the browser does the rest.
 */
async function choose(item, event) {
  if (item.disabled) return
  emit('close')
  if (isLink(item)) return
  await nextTick()
  item.onClick?.(event)
}
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="confirm"
    :title-id="titleId"
    :lock-scroll="lockScroll"
    @close="emit('close')"
  >
    <div :data-testid="testid">
      <header class="border-b border-border-muted px-6 pb-4 pt-6">
        <h3 :id="titleId" class="break-words text-base font-bold text-text-default">
          {{ shown.title }}
        </h3>
        <p v-if="shown.subtitle" class="mt-1 break-words text-sm text-text-muted">
          {{ shown.subtitle }}
        </p>
      </header>

      <ul class="py-2">
        <template v-for="(item, index) in shown.items" :key="index">
          <li v-if="item.divider" role="separator" class="my-2 border-t border-border-muted" />
          <li v-else>
            <component
              :is="entryTag(item)"
              v-bind="entryAttrs(item)"
              :aria-describedby="itemHint(item) ? hintId(index) : undefined"
              :data-testid="item.testid || undefined"
              class="flex min-h-11 w-full items-start gap-3 px-6 py-3 text-left text-sm transition-colors"
              :class="[
                item.danger
                  ? 'text-danger-strong hover:bg-danger-soft'
                  : 'text-text-default hover:bg-surface-raised',
                item.disabled ? 'cursor-not-allowed opacity-50' : '',
              ]"
              @click="choose(item, $event)"
            >
              <BaseActionIcon v-if="item.action" :action="item.action" class="mt-0.5" />
              <component :is="item.icon" v-else-if="item.icon" class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span class="min-w-0">
                <span class="block">{{ itemLabel(item) }}</span>
                <span
                  v-if="itemHint(item)"
                  :id="hintId(index)"
                  class="mt-0.5 block text-xs text-text-subtle"
                >{{ itemHint(item) }}</span>
              </span>
            </component>
          </li>
        </template>
      </ul>
    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton variant="secondary" @click="emit('close')">Cerrar</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
