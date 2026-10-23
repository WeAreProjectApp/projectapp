<template>
  <section ref="sectionRef" class="next-steps py-16 md:py-24 bg-surface">
    <div class="container mx-auto px-6 md:px-12 lg:px-24 max-w-5xl">
      <div class="section-header mb-12">
        <div data-animate="fade-up" class="flex items-baseline gap-4 mb-10">
          <span class="text-text-muted font-light tracking-[0.25em] text-xs md:text-sm">
            {{ index }}
          </span>
          <h2 class="text-text-brand font-light leading-tight text-4xl md:text-6xl">
            {{ title }}
          </h2>
        </div>
      </div>

      <div data-animate="fade-up" class="intro-message mb-12 text-center">
        <p class="text-xl sm:text-2xl text-text-default/80 leading-relaxed font-light">
          {{ introMessage }}
        </p>
      </div>

      <div class="steps-container mb-12">
        <div data-animate="fade-up-stagger" class="grid md:grid-cols-3 gap-4 sm:gap-8">
          <div v-for="(step, index) in steps" :key="index"
               class="step-card bg-esmerald/5 p-5 sm:p-8 rounded-2xl border-2 border-esmerald/10 hover:border-esmerald/30 transition-all text-center">
            <div class="step-number w-12 h-12 sm:w-16 sm:h-16 bg-primary text-accent rounded-full flex items-center justify-center text-xl sm:text-2xl font-bold mx-auto mb-4 sm:mb-6 shadow-lg">
              {{ index + 1 }}
            </div>
            <h3 class="text-xl font-bold text-text-brand mb-3">{{ step.title }}</h3>
            <BaseRichTextContent class="text-text-default/70 font-light leading-relaxed" :source="step.description" :format="step.text_formats?.['/description'] || 'plain'" />
          </div>
        </div>
      </div>

      <div data-animate="fade-up" class="cta-section bg-primary p-5 sm:p-8 md:p-12 rounded-3xl text-white text-center mb-12 shadow-2xl">
        <h3 class="text-2xl sm:text-3xl md:text-4xl font-bold text-accent mb-4">¿Listo para Comenzar?</h3>
        <p class="text-base sm:text-xl text-primary mb-6 sm:mb-8 max-w-2xl mx-auto">
          {{ ctaMessage }}
        </p>

        <div class="cta-buttons flex flex-col md:flex-row gap-4 justify-center">
          <a :href="primaryCTA.link"
             target="_blank"
             class="inline-flex items-center justify-center px-6 sm:px-8 py-3 sm:py-4 bg-accent text-text-brand rounded-xl font-bold text-base sm:text-lg hover:bg-lemon/90 transition-all shadow-lg hover:shadow-xl">
            <svg class="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
            </svg>
            {{ primaryCTA.text }}
          </a>

          <button
             type="button"
             data-cal-link="projectapp/discovery-call-projectapp"
             data-cal-namespace="discovery-call-projectapp"
             data-cal-config='{"layout":"month_view","useSlotsViewOnSmallScreen":"true"}'
             class="inline-flex items-center justify-center px-6 sm:px-8 py-3 sm:py-4 bg-primary-strong text-primary rounded-xl font-bold text-base sm:text-lg hover:bg-primary-strong transition-all cursor-pointer">
            <svg class="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
            </svg>
            {{ secondaryCTA.text }}
          </button>
        </div>
      </div>

      <div data-animate="fade-up-stagger" class="contact-info grid md:grid-cols-3 gap-6 mb-12">
        <div v-for="(contact, index) in contactMethods" :key="index"
             class="contact-card bg-esmerald/5 p-4 sm:p-6 rounded-xl text-center border border-esmerald/10 hover:border-esmerald/20 transition-colors">
          <div class="text-4xl mb-3">{{ contact.icon }}</div>
          <h4 class="font-bold text-text-brand mb-2">{{ contact.title }}</h4>
          <a :href="contact.link" target="_blank" class="text-green-light hover:text-text-brand font-medium transition-colors">
            {{ contact.value }}
          </a>
        </div>
      </div>

    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue';
import { useSectionAnimations } from '~/composables/useSectionAnimations';

const sectionRef = ref(null);
useSectionAnimations(sectionRef);

const props = defineProps({
  index: {
    type: String,
    default: '11'
  },
  title: {
    type: String,
    default: 'Próximos Pasos'
  },
  introMessage: {
    type: String,
    default: 'Estamos listos para comenzar este viaje juntos. Aquí te explicamos cómo dar el siguiente paso:'
  },
  steps: {
    type: Array,
    default: () => [
      {
        title: 'Revisión y Preguntas',
        description: 'Revisa la propuesta y envíanos cualquier pregunta o ajuste que necesites.'
      },
      {
        title: 'Reunión de Confirmación',
        description: 'Agendamos una llamada para alinear detalles finales y firmar el contrato.'
      },
      {
        title: '¡Comenzamos!',
        description: 'Iniciamos el proyecto con la reunión de kickoff y arrancamos la fase de Discovery.'
      }
    ]
  },
  ctaMessage: {
    type: String,
    default: 'Contáctanos hoy mismo y comencemos a trabajar en tu proyecto. Estamos a solo un mensaje de distancia.'
  },
  primaryCTA: {
    type: Object,
    default: () => ({
      text: 'Contactar por WhatsApp',
      link: 'https://wa.me/1234567890'
    })
  },
  secondaryCTA: {
    type: Object,
    default: () => ({
      text: 'Agendar Reunión',
      link: 'https://calendly.com/projectapp'
    })
  },
  contactMethods: {
    type: Array,
    default: () => [
      {
        icon: '📧',
        title: 'Email',
        value: 'hola@projectapp.com',
        link: 'mailto:hola@projectapp.com'
      },
      {
        icon: '📱',
        title: 'WhatsApp',
        value: '+57 123 456 7890',
        link: 'https://wa.me/571234567890'
      },
      {
        icon: '🌐',
        title: 'Website',
        value: 'www.projectapp.com',
        link: 'https://www.projectapp.com'
      }
    ]
  },
});
</script>

<style scoped>
.step-card {
  transition: all 0.3s ease;
}

.step-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 24px rgba(16, 185, 129, 0.2);
}

.step-number {
  transition: transform 0.3s ease;
}

.step-card:hover .step-number {
  transform: scale(1.1) rotate(5deg);
}

.contact-card {
  transition: all 0.3s ease;
}

.contact-card:hover {
  transform: scale(1.05);
}

.cta-buttons a {
  transition: all 0.3s ease;
}

.cta-buttons a:hover {
  transform: translateY(-2px);
}
</style>
