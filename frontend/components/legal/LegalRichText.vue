<script setup>
import { computed, h, resolveComponent } from 'vue'

// Renders the small inline markup used by the legal copy without v-html:
// **bold**, `code` and [label](href). Internal hrefs (starting with "/")
// become locale-aware NuxtLinks; mailto:, tel: and http(s) stay anchors.
const props = defineProps({
  text: { type: String, default: '' },
})

const localePath = useLocalePath()
const NuxtLink = resolveComponent('NuxtLink')

const SPLIT = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/
const LINK = /^\[([^\]]+)\]\(([^)\s]+)\)$/
const SAFE_EXTERNAL = /^(https?:|mailto:|tel:)/

const linkClass = 'font-medium text-text-brand underline underline-offset-2 hover:opacity-80'

function renderPart(part, key) {
  if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) {
    return h('strong', { key, class: 'font-semibold' }, part.slice(2, -2))
  }
  if (part.length > 2 && part.startsWith('`') && part.endsWith('`')) {
    return h('code', { key, class: 'rounded bg-surface px-1 py-0.5 text-[0.9em]' }, part.slice(1, -1))
  }
  const link = part.match(LINK)
  if (!link) return part
  const [, label, href] = link
  if (href.startsWith('/')) {
    return h(NuxtLink, { key, to: localePath(href), class: linkClass }, () => label)
  }
  if (!SAFE_EXTERNAL.test(href)) return label
  const external = href.startsWith('http')
  return h('a', {
    key,
    href,
    class: linkClass,
    ...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {}),
  }, label)
}

const nodes = computed(() =>
  props.text.split(SPLIT).filter(Boolean).map(renderPart),
)

const RichText = () => nodes.value
</script>

<template>
  <RichText />
</template>
