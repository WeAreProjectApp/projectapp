### FLOW: `public-contact-submit`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Routes:** `/contact`, `/en-us/contact`, `/es-co/contact` → `/contact-success`
- **Description:** Submit a contact form to reach the company.
- **Steps:**
  1. User navigates to the contact page.
  2. Contact form renders with fields (name, email, message, etc.).
  3. User fills in the form fields.
  4. User submits the form.
  5. API call to `POST /api/new-contact/`.
  6. On success, the form locks further submissions and opens `/contact-success` in the active locale.
- **Branches:**
  - [Branch A — Validation error] Form shows inline validation errors, user corrects and resubmits.
  - [Branch B — API error] The localized `contact-submit-error` message renders below the submit button and the form remains editable.
  - [Branch C — Navigation failure] A successful submission stays locked if the router rejects the destination. The user action produces one POST.
  - [Branch D — Locale display] The form and confirmation use the active locale in the visible copy and document language.
- **Coverage:** `success`, `error`, `failure`, `display` in the browser spec.
- **E2E Spec:** `e2e/public/public-contact.spec.js` and `e2e/published/contact-confirmation.spec.js`. On the Django build, a single accepted POST removes the form and displays the confirmation heading in the submitting tab. The disposable mailbox receives three local deliveries for one contact.
