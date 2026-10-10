<template>
  <footer class="p-3 h-svh" @mousemove="handleMouseMove">
    <div class="relative w-full h-full overflow-hidden">
      <video
        ref="mainVideo"
        class="absolute top-0 left-0 w-full h-full object-cover rounded-xl"
        muted
        loop
        playsinline
        preload="auto"
      >
        <source src="~/assets/videos/presentationPrevPc.mp4" type="video/mp4">
        <p class="sr-only">Video showcasing our web design and development services</p>
      </video>
      <button 
        ref="ball" 
        class="absolute bg-window-black bg-opacity-40 backdrop-blur-md text-white rounded-full flex items-center justify-center w-32 h-32 transition-opacity duration-300 cursor-pointer" 
        @click="showModal = true"
        aria-label="Play our web design portfolio showcase video"
        >
        <span ref="ballText" class="font-light text-xl">
          {{ globalMessages.play_reel || 'Play Reel' }}
        </span>
      </button>
      <div class="absolute bottom-0 right-0 w-full h-1/2 rounded-b-xl bg-window-black bg-opacity-40 backdrop-blur-md">
          <div class="flex justify-end w-full">
            <nav aria-label="Website sections" class="md:w-max grid grid-cols-2 text-white mt-4">
              <NuxtLink
                :to="item.absolute ? item.href : localePath(item.href)" 
                v-for="item in solutions" 
                :key="item.name" 
                class="flex p-2 ps-4 font-regular text-white text-xl relative group"
                @mouseover="hoverMenu($event, true)" 
                @mouseleave="hoverMenu($event, false)"
                :aria-label="item.name"
              >
                {{ item.name }}
                <div class="absolute ms-4 left-0 bottom-0 h-0.5 w-0 bg-surface transition-all duration-300 group-hover:w-full"></div>
                <div class="relative ps-2 transform opacity-0 group-hover:opacity-100 transition-opacity duration-300 font-regular">
                  ➜
                </div>
              </NuxtLink>
            </nav>
            <div class="w-60">
              <div class="mt-4 p-2 ps-4">
                <a 
                  href="https://www.instagram.com/projectapp.co/" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="block text-lg cursor-pointer social-link text-white font-regular"
                  aria-label="Visit our Instagram profile"
                  >
                  {{ globalMessages.instagram || 'Instagram' }} 
                  <ArrowUpRightIcon class="w-5 inline arrow-icon"></ArrowUpRightIcon>
                  <span class="sr-only">Opens in a new window</span>
                </a>
                <a 
                  href="https://www.facebook.com/projectapp.co" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="block text-lg cursor-pointer social-link text-white font-regular"
                  aria-label="Visit our Facebook page"
                  >
                  {{ globalMessages.facebook || 'Facebook' }} 
                  <ArrowUpRightIcon class="w-5 inline arrow-icon"></ArrowUpRightIcon>
                  <span class="sr-only">Opens in a new window</span>
                </a>
                <a 
                  href="https://wa.me/message/XX77FJEUEM26H1?src=qr" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="block text-lg cursor-pointer social-link text-white font-regular"
                  aria-label="Contact us on WhatsApp">
                  {{ globalMessages.whatsapp || 'WhatsApp' }} 
                  <ArrowUpRightIcon class="w-5 inline arrow-icon"></ArrowUpRightIcon>
                  <span class="sr-only">Opens in a new window</span>
                </a>
                <a
                  @click.prevent="showModalEmail = true"
                  href="#"
                  class="flex cursor-pointer font-regular text-white text-lg relative group"
                  @mouseover="hoverMenu($event, true)"
                  @mouseleave="hoverMenu($event, false)"
                  aria-label="Email our web design team"
                  >
                  {{ globalMessages.email_address || 'team@projectapp.co' }}
                  <div class="absolute left-0 bottom-0 h-0.5 w-0 bg-surface transition-all duration-300 group-hover:w-full"></div>
                  <span class="sr-only">Open contact form</span>
                </a>
                <NuxtLink
                  to="/es-co/platform"
                  class="inline-block mt-3 px-5 py-2 rounded-full text-sm font-medium bg-surface text-text-brand hover:bg-surface/80 transition-colors"
                >
                  {{ globalMessages.sign_in || 'Sign In' }}
                </NuxtLink>
              </div>
            </div>
          </div>
        <div class="absolute bottom-0 w-full">
          <div class="hidden px-4 pb-1 lg:block">
            <LegalFooter variant="overlay" />
          </div>
          <div class="flex w-full justify-between items-end">
            <h3 
              class="hidden ms-4 mb-4 text-lg font-regular text-white opacity-40 lg:block"
              >
              {{ globalMessages.based_in || 'Website Design Company Based in Colombia, Working Worldwide' }}
            </h3>
            <div class="hidden lg:flex items-center gap-4 mb-4">
              <NuxtLink
                :to="localePath('/terms-and-conditions')"
                class="text-sm font-regular text-white opacity-40 hover:opacity-70 transition-opacity"
              >
                {{ globalMessages.terms_and_conditions || 'Terms and Conditions' }}
              </NuxtLink>
              <NuxtLink
                :to="localePath('/privacy-policy')"
                class="text-sm font-regular text-white opacity-40 hover:opacity-70 transition-opacity"
              >
                {{ globalMessages.privacy_policy || 'Privacy Policy' }}
              </NuxtLink>
            </div>
            <h3 class="hidden me-4 mb-4 text-lg font-regular text-white opacity-40 lg:block">
              {{ globalMessages.copyright || '©2026 Project App.' }}
            </h3>
          </div>
        </div>
      </div>
    </div>
  </footer>

  <!-- Modal -->
  <Teleport to="body">
    <div 
      v-if="showModal" 
      class="fixed inset-0 flex items-center justify-center z-50 bg-black bg-opacity-50 backdrop-blur-md" 
      @mousemove="handleModalMouseMove"
      role="dialog"
      aria-modal="true"
      aria-labelledby="video-modal-title"
      >
      <span id="video-modal-title" class="sr-only">Project App web design showcase video</span>
      <!-- Loading Animation -->
      <div
        v-show="isLoading"
        class="absolute inset-0 flex items-center justify-center"
        aria-live="polite"
        aria-label="Loading video"
      >
          <div v-if="Vue3Lottie">
            <Vue3Lottie
              :animationData="whiteAnimation"
              :height="300"
              :width="300"
              :loop="true"
              :autoplay="true"
            />
          </div>
          <div v-else class="w-12 h-12 border-4 border-white rounded-full border-t-transparent animate-spin"></div>
      </div>
      <div 
        v-show="!isLoading" 
        class="relative w-screen lg:h-svh"
      >
        <video 
          ref="modalVideo" 
          class="w-full h-full object-cover" 
          preload="metadata"
          @loadeddata="onVideoLoad"
          aria-label="Project App web design portfolio showcase video"
        >
          <source src="/videos/presentationComp.mp4" type="video/mp4">
          <p class="sr-only">Video showcasing our web design and development portfolio</p>
        </video>
      </div>
      <BaseButton
        unstyled
        icon-only
        :ref="setModalBallRef"
        class="absolute z-50 bg-window-black bg-opacity-60 backdrop-blur-md text-white rounded-full flex items-center justify-center w-20 h-20 transition-opacity duration-300 cursor-pointer" 
        @click="closeModal"
        aria-label="Close video"
        >
        <XMarkIcon ref="modalBallText" class="w-8"></XMarkIcon>
        <span class="sr-only">Close showcase video</span>
      </BaseButton>
    </div>
  </Teleport>
  
  <Email :visible="showModalEmail" @update:visible="showModalEmail = $event"></Email>
</template>

<script setup>
import Email from '~/components/layouts/Email.vue';
import LegalFooter from '~/components/legal/LegalFooter.vue';
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { gsap } from 'gsap';
import { XMarkIcon } from '@heroicons/vue/24/outline';
import ArrowUpRightIcon from '@heroicons/vue/20/solid/ArrowUpRightIcon';
import { useGlobalMessages } from '~/composables/useMessages';
import { useFreeResources } from '~/composables/useFreeResources';

// Cargar componentes de Lottie de forma convencional
import { Vue3Lottie } from "vue3-lottie";
let whiteAnimation = null;

// Cargar la animación de forma diferida
onMounted(async () => {
  try {
    const animationModule = await import("~/assets/loading/white.json");
    whiteAnimation = animationModule.default;
  } catch (error) {
    console.error("Error loading animation:", error);
  }
});

const localePath = useLocalePath();
const { t } = useI18n();
const { globalMessages } = useGlobalMessages('footer');

// Animación de estado de carga
const isLoading = ref(true);

// Estado reactivo
const showModalEmail = ref(false);
const solutions = computed(() => {
  const s = globalMessages.value?.solutions || {};
  return [
    { name: s.software || 'Custom Software', href: '/' },
    { name: s.apps || 'App Development', href: '/landing-apps' },
    { name: s.web_developments || 'Our work', href: '/portfolio-works' },
    { name: s.blog || 'Blog', href: '/blog' },
    { name: t('additionalModules.title'), href: '/additional-modules' },
    { name: t('financing.title'), href: '/partnership-program' },
    { name: t('buildingWithUs.title'), href: '/building-with-us' },
  ];
});

const showModal = ref(false);
const ball = ref(null);
const ballText = ref(null);
const modalBall = ref(null);
const modalBallText = ref(null);
const mainVideo = ref(null);
const modalVideo = ref(null);

function setModalBallRef(component) {
  modalBall.value = component?.$el || null;
}

// Variables para seguimiento de ratón y posiciones de elementos
let mouseX = 0, mouseY = 0, modalMouseX = 0, modalMouseY = 0;
let ballX = 0, ballY = 0, textX = 0, textY = 0;
let modalBallX = 0, modalBallY = 0, modalTextX = 0, modalTextY = 0;
let animationFrameId = null;

/**
 * Función que se ejecuta cuando el video se ha cargado completamente.
 */
const onVideoLoad = () => {
  isLoading.value = false;
  if (modalVideo.value) {
    modalVideo.value.play();
  }
};

/**
 * Maneja el movimiento del ratón dentro de un elemento específico.
 * Actualiza las coordenadas del ratón relativas a la posición del elemento.
 * 
 * @param {Event} event - El evento de movimiento del ratón.
 */
const handleMouseMove = (event) => {
  const rect = event.currentTarget.getBoundingClientRect();
  mouseX = event.clientX - rect.left;
  mouseY = event.clientY - rect.top;
};

/**
 * Maneja el movimiento del ratón dentro del modal.
 * Actualiza las coordenadas específicas del modal.
 * 
 * @param {Event} event - El evento de movimiento del ratón dentro del modal.
 */
const handleModalMouseMove = (event) => {
  const rect = event.currentTarget.getBoundingClientRect();
  modalMouseX = event.clientX - rect.left;
  modalMouseY = event.clientY - rect.top;
};

/**
 * Actualiza continuamente la posición de la bola y su texto basado en el movimiento del ratón.
 * Utiliza GSAP para animaciones suaves.
 */
const updateBallPosition = () => {
  if (ball.value) {
    ballX += (mouseX - ballX - ball.value.offsetWidth / 2) * 0.2;
    ballY += (mouseY - ballY - ball.value.offsetHeight / 2) * 0.2;
    gsap.to(ball.value, { x: ballX, y: ballY, duration: 0.1, ease: 'power2.out' });
  }

  if (ballText.value) {
    textX += (mouseX - ballX - textX - ball.value?.offsetWidth / 2 || 0) * 0.15;
    textY += (mouseY - ballY - textY - ball.value?.offsetHeight / 2 || 0) * 0.15;
    gsap.to(ballText.value, { x: textX, y: textY, duration: 0.1, ease: 'power2.out' });
  }

  if (showModal.value && modalBall.value) {
    modalBallX += (modalMouseX - modalBallX - window.innerWidth / 2) * 0.2;
    modalBallY += (modalMouseY - modalBallY - window.innerHeight / 2) * 0.2;
    gsap.to(modalBall.value, { x: modalBallX, y: modalBallY, duration: 0.1, ease: 'power2.out' });
  }

  animationFrameId = requestAnimationFrame(updateBallPosition);
};

/**
 * Cierra el modal y pausa el video si corresponde.
 */
const closeModal = () => {
  showModal.value = false;
  if (modalVideo.value) {
    modalVideo.value.pause();
    modalVideo.value.currentTime = 0;
  }
};

/**
 * Maneja animaciones de hover para elementos de menú.
 * 
 * @param {Event} event - El evento de hover.
 * @param {Boolean} isHover - Si el elemento del menú está siendo hover o no.
 */
const hoverMenu = (event, isHover) => {
  const underline = event.target.querySelector('.underline');
  const arrow = event.target.querySelector('.arrow');
  if (underline) {
    gsap.to(underline, { width: isHover ? '100%' : '0%', duration: 0.3 });
  }
  if (arrow) {
    gsap.to(arrow, { opacity: isHover ? 1 : 0, duration: 0.3 });
  }
};

let videoObserver = null;

// Hook de ciclo de vida que se ejecuta cuando el componente está montado
onMounted(() => {
  // Verificar que window esté definido
  if (typeof window === 'undefined') return;

  // Lazy-load: play background video only when footer is visible
  if (mainVideo.value) {
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
  }

  // Iniciar la actualización de la posición de la bola
  animationFrameId = requestAnimationFrame(updateBallPosition);

  // Observar cambios en el estado showModal y reproducir/pausar el video en consecuencia
  watch(showModal, (newVal) => {
    if (newVal) {
      document.body.style.overflow = 'hidden';
      isLoading.value = true;
      
      // Cargar el video solo cuando se muestra el modal
      if (modalVideo.value) {
        modalVideo.value.load();
      }
    } else {
      document.body.style.overflow = '';
    }
  });

  // Añadir efectos hover a los enlaces sociales usando delegación de eventos
  const container = document.querySelector('.w-60');
  if (container) {
    container.addEventListener('mouseenter', (e) => {
      if (e.target.classList.contains('social-link')) {
        const arrow = e.target.querySelector('.arrow-icon');
        if (arrow) {
          gsap.to(arrow, {
            x: 10,
            y: -10,
            opacity: 0,
            duration: 0.1,
            onComplete: () => {
              gsap.set(arrow, { x: -10, y: 10, opacity: 0 });
              gsap.to(arrow, { x: 0, y: 0, opacity: 1, duration: 0.1 });
            }
          });
        }
      }
    }, true);
  }
});

// Hook de ciclo de vida que se ejecuta cuando el componente es desmontado
onUnmounted(() => {
  // Verificar que window esté definido
  if (typeof window === 'undefined') return;

  // Detener las actualizaciones de la posición de la bola
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
  }

  // Limpiar IntersectionObserver
  if (videoObserver) {
    videoObserver.disconnect();
  }
});

// Usar recursos gratuitos para limpiar los recursos de video al desmontar
useFreeResources({
  videos: [mainVideo, modalVideo],
});
</script>

<style scoped>
.group:hover .group-hover\:w-full {
  width: 50%;
}
.group:hover .group-hover\:opacity-100 {
  opacity: 1;
}
</style>
