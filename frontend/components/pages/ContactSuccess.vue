<template>
  <div class="min-h-screen bg-bone flex items-center justify-center">
    <main class="w-full py-20 px-6 lg:px-32">
      <div class="max-w-3xl mx-auto text-center">
        <h1 ref="titleRef" data-testid="contact-success-heading" class="text-4xl lg:text-6xl font-bold text-text-brand mb-6 opacity-0">
          {{ t('contactSuccess.title') }} <span ref="emojiRef">✨</span>
        </h1>
        
        <p ref="messageRef" class="text-xl lg:text-2xl font-light text-green-light mb-12 opacity-0">
          {{ t('contactSuccess.message') }}
        </p>

        <div ref="buttonRef" class="opacity-0">
          <a
            :href="portfolioLink"
            class="inline-block px-12 py-5 text-xl lg:text-2xl font-medium bg-primary text-bone rounded-full hover:bg-primary-strong transition-colors duration-200"
          >
            {{ t('contactSuccess.button') }}
          </a>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import gsap from 'gsap'

const { t } = useI18n()
const localePath = useLocalePath()
const portfolioLink = computed(() => localePath('/portfolio-works'))

const titleRef = ref(null)
const emojiRef = ref(null)
const messageRef = ref(null)
const buttonRef = ref(null)

onMounted(() => {
  const timeline = gsap.timeline({ defaults: { ease: 'power3.out' } })
  
  timeline
    .to(titleRef.value, {
      opacity: 1,
      y: 0,
      duration: 1
    })
    .to(messageRef.value, {
      opacity: 1,
      y: 0,
      duration: 0.8
    }, '-=0.4')
    .to(buttonRef.value, {
      opacity: 1,
      y: 0,
      duration: 0.8
    }, '-=0.4')
  
  gsap.to(emojiRef.value, {
    rotation: 20,
    transformOrigin: 'center',
    duration: 0.3,
    ease: 'power1.inOut',
    yoyo: true,
    repeat: 3,
    delay: 0.8
  })
})
</script>
