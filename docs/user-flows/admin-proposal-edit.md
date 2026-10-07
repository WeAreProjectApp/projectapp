### FLOW: `admin-proposal-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit`
- **Description:** Edit an existing business proposal through grouped navigation: General, Propuesta, Comunicación, Documentos, Proyecto and Seguimiento. Document and project tools remain available according to the proposal status.
- **Steps:**
  1. Admin navigates to `/panel/proposals/:id/edit`.
  2. Proposal data loads from API (`GET /api/proposals/:id/detail/`).
  3. Edit form renders pre-filled with current data.
  4. Admin modifies proposal details, sections, requirements.
  5. Admin saves changes.
  6. API call to `PATCH /api/proposals/:id/update/`.
  7. Success feedback displays.
- **Branches:**
  - [Datos del proyecto] Proyecto → Datos está disponible en todos los estados. Reúne el cliente y los contactos con guardado propio; una propuesta ya vinculada conserva su cliente. El proyecto actual se muestra allí y su cambio exige destino del mismo cliente, motivo, revisión y confirmación.
  - [Recursos y correos] Recursos pertenece a Propuesta. Los enlaces anteriores a Comunicación → Recursos abren la nueva ubicación. Firma, funcionalidades y fases del correo se guardan desde Comunicación → Correos sin sobrescribir cambios pendientes en General.
  - [Disponibilidad de Documentos] La pestaña está disponible en todos los estados y permanece seleccionada cuando la propuesta pasa a finalizada. General conserva los PDFs originales de propuestas en borrador, vencidas y finalizadas, distintos de los documentos formales.
  - [Grouped navigation] Select a primary area and one of its visible secondary tools. Compact and portrait profiles use named selectors. Returning to an area restores its last tool and preserves unsaved content or a selected video file.
  - [Shared links] Old `?tab=<tool>` links and new `?tab=<group>&section=<tool>` links open the corresponding tool after proposal data loads, preserving unrelated parameters and fragments. Unknown or unavailable destinations return to General.
  - [Lifecycle changes] When an active tool becomes unavailable, select the first available tool in its area or return to General. Finished projects retain Cronograma but not Desarrollo.

  - [Branch A] Admin reorders sections → `POST /api/proposals/:id/reorder-sections/`.
  - [Branch B] Admin updates individual section → `PATCH /api/proposals/sections/:id/update/`.
  - [Branch C — item traceability] In Propuesta → Detalle técnico, editor sections render collapsed by default (2026-08 perf round): the admin expands "Módulos del producto" (`technical-section-toggle-epics`), opens the requirement's "Vincular alcance/ítems (n)" disclosure (`technical-req-links-toggle`), and checks the commercial-item boxes (grouped by functional_requirements card, `technical-req-item-links`) that write `linked_item_ids`; saving (button always visible below the sections) persists them via the same section update endpoint. These links power the public nested requirements modal and the commercial PDF sub-rows. The JSON sub-tab mounts only when selected.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-edit.spec.js` (includes linked_item_ids save test), `e2e/admin/admin-proposal-navigation.spec.js` (grouped navigation and compatible links)
- **Known gaps:** The automations toggle now uses positive polarity (ON = automations running, 2026-07); no E2E asserts knob position / `aria-checked`, and the toggle has no `data-testid` (only `aria-label="Activar automatizaciones"`).
