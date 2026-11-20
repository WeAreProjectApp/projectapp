<template>
    <div itemscope itemtype="https://schema.org/Organization">
        <main>
            <section class="bg-accent px-3 py-32 lg:pt-52 lg:pb-60" aria-labelledby="about-main-title">
                <div class="grid lg:grid-cols-2">
                    <div class="mb-24 lg:ps-6 lg:mb-0">
                        <span class="bg-window-black bg-opacity-40 backdrop-blur-md px-6 py-2 inline-block rounded-3xl text-text-brand text-sm">
                            {{ messages.about.label }}
                            <span class="sr-only">Project App.</span>
                        </span>
                    </div>
                    <div>
                        <h1 id="about-main-title" class="inline-block text-6xl font-regular text-text-brand" itemprop="name">
                            {{ messages.about.main_title_1 }}<br>
                            {{ messages.about.main_title_2 }}<br>
                            <span class="border-4 border-transparent border-b-esmerald">
                                {{ messages.about.main_title_3 }}
                            </span>
                            <span class="sr-only">{{ messages.about.main_title_accessible }}</span>
                        </h1>
                        <p class="mt-6 font-regular text-text-brand text-md" itemprop="description">
                            {{ messages.about.sub_title_1 }}<br>
                            {{ messages.about.sub_title_2 }}
                            <span class="sr-only">by Project App.</span>
                        </p>
                    </div>
                </div>
            </section>
            <section class="bg-accent h-auto p-3" aria-label="Animated visual showcase">
                <div class="w-full rounded-xl overflow-hidden" style="height: 60vh;">
                    <PastelGradient />
                </div>
            </section>
            <section class="grid justify-items-end max-w-7xl mx-auto px-3 py-32 lg:py-52 lg:justify-items-start" aria-labelledby="digital-landscape-title" itemscope itemtype="https://schema.org/CreativeWork">
                <h2 id="digital-landscape-title" class="text-4xl text-text-brand font-light lg:text-6xl" itemprop="headline">
                    {{ messages.digital_landscape.title }}
                    <span class="sr-only">Project App. digital expertise</span>
                </h2>
                <div class="grid flex-initial w-3/5 mt-20 lg:grid-cols-2 lg:mt-32 lg:w-full">
                    <h3 class="inline-block font-light text-sm text-text-brand" itemprop="alternativeHeadline">
                        {{ messages.digital_landscape.section_label }}
                        <span class="sr-only">Project App.</span>
                    </h3>
                    <div itemprop="text">
                        <p class="lg:w-1/2">
                            <span class="text-text-brand font-regular text-lg">
                                {{ messages.digital_landscape.text_1 }}
                            </span>
                            <span class="text-green-light text-lg font-regular">
                                {{ messages.digital_landscape.text_2 }}
                            </span>
                            <br>
                            <br>
                            <span class="text-green-light text-lg font-regular">
                                {{ messages.digital_landscape.text_3 }}
                            </span>
                            <span class="sr-only">Project App. digital solutions</span>
                        </p>
                    </div>
                </div>
            </section>
            <section aria-label="Web design expertise showcase" class="py-8" itemscope itemtype="https://schema.org/ImageGallery">
                <div class="grid lg:grid-cols-2 p-3">
                    <figure ref="imageContainer" class="overflow-hidden" itemprop="image" itemscope itemtype="https://schema.org/ImageObject">
                        <img 
                            ref="leftImage" 
                            class="w-full rounded-xl" 
                            loading="lazy"
                            :src="imgLeft" 
                            alt="Professional web designer from Project App. working on a project" 
                            @load="initScrollTrigger"
                            itemprop="contentUrl"
                        >
                        <meta itemprop="name" content="Project App. professional web design process">
                    </figure>
                    <figure itemprop="image" itemscope itemtype="https://schema.org/ImageObject">
                        <img 
                            ref="mobileImage" 
                            class="w-full rounded-xl" 
                            :src="imgMobile" 
                            loading="lazy"
                            alt="Responsive mobile web design by Project App. in action"
                            itemprop="contentUrl"
                        >
                        <meta itemprop="name" content="Project App. responsive mobile design">
                    </figure>
                </div>
            </section>
            <section class="max-w-7xl mx-auto px-3 py-32 lg:py-52" aria-labelledby="team-support-title" itemscope itemtype="https://schema.org/Service">
                <div class="inline-block mx-auto space-y-20">
                    <h2 id="team-support-title" class="inline-block font-regular text-text-brand text-4xl border-2 border-transparent border-b-esmerald" itemprop="name">
                        {{ messages.team_support.title }}
                        <span class="sr-only">Project App. team support</span>
                    </h2>
                    <p class="w-1/2 ms-32 inline-block font-regular text-lg" itemprop="description">
                        <span class="text-text-brand">
                            {{ messages.team_support.text_1 }}
                        </span>
                        <span class="text-green-light">
                            {{ messages.team_support.text_2 }}
                        </span>
                        <span class="sr-only">from Project App.</span>
                    </p>
                </div>
            </section>

            <section class="h-svh p-3 relative" aria-labelledby="creatives-title" itemscope itemtype="https://schema.org/ImageObject">
                <div class="w-full h-full rounded-xl overflow-hidden">
                    <img 
                        :src="imgVisualIntro" 
                        loading="lazy"
                        class="h-full w-full object-cover"
                        alt="Creative web design visualization by Project App."
                        itemprop="contentUrl"
                    >
                    <div class="absolute inset-0 flex items-center justify-center px-3">
                        <div class="text-center text-white">
                            <h2 id="creatives-title" class="text-4xl font-bold mb-2 md:text-6xl" itemprop="name">
                                {{ messages.creatives.title_1 }}
                                <span class="sr-only">Project App.</span>
                            </h2>
                            <p class="text-4xl font-bold md:text-6xl" itemprop="description">
                                {{ messages.creatives.title_2_part_1 }} 
                                <br>
                                <span class="border-b-2 border-white">
                                    {{ messages.creatives.title_2_part_2 }}
                                </span>
                                <span class="sr-only">by Project App.</span>
                            </p>
                        </div>
                    </div>
                </div>
            </section>

            <section class="pt-32 lg:py-52" aria-labelledby="motivation-title" itemscope itemtype="https://schema.org/CreativeWork">
                <h2 id="motivation-title" class="text-7xl text-text-brand font-light text-center lg:text-9xl" itemprop="headline">
                    {{ messages.motivation.title_1 }} <br>
                    {{ messages.motivation.title_2 }}<br>
                    {{ messages.motivation.title_3 }}
                    <span class="sr-only">Project App. web solutions</span>
                </h2>
            </section>

            <section aria-label="Contact Project App. for web design services" itemscope itemtype="https://schema.org/ContactPoint">
                <Contact></Contact>
            </section>

            <footer class="mt-32" itemscope itemtype="https://schema.org/WPFooter">
                <Footer></Footer>
            </footer>
        </main>
    </div>
</template>

<script setup>
import Footer from '~/components/layouts/Footer.vue';
import Contact from '~/components/layouts/Contact.vue';
import PastelGradient from '~/components/backgrounds/PastelGradient.vue';
import { onMounted, ref } from 'vue';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useMessages } from '~/composables/useMessages';

import imgLeft from '~/assets/images/left.webp';
import imgMobile from '~/assets/images/mobile.webp';
import imgVisualIntro from '~/assets/images/visual_intro.webp';

const { messages } = useMessages(); // Destructure the localized messages from the custom composable

// Refs for DOM elements used in the scroll-triggered animations
const leftImage = ref(null);
const imageContainer = ref(null);
const mobileImage = ref(null);

/**
 * Initializes the ScrollTrigger animation on the leftImage element.
 * 
 * This function creates a GSAP scroll animation where the `leftImage` moves vertically
 * as the user scrolls through the `imageContainer`.
 */
const initScrollTrigger = () => {
  gsap.to(leftImage.value, {
    y: () => imageContainer.value.offsetHeight - leftImage.value.offsetHeight, // Set the animation distance
    ease: "none", // No easing for a smooth scroll effect
    scrollTrigger: {
      trigger: imageContainer.value, // The element that triggers the scroll animation
      start: "top bottom", // Animation starts when the top of the imageContainer hits the bottom of the viewport
      end: "bottom center", // Animation ends when the bottom of the imageContainer reaches the center of the viewport
      scrub: true, // Enables scrubbing (animation is tied to the scrollbar position)
      markers: false // Disable visible markers for debugging the scroll animation
    }
  });
};

/**
 * Lifecycle hook: Executes after the component is mounted.
 * 
 * This hook checks if the `mobileImage` is fully loaded. If so, it initializes the ScrollTrigger animation.
 */
onMounted(() => {
  gsap.registerPlugin(ScrollTrigger); // Register ScrollTrigger plugin with GSAP (client-only)
  if (mobileImage.value && mobileImage.value.complete) { // Ensure the image is fully loaded before initializing animations
    initScrollTrigger();
  }
});

</script>
