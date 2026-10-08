<script setup>
import LegalRichText from '~/components/legal/LegalRichText.vue'
import LegalList from '~/components/legal/LegalList.vue'
import LegalFooter from '~/components/legal/LegalFooter.vue'

// Generic renderer for the Waiter legal documents. The copy lives in
// locales/waiter/*.js as { title, last_updated, notice?, intro?, sections }
// where each section holds ordered blocks: p, h3, ul, ol, table or note.
defineProps({
  doc: { type: Object, required: true },
  backLabel: { type: String, default: '' },
  backTo: { type: String, default: '/waiter' },
})

const localePath = useLocalePath()
</script>

<template>
  <div class="min-h-screen bg-surface-muted">
    <main class="w-full px-4 pb-16 pt-28 sm:px-6 lg:px-32 lg:pt-32">
      <article class="mx-auto max-w-4xl" data-testid="legal-document">
        <h1 class="mb-4 text-4xl font-bold text-text-brand lg:text-6xl">
          {{ doc.title }}
        </h1>
        <p v-if="doc.last_updated" class="mb-8 text-sm font-light text-text-muted">
          {{ doc.last_updated }}
        </p>
        <p
          v-if="doc.notice"
          class="mb-10 rounded-2xl border border-border-default bg-surface px-5 py-4 text-sm font-light leading-relaxed text-text-brand"
          data-testid="legal-document-notice"
        >
          <LegalRichText :text="doc.notice" />
        </p>
        <p
          v-for="(paragraph, idx) in doc.intro || []"
          :key="`intro-${idx}`"
          class="mb-6 text-lg font-light leading-relaxed text-text-brand lg:text-xl"
        >
          <LegalRichText :text="paragraph" />
        </p>

        <section
          v-for="(section, sIdx) in doc.sections || []"
          :id="section.id"
          :key="section.id || sIdx"
          class="mb-10 scroll-mt-28"
        >
          <h2 v-if="section.title" class="mb-4 text-2xl font-bold text-text-brand lg:text-3xl">
            {{ section.title }}
          </h2>
          <template v-for="(block, bIdx) in section.blocks || []" :key="bIdx">
            <h3 v-if="block.h3" class="mb-3 mt-6 text-xl font-medium text-text-brand lg:text-2xl">
              {{ block.h3 }}
            </h3>
            <p v-else-if="block.p" class="mb-4 text-base font-light leading-relaxed text-text-brand lg:text-lg">
              <LegalRichText :text="block.p" />
            </p>
            <p
              v-else-if="block.note"
              class="mb-4 border-s-4 border-accent ps-4 text-base font-light leading-relaxed text-text-brand lg:text-lg"
            >
              <LegalRichText :text="block.note" />
            </p>
            <LegalList v-else-if="block.ul" :items="block.ul" class="mb-4" />
            <LegalList v-else-if="block.ol" :items="block.ol" ordered class="mb-4" />
            <div
              v-else-if="block.table"
              class="mb-4 overflow-x-auto rounded-2xl border border-border-default bg-surface"
            >
              <table class="w-full min-w-[32rem] text-left text-sm text-text-brand lg:text-base">
                <thead class="border-b border-border-default">
                  <tr>
                    <th
                      v-for="(head, hIdx) in block.table.head"
                      :key="hIdx"
                      scope="col"
                      class="px-4 py-3 font-semibold"
                    >
                      {{ head }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, rIdx) in block.table.rows"
                    :key="rIdx"
                    class="border-b border-border-muted last:border-b-0"
                  >
                    <td
                      v-for="(cell, cIdx) in row"
                      :key="cIdx"
                      class="px-4 py-3 align-top font-light leading-relaxed"
                    >
                      <LegalRichText :text="cell" />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </section>

        <div class="mt-16 border-t border-border-default pt-8">
          <NuxtLink
            :to="localePath(backTo)"
            class="inline-flex items-center text-lg font-medium text-text-brand hover:opacity-80"
          >
            <span class="me-2" aria-hidden="true">&larr;</span>
            {{ backLabel }}
          </NuxtLink>
        </div>
      </article>
    </main>
    <LegalFooter />
  </div>
</template>
