<template>
  <!--Navbar Desktop — Glassmorphism pill with sliding lemon indicator -->
  <nav
    data-hosting-offset="floating"
    class="hidden lg:flex fixed top-6 left-1/2 -translate-x-1/2 z-50 items-center gap-2 pl-7 pr-3 py-3.5 rounded-full bg-surface/60 backdrop-blur-2xl border border-white/30 shadow-xl"
    aria-label="Main navigation"
  >
    <!-- Logo -->
    <NuxtLink
      :to="localePath('/')"
      class="flex items-center pr-4 mr-2 text-text-brand font-bold text-xl tracking-tight hover:opacity-80 transition-opacity flex-shrink-0 border-r border-input-border"
      aria-label="Project App. - Homepage"
    >
      Project<span class="text-text-brand">App.</span>
    </NuxtLink>

    <!-- Nav links container with sliding lemon pill -->
    <div ref="navLinksContainer" class="relative flex items-center gap-1">
      <!-- Sliding lemon pill indicator -->
      <div
        ref="lemonPill"
        class="absolute top-0 left-0 h-full rounded-full bg-accent pointer-events-none will-change-transform"
        style="width: 0; opacity: 0;"
      />

      <!-- Nav links -->
      <NuxtLink
        v-for="(item, idx) in navItems"
        :key="item.href"
        :ref="el => { if (el) navLinkRefs[idx] = el.$el || el; }"
        :to="item.external ? item.href : localePath(item.href)"
        :target="item.external ? '_blank' : undefined"
        :rel="item.external ? 'noopener noreferrer' : undefined"
        class="relative z-10 px-6 py-3 rounded-full text-base transition-colors duration-200 whitespace-nowrap"
        :class="isActiveRoute(item.routeKey) ? 'text-text-brand font-medium' : 'text-text-brand/60 font-regular hover:text-text-brand'"
      >
        {{ item.name }}
      </NuxtLink>
    </div>

    <!-- Language toggle -->
    <button
      @click="toggleLanguage"
      :disabled="!isHydrated"
      class="px-4 py-2.5 rounded-full text-sm font-medium text-text-brand/50 hover:text-text-brand hover:bg-surface/40 transition-all uppercase tracking-wider ml-2"
      :aria-label="`Switch to ${isEnglish ? 'Spanish' : 'English'}`"
    >
      {{ isEnglish ? 'EN' : 'ES' }}
    </button>

    <!-- Sign In -->
    <NuxtLink
      to="/es-co/platform"
      class="px-5 py-2.5 rounded-full text-sm font-medium bg-primary text-white hover:bg-primary/90 transition-colors ml-1 whitespace-nowrap"
    >
      {{ globalMessages.sign_in || 'Sign In' }}
    </NuxtLink>
  </nav>

  <!--Navbar Mobile — Fixed glassmorphism bar -->
  <nav data-hosting-offset="top" class="flex lg:hidden fixed top-0 left-0 right-0 z-50 items-center justify-between px-5 py-4 bg-surface/60 backdrop-blur-2xl border-b border-white/20" aria-label="Mobile navigation">
    <NuxtLink
      :to="localePath('/')"
      class="text-text-brand font-bold text-lg tracking-tight"
      aria-label="Project App. - Homepage"
    >
      Project<span>App.</span>
    </NuxtLink>

    <div class="flex items-center gap-2">
      <button
        @click="toggleLanguage"
        :disabled="!isHydrated"
        class="px-2.5 py-1.5 rounded-full text-xs font-medium text-text-brand/50 uppercase tracking-wider"
        :aria-label="`Switch to ${isEnglish ? 'Spanish' : 'English'}`"
      >
        {{ isEnglish ? 'EN' : 'ES' }}
      </button>
      <NuxtLink
        to="/es-co/platform"
        class="px-3 py-1.5 rounded-full text-xs font-medium bg-primary text-white hover:bg-primary/90 transition-colors whitespace-nowrap"
      >
        {{ globalMessages.sign_in || 'Sign In' }}
      </NuxtLink>
      <BaseButton
        unstyled
        icon-only
        @click="openMenuMobile"
        class="w-10 h-10 rounded-full bg-primary flex items-center justify-center"
        aria-label="Open menu"
      >
        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
      </BaseButton>
    </div>
  </nav>

  <!-- Fullscreen mobile menu overlay -->
  <Teleport to="body">
    <div
      v-show="showMenu"
      class="fixed inset-0 z-[100]"
      id="mobile-menu"
      role="dialog"
      aria-modal="true"
    >
      <!-- Backdrop -->
      <div
        ref="background"
        @click="closeBackdrop"
        class="absolute inset-0 bg-surface/40 backdrop-blur-xl"
        style="opacity: 0;"
      />

      <!-- Menu panel -->
      <div
        ref="menuBox"
        class="absolute inset-0 flex flex-col bg-primary-soft backdrop-blur-md"
        style="opacity: 0;"
      >
        <!-- Top bar: logo + close -->
        <div class="flex items-center justify-between px-5 py-4">
          <NuxtLink
            :to="localePath('/')"
            class="text-text-brand font-bold text-lg tracking-tight"
            @click="closeMenu"
          >
            ProjectApp.
          </NuxtLink>
          <BaseButton
            unstyled
            icon-only
            @click="closeMenuMobile"
            class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-text-brand hover:bg-primary/20 transition-colors"
            aria-label="Close menu"
          >
            <XMarkIcon class="w-6 h-6" />
          </BaseButton>
        </div>

        <!-- Nav links — large, staggered -->
        <div class="flex-1 flex flex-col justify-center px-8 gap-2">
          <NuxtLink
            v-for="(item, index) in mobileMenuItems"
            :key="item.href"
            :to="item.external ? item.href : localePath(item.href)"
            :target="item.external ? '_blank' : undefined"
            :ref="el => { if (el) mobileNavRefs[index] = el.$el || el; }"
            class="mobile-nav-item text-text-brand font-light text-5xl py-3 border-b border-input-border transition-colors hover:text-green-light"
            style="opacity: 0; transform: translateY(20px);"
            @click="closeMenu"
          >
            {{ item.name }}
          </NuxtLink>
        </div>

        <!-- Bottom: WhatsApp CTA + socials -->
        <div class="px-8 pb-8 space-y-4" ref="mobileBottomRef" style="opacity: 0; transform: translateY(15px);">
          <a
            href="https://wa.me/message/XX77FJEUEM26H1?src=qr"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center justify-center gap-3 w-full py-4 rounded-2xl bg-primary text-white text-base font-medium transition-all hover:bg-primary/90"
          >
            <svg class="w-5 h-5" viewBox="0 0 448 512" fill="currentColor"><path d="M380.9 97.1C339 55.1 283.2 32 223.9 32c-122.4 0-222 99.6-222 222 0 39.1 10.2 77.3 29.6 111L0 480l117.7-30.9c32.4 17.7 68.9 27 106.1 27h.1c122.3 0 224.1-99.6 224.1-222 0-59.3-25.2-115-67.1-157" /></svg>
            {{ globalMessages?.contact_us || 'Contact' }}
          </a>
          <div class="flex items-center justify-center gap-6 text-sm text-text-brand/50">
            <a href="https://instagram.com/projectapp.co" target="_blank" rel="noopener noreferrer" class="hover:text-text-brand transition-colors">Instagram</a>
            <a href="https://facebook.com/projectapp.co" target="_blank" rel="noopener noreferrer" class="hover:text-text-brand transition-colors">Facebook</a>
            <button @click="toggleLanguage" :disabled="!isHydrated" class="hover:text-text-brand transition-colors uppercase">{{ isEnglish ? 'ES' : 'EN' }}</button>
            <NuxtLink to="/es-co/platform" class="hover:text-text-brand transition-colors" @click="closeMenu">{{ globalMessages.sign_in || 'Sign In' }}</NuxtLink>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <Email :visible="showModalEmail" @update:visible="showModalEmail = $event"></Email>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { gsap } from 'gsap';
import { XMarkIcon } from '@heroicons/vue/24/outline';
import { useGlobalMessages } from '~/composables/useMessages';
import Email from '~/components/layouts/Email.vue';

const localePath = useLocalePath();
const { locale } = useI18n();
const { globalMessages } = useGlobalMessages('navbar');
const isHydrated = ref(false);

// Derived from i18n locale (SSR-safe, unlike store)
const isEnglish = computed(() => locale.value.startsWith('en'));

// Props
defineProps({
  theme: {
    type: String,
    default: 'light',
  }
})

// Referencias reactivas
const background = ref(null);
const menuBox = ref(null);
const showModalEmail = ref(false);
const showMenu = ref(false);

/**
 * Toggle between English and Spanish
 */
const switchLocalePath = useSwitchLocalePath();
const toggleLanguage = () => {
  const targetLocale = isEnglish.value ? 'es-co' : 'en-us';
  const path = switchLocalePath(targetLocale);
  if (path) {
    // Close mobile menu immediately to avoid blank screen during navigation
    if (showMenu.value) {
      showMenu.value = false;
    }
    navigateTo(path);
  }
};

// Desktop navbar — sliding lemon pill
const route = useRoute();
const lemonPill = ref(null);
const navLinksContainer = ref(null);
const navLinkRefs = ref([]);

// Nav items: includes Contact as the last item (WhatsApp link)
const navItems = computed(() => {
  const s = globalMessages.value?.solutions || {};
  const cta = globalMessages.value?.contact_us || 'Contact';
  return [
    { name: s.software || 'Custom Software', href: '/', routeKey: 'index' },
    { name: s.apps || 'App Development', href: '/landing-apps', routeKey: 'landing-apps' },
    { name: s.web_developments || 'Our work', href: '/portfolio-works', routeKey: 'portfolio-works' },
    { name: s.blog || 'Blog', href: '/blog', routeKey: 'blog' },
    { name: cta, href: 'https://wa.me/message/XX77FJEUEM26H1?src=qr', external: true, routeKey: 'contact' },
  ];
});

// Mobile menu items (same nav + no external Contact, that's the CTA button)
const mobileMenuItems = computed(() => {
  const s = globalMessages.value?.solutions || {};
  return [
    { name: s.software || 'Custom Software', href: '/' },
    { name: s.apps || 'App Development', href: '/landing-apps' },
    { name: s.web_developments || 'Our work', href: '/portfolio-works' },
    { name: s.blog || 'Blog', href: '/blog' },
  ];
});
const mobileNavRefs = ref([]);
const mobileBottomRef = ref(null);

const isActiveRoute = (routeKey) => {
  if (routeKey === 'contact') return false;
  const name = route.name;
  if (!name || typeof name !== 'string') return false;
  const baseName = name.split('___')[0];
  if (routeKey === 'index') return baseName === 'index' || baseName === 'landing-software';
  return baseName.startsWith(routeKey);
};

const activeNavIndex = computed(() => {
  const idx = navItems.value.findIndex(item => isActiveRoute(item.routeKey));
  return idx >= 0 ? idx : -1;
});

let pillInitialized = false;

function slidePillToActive(animate = true) {
  const idx = activeNavIndex.value;
  const pill = lemonPill.value;
  if (!pill) return;

  // If no active route (e.g. external page), keep pill at last position
  if (idx < 0) return;

  const el = navLinkRefs.value[idx];
  if (!el) return;
  const container = navLinksContainer.value;
  if (!container) return;
  const containerRect = container.getBoundingClientRect();
  const elRect = el.getBoundingClientRect();
  const targetX = elRect.left - containerRect.left;
  const targetW = elRect.width;

  if (!pillInitialized) {
    // First time: instant position, then fade in
    gsap.set(pill, { x: targetX, width: targetW });
    gsap.to(pill, { opacity: 1, duration: 0.3 });
    pillInitialized = true;
    return;
  }

  if (animate) {
    // Pure horizontal slide — no opacity change
    gsap.to(pill, {
      x: targetX,
      width: targetW,
      duration: 0.5,
      ease: 'power3.inOut',
    });
  } else {
    gsap.set(pill, { x: targetX, width: targetW, opacity: 1 });
  }
}

watch(() => route.fullPath, () => {
  nextTick(() => slidePillToActive(true));
});

/**
 * Optimización de las animaciones de hover para los elementos del menú
 * Usa un único listener con delegación de eventos
 */
const hoverMenu = (event, isHover) => {
  const target = event.currentTarget;
  const underline = target.querySelector('.underline');
  const arrow = target.querySelector('.arrow');
  
  if (underline) {
    gsap.to(underline, { width: isHover ? '50%' : '0%', duration: 0.05 });
  }
  if (arrow) {
    gsap.to(arrow, { opacity: isHover ? 1 : 0, duration: 0.05 });
  }
};

const openMenuMobile = (event) => {
  event.stopPropagation();
  openMenu();
};

const openMenu = () => {
  showMenu.value = true;

  requestAnimationFrame(() => {
    const tl = gsap.timeline();

    // 1. Backdrop fades in
    if (background.value) {
      tl.fromTo(background.value, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: 'power2.out' }, 0);
    }

    // 2. Menu panel fades in
    if (menuBox.value) {
      tl.fromTo(menuBox.value, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: 'power2.out' }, 0.05);
    }

    // 3. Each nav link staggers in — the premium feel
    const navEls = mobileNavRefs.value.filter(Boolean);
    if (navEls.length) {
      tl.fromTo(navEls,
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: 0.5, stagger: 0.08, ease: 'power3.out' },
        0.15
      );
    }

    // 4. Bottom CTA slides up last
    if (mobileBottomRef.value) {
      tl.fromTo(mobileBottomRef.value,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' },
        0.45
      );
    }
  });
};

const closeMenuMobile = (event) => {
  event.stopPropagation();
  closeMenu();
};

const closeBackdrop = (event) => {
  event.stopPropagation();
  closeMenu();
};

const closeMenu = () => {
  const tl = gsap.timeline({
    onComplete: () => { showMenu.value = false; }
  });

  // Fade everything out together, fast
  const navEls = mobileNavRefs.value.filter(Boolean);
  if (navEls.length) {
    tl.to(navEls, { opacity: 0, y: -10, duration: 0.2, stagger: 0.03, ease: 'power2.in' }, 0);
  }
  if (mobileBottomRef.value) {
    tl.to(mobileBottomRef.value, { opacity: 0, duration: 0.15 }, 0);
  }
  if (menuBox.value) {
    tl.to(menuBox.value, { opacity: 0, duration: 0.25, ease: 'power2.in' }, 0.1);
  }
  if (background.value) {
    tl.to(background.value, { opacity: 0, duration: 0.25, ease: 'power2.in' }, 0.1);
  }
};

// Inicialización de efectos al montar el componente
onMounted(() => {
  isHydrated.value = true;

  // Slide lemon pill to active link on initial load
  setTimeout(() => slidePillToActive(false), 100);

  document.addEventListener('click', (e) => {
    // Solo cerrar el menú si está abierto y el clic no fue en el menú ni en el botón de apertura
    if (showMenu.value) {
      // Verificar si el clic fue en el menú o en cualquier elemento dentro de él
      const isClickInsideMenu = menuBox.value?.contains(e.target);
      // Verificar si el clic fue en el fondo semitransparente
      const isClickOnBackground = background.value === e.target;
      // Verificar si el clic fue en el botón de menú móvil (por selector)
      const menuBtn = document.querySelector('.block.lg\\:hidden .flex.absolute span:first-child');
      const isClickOnMenuButton = menuBtn?.contains(e.target);

      // Si el clic no fue en ninguno de estos elementos, cerrar el menú
      if (!isClickInsideMenu && !isClickOnBackground && !isClickOnMenuButton) {
        closeMenu();
      }
    }
  });
  
  // Cerrar menú al presionar Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && showMenu.value) {
      closeMenu();
    }
  });
});
</script>

<style scoped>
.underline, 
.arrow {
  will-change: transform, opacity, width;
}
</style>
