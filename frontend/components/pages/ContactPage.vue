<template>
  <div class="min-h-screen bg-bone flex items-center justify-center">
    <main class="w-full py-20 px-6 lg:px-32">
      <div class="max-w-3xl mx-auto">
        <h1 ref="titleRef" class="text-5xl lg:text-7xl font-bold text-text-brand mb-6 opacity-0">
          <span ref="waveEmoji" class="inline-block">👋</span> {{ messages?.title || 'Need a professional website?' }}
        </h1>
        
        <p ref="subtitleRef" class="text-xl lg:text-2xl font-light text-green-light mb-16 opacity-0">
          {{ messages?.subtitle || 'We develop custom websites, no templates. Tell us your idea and we\'ll make it real.' }}
        </p>

        <form @submit.prevent="handleSubmit" class="space-y-8">
          <div ref="formField1" class="opacity-0">
            <input
              v-model="form.fullName"
              type="text"
              :placeholder="messages?.form?.fullName || 'Full name'"
              class="w-full text-2xl lg:text-3xl font-light text-text-brand placeholder-green-light bg-transparent border-b-2 border-input-border focus:border-border-default outline-none py-4 transition-colors"
              required
            />
          </div>

          <div ref="formField2" class="opacity-0">
            <input
              v-model="form.phone"
              type="tel"
              :placeholder="messages?.form?.phone || 'Phone number'"
              class="w-full text-2xl lg:text-3xl font-light text-text-brand placeholder-green-light bg-transparent border-b-2 border-input-border focus:border-border-default outline-none py-4 transition-colors"
              required
            />
          </div>

          <div ref="formField3" class="opacity-0">
            <input
              v-model="form.email"
              type="email"
              :placeholder="messages?.form?.email || 'Your email'"
              class="w-full text-2xl lg:text-3xl font-light text-text-brand placeholder-green-light bg-transparent border-b-2 border-input-border focus:border-border-default outline-none py-4 transition-colors"
              required
            />
          </div>

          <div ref="formField4" class="opacity-0">
            <textarea
              v-model="form.project"
              :placeholder="messages?.form?.project || 'Tell us about your web project'"
              rows="4"
              class="w-full text-2xl lg:text-3xl font-light text-text-brand placeholder-green-light bg-transparent border-b-2 border-input-border focus:border-border-default outline-none py-4 transition-colors resize-none"
            ></textarea>
          </div>

          <div ref="formField5" class="opacity-0">
            <label class="block text-xl lg:text-2xl font-light text-green-light mb-6">{{ messages?.form?.budget || 'Estimated budget' }}</label>
            <div class="flex flex-wrap gap-4">
              <!-- design-tokens: allow-raw-button (selectable budget options, not an action) -->
              <button
                v-for="option in budgetOptions"
                :key="option"
                type="button"
                @click="selectBudget(option)"
                :class="[
                  'px-6 py-3 text-lg lg:text-xl rounded-full border-2 transition-all duration-200',
                  form.budget === option
                    ? 'bg-primary text-bone border-border-default'
                    : 'bg-transparent text-text-brand border-border-default hover:bg-primary-soft'
                ]"
              >
                {{ option }}
              </button>
            </div>
          </div>

          <div ref="formField6" class="pt-8 opacity-0">
            <BaseButton variant="primary" size="md" type="submit" class="w-full lg:w-auto lg:text-3xl" :disabled="isSubmitting">
              <span v-if="!isSubmitting">{{ messages?.form?.submit || 'Send message' }}</span>
              <span v-else>Enviando...</span>
            </BaseButton>
          </div>

          <p
            v-if="submitErrorText"
            role="alert"
            data-testid="contact-submit-error"
            class="text-xl lg:text-2xl font-light text-danger-strong"
          >
            {{ submitErrorText }}
          </p>

        </form>

        <CompanyDetails class="mt-20" />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useLanguageStore } from '~/stores/language'
import { useContactsStore } from '~/stores/contacts'
import { useGtagConversions } from '~/composables/useGtagConversions'
import gsap from 'gsap'
import CompanyDetails from '~/components/legal/CompanyDetails.vue'
import { waveEmoji as waveEmojiAnimation } from '~/animations'

const router = useRouter()
const languageStore = useLanguageStore()
const { messages: allMessages, currentLocale } = storeToRefs(languageStore)

const messages = computed(() => allMessages.value.contact || {})

const contactsStore = useContactsStore()
const { isSubmitting, submitSuccess, submitError } = storeToRefs(contactsStore)

// The store may hold a raw DRF payload (object) or its own fallback string —
// always show a generic localized message instead. Nothing populates
// messages.contact today (loadMessagesForView has no callers), so the
// fallback picks the language from the active locale.
const submitErrorText = computed(() => {
  if (!submitError.value) return ''
  if (messages.value?.form?.error) return messages.value.form.error
  return currentLocale.value?.startsWith('es')
    ? 'No pudimos enviar tu mensaje. Por favor inténtalo de nuevo.'
    : 'We could not send your message. Please try again.'
})
const { trackFormSubmission } = useGtagConversions()

const titleRef = ref(null)
const waveEmoji = ref(null)
const subtitleRef = ref(null)
const formField1 = ref(null)
const formField2 = ref(null)
const formField3 = ref(null)
const formField4 = ref(null)
const formField5 = ref(null)
const formField6 = ref(null)

const form = ref({
  fullName: '',
  phone: '',
  email: '',
  project: '',
  budget: ''
})

const budgetOptions = computed(() => {
  return messages.value?.budgetOptions || [
    '500-5K',
    '5-10K',
    '10-20K',
    '20-30K',
    '>30K'
  ]
})

const selectBudget = (option) => {
  form.value.budget = option
}

const handleSubmit = async () => {
  const result = await contactsStore.sendContact(form.value)
  console.log('Contact form result:', result)
  
  if (result.success) {
    trackFormSubmission()
    if (typeof window !== 'undefined' && window.fbq) {
      console.log('Facebook Pixel: Contact event tracked')
      window.fbq('track', 'Contact')
    }
    const successRoute = currentLocale.value 
      ? `/${currentLocale.value}/contact-success` 
      : '/contact-success'
    
    setTimeout(() => {
      router.push(successRoute)
    }, 800)
  }
}

onMounted(() => {
  const timeline = gsap.timeline({ defaults: { ease: 'power3.out' } })
  
  timeline
    .to(titleRef.value, {
      opacity: 1,
      y: 0,
      duration: 1.2,
      ease: 'power4.out'
    })
    .to(subtitleRef.value, {
      opacity: 1,
      y: 0,
      duration: 1,
      ease: 'power3.out'
    }, '-=0.6')
    .to([
      formField1.value,
      formField2.value,
      formField3.value,
      formField4.value,
      formField5.value,
      formField6.value
    ], {
      opacity: 1,
      y: 0,
      duration: 0.8,
      stagger: 0.15,
      ease: 'power2.out'
    }, '-=0.4')
  
  waveEmojiAnimation(waveEmoji.value, {
    rotation: 20,
    transformOrigin: 'bottom center',
    duration: 0.3,
    ease: 'power1.inOut',
    repeat: 5,
    delay: 0.5
  })
})
</script>
