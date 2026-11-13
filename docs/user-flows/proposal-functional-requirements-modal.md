### FLOW: `proposal-functional-requirements-modal`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Client clicks a functional requirement group card in the proposal to open a detail modal showing individual requirement items with icons and descriptions. Items with linked technical requirements (`linked_item_ids` in the technical document, matched by the item's stable `id`) additionally show a "Ver requerimientos (N)" link that opens a nested `LinkedRequirementsModal` listing each requirement's title, priority badge, and description (no configuration/usageFlow). Works in both detailed and executive modes; legacy proposals without item ids show no link.
- **Steps:**
  1. Client views the functional requirements section of the proposal.
  2. Client clicks a requirement group card.
  3. Detail modal opens listing individual items with icons and descriptions.
  4. [Branch — linked requirements] Client clicks "Ver requerimientos (N)" under an item → nested modal opens with the technical requirements that implement that item; closing it returns to the group modal.
  5. Client closes the modal by clicking outside or the close button.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-requirements-modal.spec.js` (includes nested-modal, executive-mode, and legacy-fallback tests)


**PA-251/253/257/261 · delta de interfaz:** El modal conserva uno o varios requerimientos por elemento y muestra configuration y usageFlow con su formato cuando existen, manteniendo propuestas antiguas sin esos campos.
La autoría de pruebas de este delta se valida en CI sobre el SHA del PR; no acredita recorrido manual.

El éxito del nuevo delta consiste en abrir el detalle técnico desde el enlace del elemento y leer configuración/flujo. Error y failure propios del modal: no aplican, porque este modal de lectura usa datos ya cargados y no envía peticiones ni formularios; los fallos al cargar la propuesta pertenecen al flujo de entrada.
