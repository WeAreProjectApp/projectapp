### FLOW: `proposal-module-interests`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** Desde Inversión, el cliente explora el catálogo vigente por categorías y registra módulos que le interesan conversar. El modal no muestra precios; guardar intereses no cambia el alcance contratado, el importe, los plazos ni el PDF.
- **Steps:**
  1. Elegir la vista detallada y abrir Inversión.
  2. Pulsar «Explorar módulos adicionales»; se carga el catálogo y la selección guardada.
  3. Ver el video disponible y desplegar categorías y detalles de módulos.
  4. Marcar módulos y guardar; aparece una confirmación y la selección persiste al reabrir.
- **Branches:**
  - Si falla la carga, aparece Reintentar.
  - Si falla el guardado, los cambios pendientes siguen visibles para reintentar.
  - El catálogo vacío se informa sin precios ni una selección ficticia.
  - Los intereses anteriores desactivados se conservan y pueden retirarse.
  - La vista previa informa que no registra intereses.
- **E2E Spec:** `e2e/proposal/proposal-module-interests.spec.js`
- **Components:** `Investment.vue`, `ModuleInterestsModal.vue`, `AdditionalModules/ModuleDetails.vue`
