<template>
  <section ref="sectionRef" class="proposal-closing min-h-screen w-full bg-surface flex flex-col items-center justify-center py-8 px-6 md:px-12 lg:px-24">
    <div class="max-w-4xl w-full mx-auto text-center flex flex-col items-center gap-6">
      <!-- Validity notice -->
      <div v-if="displayedValidity" ref="validityRef" data-animate="fade-up" class="validity-notice w-full bg-primary/5 border border-primary/15 p-4 md:p-6 rounded-xl text-left">
        <div class="flex items-start">
          <svg class="w-5 h-5 text-text-brand/60 mr-3 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
          </svg>
          <div>
            <h4 class="font-bold text-text-brand mb-1 text-sm md:text-base">{{ t.validityTitle }}</h4>
            <p class="text-xs md:text-sm text-text-brand/70">{{ displayedValidity }}</p>
          </div>
        </div>
      </div>

      <!-- Thank you message -->
      <div v-if="thankYouMessage" data-animate="fade-up">
        <h3 class="text-2xl md:text-3xl font-bold text-text-brand mb-2">{{ t.thankYouTitle }}</h3>
        <p class="text-base md:text-lg text-text-brand/70 font-light max-w-2xl mx-auto" v-html="linkify(thankYouMessage)" />
      </div>

      <!-- Commercial CTA and contact channels belong to the final closing panel. -->
      <div
        v-if="ctaMessage || primaryCTA?.link || secondaryCTA?.text || contactMethods?.length"
        data-animate="fade-up"
        data-testid="proposal-ready-contact"
        class="w-full bg-primary rounded-3xl p-5 sm:p-8 md:p-10 text-center shadow-2xl"
      >
        <h3 class="text-2xl sm:text-3xl font-bold text-accent mb-3">{{ t.readyTitle }}</h3>
        <p
          v-if="ctaMessage"
          class="text-base sm:text-lg text-white/85 leading-relaxed mb-6 max-w-2xl mx-auto"
          v-html="linkify(ctaMessage)"
        />
        <div v-if="primaryCTA?.link || secondaryCTA?.text" class="flex flex-col sm:flex-row gap-3 justify-center mb-7">
          <a
            v-if="primaryCTA?.link"
            :href="primaryCTA.link"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center justify-center px-6 py-3 bg-accent text-text-brand rounded-xl font-bold hover:opacity-90 transition-opacity"
          >
            {{ primaryCTA.text }}
          </a>
          <button
            v-if="secondaryCTA?.text"
            type="button"
            data-cal-link="projectapp/discovery-call-projectapp"
            data-cal-namespace="discovery-call-projectapp"
            data-cal-config='{"layout":"month_view","useSlotsViewOnSmallScreen":"true"}'
            class="inline-flex items-center justify-center px-6 py-3 bg-primary-strong text-accent rounded-xl font-bold hover:opacity-85 transition-opacity cursor-pointer"
          >
            {{ secondaryCTA.text }}
          </button>
        </div>
        <div v-if="contactMethods?.length" class="grid sm:grid-cols-3 gap-3">
          <a
            v-for="(contact, cIdx) in contactMethods"
            :key="cIdx"
            :href="contact.link || undefined"
            target="_blank"
            rel="noopener noreferrer"
            class="contact-card bg-surface/10 border border-white/15 rounded-xl p-4 text-white hover:bg-surface/15 transition-colors"
          >
            <span class="block text-2xl mb-2">{{ contact.icon }}</span>
            <span class="block text-sm font-bold">{{ contact.title }}</span>
            <span class="block text-xs text-white/75 mt-1 break-words">{{ contact.value }}</span>
          </a>
        </div>
      </div>

      <!-- Discount badge near accept button -->
      <div v-if="canRespond && !submitted && hasActiveDiscount" data-animate="fade-up" class="w-full max-w-md bg-accent/20 border border-accent/50 rounded-xl p-4 text-center">
        <p class="text-xs font-semibold text-text-brand uppercase tracking-wider mb-1">🔥 {{ t.specialPrice }}</p>
        <div class="flex items-baseline justify-center gap-2">
          <span class="text-2xl font-bold text-text-brand">{{ formatCurrency(proposal?.discounted_investment) }}</span>
          <span class="text-sm text-text-brand/40 line-through">{{ formatCurrency(effectiveTotal) }}</span>
          <span class="text-xs text-text-brand/60">{{ proposal?.currency }}</span>
          <span class="text-xs font-semibold text-text-brand/70">{{ taxLabel }}</span>
        </div>
      </div>

      <!-- F12: Payment plan milestones -->
      <div v-if="canRespond && !submitted && paymentMilestones.length" data-animate="fade-up" class="w-full max-w-md bg-primary/5 border border-primary/15 rounded-xl p-4 text-left">
        <p class="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">{{ t.paymentPlanTitle }}</p>
        <div class="space-y-2">
          <div v-for="(m, i) in paymentMilestones" :key="i" class="flex items-center gap-3">
            <span class="w-6 h-6 rounded-full bg-primary-soft text-text-brand text-xs font-bold flex items-center justify-center flex-shrink-0">{{ i + 1 }}</span>
            <div class="flex-1 min-w-0">
              <span class="text-sm font-medium text-text-brand/80">{{ m.label }}</span>
              <span class="text-sm text-text-brand font-bold ml-2">{{ m.amount }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Payment options breakdown — visible before accept -->
      <div v-if="canRespond && !submitted && closingPaymentOptions.length" data-animate="fade-up" class="w-full max-w-lg bg-primary rounded-2xl p-5 text-left">
        <p class="text-xs font-semibold text-white uppercase tracking-wider mb-1">{{ t.paymentPlanTitle }}</p>
        <p class="text-lg font-bold text-white mb-3">{{ closingPaymentOptions.length }} {{ t.flexiblePayments }}</p>
        <div class="space-y-2">
          <div v-for="(opt, i) in closingPaymentOptions" :key="i" class="flex items-center justify-between gap-3 bg-surface/10 rounded-xl px-4 py-3">
            <span class="text-sm text-white/80">{{ opt.label }}</span>
            <span class="text-sm font-bold text-white whitespace-nowrap">{{ opt.description }}</span>
          </div>
        </div>
        <div v-if="effectiveTotal" class="text-center mt-4 pt-3 border-t border-border-default/15">
          <span class="text-xs text-white/70">{{ t.scopeInvestment }}:</span>
          <span class="text-lg font-bold text-white ml-2">{{ formatCurrency(effectiveTotal) }}</span>
          <span class="text-xs text-white/70 ml-1">{{ proposal.currency }}</span>
          <span class="text-xs font-semibold text-accent ml-1">{{ taxLabel }}</span>
        </div>
      </div>

      <!-- Action buttons — professional B2B hierarchy -->
      <div v-if="canRespond && !submitted" data-animate="fade-up" class="w-full max-w-md pt-4 border-t border-border-default/10">
        <!-- Primary CTA -->
        <button
          class="w-full py-4 bg-gradient-to-br from-primary to-primary-strong text-accent rounded-2xl font-bold text-lg
                 hover:opacity-95 transition-all
                 shadow-[0_4px_20px_rgba(16,185,129,0.25)] hover:shadow-[0_6px_28px_rgba(16,185,129,0.38)]
                 flex items-center justify-center gap-2.5 accept-pulse disabled:opacity-60 disabled:cursor-not-allowed"
          :disabled="isSubmitting"
          @click="showAcceptConfirm = true"
        >
          <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          {{ t.acceptBtn }}
        </button>

        <!-- Secondary actions — side by side -->
        <div class="grid grid-cols-2 gap-3 mt-3">
          <button
            class="py-3 bg-surface/8 border border-primary/25 text-text-brand rounded-xl font-medium text-sm
                   hover:bg-surface/15 hover:border-primary/40 transition-all shadow-sm
                   flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            :disabled="isSubmitting"
            @click="showNegotiateModal = true"
          >
            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7 11.5V14m0-2.5v-6a1.5 1.5 0 113 0m-3 6a1.5 1.5 0 00-3 0v2a7.5 7.5 0 0015 0v-5a1.5 1.5 0 00-3 0m-6-3V11m0-5.5v-1a1.5 1.5 0 013 0v1m0 0V11m0-5.5a1.5 1.5 0 013 0v3m0 0V11" />
            </svg>
            {{ t.negotiateBtn }}
          </button>
          <button
            class="py-3 bg-surface/8 border border-primary/25 text-text-brand rounded-xl font-medium text-sm
                   hover:bg-surface/15 hover:border-primary/40 transition-all shadow-sm
                   flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            :disabled="isSubmitting"
            @click="showCommentModal = true"
          >
            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            {{ t.commentBtn }}
          </button>
        </div>

        <!-- Tertiary links — inline, subtle -->
        <div class="flex items-center justify-center gap-3 mt-4">
          <button
            class="text-xs text-text-brand/50 hover:text-text-brand/75 transition-colors font-medium tracking-wide disabled:opacity-40"
            :disabled="isSubmitting"
            @click="showRejectModal = true"
          >
            {{ t.rejectBtn }}
          </button>
          <span v-if="whatsappTalkUrl" class="text-text-brand/25 select-none">·</span>
          <a
            v-if="whatsappTalkUrl"
            :href="whatsappTalkUrl"
            target="_blank"
            class="text-xs text-text-brand/50 hover:text-text-brand/75 transition-colors font-medium tracking-wide flex items-center gap-1.5"
          >
            <svg class="w-3.5 h-3.5 shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
            </svg>
            {{ t.talkBtn }}
          </a>
        </div>
      </div>

      <!-- Comment submitted confirmation -->
      <div v-if="commentSubmitted && canRespond && !submitted" data-animate="fade-up" class="w-full max-w-md bg-primary/5 border border-primary/15 rounded-xl p-4 text-center">
        <p class="text-sm font-medium text-text-brand">✅ {{ t.commentSent }}</p>
      </div>

      <!-- F13: Post-acceptance welcome kit -->
      <div v-if="submitted || proposal?.status === 'accepted'" data-animate="fade-up" class="py-4 w-full max-w-lg">
        <div class="text-5xl mb-3 celebration-bounce">🎉</div>
        <p class="text-xl font-bold text-text-brand">{{ t.accepted }}</p>
        <p class="text-text-brand/70 mt-2 mb-6">{{ t.acceptedSub }}</p>

        <!-- Payment options breakdown -->
        <div v-if="closingPaymentOptions.length" class="w-full bg-primary p-5 rounded-2xl text-left mb-6">
          <p class="text-xs font-semibold text-accent uppercase tracking-wider mb-1">{{ t.paymentPlanTitle }}</p>
          <p class="text-lg font-bold text-accent mb-3">{{ closingPaymentOptions.length }} {{ t.flexiblePayments }}</p>
          <div class="space-y-2">
            <div v-for="(opt, i) in closingPaymentOptions" :key="i" class="flex items-center justify-between gap-3 bg-surface/10 rounded-xl px-4 py-3">
              <span class="text-sm text-accent/80">{{ opt.label }}</span>
              <span class="text-sm font-bold text-accent whitespace-nowrap">{{ opt.description }}</span>
            </div>
          </div>
          <div v-if="effectiveTotal" class="text-center mt-4 pt-3 border-t border-border-default/15">
            <span class="text-xs text-accent/70">{{ t.scopeInvestment }}:</span>
            <span class="text-lg font-bold text-accent ml-2">{{ formatCurrency(effectiveTotal) }}</span>
            <span class="text-xs text-accent/70 ml-1">{{ proposal.currency }}</span>
            <span class="text-xs font-semibold text-accent ml-1">{{ taxLabel }}</span>
          </div>
        </div>

        <!-- PDF download -->
        <a
          v-if="proposal?.uuid"
          :href="pdfExpired ? undefined : pdfUrl"
          :aria-disabled="pdfExpired || pdfGenerating"
          :aria-describedby="pdfMessage ? pdfMessageId : undefined"
          @click.prevent="downloadPdf"
          :download="pdfFilename"
          target="_blank"
          class="inline-flex items-center gap-2 px-6 py-3 bg-primary text-accent rounded-xl font-bold text-sm hover:bg-primary-strong transition-colors shadow-sm mb-6"
        >
          📄 {{ t.downloadPdf }}
        </a>
        <p v-if="pdfMessage" :id="pdfMessageId" role="status" class="mb-6 text-sm text-text-default">
          {{ pdfMessage }}
        </p>

        <!-- Onboarding timeline -->
        <div class="bg-primary/5 border border-primary/15 rounded-xl p-5 text-left space-y-4">
          <h4 class="font-bold text-text-brand text-sm">{{ t.onboardingTitle }}</h4>
          <div v-for="(step, i) in onboardingSteps" :key="i" class="flex items-start gap-3">
            <div class="w-8 h-8 rounded-full bg-accent text-text-brand text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{{ i + 1 }}</div>
            <div>
              <p class="text-sm font-medium text-text-brand">{{ step.title }}</p>
              <p class="text-xs text-text-brand/70">{{ step.desc }}</p>
            </div>
          </div>
        </div>

        <!-- PM WhatsApp contact -->
        <a
          v-if="whatsappTalkUrl"
          :href="whatsappTalkUrl"
          target="_blank"
          class="inline-flex items-center gap-2 px-5 py-2.5 bg-primary/5 border border-primary/15 text-text-brand rounded-xl text-sm font-medium hover:bg-primary/10 transition-colors mt-4"
        >
          💬 {{ t.contactPm }}
        </a>
      </div>

      <!-- Negotiating success -->
      <div v-else-if="negotiatingSubmitted || proposal?.status === 'negotiating'" data-animate="fade-up" class="py-4 w-full max-w-lg">
        <div class="text-5xl mb-3 celebration-bounce">🤝</div>
        <p class="text-xl font-bold text-warning-strong">{{ t.negotiatingSuccess }}</p>
        <p class="text-text-subtle mt-2">{{ t.negotiatingSub }}</p>
      </div>

      <!-- Smart rejection recovery (Feature 12) -->
      <div v-else-if="rejectionSubmitted || proposal?.status === 'rejected'" data-animate="fade-up" class="py-4 w-full max-w-lg">
        <p class="text-lg text-text-subtle mb-6">{{ t.rejected }}</p>

        <!-- Budget too high -->
        <div v-if="submittedReason === t.reasons[0]" class="bg-primary-soft border border-border-default rounded-xl p-5 text-left">
          <h4 class="font-bold text-text-brand mb-2">💡 {{ t.recovery.budgetTitle }}</h4>
          <p class="text-sm text-text-brand mb-4">{{ t.recovery.budgetText }}</p>
          <a :href="whatsappRecoveryLink" target="_blank" class="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-accent rounded-xl text-sm font-medium hover:bg-primary-strong transition-colors">
            💬 {{ t.recovery.budgetCta }}
          </a>
        </div>

        <!-- Not the right time -->
        <div v-else-if="submittedReason === t.reasons[2]" class="bg-primary-soft border border-border-default rounded-xl p-5 text-left">
          <h4 class="font-bold text-text-brand mb-2">⏰ {{ t.recovery.timeTitle }}</h4>
          <p class="text-sm text-text-brand mb-4">{{ t.recovery.timeText }}</p>
          <button
            v-if="!followupScheduled"
            class="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-accent rounded-xl text-sm font-medium hover:bg-primary-strong transition-colors"
            :disabled="isScheduling"
            @click="scheduleReminder"
          >
            🔔 {{ isScheduling ? t.sending : t.recovery.timeCta }}
          </button>
          <p v-else class="text-sm font-medium text-text-brand">✅ {{ t.recovery.timeScheduled }}</p>
        </div>

        <!-- Found another option -->
        <div v-else-if="submittedReason === t.reasons[1]" class="bg-surface-muted border border-border-default rounded-xl p-5 text-left">
          <h4 class="font-bold text-text-default mb-2">🤝 {{ t.recovery.otherTitle }}</h4>
          <p class="text-sm text-text-muted">{{ t.recovery.otherText }}</p>
        </div>

        <!-- Does not meet expectations -->
        <div v-else-if="submittedReason === t.reasons[3]" class="bg-primary-soft border border-border-default rounded-xl p-5 text-left">
          <h4 class="font-bold text-text-brand mb-2">🎯 {{ t.recovery.expectTitle }}</h4>
          <p class="text-sm text-text-brand mb-4">{{ t.recovery.expectText }}</p>
          <a :href="whatsappRecoveryLink" target="_blank" class="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-accent rounded-xl text-sm font-medium hover:bg-primary-strong transition-colors">
            💬 {{ t.recovery.expectCta }}
          </a>
        </div>

        <!-- Generic / Other -->
        <div v-else class="bg-surface-muted border border-border-default rounded-xl p-5 text-left">
          <h4 class="font-bold text-text-default mb-2">🙏 {{ t.recovery.genericTitle }}</h4>
          <p class="text-sm text-text-muted">{{ t.recovery.genericText }}</p>
        </div>
      </div>
    </div>
  </section>

  <!-- F16: Accept confirmation modal with optional condition note -->
  <teleport to="body">
    <div v-if="showAcceptConfirm" class="fixed inset-0 z-[9990] flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="showAcceptConfirm = false">
      <div class="bg-surface rounded-2xl shadow-2xl max-w-md w-full mx-4 p-5 sm:p-8 text-center">
        <div class="text-5xl mb-4">🎉</div>
        <h3 class="text-xl font-bold text-text-brand mb-2">{{ confirmTitleText }}</h3>
        <p class="text-text-brand/70 text-sm mb-4">{{ t.confirmText }}</p>
        <p v-if="scopeDisplay.length" class="text-xs text-text-muted mb-4">
          {{ scopeDisplay.map(i => `${i.label}: ${i.value}`).join(' · ') }}
        </p>
        <div class="text-left mb-4">
          <label class="block text-xs text-text-brand/50 mb-1">{{ t.conditionLabel }}</label>
          <textarea
            v-model="conditionNote"
            rows="2"
            :placeholder="t.conditionPlaceholder"
            class="w-full px-3 py-2 border border-primary/15 rounded-xl text-sm focus:ring-2 focus:ring-focus-ring outline-none resize-none bg-input-bg text-input-text"
          />
        </div>
        <div class="flex gap-3 justify-center">
          <button class="px-6 py-2.5 bg-primary text-accent rounded-xl font-medium text-sm hover:bg-primary-strong transition-colors" :disabled="isSubmitting" @click="confirmAccept">
            {{ isSubmitting ? t.sending : t.confirmYes }}
          </button>
          <button class="px-6 py-2.5 bg-primary/5 text-text-brand rounded-xl text-sm font-medium hover:bg-primary/10 transition-colors" @click="showAcceptConfirm = false">{{ t.cancel }}</button>
        </div>
      </div>
    </div>
  </teleport>

  <!-- Negotiate modal — adjustments only -->
  <teleport to="body">
    <div v-if="showNegotiateModal" class="fixed inset-0 z-[9990] flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="showNegotiateModal = false">
      <div class="bg-surface rounded-2xl shadow-2xl max-w-lg w-full mx-4 p-5 sm:p-8">
        <h3 class="text-xl font-bold text-text-default mb-2">{{ t.negotiateTitle }}</h3>
        <p class="text-text-muted text-sm mb-4">{{ t.negotiateText }}</p>

        <!-- Structured adjustment reasons -->
        <div class="space-y-2 mb-4">
          <label
            v-for="reason in t.adjustmentReasons"
            :key="reason"
            class="flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors"
            :class="selectedAdjustments.includes(reason) ? 'bg-warning-soft border-warning-strong' : 'border-border-default hover:border-warning-strong'"
          >
            <input type="checkbox" :value="reason" v-model="selectedAdjustments" class="w-4 h-4 accent-warning-strong rounded" />
            <span class="text-sm text-text-default">{{ reason }}</span>
          </label>
        </div>

        <textarea
          v-model="negotiateComment"
          rows="3"
          :placeholder="t.negotiatePlaceholder"
          class="w-full px-4 py-3 border border-input-border rounded-xl text-sm focus:ring-2 focus:ring-focus-ring outline-none resize-none bg-input-bg text-input-text"
        />

        <div class="flex gap-3 justify-end mt-4">
          <button class="px-5 py-2 bg-surface-muted text-text-muted rounded-xl text-sm font-medium hover:bg-surface-raised transition-colors" @click="showNegotiateModal = false">{{ t.cancel }}</button>
          <button
            class="px-5 py-2 bg-warning-strong text-text-default rounded-xl text-sm font-medium hover:opacity-90 transition-colors"
            :disabled="isSubmitting || (!negotiateComment.trim() && !selectedAdjustments.length)"
            @click="confirmNegotiate"
          >
            {{ negotiateCtaText }}
          </button>
        </div>
      </div>
    </div>
  </teleport>

  <!-- Comment modal — lightweight, separate from negotiate -->
  <teleport to="body">
    <div v-if="showCommentModal" class="fixed inset-0 z-[9990] flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="showCommentModal = false">
      <div class="bg-surface rounded-2xl shadow-2xl max-w-md w-full mx-4 p-5 sm:p-8">
        <h3 class="text-lg font-bold text-text-default mb-2">💬 {{ t.commentBtn }}</h3>
        <p class="text-text-subtle text-sm mb-4">{{ t.commentPlaceholder2 }}</p>

        <textarea
          v-model="negotiationComment"
          rows="3"
          :placeholder="t.commentPlaceholder2"
          class="w-full px-4 py-3 border border-input-border rounded-xl text-sm focus:ring-2 focus:ring-focus-ring outline-none resize-none bg-input-bg text-input-text"
        />

        <div class="flex gap-3 justify-end mt-4">
          <button class="px-5 py-2 bg-surface-muted text-text-muted rounded-xl text-sm font-medium hover:bg-surface-raised transition-colors" @click="showCommentModal = false">{{ t.cancel }}</button>
          <button
            class="px-5 py-2 bg-primary text-accent rounded-xl text-sm font-medium hover:bg-primary-strong transition-colors"
            :disabled="isCommenting || !negotiationComment.trim()"
            @click="submitComment"
          >
            {{ isCommenting ? t.sending : t.commentSend }}
          </button>
        </div>
      </div>
    </div>
  </teleport>

  <!-- Reject modal -->
  <teleport to="body">
    <div v-if="showRejectModal" class="fixed inset-0 z-[9990] flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="showRejectModal = false">
      <div class="bg-surface rounded-2xl shadow-2xl max-w-lg w-full mx-4 p-5 sm:p-8">
        <h3 class="text-xl font-bold text-text-default mb-2">{{ t.rejectTitle }}</h3>
        <p class="text-text-muted text-sm mb-6">{{ t.rejectText }}</p>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">{{ t.reasonLabel }}</label>
            <p class="text-xs text-text-subtle italic mb-2">{{ t.reasonNudge }}</p>
            <select v-model="rejectReason" class="w-full px-4 py-2.5 border border-input-border rounded-xl text-sm focus:ring-2 focus:ring-focus-ring outline-none bg-input-bg text-input-text">
              <option value="">{{ t.selectReason }}</option>
              <option v-for="reason in t.reasons" :key="reason" :value="reason">{{ reason }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">{{ isOtherReason ? t.otherLabel : t.commentLabel }}</label>
            <textarea v-model="rejectComment" rows="3" :placeholder="isOtherReason ? t.otherPlaceholder : t.commentPlaceholder"
              class="w-full px-4 py-2.5 border border-input-border rounded-xl text-sm focus:ring-2 focus:ring-focus-ring outline-none resize-none bg-input-bg text-input-text" />
          </div>
        </div>
        <div class="flex gap-3 justify-end mt-6">
          <button class="px-5 py-2 bg-surface-muted text-text-muted rounded-xl text-sm font-medium hover:bg-surface-raised transition-colors" @click="showRejectModal = false">{{ t.cancel }}</button>
          <button class="px-5 py-2 bg-danger-strong text-text-default rounded-xl text-sm font-medium hover:opacity-90 transition-colors" :disabled="isSubmitting" @click="confirmReject">
            {{ isSubmitting ? t.sending : t.confirmReject }}
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, useId } from 'vue';
import { useProposalPdfDownload } from '~/composables/useProposalPdfDownload';
import { useSectionAnimations } from '~/composables/useSectionAnimations';
import { linkify } from '~/composables/useLinkify';
import { ensureProposalTaxLabel, proposalTaxLabel } from '~/utils/proposalTax';
import confetti from 'canvas-confetti';

const sectionRef = ref(null);
const validityRef = ref(null);
useSectionAnimations(sectionRef);

const props = defineProps({
  proposal: { type: Object, default: null },
  validityMessage: { type: String, default: '' },
  thankYouMessage: { type: String, default: '' },
  expiresAt: { type: String, default: '' },
  language: { type: String, default: 'es' },
  whatsappLink: { type: String, default: '' },
  paymentOptions: { type: Array, default: () => [] },
  investmentTotal: { type: Number, default: null },
  viewMode: { type: String, default: 'detailed' },
  ctaMessage: { type: String, default: '' },
  primaryCTA: { type: Object, default: () => ({}) },
  secondaryCTA: { type: Object, default: () => ({}) },
  contactMethods: { type: Array, default: () => [] },
});

// Use the resolved manual total supplied by the proposal page.
const effectiveTotal = computed(() => props.investmentTotal ?? props.proposal?.total_investment);
const taxLabel = computed(() => proposalTaxLabel(props.proposal?.currency));

const whatsappTalkUrl = computed(() => {
  if (props.whatsappLink) return props.whatsappLink;
  const title = props.proposal?.title || '';
  if (!title) return '';
  const msg = props.language === 'en'
    ? encodeURIComponent(`Hi, I'm reviewing the proposal "${title}" and I'd like to talk before making a decision.`)
    : encodeURIComponent(`Hola, estoy revisando la propuesta "${title}" y me gustaría hablar antes de tomar una decisión.`);
  return `https://wa.me/573238122373?text=${msg}`;
});

const i18nStrings = {
  es: {
    validityTitle: 'Validez de la Propuesta',
    thankYouTitle: '¡Gracias por tu Tiempo!',
    readyTitle: '¿Listo para comenzar?',
    acceptBtn: 'Acepto la propuesta',
    negotiateBtn: 'Necesito ajustes',
    negotiateTitle: 'Me interesa, pero negociemos alcance',
    negotiateText: 'Cuéntanos qué ajustes necesitas. Nuestro equipo te contactará para conversar opciones sin compromiso.',
    negotiatePlaceholder: 'Ej: Me gustaría reducir el número de módulos, ajustar el timeline, explorar un precio diferente...',
    negotiateConfirm: 'Enviar solicitud de ajustes',
    negotiatingSuccess: '¡Solicitud recibida!',
    negotiatingSub: 'Nuestro equipo revisará tus notas y te contactará pronto para conversar opciones.',
    talkBtn: 'Prefiero hablar antes de decidir',
    commentBtn: 'Tengo comentarios',
    commentTitle: 'Tus comentarios nos ayudan',
    commentText: 'Sin compromiso — cuéntanos qué dudas tienes o qué ajustes necesitarías para avanzar.',
    commentPlaceholder2: 'Ej: El precio está un poco fuera de mi presupuesto, ¿podemos explorar opciones?',
    commentSend: 'Enviar mensaje',
    commentSent: 'Mensaje enviado. Te contactaremos pronto.',
    rejectBtn: 'No es el momento',
    confirmTitle: '¡Perfecto{clientName}!',
    confirmText: 'Te escribiremos en menos de 2 horas. Mientras, puedes descargar un resumen de lo acordado.',
    confirmYes: '¡Confirmar!',
    cancel: 'Cancelar',
    sending: 'Enviando...',
    accepted: '¡Propuesta aceptada!',
    acceptedSub: 'Te enviaremos un email de confirmación. Nuestro equipo revisará los datos y documentos antes de vincular el proyecto.',
    rejected: 'Propuesta rechazada. Gracias por tu tiempo.',
    rejectTitle: 'Lamentamos que no sea el momento',
    rejectText: 'Tu opinión es muy importante para nosotros. ¿Podrías indicarnos el motivo?',
    reasonLabel: 'Motivo (opcional)',
    reasonNudge: 'Nos ayudaría mucho saber por qué — tu respuesta es opcional y confidencial.',
    selectReason: 'Selecciona un motivo...',
    reasons: ['Presupuesto muy alto', 'Encontré otra opción', 'No es el momento', 'No cumple mis expectativas', 'Otros'],
    otherReason: 'Otros',
    otherLabel: 'Cuéntanos más',
    commentLabel: 'Comentario adicional (opcional)',
    otherPlaceholder: 'Escribe tu motivo aquí...',
    commentPlaceholder: 'Algún comentario adicional...',
    confirmReject: 'Confirmar rechazo',
    specialPrice: 'Precio especial disponible',
    paymentPlanTitle: 'Formas de pago',
    flexiblePayments: 'pagos flexibles',
    downloadPdf: 'Descargar resumen PDF',
    onboardingTitle: '¿Qué sigue?',
    contactPm: 'Contactar a tu Project Manager',
    conditionLabel: '¿Aceptas con alguna condición? (opcional)',
    conditionPlaceholder: 'Ej: Acepto, pero necesito que se incluya X...',
    adjustmentReasons: [
      'El presupuesto es alto para este momento',
      'Necesito ajustar el alcance o quitar módulos',
      'Los tiempos de entrega no me funcionan',
      'Quiero agregar o cambiar funcionalidades',
      'Necesito aprobación de otro decisor',
      'Otro ajuste',
    ],
    negotiateConfirmOne: 'Enviar solicitud de ajuste',
    negotiateConfirmMultiple: 'Enviar {count} ajustes',
    scopeSummaryTitle: 'Estás aprobando:',
    scopeProject: 'Proyecto',
    scopeInvestment: 'Inversión',
    scopeModules: 'Módulos',
    scopeStart: 'Inicio estimado',
    recovery: {
      budgetTitle: '¿Qué tal una versión más enfocada?',
      budgetText: 'Entendemos. Podemos ajustar el alcance del proyecto para adaptarnos a tu presupuesto. ¿Te gustaría explorar opciones?',
      budgetCta: 'Explorar opciones',
      timeTitle: '¿Te recordamos más adelante?',
      timeText: 'Sin problema. Podemos recordarte en 3 meses para retomar la conversación cuando sea más oportuno.',
      timeCta: 'Recordármelo en 3 meses',
      timeScheduled: 'Listo, te recordaremos en 3 meses.',
      otherTitle: 'Gracias por tu honestidad',
      otherText: 'Apreciamos tu transparencia. Si algo cambia o necesitas una segunda opinión, estaremos aquí.',
      expectTitle: 'Queremos entender mejor',
      expectText: '¿Te gustaría agendar 15 minutos para contarnos qué esperabas? Podemos ajustar la propuesta.',
      expectCta: 'Conversemos',
      genericTitle: 'Gracias por tu tiempo',
      genericText: 'Valoramos tu opinión. Si en el futuro necesitas algo, no dudes en contactarnos.',
    },
  },
  en: {
    validityTitle: 'Proposal Validity',
    thankYouTitle: 'Thank You for Your Time!',
    readyTitle: 'Ready to get started?',
    acceptBtn: 'I accept the proposal',
    negotiateBtn: 'I need adjustments',
    negotiateTitle: 'I\'m interested, but let\'s adjust the scope',
    negotiateText: 'Tell us what adjustments you need. Our team will reach out to discuss options with no commitment.',
    negotiatePlaceholder: 'E.g.: I\'d like to reduce the number of modules, adjust the timeline, explore a different price...',
    negotiateConfirm: 'Send adjustment request',
    negotiatingSuccess: 'Request received!',
    negotiatingSub: 'Our team will review your notes and contact you soon to discuss options.',
    talkBtn: 'I prefer to talk before deciding',
    commentBtn: 'I have comments',
    commentTitle: 'Your feedback helps us',
    commentText: 'No commitment — tell us what questions you have or what adjustments you would need to move forward.',
    commentPlaceholder2: 'E.g.: The price is a bit over my budget, can we explore options?',
    commentSend: 'Send message',
    commentSent: 'Message sent. We will be in touch soon.',
    rejectBtn: 'Not the right time',
    confirmTitle: 'Awesome{clientName}!',
    confirmText: 'We\'ll reach out within 2 hours. Meanwhile, you can download a summary of what was agreed.',
    confirmYes: 'Confirm!',
    cancel: 'Cancel',
    sending: 'Sending...',
    accepted: 'Proposal accepted!',
    acceptedSub: 'We will send you a confirmation email. Our team will review the details and documents before linking the project.',
    rejected: 'Proposal declined. Thank you for your time.',
    rejectTitle: 'We\'re sorry it\'s not the right time',
    rejectText: 'Your feedback is very important to us. Could you let us know why?',
    reasonLabel: 'Reason (optional)',
    reasonNudge: 'It would really help us to know why — your answer is optional and confidential.',
    selectReason: 'Select a reason...',
    reasons: ['Budget too high', 'Found another option', 'Not the right time', 'Does not meet my expectations', 'Other'],
    otherReason: 'Other',
    otherLabel: 'Tell us more',
    commentLabel: 'Additional comment (optional)',
    otherPlaceholder: 'Write your reason here...',
    commentPlaceholder: 'Any additional comments...',
    confirmReject: 'Confirm rejection',
    specialPrice: 'Special price available',
    paymentPlanTitle: 'Payment options',
    flexiblePayments: 'flexible payments',
    downloadPdf: 'Download PDF summary',
    onboardingTitle: 'What\'s next?',
    contactPm: 'Contact your Project Manager',
    conditionLabel: 'Accept with a condition? (optional)',
    conditionPlaceholder: 'E.g.: I accept, but I need X to be included...',
    adjustmentReasons: [
      'The budget is high for right now',
      'I need to adjust the scope or remove modules',
      'The delivery timeline doesn\'t work for me',
      'I want to add or change features',
      'I need approval from another decision-maker',
      'Other adjustment',
    ],
    negotiateConfirmOne: 'Send adjustment request',
    negotiateConfirmMultiple: 'Send {count} adjustments',
    scopeSummaryTitle: 'You are approving:',
    scopeProject: 'Project',
    scopeInvestment: 'Investment',
    scopeModules: 'Modules',
    scopeStart: 'Estimated start',
    recovery: {
      budgetTitle: 'How about a more focused version?',
      budgetText: 'We understand. We can adjust the project scope to fit your budget. Would you like to explore options?',
      budgetCta: 'Explore options',
      timeTitle: 'Should we remind you later?',
      timeText: 'No problem. We can remind you in 3 months to revisit the conversation when the timing is better.',
      timeCta: 'Remind me in 3 months',
      timeScheduled: 'Done! We\'ll remind you in 3 months.',
      otherTitle: 'Thank you for your honesty',
      otherText: 'We appreciate your transparency. If anything changes or you need a second opinion, we\'re here.',
      expectTitle: 'We want to understand better',
      expectText: 'Would you like to schedule 15 minutes to tell us what you expected? We can adjust the proposal.',
      expectCta: 'Let\'s talk',
      genericTitle: 'Thank you for your time',
      genericText: 'We value your feedback. If you need anything in the future, don\'t hesitate to reach out.',
    },
  },
};

const t = computed(() => i18nStrings[props.language] || i18nStrings.es);

// The validity sentence is computed once on the backend
// (ProposalService.compute_validity_text — same source the PDF prints), so
// web and PDF can never drift. Proposals without an expiry fall back to the
// (number-free) seeded/custom message.
const displayedValidity = computed(() => (
  props.proposal?.validity_text || props.validityMessage || ''
));

onMounted(() => {
  setTimeout(() => {
    if (validityRef.value) {
      validityRef.value.classList.add('validity-blink');
      setTimeout(() => {
        validityRef.value?.classList.remove('validity-blink');
      }, 1400);
    }
  }, 600);
});

const proposalStore = useProposalStore();

const pdfUrl = computed(() => {
  const base = `/api/proposals/${props.proposal?.uuid}/pdf/`;
  const params = new URLSearchParams();
  if (props.viewMode === 'technical') {
    params.set('doc', 'technical');
  }
  const q = params.toString();
  return q ? `${base}?${q}` : base;
});

const pdfFilename = computed(() => {
  const title = props.proposal?.title || props.proposal?.client_name || 'Propuesta';
  const safe = title.replace(/[^\w\sáéíóúñÁÉÍÓÚÑ-]/g, '').trim().replace(/\s+/g, '_').slice(0, 100);
  const created = props.proposal?.created_at;
  const date = created ? new Date(created).toISOString().slice(0, 10) : new Date().toISOString().slice(0, 10);
  return `${safe}_${date}.pdf`;
});

const pdfMessageId = useId();
const { isGenerating: pdfGenerating, isExpired: pdfExpired, message: pdfMessage, downloadPdf } = useProposalPdfDownload({
  proposal: () => props.proposal,
  url: pdfUrl,
  filename: pdfFilename,
});

const canRespond = computed(() => {
  const s = props.proposal?.status;
  return s === 'sent' || s === 'viewed';
});

const confirmTitleText = computed(() => {
  const name = props.proposal?.client_name;
  const suffix = name ? `, ${name}` : '';
  return t.value.confirmTitle.replace('{clientName}', suffix);
});

const hasActiveDiscount = computed(() => {
  return props.proposal?.discount_percent > 0 && props.proposal?.discounted_investment;
});

function formatCurrency(value) {
  if (!value) return '';
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return '$' + num.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

const isSubmitting = ref(false);
const submitted = ref(false);
const rejectionSubmitted = ref(false);
const submittedReason = ref('');
const showAcceptConfirm = ref(false);
const showRejectModal = ref(false);
const showNegotiateModal = ref(false);
const negotiateComment = ref('');
const negotiatingSubmitted = ref(false);
const showCommentModal = ref(false);
const negotiationComment = ref('');
const isCommenting = ref(false);
const commentSubmitted = ref(false);
const rejectReason = ref('');
const rejectComment = ref('');
const isOtherReason = computed(() => rejectReason.value === t.value.otherReason);
const followupScheduled = ref(false);
const isScheduling = ref(false);
const conditionNote = ref('');
const selectedAdjustments = ref([]);

const negotiateCtaText = computed(() => {
  const count = selectedAdjustments.value.length;
  if (isSubmitting.value) return t.value.sending;
  if (count <= 1) return t.value.negotiateConfirmOne || t.value.negotiateConfirm;
  return (t.value.negotiateConfirmMultiple || t.value.negotiateConfirm).replace('{count}', count);
});

const scopeSummary = computed(() => {
  const p = props.proposal;
  if (!p) return [];
  const items = [];
  if (p.title) items.push({ label: t.value.scopeProject, value: p.title });
  const inv = effectiveTotal.value || p.investment;
  if (inv) {
    const numVal = parseFloat(String(inv).replace(/[^\d.]/g, ''));
    const formatted = !isNaN(numVal) && numVal > 0 ? formatCurrency(numVal) : inv;
    items.push({
      label: t.value.scopeInvestment,
      value: `${formatted} ${p.currency || ''} ${taxLabel.value}`.trim(),
    });
  }
  const mods = p.selected_modules || p.modules;
  if (Array.isArray(mods) && mods.length) items.push({ label: t.value.scopeModules, value: String(mods.length) });
  const start = p.estimated_start || p.start_date;
  if (start) items.push({ label: t.value.scopeStart, value: start });
  return items;
});

// scopeDisplay: like scopeSummary but replaces raw price with payment plan reference
const scopeDisplay = computed(() => {
  const p = props.proposal;
  if (!p) return [];
  const items = [];
  if (p.title) items.push({ label: t.value.scopeProject, value: p.title });
  // If payment milestones exist, show payment count instead of raw total
  const milestones = paymentMilestones.value;
  if (milestones.length) {
    const countLabel = props.language === 'en'
      ? `${milestones.length} payments`
      : `${milestones.length} pagos`;
    items.push({ label: t.value.scopeInvestment, value: countLabel });
  } else {
    const inv = effectiveTotal.value || p.investment;
    if (inv) {
      const numVal = parseFloat(String(inv).replace(/[^\d.]/g, ''));
      const formatted = !isNaN(numVal) && numVal > 0 ? formatCurrency(numVal) : inv;
      items.push({
        label: t.value.scopeInvestment,
        value: `${formatted} ${p.currency || ''} ${taxLabel.value}`.trim(),
      });
    }
  }
  const mods = p.selected_modules || p.modules;
  if (Array.isArray(mods) && mods.length) items.push({ label: t.value.scopeModules, value: String(mods.length) });
  const start = p.estimated_start || p.start_date;
  if (start) items.push({ label: t.value.scopeStart, value: start });
  return items;
});

const paymentMilestones = computed(() => {
  const opts = props.proposal?.payment_options;
  if (!opts || typeof opts !== 'object') return [];
  const milestones = Array.isArray(opts)
    ? opts
    : (Array.isArray(opts.milestones) ? opts.milestones : []);
  return milestones.map(o => ({
    ...o,
    label: o.label || o.name || '',
    amount: ensureProposalTaxLabel(o.amount || '', props.proposal?.currency),
  }));
});

const closingPaymentOptions = computed(() => {
  if (!props.paymentOptions || !Array.isArray(props.paymentOptions)) return [];
  return props.paymentOptions
    .filter(o => o.label && o.description)
    .map(o => ({
      ...o,
      description: ensureProposalTaxLabel(o.description, props.proposal?.currency),
    }));
});

const onboardingSteps = computed(() => {
  const lang = props.language;
  if (lang === 'en') {
    return [
      { title: 'Confirmation email', desc: 'You will receive an email with the summary and next steps.' },
      { title: 'Kickoff call', desc: 'Within 48h, your Project Manager will contact you.' },
      { title: 'Project setup', desc: 'We set up the environment and start the first sprint.' },
    ];
  }
  return [
    { title: 'Email de confirmación', desc: 'Recibirás un email con el resumen y próximos pasos.' },
    { title: 'Llamada de kickoff', desc: 'En menos de 48h, tu Project Manager te contactará.' },
    { title: 'Setup del proyecto', desc: 'Configuramos el entorno e iniciamos el primer sprint.' },
  ];
});

const whatsappRecoveryLink = computed(() => {
  const title = props.proposal?.title || '';
  const msg = props.language === 'en'
    ? encodeURIComponent(`Hi, I'm reviewing the proposal "${title}" and I'd like to discuss options.`)
    : encodeURIComponent(`Hola, estoy revisando la propuesta "${title}" y me gustaría conversar sobre opciones.`);
  return `https://wa.me/573238122373?text=${msg}`;
});

function fireConfetti() {
  const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 10000 };
  confetti({ ...defaults, particleCount: 80, origin: { x: 0.5, y: 0.5 } });
  setTimeout(() => confetti({ ...defaults, particleCount: 50, origin: { x: 0.3, y: 0.6 } }), 250);
  setTimeout(() => confetti({ ...defaults, particleCount: 50, origin: { x: 0.7, y: 0.6 } }), 400);
}

async function confirmAccept() {
  if (!props.proposal?.uuid) return;
  isSubmitting.value = true;
  try {
    const extra = {};
    if (conditionNote.value.trim()) {
      extra.condition = conditionNote.value.trim();
    }
    const result = await proposalStore.respondToProposal(props.proposal.uuid, 'accepted', extra);
    if (result.success) {
      submitted.value = true;
      showAcceptConfirm.value = false;
      setTimeout(() => fireConfetti(), 500);
    }
  } finally {
    isSubmitting.value = false;
  }
}

async function confirmNegotiate() {
  if (!props.proposal?.uuid) return;
  isSubmitting.value = true;
  try {
    const parts = [];
    if (selectedAdjustments.value.length) {
      parts.push('[' + selectedAdjustments.value.join(', ') + ']');
    }
    if (negotiateComment.value.trim()) {
      parts.push(negotiateComment.value.trim());
    }
    const result = await proposalStore.respondToProposal(
      props.proposal.uuid, 'negotiating',
      { comment: parts.join(' — ') },
    );
    if (result.success) {
      negotiatingSubmitted.value = true;
      showNegotiateModal.value = false;
    }
  } finally {
    isSubmitting.value = false;
  }
}

async function confirmReject() {
  if (!props.proposal?.uuid) return;
  isSubmitting.value = true;
  try {
    const result = await proposalStore.respondToProposal(
      props.proposal.uuid, 'rejected',
      { reason: rejectReason.value, comment: rejectComment.value },
    );
    if (result.success) {
      submittedReason.value = rejectReason.value;
      rejectionSubmitted.value = true;
      showRejectModal.value = false;
    }
  } finally {
    isSubmitting.value = false;
  }
}

async function submitComment() {
  if (!props.proposal?.uuid || !negotiationComment.value.trim()) return;
  isCommenting.value = true;
  try {
    await proposalStore.commentOnProposal(props.proposal.uuid, negotiationComment.value.trim());
    commentSubmitted.value = true;
    showCommentModal.value = false;
    negotiationComment.value = '';
  } finally {
    isCommenting.value = false;
  }
}

async function scheduleReminder() {
  if (!props.proposal?.uuid) return;
  isScheduling.value = true;
  try {
    await proposalStore.scheduleFollowup(props.proposal.uuid, 3);
    followupScheduled.value = true;
  } finally {
    isScheduling.value = false;
  }
}
</script>

<style scoped>
.validity-blink {
  animation: validityDoublePulse 3.8s ease-in-out;
}

@keyframes validityDoublePulse {
  0%   { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0.25); }
  10%  { box-shadow: 0 0 14px 5px rgba(234, 179, 8, 0.22); }
  24%  { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0); }
  38%  { box-shadow: 0 0 14px 5px rgba(234, 179, 8, 0.22); }
  54%  { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0); }
  100% { box-shadow: none; }
}

.accept-pulse {
  animation: acceptPulse 2.5s ease-in-out infinite;
}

@keyframes acceptPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.03); }
}

.celebration-bounce {
  animation: celebrationBounce 0.8s ease-out;
}

@keyframes celebrationBounce {
  0%   { transform: scale(0.3); opacity: 0; }
  50%  { transform: scale(1.2); }
  70%  { transform: scale(0.9); }
  100% { transform: scale(1); opacity: 1; }
}
</style>
