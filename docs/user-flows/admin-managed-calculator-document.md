### FLOW: `admin-managed-calculator-document`

- **Module:** documents
- **Role:** admin
- **Priority:** P2
- **Route:** `/panel/documents/<id>/edit`
- **Description:** El administrador abre desde una versión de proyecto su documento de calculadora, ve el aviso de contenido administrado y vuelve a la calculadora correspondiente. El editor documental permanece de sólo lectura.
- **Steps:** Abrir documento de una versión → comprobar doc-calculator-alert y contenido → seguir enlace a la calculadora → comprobar contexto de proyecto.
- **Branches:** Los errores de carga y permiso pertenecen a los flujos existentes del editor documental.
- **Coverage:** ✅ Covered — `display`; ejecución de navegador aprobada en `frontend/e2e/admin/admin-managed-calculator-document.spec.js`.
