<template>
  <footer class="relative p-3 h-svh">
      <div class="relative w-full h-full overflow-hidden">
          <video
            ref="mainVideo"
            class="absolute top-0 left-0 w-full h-full object-cover rounded-xl"
            muted
            loop
            playsinline
            preload="auto"
          >
            <source src="~/assets/videos/presentationMobile.mp4" type="video/mp4">
            <p class="sr-only">Video showcasing our web design and development services</p>
          </video>
      </div>

      <div class="absolute bottom-0 right-0 w-full h-2/3 p-3">
        <div class="relative h-full overflow-y-auto overscroll-contain rounded-b-xl bg-window-black bg-opacity-40 backdrop-blur-md flex flex-col justify-between gap-4 py-4">
            <nav aria-label="Mobile website sections" class="grid shrink-0 grid-cols-2 auto-rows-min text-white">
              <NuxtLink
                :to="item.absolute ? item.href : localePath(item.href)" 
                v-for="item in solutions" 
                :key="item.name" 
                class="flex p-1 ps-4 font-regular text-white text-sm relative group"
                :aria-label="item.name"
              >
                {{ item.name }}
                <div class="absolute ms-4 left-0 bottom-0 h-0.5 w-0 bg-surface transition-all duration-300 group-hover:w-full"></div>
                <div class="relative ps-2 transform opacity-0 group-hover:opacity-100 transition-opacity duration-300 font-regular">
                  ➜
                </div>
              </NuxtLink>
            </nav>
            <div class="shrink-0 ps-4 mt-2">
                <a 
                  href="https://www.instagram.com/projectapp.co/" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="block text-sm cursor-pointer text-white font-regular py-0.5"
                  aria-label="Visit our Instagram profile"
                >
                  <span>{{ globalMessages.instagram || 'Instagram' }}</span>
                  <ArrowUpRightIcon class="w-4 inline ml-1"></ArrowUpRightIcon>
                </a>
                <a 
                  href="https://www.facebook.com/projectapp.co" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="block text-sm cursor-pointer text-white font-regular py-0.5"
                  aria-label="Visit our Facebook page"
                >
                  <span>{{ globalMessages.facebook || 'Facebook' }}</span>
                  <ArrowUpRightIcon class="w-4 inline ml-1"></ArrowUpRightIcon>
                </a>
                <a 
                  href="https://wa.me/message/XX77FJEUEM26H1?src=qr" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="block text-sm cursor-pointer text-white font-regular py-0.5"
                  aria-label="Contact us on WhatsApp"
                >
                  <span>{{ globalMessages.whatsapp || 'WhatsApp' }}</span>
                  <ArrowUpRightIcon class="w-4 inline ml-1"></ArrowUpRightIcon>
                </a>
                <a
                  @click.prevent="showModalEmail = true"
                  href="#"
                  class="block text-sm cursor-pointer font-regular text-white py-0.5"
                  aria-label="Email our web design team"
                >
                  {{ globalMessages.email_address || 'team@projectapp.co' }}
                </a>
                <NuxtLink
                  to="/es-co/platform"
                  class="inline-block mt-2 px-4 py-1.5 rounded-full text-xs font-medium bg-surface text-text-brand hover:bg-surface/80 transition-colors"
                >
                  {{ globalMessages.sign_in || 'Sign In' }}
                </NuxtLink>
            </div>
            <div class="shrink-0 ps-4 pb-2">
              <div class="flex gap-3 mb-2">
                <NuxtLink
                  :to="localePath('/terms-and-conditions')"
                  class="text-xs font-regular text-white opacity-40 hover:opacity-70 transition-opacity"
                >
                  {{ globalMessages.terms_and_conditions || 'Terms and Conditions' }}
                </NuxtLink>
                <NuxtLink
                  :to="localePath('/privacy-policy')"
                  class="text-xs font-regular text-white opacity-40 hover:opacity-70 transition-opacity"
                >
                  {{ globalMessages.privacy_policy || 'Privacy Policy' }}
                </NuxtLink>
              </div>
              <div class="mb-2 pe-4">
                <LegalFooter variant="overlay" />
              </div>
              <h3 class="text-xs font-regular text-white opacity-40">
                {{ globalMessages.based_in || 'Based in Colombia' }}
              </h3>
            </div>
        </div>
    </div>
  </footer>
  <Email :visible="showModalEmail" @update:visible="showModalEmail = $event"></Email>
</template>

<script setup>
import Email from '~/components/layouts/Email.vue';
import LegalFooter from '~/components/legal/LegalFooter.vue';
import { ref, computed, onMounted, onUnmounted } from 'vue';
import ArrowUpRightIcon from '@heroicons/vue/20/solid/ArrowUpRightIcon';
import { useGlobalMessages } from '~/composables/useMessages';
import { useFreeResources } from '~/composables/useFreeResources';

const localePath = useLocalePath();
const { t } = useI18n();
const { globalMessages } = useGlobalMessages('footer');

// Estado reactivo
const showModalEmail = ref(false);
const solutions = computed(() => [
  { name: globalMessages.value?.solutions?.software || 'Custom Software', href: '/' },
  { name: globalMessages.value?.solutions?.apps || 'App Development', href: '/landing-apps' },
  { name: globalMessages.value?.solutions?.web_developments || 'Our work', href: '/portfolio-works' },
  { name: globalMessages.value?.solutions?.blog || 'Blog', href: '/blog' },
  { name: t('additionalModules.title'), href: '/additional-modules' },
  { name: t('financing.title'), href: '/partnership-program' },
  { name: t('buildingWithUs.title'), href: '/building-with-us' },
]);

const mainVideo = ref(null);
let videoObserver = null;

// Lazy-load: play video only when footer is visible
onMounted(() => {
  if (typeof window === 'undefined' || !mainVideo.value) return;

  videoObserver = new IntersectionObserver(
    ([entry]) => {
      if (entry.isIntersecting) {
        mainVideo.value?.play();
      } else {
        mainVideo.value?.pause();
      }
    },
    { threshold: 0.1 }
  );
  videoObserver.observe(mainVideo.value);
});

// Limpiar recursos cuando el componente se desmonta
const { freeMediaResources } = useFreeResources({
  videos: [mainVideo],
});

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    if (videoObserver) {
      videoObserver.disconnect();
    }
    freeMediaResources();
  }
});
</script>

<style scoped>
.group:hover .group-hover\:w-full {
  width: 100%;
}
.group:hover .group-hover\:opacity-100 {
  opacity: 1;
}
</style>
