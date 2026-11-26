# PA-304 · Enlaces seguros

Verificación automatizada en el worktree de W4, con datos ficticios. Base
`main@6d0eb14b6898ed2881e67cb46456006ece090683`. Código de producto
`bfd6894081eada55a13aa4bffb464b213036916e`.

| Criterio | Comprobación |
|---|---|
| Reactivación | Chromium midió una separación positiva entre plazos, etiqueta y botón en 412 × 915 y 1440 × 900. En ambos perfiles se seleccionaron 30 días y se activó la rotación por teclado. En la API Django, un reloj fijo permitió verificar los cuatro plazos con y sin rotación, la validez de la URL anterior y una sola apertura por activación. |
| Credenciales | En español e inglés, el navegador permitió crear con título y contraseña. El formulario y la petición omitieron nombre y dirección del sistema. El test de edición del formulario verificó que ambos valores anteriores vuelven a enviarse. La API comprobó que sobreviven al cambio de título y de nota. |
| Campos esenciales | La API aceptó los nueve mínimos y devolvió el campo obligatorio correspondiente cuando faltaba o sólo tenía espacios. Los rechazos dejaron el enlace y el historial sin filas nuevas. En inglés, el navegador enfocó el campo Mensaje tras un rechazo de la API, mostró el error en ese idioma y permitió guardar de nuevo el borrador. |

Las capturas muestran la sección de reactivación con la casilla marcada.
[Modal estrecho](reactivacion-compact.png) · [Escritorio](reactivacion-desktop.png)

Las pruebas de API utilizan pytest, `projectapp.settings_test` y SQLite.
Las de navegador utilizan Nuxt en loopback y respuestas HTTP simuladas.
Los casos reproducibles están en
[API del Panel](../../../backend/secure_links/tests/test_panel_content_contract.py),
[formulario](../../../frontend/test/components/SecureLinkFormModal.test.js) y
[recorridos del Panel](../../../frontend/e2e/admin/admin-secure-links.spec.js).
