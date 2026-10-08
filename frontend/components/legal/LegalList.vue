<script setup>
import LegalRichText from '~/components/legal/LegalRichText.vue'

// Items are strings or { text, items } for one nested level (the privacy
// policy lists data categories with their fields underneath).
defineProps({
  items: { type: Array, default: () => [] },
  ordered: { type: Boolean, default: false },
  nested: { type: Boolean, default: false },
})
</script>

<template>
  <component
    :is="ordered ? 'ol' : 'ul'"
    :class="[
      ordered ? 'list-decimal' : (nested ? 'list-[circle]' : 'list-disc'),
      nested ? 'mt-2 space-y-1 ps-6' : 'space-y-2 ps-6',
    ]"
  >
    <li
      v-for="(item, idx) in items"
      :key="idx"
      class="text-base font-light leading-relaxed text-text-brand lg:text-lg"
    >
      <LegalRichText :text="typeof item === 'string' ? item : item.text" />
      <LegalList v-if="item?.items?.length" :items="item.items" nested />
    </li>
  </component>
</template>
