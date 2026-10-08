<template>
  <section class="hero-frame relative px-3 pb-3 pt-20 sm:px-4 sm:pb-4 lg:px-6 lg:pb-6 lg:pt-24">
    <!-- Framed artwork: random light cover, margin + rounded corners -->
    <div
      class="relative flex min-h-[80vh] items-center overflow-hidden rounded-[2rem] bg-slate-100 lg:min-h-[85vh]"
    >
      <!-- Background: draggable, auto-panning artwork mosaic -->
      <HeroMosaicCarousel />
      <!-- Soft depth: keeps the glass edge readable over the mosaic.
           pointer-events-none so drags pass through to the mosaic underneath. -->
      <div class="pointer-events-none absolute inset-0 bg-gradient-to-tr from-black/20 via-transparent to-white/10" />

      <!-- Content: main copy (left) + benefit bubbles (bottom-right) -->
      <div class="pointer-events-none relative z-10 flex w-full flex-col gap-8 px-5 py-10 sm:px-8 lg:min-h-[85vh] lg:justify-end lg:px-14 lg:pt-16 lg:pb-10">
        <div class="hero-glass pointer-events-auto max-w-2xl rounded-3xl px-6 py-8 sm:px-10 sm:py-12 lg:px-12 lg:py-14">
          <div class="space-y-8 lg:space-y-10">
            <!-- Main Headline -->
            <h1 class="text-4xl font-bold leading-tight text-slate-900 sm:text-5xl xl:text-6xl">
              {{ messages?.hero?.title_part1 || 'Your Trusted' }}
              <span class="mt-2 block text-text-brand">
                {{ messages?.hero?.title_part2 || 'Web Design Partner' }}
              </span>
            </h1>

            <!-- Subheadline -->
            <p
              class="max-w-xl text-base leading-relaxed text-slate-700 sm:text-lg lg:text-xl"
              v-html="messages?.hero?.subtitle || 'We design high-converting websites that increase retention, boost SEO rankings, and drive measurable business growth.'"
            />

            <!-- CTAs: WhatsApp (emerald, primary) + Book a meeting (secondary, cal.com) -->
            <div class="flex flex-wrap items-center gap-x-5 gap-y-3">
              <!-- Primary: contact via WhatsApp -->
              <a
                v-if="messages?.hero?.cta_whatsapp_url"
                :href="messages.hero.cta_whatsapp_url"
                target="_blank"
                rel="noopener noreferrer"
                @click="trackWhatsAppClick()"
                class="inline-flex items-center gap-2.5 rounded-full bg-accent px-6 py-3 text-sm font-semibold text-black shadow-md transition-all hover:scale-105 hover:bg-accent/90 hover:shadow-lg sm:text-base"
              >
                <svg class="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                </svg>
                {{ messages?.hero?.cta_primary || 'Contact us on WhatsApp' }}
              </a>
              <button
                v-else
                @click="goToWhatsApp"
                class="inline-flex items-center gap-2.5 rounded-full bg-accent px-6 py-3 text-sm font-semibold text-black shadow-md transition-all hover:scale-105 hover:bg-accent/90 hover:shadow-lg sm:text-base"
              >
                <svg class="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                </svg>
                {{ messages?.hero?.cta_primary || 'Contact us on WhatsApp' }}
              </button>

              <!-- Secondary: book a meeting — triggers the cal.com modal -->
              <button
                type="button"
                class="group inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 transition hover:underline sm:text-base"
                data-cal-link="projectapp/discovery-call-projectapp"
                data-cal-namespace="discovery-call-projectapp"
                data-cal-config='{"layout":"week_view","theme":"dark"}'
              >
                <svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
                  <rect x="3" y="4.5" width="18" height="16" rx="2" />
                  <path stroke-linecap="round" d="M3 9h18M8 2.5v4M16 2.5v4" />
                </svg>
                {{ messages?.hero?.cta_book_call || 'Book a meeting' }}
                <svg class="h-4 w-4 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </div>

            <!-- NDA confidentiality note -->
            <div class="flex items-center gap-2 text-sm text-slate-700">
              <svg class="h-5 w-5 flex-shrink-0 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.3 12l1.8 1.8 3.4-3.8" />
              </svg>
              <span>{{ ndaNote }}</span>
            </div>
          </div>
        </div>

        <!-- Two feature cards — big, staggered diagonally (bottom-right) -->
        <div class="grid grid-cols-1 gap-4 lg:absolute lg:bottom-10 lg:right-8 lg:left-auto lg:w-[34rem] lg:grid-cols-2">
          <div
            v-for="(c, i) in cards"
            :key="i"
            class="hero-bubble pointer-events-auto rounded-3xl p-6 lg:p-7"
            :class="i === 0 ? 'lg:col-start-1 lg:row-start-2' : 'lg:col-start-2 lg:row-start-2'"
          >
            <svg class="mb-3 h-7 w-7 text-text-brand" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
            <p class="text-xl font-bold leading-tight text-slate-900 lg:text-2xl">{{ c.title }}</p>
            <p class="mt-2 text-sm leading-snug text-slate-700 lg:text-base">{{ c.text }}</p>
          </div>

          <!-- 2x1 cell (top-right): the lemon dot itself morphs into the "art" card -->
          <div class="relative hidden lg:col-start-2 lg:row-start-1 lg:block">
            <div class="art-blob pointer-events-auto" tabindex="0" role="button" :aria-label="artPhrase">
              <div class="art-blob__content">
                <svg class="mb-2 h-6 w-6 text-primary/70" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M7.17 6A5.17 5.17 0 002 11.17V18h6.83v-6.83H5.6A3.6 3.6 0 019.2 7.6V6H7.17zm9 0A5.17 5.17 0 0011 11.17V18h6.83v-6.83H14.6A3.6 3.6 0 0118.2 7.6V6h-2.03z" />
                </svg>
                <p class="font-serif text-lg italic leading-snug text-primary">{{ artPhrase }}</p>
              </div>
            </div>
            <span class="art-ping animate-ping"></span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import HeroMosaicCarousel from '~/components/home/HeroMosaicCarousel.vue'
import { useMessages } from '~/composables/useMessages'
import { useGtagConversions } from '~/composables/useGtagConversions'

const { messages } = useMessages()
const router = useRouter()
const localePath = useLocalePath()
const { trackWhatsAppClick } = useGtagConversions()

// Two prominent cards: social proof (+50) and real-advisor response.
const cards = computed(() => [
  {
    title: messages.value?.hero?.benefit4_title || '+50 companies trust us',
    text: messages.value?.hero?.benefit4_text || 'Logistics, health, legal, e-commerce and more already transformed their operations with us.',
  },
  {
    title: messages.value?.hero?.benefit2_title || 'A real advisor replies',
    text: messages.value?.hero?.benefit2_text || 'No bots, no queues — a senior specialist gets back to you the same day.',
  },
])

const ndaNote = computed(
  () => messages.value?.hero?.nda_note || 'We sign an NDA so your project stays 100% confidential.',
)

const artPhrase = computed(
  () => messages.value?.hero?.art_phrase || 'We are the artisans of code.',
)

const goToContact = () => {
  router.push(localePath('/contact'))
}

const goToWhatsApp = () => {
  trackWhatsAppClick()
  window.open('https://api.whatsapp.com/send/?phone=573238122373&text&type=phone_number&app_absent=0', '_blank')
}
</script>

<style scoped>
.hero-frame {
  animation: fadeIn 0.6s ease-out;
}

/* Glassmorphism — light variant, mirrors /platform platform-cover.css */
.hero-glass {
  background: rgba(255, 255, 255, 0.4);
  -webkit-backdrop-filter: blur(22px) saturate(1.5);
  backdrop-filter: blur(22px) saturate(1.5);
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.12);
}

.hero-btn-glass {
  background: rgba(255, 255, 255, 0.55);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 1px 10px rgba(0, 0, 0, 0.06);
}
.hero-btn-glass:hover {
  background: rgba(255, 255, 255, 0.75);
}

/* Benefit bubbles — same frost, lighter footprint */
.hero-bubble {
  background: rgba(255, 255, 255, 0.4);
  -webkit-backdrop-filter: blur(18px) saturate(1.4);
  backdrop-filter: blur(18px) saturate(1.4);
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
}

/* "Art" easter-egg: the lemon dot itself morphs into a frosted quote card.
   One element grows from a 1.4rem circle (top-right) into an 18rem card. */
/* The card fills its whole grid cell (inset:0) but is clipped to a tiny
   circle at the top-right — the "bolita". On hover the circle grows and
   reveals the full, fully-lemon card. clip-path also limits the hover
   hit-area to the dot while collapsed. */
.art-blob {
  position: absolute;
  inset: 0;
  z-index: 20;
  border-radius: 1.5rem;
  background: #f0ff3d;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.18);
  cursor: pointer;
  outline: none;
  overflow: hidden;
  clip-path: circle(0.7rem at calc(100% - 0.7rem) 0.7rem);
  transition: clip-path 0.55s cubic-bezier(0.16, 1, 0.3, 1);
}
.art-blob:hover,
.art-blob:focus,
.art-blob:focus-within {
  clip-path: circle(150% at calc(100% - 0.7rem) 0.7rem);
}

/* Pulsing ring — sibling so it isn't clipped; hidden once expanded */
.art-ping {
  position: absolute;
  top: 0;
  right: 0;
  width: 1.4rem;
  height: 1.4rem;
  border-radius: 9999px;
  background: #f0ff3d;
  opacity: 0.75;
  pointer-events: none;
  transition: opacity 0.25s ease;
}
.art-blob:hover ~ .art-ping,
.art-blob:focus ~ .art-ping,
.art-blob:focus-within ~ .art-ping {
  opacity: 0;
  animation: none;
}

/* Quote content — fades in once the card has opened */
.art-blob__content {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 1.5rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}
.art-blob:hover .art-blob__content,
.art-blob:focus .art-blob__content,
.art-blob:focus-within .art-blob__content {
  opacity: 1;
  transition: opacity 0.3s ease 0.2s;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-frame {
    animation: none;
  }
  .absolute.bg-cover {
    transition: none;
  }
  .animate-ping {
    animation: none;
  }
  .art-blob,
  .art-blob__content {
    transition: none;
  }
}
</style>
