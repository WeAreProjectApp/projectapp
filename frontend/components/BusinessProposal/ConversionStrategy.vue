<template>
  <section ref="sectionRef" class="conversion-strategy min-h-screen w-full bg-surface">
    <div class="w-full px-6 md:px-12 lg:px-24 py-10 md:py-14">
      <div class="max-w-7xl mx-auto">
        <div data-animate="fade-up" class="flex items-baseline gap-4 mb-10">
          <span class="text-text-muted font-light tracking-[0.25em] text-xs md:text-sm">
            {{ content.index }}
          </span>
          <h2 class="text-text-brand font-light leading-tight text-4xl md:text-6xl">
            {{ content.title }}
          </h2>
        </div>

        <div class="grid lg:grid-cols-12 gap-10 items-start">
          <div class="lg:col-span-8 space-y-8">
            <div data-animate="fade-up" class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl" v-html="linkify(content.intro, content.text_formats?.['/intro'])" />

            <div data-animate="fade-up-stagger" class="grid md:grid-cols-2 gap-6">
              <div
                v-for="(step, idx) in content.steps"
                :key="idx"
                class="rounded-3xl border border-esmerald/20 bg-esmerald/5 p-6 md:p-7"
              >
                <div class="flex items-baseline justify-between gap-6 mb-4">
                  <!-- eslint-disable-next-line vue/no-v-html — same linkify path as intro/bullets/result -->
                  <h3
                    class="text-text-brand font-light text-lg md:text-xl leading-snug"
                    v-html="linkify(step.title, step.text_formats?.['/title'])"
                  />
                  <span class="text-text-muted font-light tracking-[0.25em] text-xs">
                    {{ idx + 1 }}
                  </span>
                </div>

                <ul class="space-y-3">
                  <li v-for="(item, j) in step.bullets" :key="j" class="flex gap-3">
                    <span class="mt-3 h-1.5 w-1.5 rounded-full bg-primary flex-shrink-0"></span>
                    <div class="text-text-default/80 font-light leading-relaxed" v-html="linkify(item, step.text_formats?.['/bullets/' + j])" />
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <aside v-if="content.result" data-animate="fade-up" class="lg:col-span-4">
            <div class="rounded-3xl bg-primary p-6 md:p-8">
              <h3 class="text-accent font-light text-base md:text-lg tracking-wide mb-4">
                {{ content.resultTitle }}
              </h3>
              <div class="text-white font-light leading-relaxed text-lg" v-html="linkify(content.result, content.text_formats?.['/result'])" />
            </div>
          </aside>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue';
import { useSectionAnimations } from '~/composables/useSectionAnimations';
import { linkify } from '~/composables/useLinkify';

const sectionRef = ref(null);
useSectionAnimations(sectionRef);

const props = defineProps({
  text_formats: { type: Object, default: () => ({}) },
  content: {
    type: Object,
    default: () => ({
      index: '3',
      title: 'Enfoque propuesto y estrategia de conversión',
      intro: 'La landing se construirá como una herramienta para generar confianza y convertir visitas en conversaciones (personas que preguntan y agendan) ✅📲. Para lograrlo, la página seguirá un flujo sencillo y natural:',
      steps: [
        {
          title: '👀 Captar atención en los primeros segundos',
          bullets: [
            'Mensaje principal claro: qué hace el cliente y a quién ayuda',
            'Beneficio directo (ej.: “asesoría contable clara y confiable para personas y negocios”)',
            'Botón visible de contacto: “Escríbeme por WhatsApp” / “Solicitar asesoría”'
          ]
        },
        {
          title: '🤝 Construir confianza rápidamente',
          bullets: [
            'Sección breve de “Quién soy” + enfoque profesional',
            'Señales de credibilidad: experiencia, metodología, certificaciones (si aplica)',
            'Lenguaje simple: sin tecnicismos, centrado en resolver problemas reales'
          ]
        },
        {
          title: '🧾 Presentar servicios como “soluciones”',
          bullets: [
            'Servicios organizados por necesidades (declaraciones, contabilidad, impuestos, asesoría)',
            'Para cada servicio: qué incluye / para quién es / resultado que obtiene el cliente',
            'Evitar listas largas: contenido corto y escaneable'
          ]
        },
        {
          title: '🖼️ Mantener contenido fresco sin depender de desarrollo',
          bullets: [
            'Autogestión para actualizar imágenes y/o videos',
            'Ideal para renovar material, campañas o contenido sin pedir ayuda técnica ⚙️🎥'
          ]
        }
      ],
      resultTitle: '🎯 Resultado esperado',
      result: 'Una página que no solo “se vea bonita”, sino que genere contactos, transmita profesionalismo y haga fácil que la gente diga: “Listo, le escribo”.'
    })
  }
});
</script>

<style scoped>
:deep(.linkify-link) {
  color: #059669;
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: rgba(5, 150, 105, 0.3);
  transition: text-decoration-color 0.2s ease;
}
:deep(.linkify-link:hover) {
  text-decoration-color: rgba(5, 150, 105, 0.8);
}
:deep(b), :deep(strong) {
  font-weight: 700;
}
</style>
