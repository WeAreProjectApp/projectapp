### FLOW: `proposal-section-onboarding`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P3
- **Routes:** `/proposal/:uuid`
- **Description:** Per-section spotlight onboarding tutorials that trigger automatically the first time a client navigates to specific sections. Each section has its own component with a spotlight overlay (blur backdrop + cloned element), progress dots, and positioned tooltip card. Tutorials are skipped for returning visitors (localStorage flag per proposal UUID).
- **Steps:**
  1. Client navigates to the Investment section for the first time (detailed view).
  2. InvestmentOnboarding component triggers after 800ms delay.
  3. Spotlight highlights the "Explorar módulos adicionales" button with a tooltip explaining the catalog and saving commercial interests.
  4. Client clicks through onboarding steps → completes → localStorage flag set.
  5. [Separate trigger] Client navigates to functional_requirements section.
  6. RequirementsOnboarding component triggers after 800ms delay.
  7. Spotlight highlights requirement group cards with a tooltip explaining how to expand them.
  8. [Separate trigger] Client in executive view navigates to investment section.
  9. ExecutiveInvestmentOnboarding triggers, highlighting the "Ver detalle" teaser button.
- **Branches:**
  - [Branch A — Detailed Investment] InvestmentOnboarding triggers only in detailed view for a public proposal.
  - [Branch B — Executive Investment] ExecutiveInvestmentOnboarding triggers only in executive view.
  - [Branch C — Requirements] RequirementsOnboarding triggers in both view modes.
  - [Branch D — Returning visitor] Each tutorial is skipped if already completed (per-UUID localStorage flag).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-section-onboarding.spec.js`
- **Components:** `InvestmentOnboarding.vue`, `RequirementsOnboarding.vue`, `ExecutiveInvestmentOnboarding.vue`
