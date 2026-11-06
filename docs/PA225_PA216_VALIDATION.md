# PA-225 y PA-216 — traspaso de validación

## Corte y coordinación

Rama: `fix/06112026-pa225-216-project-approval`; base: `main`. El PR, SHA exacto y corrida CI se entregan por cola directa a dev-qa; la evidencia de ejecución reside en GitHub. DEV pertenece a dev-qa: esta sesión no inicia servidores ni prepara datos en la base compartida. Las pruebas automatizadas se ejecutan exclusivamente en CI. Chrome real lo coordina dev-qa con Backlog ProjectApp; estos pasos no acreditan ejecución manual.

## Datos y permisos

Datos ficticios: administrador de Panel y perfil admin de Plataforma, propietario de un proyecto, otro cliente y visitante sin sesión. Un proyecto con referencias en Hosting, Ingresos y Cuentas de cobro; referencias sin proyecto para comprobar su estado y selección de uno existente. Propuestas en negociación, aceptada sin proyecto y con un paquete previo; contratos único, producto sin servicio aprobado, producto y servicio aprobados y personalizados. Dos anexos activos y uno archivado, más un anexo nuevo posterior al primer cierre. dev-qa publica los IDs y precondiciones del corte servido; los IDs de las pruebas anteriores no se asumen vigentes.

## PA-225

1. En `/panel/projects`, comprobar disponibilidad en tabla y tarjetas. Acciones → Ver detalle → Abrir espacio en la plataforma abre otra pestaña con el ID correcto. Repetir desde la acción de fila.
2. Renombrar el proyecto ficticio y repetir ambos saltos: permanece el mismo ID. La acción Ficha comercial de Plataforma abre Panel con `highlight=<id>` sólo para admin.
3. Abrir las referencias de Hosting, Ingresos y Cuentas de cobro. Una referencia sin proyecto informa Sin proyecto y no ofrece enlace; seleccionar un proyecto existente habilita el destino correcto. No hay una vinculación separada: Panel y Plataforma comparten Project.
4. Con propietario, comprobar acceso; con otro cliente, explicación de falta de acceso sin nombre, datos, navegación interna ni retorno al Panel. Sin sesión, inicio de sesión. Abrir ID inexistente muestra no disponible. Navegar de un proyecto accesible a uno denegado no recupera contenido anterior.

## PA-216

1. Desde listado y editor, abrir Aprobar. Cancelar conserva el estado y no guarda cliente/proyecto preparados.
2. Preparar un nuevo cliente/proyecto y archivos sin confirmar. Aprobar y revisar después acepta, muestra revisión pendiente y no crea cliente, proyecto, entregable, carpeta, paquete ni archivos; repetir conserva el mismo estado. Recargar y retomar: permite confirmar con existentes o crear al confirmar.
3. En primer cierre, ningún anexo opcional está marcado. Marcar sólo uno y cotejar resumen, carpeta del proyecto y consulta desde propuesta: sólo ese anexo, contratos elegidos y ambos detalles. El archivado no es seleccionable.
4. Repetir con contrato único, separados producto sólo/producto y servicio y personalizados. El proyecto operativo conserva dueño, progreso, recursos y datos financieros.
5. Revisar el paquete previo: recupera sólo los anexos confirmados, no el anexo nuevo. Confirmar otra revisión con selección vacía retira anexos del vigente, conservando sus documentos y descargas históricas; reintentar la misma solicitud no duplica entidades ni reemplaza contrato vigente.
6. Cotejar el mismo documento por ID desde propuesta, gestor y MCP: cambios permitidos preparan borrador, guardado antiguo devuelve conflicto y no sobreescribe. Sólo reconfirmar publica una revisión; originales, firmas y referencias históricas conservan sus bytes e identidad. Reconciliar un cierre antiguo usa los archivos confirmados, sin regenerar contratos ni incorporar anexos nuevos.

## Comprobaciones transversales y resultado

En controles afectados: móvil, tableta vertical/horizontal y escritorio, temas claro/oscuro, Tab, foco visible, activación por teclado y retorno del foco al cerrar. Registrar tamaño CSS, rol, IDs, SHA servido, pasos, esperado, observado y evidencia por caso. Cotejar `/panel/views`; brechas adicionales o del generador se vinculan como seguimientos según el acuerdo de QA, sin mezclarlas con el dictamen de los criterios originales.
