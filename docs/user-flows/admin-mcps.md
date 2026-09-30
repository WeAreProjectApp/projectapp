### FLOW: `admin-mcps`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/mcps`
- **Description:** El superusuario administra los conectores MCP agrupados por área. Cada card muestra estado, riesgos, catálogo, credenciales limitadas y actividad atribuida; los secretos aparecen una sola vez. Puede activar un conector, crear o editar el alcance/vencimiento de una credencial, rotarla o revocarla. Los errores de validación quedan en el formulario y los fallos del servidor no cierran ni confirman la acción.
- **Steps:**
  1. El superusuario llega desde la navegación del Panel a Integraciones → MCPs.
  2. Expande una card y revisa riesgos, funciones, credenciales, actor técnico y actividad con request/objeto atribuido.
  3. Genera la principal o crea una limitada → recibe la URL una sola vez → la copia al cliente MCP.
  4. Edita alcance/vencimiento, rota o revoca una credencial individual; la revocación exige confirmación en el modal estándar del Panel.
  5. Activa o desactiva el conector con el toggle.
  - [Display] La card y sus acordeones presentan inventario real. En los cinco perfiles del Panel se leen etiquetas, actores e identificadores de petición largos sin desborde horizontal; en móvil y tableta vertical los acordeones ofrecen zonas táctiles de al menos 44 px. En tableta vertical se puede abrir la edición del alcance y cancelarla sin cambiar la credencial.
  - [Success] Crear, editar, rotar, revocar y activar producen el estado observable correspondiente.
  - [Error] Un staff no superusuario es redirigido; etiqueta vacía o alcance custom vacío permanecen bloqueados en cliente.
  - [Failure] Un 4xx/5xx conserva el formulario o estado anterior y muestra el detalle accionable.
  - [Security] El plaintext no puede recuperarse al recargar; sólo quedan prefijo y hash. Las escrituras —incluidos `created_by` y `linked_by` de hilos documentales, ingresos y extractos— se atribuyen a un principal técnico no interactivo del conector, nunca al superusuario humano del Panel.
  - [Contract] El servidor rechaza envelopes MCP incoherentes, alcances o vencimientos inválidos, confirmaciones vencidas/alteradas y assets temporales con tamaño, hash, MIME o firma incompatibles; un fallo de auditoría no interrumpe la respuesta del transporte.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-mcps.spec.js`

### 24.1 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-mcps` | admin | superuser | P2 | ✅ display · success · error · failure | `e2e/admin/admin-mcps.spec.js` |
