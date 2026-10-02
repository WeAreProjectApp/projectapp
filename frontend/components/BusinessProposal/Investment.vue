<template>
  <section ref="sectionRef" class="investment py-16 md:py-24 bg-surface">
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

      <div data-animate="fade-up" class="investment-intro mb-12">
        <p class="text-text-brand/80 font-light leading-relaxed text-lg md:text-xl" v-html="linkify(introText)" />
      </div>

      <!-- F5: Value proposition — why this investment is worth it -->
      <div v-if="valueReasons && valueReasons.length" data-animate="fade-up" class="value-proposition mb-12 bg-primary p-5 sm:p-8 md:p-12 rounded-2xl">
        <h3 class="text-2xl font-bold text-accent mb-6">{{ t.whyWorthIt }}</h3>
        <div class="grid md:grid-cols-2 gap-6">
          <div v-for="(reason, index) in normalizedReasons" :key="index"
               class="value-reason flex items-start">
            <div class="flex-shrink-0 w-10 h-10 bg-accent rounded-lg flex items-center justify-center mr-4">
              <svg class="w-6 h-6 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
              </svg>
            </div>
            <div>
              <p class="text-sm text-white leading-relaxed" v-html="linkify(reason)" />
            </div>
          </div>
        </div>
        <!-- CTA after value reasons -->
        <div v-if="whatsappLink" class="text-center mt-8">
          <a
            :href="whatsappLink"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-2 px-6 py-3 bg-primary-strong text-accent rounded-xl font-bold text-sm hover:bg-primary transition-colors shadow-lg ring-1 ring-accent/40"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
            {{ t.whatsappCta }}
          </a>
        </div>
      </div>

      <!-- F5: Pricing card — payment plan as hero, total secondary -->
      <div data-animate="fade-up" class="pricing-card bg-primary p-5 sm:p-8 md:p-12 rounded-3xl text-on-primary mb-12 shadow-2xl">
        <!-- Payment plan as hero (if available) -->
        <div v-if="paymentOptions && paymentOptions.length" class="mb-8">
          <div class="text-center mb-6">
            <div class="text-sm font-semibold uppercase tracking-wider text-on-primary mb-1">{{ t.paymentOptions }}</div>
            <div class="text-2xl sm:text-3xl font-bold text-on-primary">{{ computedPaymentOptions.length }} {{ t.convenientPayments }}</div>
          </div>
          <div data-testid="payment-options-list" class="mx-auto max-w-2xl space-y-3">
            <div v-for="(option, idx) in computedPaymentOptions" :key="idx"
                 class="payment-option-card flex flex-col gap-1 rounded-xl bg-surface/10 p-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:p-4">
              <span data-testid="payment-option-label" class="min-w-0 flex-1 text-sm text-on-primary/80">{{ option.label }}</span>
              <span data-testid="payment-option-amount" class="shrink-0 whitespace-nowrap text-lg font-bold tabular-nums text-on-primary">{{ option.description }}</span>
            </div>
          </div>
          <!-- Total as secondary line -->
          <div class="text-center mt-6 pt-5 border-t border-border-default/15">
            <span class="text-sm text-on-primary/70">{{ t.totalInvestment }}:</span>
            <span class="text-xl font-bold text-on-primary ml-2 tabular-nums">{{ formatCurrency(displayTotal) }}</span>
            <span class="text-sm text-on-primary/70 ml-1">{{ currency }}</span>
            <span class="text-sm font-semibold text-accent ml-1">{{ taxLabel }}</span>
          </div>
        </div>

        <!-- Fallback: total as hero when no payment options -->
        <div v-else class="text-center mb-8">
          <div class="text-sm font-semibold uppercase tracking-wider mb-4 text-on-primary">{{ t.totalInvestment }}</div>
          <div class="text-3xl sm:text-4xl md:text-5xl font-bold mb-2 text-on-primary tabular-nums">{{ formatCurrency(displayTotal) }}</div>
          <div class="text-on-primary">{{ currency }} {{ taxLabel }}</div>
        </div>

        <!-- What's included grid -->
        <div class="grid md:grid-cols-3 gap-6">
          <div v-for="(item, index) in whatsIncluded" :key="index"
               class="text-center p-4 bg-surface/10 backdrop-blur-sm rounded-xl">
            <div class="text-3xl mb-2">{{ item.icon }}</div>
            <div class="font-bold text-on-primary mb-1">{{ item.title }}</div>
            <div class="text-sm text-on-primary/70">{{ item.description }}</div>
          </div>
        </div>
        <!-- Customize investment + Contact CTA buttons -->
        <div class="flex flex-col sm:flex-row items-center justify-center gap-3 mt-6">
          <button
            v-if="props.viewMode !== 'executive'"
            ref="customizeBtnRef"
            class="customize-investment-btn px-6 py-3 bg-accent text-text-brand rounded-xl font-bold text-sm hover:opacity-90 transition-all shadow-lg relative overflow-visible"
            :class="{ 'btn-pulse': btnPulse }"
            @click="interestsOpen = true"
          >
            🧩 {{ t.customizeBtn }}
          </button>
          <a
            v-if="whatsappLink"
            :href="whatsappLink"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-2 px-6 py-3 bg-surface/15 text-white rounded-xl font-medium text-sm hover:bg-surface/25 transition-colors border border-border-default/20"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
            {{ t.contactCta }}
          </a>
        </div>
        <!-- Teaser for executive mode: invite user to explore full proposal -->
        <InvestmentDetailedTeaser
          v-if="props.viewMode === 'executive'"
          :language="props.language"
          @switchToDetailed="$emit('switchToDetailed')"
        />
      </div>

      <!-- Discount banner -->
      <div v-if="hasActiveDiscount" data-animate="fade-up" class="discount-banner mb-12 relative overflow-hidden bg-primary-strong rounded-2xl p-6 sm:p-8 shadow-2xl ring-1 ring-accent/40">
        <!-- Corner chip -->
        <div class="absolute top-3 right-3 inline-flex items-center gap-1 bg-accent text-primary rounded-full px-3 py-1 text-[11px] font-bold tracking-wide shadow-sm">
          🔥 {{ discountPercent }}% OFF
        </div>

        <div class="flex flex-col sm:flex-row sm:items-end gap-5 sm:gap-8 pr-2 sm:pr-28">
          <div class="text-center sm:text-left flex-1">
            <p class="text-[11px] uppercase tracking-[0.18em] font-semibold text-accent/80 mb-2">
              {{ t.specialPriceLabel }}
            </p>
            <div class="flex items-baseline justify-center sm:justify-start gap-3 flex-wrap">
              <span class="text-3xl sm:text-4xl font-bold text-accent leading-none tabular-nums">
                {{ formatCurrency(discountedInvestment) }}
              </span>
              <span class="text-base text-on-primary/50 line-through tabular-nums">
                {{ discountOriginalInvestment ? formatCurrency(discountOriginalInvestment) : totalInvestment }}
              </span>
              <span class="text-xs text-on-primary/70 font-medium">{{ currency }}</span>
              <span class="text-xs text-accent font-semibold">{{ taxLabel }}</span>
            </div>
          </div>
          <!-- Countdown chip -->
          <div
            class="countdown-pill inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface/10 border border-accent/30 text-[11px] font-semibold text-accent self-center sm:self-end whitespace-nowrap"
            :class="{ 'countdown-pulse': urgencyLevel === 'high' }"
            role="status"
            aria-live="polite"
          >
            <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>
              <template v-if="daysRemaining !== null">{{ t.validFor }} {{ daysRemaining }} {{ daysRemaining !== 1 ? t.days : t.day }}</template>
              <template v-else>{{ t.limitedTime }}</template>
            </span>
          </div>
        </div>
      </div>

      <!-- Hosting plan -->
      <div v-if="hostingPlan?.title" data-animate="fade-up" class="hosting-plan mt-12 mb-16 bg-surface p-5 sm:p-8 md:p-10 rounded-2xl border-2 border-primary/10">
        <div class="flex items-center mb-4">
          <div class="w-12 h-12 bg-primary-soft rounded-xl flex items-center justify-center mr-4">
            <span class="text-2xl">☁️</span>
          </div>
          <h3 class="text-2xl font-bold text-text-brand">{{ hostingPlan.title }}</h3>
        </div>
        <p v-if="hostingPlan.description" class="text-text-brand/70 font-light leading-relaxed mb-6 pl-0 sm:pl-16">{{ hostingPlan.description }}</p>

        <div class="mb-6 pl-0 sm:pl-16">
          <div class="grid sm:grid-cols-3 gap-4">
            <div v-for="(card, cIdx) in t.coverageCards" :key="cIdx"
                 class="bg-primary/5 border border-primary/10 rounded-xl p-5 text-center">
              <div class="text-3xl mb-3">{{ card.icon }}</div>
              <div class="font-bold text-text-brand text-sm mb-1">{{ card.title }}</div>
              <p class="text-xs text-text-brand/60 leading-relaxed">{{ card.description }}</p>
            </div>
          </div>
        </div>

        <div v-if="computedBillingTiers.length" class="mt-8 pl-0 sm:pl-16">
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-4 sm:gap-3 md:gap-5 items-stretch">
            <div
              v-for="(tier, tIdx) in computedBillingTiers"
              :key="tIdx"
              class="billing-tier-card relative rounded-2xl p-5 sm:p-4 md:p-6 border-2 transition-all flex flex-col"
              :class="tIdx === 0
                ? 'bg-gradient-to-b from-primary-soft to-surface border-primary ring-2 ring-focus-ring/40 shadow-lg sm:scale-[1.03] z-10'
                : 'bg-surface border-primary/10 hover:border-primary/25 hover:shadow-md'"
            >
              <!-- Badge -->
              <span
                v-if="tier.badge"
                class="absolute -top-3 left-1/2 -translate-x-1/2 sm:left-4 sm:translate-x-0 bg-accent text-text-brand text-[10px] sm:text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap shadow-sm"
              >
                {{ tier.badge }}
              </span>

              <!-- Label -->
              <div class="text-xs uppercase tracking-widest font-semibold mb-3 mt-1"
                   :class="tIdx === 0 ? 'text-text-brand' : 'text-text-brand/50'">
                {{ tier.label }}
              </div>

              <!-- Monthly price -->
              <div class="flex items-baseline gap-1.5 mb-1">
                <span class="text-3xl sm:text-2xl md:text-3xl font-bold text-text-brand leading-none">{{ tier.monthlyPrice }}</span>
                <span class="text-sm text-text-brand/50 font-medium">{{ currency }}</span>
              </div>
              <div class="text-xs text-text-brand/45 font-medium mb-4">{{ t.perMonth }}</div>

              <!-- Spacer to push bottom content down -->
              <div class="flex-1"></div>

              <!-- Discount badge -->
              <div v-if="tier.discountPercent > 0 && !isResolved"
                   class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold mb-2 w-fit"
                   :class="tIdx === 0 ? 'bg-primary-soft text-primary-strong' : 'bg-surface-muted text-text-muted'">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                </svg>
                {{ tier.discountPercent }}% {{ t.discount }}
              </div>

              <!-- Savings -->
              <div v-if="tier.savings"
                   class="text-[11px] font-semibold mb-2"
                   :class="tIdx === 0 ? 'text-text-brand' : 'text-primary'">
                {{ t.youSave }} {{ tier.savings }} {{ currency }}
              </div>

              <!-- Billing frequency -->
              <div class="text-[11px] text-text-brand/40 leading-snug">
                {{ t.billedEvery }} {{ tier.months }} {{ tier.months === 1 ? t.month : t.months }}
              </div>
            </div>
          </div>
        </div>

        <!-- Free month gift bucket -->
        <div v-if="freeMonthsVisible" class="mt-8 pl-0 sm:pl-16">
          <div class="flex items-start gap-4 rounded-2xl border-2 border-accent/40 bg-accent/10 p-5 sm:p-6">
            <div class="text-3xl flex-shrink-0">🎁</div>
            <div>
              <div class="font-bold text-text-brand mb-1">{{ freeMonthTitle }}</div>
              <p class="text-sm text-text-brand/70 font-light leading-relaxed">{{ freeMonthBody }}</p>
            </div>
          </div>
        </div>

        <!-- Collapsible tech specs -->
        <div v-if="filteredSpecs.length" class="mt-6 pl-0 sm:pl-16">
          <button
            class="flex items-center gap-2 text-sm font-medium text-text-brand/60 hover:text-text-brand transition-colors mb-4"
            @click="specsOpen = !specsOpen"
          >
            <svg class="w-4 h-4 transition-transform" :class="{ 'rotate-90': specsOpen }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
            {{ t.viewTechSpecs }}
          </button>
          <Transition name="collapse">
            <div v-if="specsOpen" class="grid md:grid-cols-2 gap-4">
              <div
                v-for="(spec, idx) in filteredSpecs"
                :key="idx"
                class="bg-primary/5 p-5 rounded-xl border border-primary/10"
              >
                <div class="flex items-start">
                  <div class="w-9 h-9 rounded-lg bg-primary-soft border border-primary/10 flex items-center justify-center mr-3 flex-shrink-0">
                    <span class="text-lg">{{ spec.icon }}</span>
                  </div>
                  <div>
                    <div class="font-bold text-text-brand">{{ spec.label }}</div>
                    <div class="text-sm text-text-brand/70">{{ spec.value }}</div>
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>

    </div>

    <ModuleInterestsModal
      :visible="interestsOpen"
      :proposal-uuid="proposalUuid"
      :language="language"
      :preview="preview"
      @close="interestsOpen = false"
    />
  </section>
</template>

<script setup>
import { ref, computed, toRef, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useSectionAnimations } from '~/composables/useSectionAnimations';
import { useExpirationTimer } from '~/composables/useExpirationTimer';
import { useAnimatedNumber } from '~/composables/useAnimatedNumber';
import { useLinkify } from '~/composables/useLinkify';
import { RESOLVED_PROPOSAL_STATUSES, DEFAULT_HOSTING_PERCENT, DEFAULT_BILLING_TIERS } from '~/stores/proposals_constants';
import { ensureProposalTaxLabel, proposalTaxLabel } from '~/utils/proposalTax';
import ModuleInterestsModal from './ModuleInterestsModal.vue';
import InvestmentDetailedTeaser from './InvestmentDetailedTeaser.vue';

const { linkify } = useLinkify();

defineEmits(['navigateToRequirements', 'switchToDetailed']);

const sectionRef = ref(null);
useSectionAnimations(sectionRef);

const specsOpen = ref(false);
const interestsOpen = ref(false);
const customizeBtnRef = ref(null);
const btnPulse = ref(false);
let customizeObserver = null;

const props = defineProps({
  preview: { type: Boolean, default: false },
  language: {
    type: String,
    default: 'es',
  },
  index: {
    type: String,
    default: '9'
  },
  title: {
    type: String,
    default: 'Inversión y Formas de Pago'
  },
  introText: {
    type: String,
    default: 'Conoce el detalle de tu inversión, las formas de pago disponibles y todo lo que incluye tu proyecto.'
  },
  totalInvestment: {
    type: String,
    default: '$1.490.000'
  },
  currency: {
    type: String,
    default: 'COP'
  },
  whatsIncluded: {
    type: Array,
    default: () => [
      { icon: '🎨', title: 'Diseño', description: 'UX/UI enfocado en conversión' },
      { icon: '⚙️', title: 'Desarrollo', description: 'Implementación completa del proyecto' },
      { icon: '📦', title: 'Entrega y despliegue', description: 'Despliegue en producción y puesta en marcha' }
    ]
  },
  paymentOptions: {
    type: Array,
    default: () => [
      { label: '40% al firmar el contrato ✍️', description: '$596.000 COP' },
      { label: '30% al aprobar el diseño final ✅', description: '$447.000 COP' },
      { label: '30% al desplegar el sitio web 🚀', description: '$447.000 COP' }
    ]
  },
  hostingPlan: {
    type: Object,
    default: () => ({
      title: 'Hosting, Mantenimiento y Soporte',
      description: 'Infraestructura optimizada para proyectos de alto rendimiento y disponibilidad:',
      specs: [
        { icon: '🧠', label: 'vCPU', value: '1 núcleo de vCPU' },
        { icon: '🧮', label: 'RAM', value: '1 GB de RAM dedicada' },
        { icon: '💾', label: 'Almacenamiento', value: '2 GB de almacenamiento NVMe' },
        { icon: '🌐', label: 'Ancho de banda', value: '600 GB mensual' },
        { icon: '📍', label: 'Centros de datos', value: 'EE.UU., Brasil, Francia, Lituania e India' },
        { icon: '🧬', label: 'Compatibilidad', value: 'Linux (Ubuntu)' }
      ],
      hostingPercent: DEFAULT_HOSTING_PERCENT,
      monthlyLabel: 'por mes',
      renewalNote: '',
      coverageNote: '',
      freeMonths: 1,
      freeMonthsVisible: true,
      freeMonthNote: ''
    })
  },
  paymentMethods: {
    type: Array,
    default: () => []
  },
  valueReasons: {
    type: Array,
    default: () => [
      'Diseño hecho a medida',
      'Código optimizado',
      'Soporte post-lanzamiento',
    ]
  },
  discountPercent: {
    type: Number,
    default: 0
  },
  discountOriginalInvestment: { type: String, default: '' },
  discountedInvestment: {
    type: String,
    default: ''
  },
  expiresAt: {
    type: String,
    default: ''
  },
  proposalStatus: {
    type: String,
    default: ''
  },
  proposalUuid: {
    type: String,
    default: ''
  },
  whatsappLink: {
    type: String,
    default: ''
  },
  viewMode: {
    type: String,
    default: 'detailed'
  },
  effectiveTotal: {
    type: Number,
    default: null
  },
});

function parseInvestment(str) {
  if (!str) return 0;
  const cleaned = String(str).replace(/[^\d]/g, '');
  return parseInt(cleaned, 10) || 0;
}

const baseNumber = computed(() => parseInvestment(props.totalInvestment));

const effectiveNumber = computed(() => {
  const raw = Number(props.effectiveTotal);
  return Number.isFinite(raw) && raw > 0 ? raw : baseNumber.value;
});

const displayNumber = computed(() => effectiveNumber.value);
const taxLabel = computed(() => proposalTaxLabel(props.currency));


const { animated: displayTotal } = useAnimatedNumber(displayNumber, 500);

onMounted(() => {
  if (props.proposalUuid && props.viewMode !== 'executive') {
    nextTick(() => {
      const el = customizeBtnRef.value;
      if (!el) return;
      customizeObserver = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            btnPulse.value = false;
            void el.offsetWidth;
            btnPulse.value = true;
          } else {
            btnPulse.value = false;
          }
        },
        { rootMargin: '-55% 0px -10% 0px', threshold: 0 }
      );
      customizeObserver.observe(el);
    });
  }
});



onBeforeUnmount(() => customizeObserver?.disconnect());

// Each payment option's amount is derived from its label percentage applied
// to the manually agreed total.
// Source of truth is the label ("40% al firmar..."), not the stored
// description — that avoids double-scaling against backend-rebuilt amounts.
const computedPaymentOptions = computed(() => {
  if (!props.paymentOptions?.length) return props.paymentOptions;
  const target = displayNumber.value;
  if (!target) return props.paymentOptions;

  return props.paymentOptions.map(opt => {
    const pctMatch = String(opt.label || '').match(/(\d+)\s*%/);
    if (!pctMatch) {
      return {
        ...opt,
        description: ensureProposalTaxLabel(opt.description, props.currency),
      };
    }
    const pct = Number(pctMatch[1]) / 100;
    const newAmount = Math.round(target * pct);
    const desc = opt.description || '';
    const newDesc = desc
      ? desc.replace(/[\$]?[\d.,]+/, formatCurrency(newAmount).replace('$', ''))
      : formatCurrency(newAmount);
    const normalizedDescription = newDesc.startsWith('$') ? newDesc : '$' + newDesc;
    return {
      ...opt,
      description: ensureProposalTaxLabel(normalizedDescription, props.currency),
    };
  });
});

const { daysRemaining, urgencyLevel } = useExpirationTimer(toRef(props, 'expiresAt'));

const i18n = {
  es: {
    totalInvestment: 'Inversión Total',
    specialPriceLabel: 'Precio especial por tiempo limitado',
    validFor: 'Válido por',
    days: 'días',
    day: 'día',
    limitedTime: 'tiempo limitado',
    paymentOptions: 'Formas de Pago',
    convenientPayments: 'pagos flexibles',
    specialPrice: 'Precio especial',
    perMonth: '/ mes',
    discount: 'de descuento',
    every: 'cada',
    months: 'meses',
    month: 'mes',
    youSave: 'Te ahorras',
    billedEvery: 'Facturado cada',
    hostingPlans: 'Planes de hosting',
    whyWorthIt: '¿Por Qué Esta Inversión Vale la Pena?',
    viewTechSpecs: 'Ver especificaciones técnicas',
    customizeBtn: 'Explorar módulos adicionales',
    contactCta: 'Comunícate con nosotros',
    whatsappCta: '¿Tienes dudas? Hablemos',
    coverageCards: [
      { icon: '🔧', title: 'Mantenimiento técnico', description: 'Actualizaciones de seguridad, parches y optimización de base de datos' },
      { icon: '🛟', title: 'Soporte ante incidencias', description: 'Resolución de bugs y asistencia técnica continua' },
      { icon: '☁️', title: 'Recursos computacionales', description: 'Servidor, almacenamiento, ancho de banda y certificados SSL' },
    ],
    freeMonthTitleOne: '1 mes de hosting gratis',
    freeMonthTitleMany: (n) => `${n} meses de hosting gratis`,
    freeMonthTitleNone: 'Hosting gratis',
    freeMonthBody: 'Los cobros del hosting inician el día 1° de cada mes. Desde la entrega de tu proyecto hasta tu primer cobro, el hosting es gratis: siempre te regalamos como mínimo un mes completo.',
  },
  en: {
    totalInvestment: 'Total Investment',
    specialPriceLabel: 'Special price — limited time',
    validFor: 'Valid for',
    days: 'days',
    day: 'day',
    limitedTime: 'a limited time',
    paymentOptions: 'Payment Options',
    convenientPayments: 'flexible payments',
    specialPrice: 'Special price',
    perMonth: '/ month',
    discount: 'discount',
    every: 'every',
    months: 'months',
    month: 'month',
    youSave: 'You save',
    billedEvery: 'Billed every',
    hostingPlans: 'Hosting plans',
    whyWorthIt: 'Why Is This Investment Worth It?',
    viewTechSpecs: 'View technical specs',
    customizeBtn: 'Explore additional modules',
    contactCta: 'Get in touch with us',
    whatsappCta: 'Have questions? Let\'s talk',
    coverageCards: [
      { icon: '🔧', title: 'Technical Maintenance', description: 'Security updates, patches, and database optimization' },
      { icon: '🛟', title: 'Incident Support', description: 'Bug resolution and ongoing technical assistance' },
      { icon: '☁️', title: 'Computing Resources', description: 'Server, storage, bandwidth, and SSL certificates' },
    ],
    freeMonthTitleOne: '1 free month of hosting',
    freeMonthTitleMany: (n) => `${n} free months of hosting`,
    freeMonthTitleNone: 'Free hosting',
    freeMonthBody: 'Hosting billing starts on the 1st of each month. From your project delivery until your first charge, hosting is free: we always gift you at least one full month.',
  },
};

const t = computed(() => i18n[props.language] || i18n.es);

// Free-month gift: shown as a highlighted bucket. Visibility is the explicit
// hostingPlan.freeMonthsVisible flag, resolved by the backend's
// normalize_hosting_plan; content written before the flag existed has no key
// and falls back to the old rule (a non-zero count meant visible). The count
// now only feeds the title, and the copy can be overridden per-proposal via
// hostingPlan.freeMonthNote.
const freeMonthsCount = computed(() => Number(props.hostingPlan?.freeMonths) || 0);
const freeMonthsVisible = computed(() => {
  const flag = props.hostingPlan?.freeMonthsVisible;
  if (flag !== undefined && flag !== null) return Boolean(flag);
  return freeMonthsCount.value > 0;
});
const freeMonthTitle = computed(() => {
  const n = freeMonthsCount.value;
  if (n <= 0) return t.value.freeMonthTitleNone;
  return n === 1 ? t.value.freeMonthTitleOne : t.value.freeMonthTitleMany(n);
});
const freeMonthBody = computed(() => {
  const custom = props.hostingPlan?.freeMonthNote;
  return (custom && String(custom).trim()) || t.value.freeMonthBody;
});

// Once the proposal is resolved (accepted/rejected/finished) the urgency /
// limited-time pricing notices no longer apply and must stay hidden.
const isResolved = computed(() =>
  RESOLVED_PROPOSAL_STATUSES.includes(props.proposalStatus));

const hasActiveDiscount = computed(() => {
  return props.discountPercent > 0 && props.discountedInvestment && !isResolved.value;
});

function formatCurrency(value) {
  if (!value) return '';
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return '$' + num.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

const hostingTwelveMonthReference = computed(() => {
  const hp = props.hostingPlan;
  // Hosting follows the manually agreed investment.
  if (hp?.hostingPercent > 0) {
    const total = displayNumber.value;
    if (total > 0) return Math.round(total * hp.hostingPercent / 100);
  }
  return null;
});


const computedBillingTiers = computed(() => {
  const hp = props.hostingPlan;
  if (hostingTwelveMonthReference.value === null) return [];

  const tiers = hp?.billingTiers?.length ? hp.billingTiers : DEFAULT_BILLING_TIERS;

  const monthlyBase = Math.round(hostingTwelveMonthReference.value / 12);
  if (monthlyBase <= 0) return [];

  return tiers.map(tier => {
    const discount = tier.discountPercent || 0;
    const months = tier.months || 1;
    const monthlyDiscounted = Math.round(monthlyBase * (100 - discount) / 100);
    const savingsPerPeriod = (monthlyBase - monthlyDiscounted) * months;

    return {
      ...tier,
      monthlyPrice: formatCurrency(monthlyDiscounted),
      savings: savingsPerPeriod > 0 ? formatCurrency(savingsPerPeriod) : null,
    };
  });
});


const filteredSpecs = computed(() => {
  return (props.hostingPlan?.specs || []).filter(s => s.label || s.value);
});

const normalizedReasons = computed(() => {
  if (!props.valueReasons?.length) return [];
  return props.valueReasons.map(r => typeof r === 'string' ? r : (r.description || r.title || ''));
});
</script>

<style scoped>
.payment-option-card {
  transition: all 0.3s ease;
}

.payment-option-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.1);
}

.value-reason {
  transition: transform 0.3s ease;
}

.value-reason:hover {
  transform: translateX(8px);
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}

.collapse-enter-to,
.collapse-leave-from {
  opacity: 1;
  max-height: 600px;
}

.billing-tier-card {
  transition: all 0.3s ease;
}

.billing-tier-card:hover {
  transform: translateY(-2px);
}

.btn-pulse {
  animation: glowRays 4s ease-in-out;
}

@keyframes countdownPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.countdown-pulse {
  animation: countdownPulse 2s ease-in-out infinite;
}

@keyframes glowRays {
  0%   { filter: drop-shadow(0 0 0 rgba(225, 255, 0, 0)); }
  12%  { filter: drop-shadow(0 0 14px rgba(225, 255, 0, 0.8)) drop-shadow(0 0 30px rgba(255, 255, 255, 0.35)); }
  30%  { filter: drop-shadow(0 0 0 rgba(225, 255, 0, 0)); }
  50%  { filter: drop-shadow(0 0 14px rgba(225, 255, 0, 0.8)) drop-shadow(0 0 30px rgba(255, 255, 255, 0.35)); }
  68%  { filter: drop-shadow(0 0 0 rgba(225, 255, 0, 0)); }
  100% { filter: drop-shadow(0 0 0 rgba(225, 255, 0, 0)); }
}
</style>
