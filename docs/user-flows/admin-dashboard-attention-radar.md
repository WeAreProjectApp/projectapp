### FLOW: `admin-dashboard-attention-radar`

- **Module:** admin
- **Role:** admin; recurrent-payment records require superuser access.
- **Priority:** P1
- **Routes:** `/panel/`, with exact destinations in Emails, Recurrentes, Tasks, Documents and Proposals.
- **Description:** Each of the five attention categories is an independent accordion. It loads five identifying records per page, opens a fresh detail modal and offers a link to the exact record in its owning module. The pulse tile counts records. Linked email retry attempts form one incident, removed after a successful primary delivery; history is preserved.
- **Steps:**
  1. Open the Dashboard and expand an attention category without navigating away.
  2. Identify records by recipient/client/assignee, dates, amounts or failure reason as appropriate.
  3. Load the next five records within the same accordion.
  4. Select a record to read its current details in the modal.
  5. Follow its action to the exact record, independent of ordinary list filters, groups or pagination. The destination receives three soft pulses, or a static cue for reduced motion.
  6. Closing the modal returns focus to the selected record.
- **Outcomes:** display (identification, empty state, responsive detail); success (incremental pages, exact destinations); error (record deleted or access denied); failure (recoverable list/detail requests).
- **E2E Specs:** `e2e/admin/admin-dashboard-attention.spec.js`, `e2e/admin/admin-dashboard.spec.js`.

## Documento vinculado pendiente

El radar incluye cuentas con documento vinculado pendiente para superusuarios: borradores, emitidas y pagadas, excluyendo anuladas, archivadas y datos retenidos. Abre la cuenta exacta y permite completar el vínculo. La decisión resuelta desaparece en la siguiente lectura del radar; la autoría se conserva.
