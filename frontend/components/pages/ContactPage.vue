<template>
  <div class="min-h-screen bg-bone flex items-center justify-center">
    <main class="w-full py-20 px-6 lg:px-32">
      <div class="max-w-3xl mx-auto">
        <h1 ref="titleRef" class="text-5xl lg:text-7xl font-bold text-text-brand mb-6 opacity-0">
          <span ref="waveEmoji" class="inline-block">👋</span> {{ t('contact.title') }}
        </h1>
        
        <p ref="subtitleRef" class="text-xl lg:text-2xl font-light text-green-light mb-16 opacity-0">
          {{ t('contact.subtitle') }}
        </p>

        <form data-testid="contact-form" @submit.prevent="handleSubmit" class="space-y-8">
          <div ref="formField1" class="opacity-0">
            <input
              v-model="form.fullName"
              type="text"
              :placeholder="t('contact.form.fullName')"
              :aria-label="t('contact.form.fullName')"
              class="w-full text-2xl lg:text-3xl font-light text-text-brand placeholder-green-light bg-transparent border-b-2 border-input-border focus:border-border-default outline-none py-4 transition-colors"
              required
            />
          </div>

          <div ref="formField2" class="opacity-0">
            <input
              v-model="form.phone"
              type="tel"
              :placeholder="t('contact.form.phone')"
              :aria-label="t('contact.form.phone')"
              class="w-full text-2xl lg:text-3xl font-light text-text-brand placeholder-green-light bg-transparent border-b-2 border-input-border focus:border-border-default outline-none py-4 transition-colors"
              required
            />
          </div>

          <div ref="formField3" class="opacity-0">
            <input
              v-model="form.email"
              type="email"
              :placeholder="t('contact.form.email')"
              :aria-label="t('contact.form.email')"
              class="w-full text-2xl lg:text-3xl font-light text-text-brand placeholder-green-light bg-transparent border-b-2 border-input-border focus:border-border-default outline-none py-4 transition-colors"
              required
            />
          </div>

          <div ref="formField4" class="opacity-0">
            <textarea
              v-model="form.project"
              :placeholder="t('contact.form.project')"
              :aria-label="t('contact.form.project')"
              rows="4"
              class="w-full text-2xl lg:text-3xl font-light text-text-brand placeholder-green-light bg-transparent border-b-2 border-input-border focus:border-border-default outline-none py-4 transition-colors resize-none"
            ></textarea>
          </div>

          <div ref="formField5" class="opacity-0">
            <label class="block text-xl lg:text-2xl font-light text-green-light mb-6">{{ t('contact.form.budget') }}</label>
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
            <BaseButton
              variant="primary"
              size="md"
              type="submit"
              class="w-full lg:w-auto lg:text-3xl"
              :disabled="submitDisabled"
              :disabled-reason="t(hasSubmitted ? 'contact.form.received' : 'contact.form.submitting')"
            >
              {{ t(isSubmitting ? 'contact.form.submitting' : 'contact.form.submit') }}
            </BaseButton>
          </div>

          <p
            v-if="submitError"
            role="alert"
            data-testid="contact-submit-error"
            class="text-xl lg:text-2xl font-light text-danger-strong"
          >
            {{ t('contact.form.error') }}
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
const { t, tm, rt } = useI18n()
const languageStore = useLanguageStore()
const { currentLocale } = storeToRefs(languageStore)

const contactsStore = useContactsStore()
const { isSubmitting, submitError } = storeToRefs(contactsStore)
const hasSubmitted = ref(false)
const submitDisabled = computed(() => isSubmitting.value || hasSubmitted.value)
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

const budgetOptions = computed(() => tm('contact.budgetOptions').map(option => rt(option)))

const selectBudget = (option) => {
  form.value.budget = option
}

const handleSubmit = async () => {
  if (submitDisabled.value) return

  const result = await contactsStore.sendContact(form.value)
  
  if (result.success) {
    hasSubmitted.value = true
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
