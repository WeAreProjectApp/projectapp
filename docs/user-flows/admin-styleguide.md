### FLOW: `admin-styleguide`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/styleguide`
- **Description:** El operador consulta el catálogo de componentes y tokens, cambia el tema desde la guía o el control general del Panel y comprueba su persistencia y comportamiento responsive.
- **Interaction matrix:**
  - `display` — catálogo, perfil responsive, navegación, pestañas/filtros, tabla prioritaria y ancho limitado del contenido.
  - `success` — STAFF sin superusuario cambia el tema con Enter/Espacio; se actualizan la etiqueta, las superficies, el título y los tokens. La recarga conserva la elección y el control general permite volver al estado original. Regresión en 412×915 y 1440×900 (PA-227 / RESP-R068).
  - `error` — no aplica a elegir tema: son dos opciones válidas y no hay entrada libre. La validación de las muestras de formularios pertenece a sus componentes.
  - `failure` — no hay petición de mutación al servidor para esta preferencia local. El control no presenta un resultado de fallo por almacenamiento bloqueado; no se declara cobertura E2E de ese estado.
- **Coverage:** Regresiones existentes de visualización; selección persistente de tema pendiente de CI y de aceptación Chrome con STAFF16.
- **E2E Spec:** `e2e/visual/styleguide.spec.js`
