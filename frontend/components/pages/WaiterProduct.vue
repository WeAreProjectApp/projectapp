<template>
  <div class="min-h-screen bg-surface-muted">
    <main class="w-full px-4 pb-16 pt-28 sm:px-6 lg:px-32 lg:pt-32">
      <div class="mx-auto max-w-5xl">
        <!-- Intro -->
        <header class="max-w-3xl">
          <p class="mb-3 text-sm font-medium uppercase tracking-wide text-text-muted">
            {{ product.eyebrow }}
          </p>
          <h1 class="text-5xl font-bold text-text-brand lg:text-7xl">
            {{ product.title || 'Waiter' }}
          </h1>
          <p class="mt-4 text-2xl font-light leading-snug text-text-brand lg:text-3xl">
            {{ product.tagline }}
          </p>
          <p class="mt-6 text-base font-light leading-relaxed text-text-brand lg:text-lg">
            {{ product.intro }}
          </p>
          <div class="mt-8 flex flex-wrap items-center gap-3">
            <BaseButton as="NuxtLink" :to="localePath('/contact')" variant="primary" size="md" data-testid="waiter-cta-contact">
              {{ product.cta_contact }}
            </BaseButton>
            <BaseButton as="NuxtLink" :to="localePath(R.privacy)" variant="secondary" size="md">
              {{ product.cta_privacy }}
            </BaseButton>
          </div>
        </header>

        <!-- Features -->
        <section class="mt-16 grid gap-4 md:grid-cols-3" aria-label="Waiter">
          <article
            v-for="(feature, idx) in product.features || []"
            :key="idx"
            class="rounded-3xl border border-border-default bg-surface p-6 lg:p-8"
          >
            <h2 class="text-xl font-bold leading-tight text-text-brand lg:text-2xl">
              {{ feature.title }}
            </h2>
            <p class="mt-3 text-base font-light leading-relaxed text-text-brand">
              {{ feature.text }}
            </p>
          </article>
        </section>

        <!-- WhatsApp connection steps -->
        <section class="mt-16" aria-labelledby="waiter-steps-title">
          <h2 id="waiter-steps-title" class="text-3xl font-bold text-text-brand lg:text-4xl">
            {{ product.steps_title }}
          </h2>
          <ol class="mt-8 grid gap-4 md:grid-cols-2">
            <li
              v-for="(step, idx) in product.steps || []"
              :key="idx"
              class="flex gap-4 rounded-3xl bg-surface p-6"
            >
              <span
                class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-accent text-lg font-bold text-black"
                aria-hidden="true"
              >
                {{ idx + 1 }}
              </span>
              <p class="text-base font-light leading-relaxed text-text-brand lg:text-lg">{{ step }}</p>
            </li>
          </ol>
          <p class="mt-6 text-base font-light leading-relaxed text-text-muted">
            {{ product.steps_note }}
          </p>
        </section>

        <!-- Data ownership -->
        <section class="mt-16 rounded-3xl bg-primary p-8 text-on-primary lg:p-12" aria-labelledby="waiter-data-title">
          <h2 id="waiter-data-title" class="text-2xl font-bold lg:text-3xl">
            {{ product.data_title }}
          </h2>
          <p class="mt-4 max-w-3xl text-base font-light leading-relaxed lg:text-lg [&_a]:text-on-primary">
            <LegalRichText :text="product.data_text || ''" />
          </p>
          <BaseButton
            as="NuxtLink"
            :to="localePath('/contact')"
            variant="accent"
            size="md"
            class="mt-8"
          >
            {{ product.cta_contact }}
          </BaseButton>
        </section>
      </div>
    </main>
    <LegalFooter />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import BaseButton from '~/components/base/BaseButton.vue'
import LegalRichText from '~/components/legal/LegalRichText.vue'
import LegalFooter from '~/components/legal/LegalFooter.vue'
import { useMessages } from '~/composables/useMessages'
import { WAITER_LEGAL_ROUTES as R } from '~/config/legalEntity'

const localePath = useLocalePath()
const { messages } = useMessages('waiter')
const product = computed(() => messages.value?.product || {})
</script>
