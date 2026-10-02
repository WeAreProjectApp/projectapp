### FLOW: `proposal-view-onboarding`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P3
- **Routes:** `/proposal/:uuid`
- **Description:** Inner-view tutorial overlay (ProposalOnboarding component), independent of the gateway guide, that shows step-by-step tooltips guiding the client through the proposal interface. After completion, a reading-time popup appears.
- **Steps:**
  1. User chooses detailed or executive view from the gateway.
  2. ProposalOnboarding overlay appears with first tooltip step.
  3. User clicks through each onboarding step.
  4. Onboarding completes and emits `@complete` event.
  5. Reading time popup appears: "Tiempo de lectura: ~7 minutos".
  6. User clicks "Entendido" to dismiss popup.
- **Branches:**
  - [Branch A — Returning visitor] Onboarding is skipped if already seen (localStorage flag).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-onboarding.spec.js`
