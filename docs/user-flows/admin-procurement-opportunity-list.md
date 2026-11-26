### FLOW: `admin-procurement-opportunity-list`

- **Module:** procurement
- **Role:** staff admin
- **Priority:** P1
- **Routes:** `/panel/procurement`
- **Description:** Staff opens Secop under Contratación estatal from the expanded or compact panel menu, reads the paginated SECOP II list and source status, opens a process and retries a failed load.
- **Navegación:** En el menú expandido, el edificio identifica Secop. En el compacto, el enlace conserva el nombre accesible y la ayuda «Secop». Enter abre el listado y el enlace queda marcado como página actual.
- **Coverage:** ✅ Covered
- **E2E Spec:** `frontend/e2e/admin/admin-procurement.spec.js` (validado en navegador)
