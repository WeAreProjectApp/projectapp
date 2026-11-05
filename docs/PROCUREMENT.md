# Contratación estatal

Módulo interno en `/panel/procurement`. Desarrollo independiente; referencia funcional: GitHub `ProjectAppSunset/gym_project`, revisión `8ff8c12`, sin trasladar código, migraciones, pruebas, datos ni identidad de G&M. Esto no acredita derechos sobre el desarrollo específico del cliente.

## Uso

Procesos permite filtrar, ordenar, paginar y exportar hasta 5.000 coincidencias a Excel. Mis clasificados conserva el seguimiento personal; las notas y su historial se ven en el equipo. Descartar exige motivo y restaurar recupera el estado anterior. Se muestra cierre, días restantes y urgencia con tres días o menos; no hay recordatorios de cierre.

Búsquedas guardadas permite nombre, edición, favorito y borrado confirmado. Crear una alerta desde una búsqueda copia sus criterios: editar la búsqueda no cambia la alerta. Palabras clave y prefijos UNSPSC se combinan con O; los demás criterios con Y. Dentro de una frase deben coincidir todas las palabras en nombre o descripción. Listas de entidad/departamento/modalidad/tipo/estado admiten cualquiera de sus valores. Región es departamento de la entidad según la fuente, no lugar de ejecución garantizado. El motor se comparte entre panel, exportación, alertas y MCP.

Las alertas tienen uno a diez destinatarios y frecuencia inmediata, diaria o semanal. Empiezan inactivas; correo y actualización automática global también apagados. Configurar destinatarios reales y revisar coincidencias antes de activar. No hay correo de Carlos fijado en código. Cada destinatario recibe un envío separado.

## Actualización y entregas

Fuente: datos públicos oficiales SECOP II de Colombia Compra Eficiente, conjunto `p6dx-8zbt`, API Socrata. Se consulta una página por trabajo Huey, con cursor reanudable y exclusión de ejecuciones simultáneas. La consulta inicial abarca 90 días (configurable 1–365); las incrementales incluyen cambios de estado y reconcilian los procesos con seguimiento. Los fallos conservan datos previos; registros defectuosos producen resultado parcial, y tres fallos de origen cierran la ejecución.

Horarios iniciales Bogotá: actualización 02:00, resumen diario 07:00, semanal lunes 07:00. Son configurables. Inmediata significa al detectar coincidencias durante una actualización. Los resúmenes esperan una sincronización en curso y fijan su ventana de notificaciones: continuar los lotes no los convierte en alertas inmediatas durante el resto del día.

Las entregas usan la pasarela `EmailDeliveryGateway`, su política de copias e historial. El outbox conserva evidencia de oportunidades y filtros; el contenido se carga bajo demanda. Antes de enviar se revalidan vigencia, filtros, frecuencia, activación y destinatario. El vaciado encola un trabajo por correo; SMTP usa conexión con plazo finito.

Los fallos admiten reintento acotado o manual. Un timeout, desconexión incierta o envío interrumpido exige verificar el buzón antes de reintentar manualmente; no se promete entrega exactamente una vez ante incertidumbre SMTP. Los resultados inciertos no se repiten automáticamente.

## API, MCP y análisis

API `/api/procurement/`, exclusiva de staff con sesión Django y CSRF. Recursos: oportunidades y detalle, clasificación/restauración, búsquedas propias, alertas compartidas, configuración, filtros, sincronización, entregas y su detalle/reintento, exportación. Oportunidades y entregas son paginadas; máximo 100 oportunidades por página. La respuesta cruda del origen no se expone.

Conector único `procurement` con las capacidades equivalentes. Las acciones sensibles, incluidas activar correo/alertas y reintentar, usan confirmación MCP. Las operaciones personales requieren `owner_id` de staff activo; el actor y la credencial MCP quedan registrados aparte. Actuar para otra persona requiere autoridad de superusuario del principal MCP; un actor staff sin ese privilegio sólo puede seleccionar su propio dueño.

El asistente externo conecta su Gmail/Outlook y este MCP: lee el correo de SECOP, consulta procesos y registra en notas la selección y el porqué. El perfil comercial y la comprobación de requisitos los aporta el operador/asistente. ProjectApp no ejecuta modelos, almacena credenciales del buzón ni lee avisos privados del portal SECOP.

## Despliegue y datos de ejemplo

El deploy aplica las migraciones de `procurement`. La siembra crea configuración y conector inactivo, sin generar credenciales ni activar envíos. La ficha comercial existente se conserva independiente. La sesión no migra ni refresca datos del servicio.

`create_fake_procurement` integra ejemplos en `create_fake_data`, sin red ni correo y con alerta inactiva. Requiere `FAKE_DATA_ALLOWED=True` y reloj reproducible; `delete_fake_data --confirm` limpia su grafo antes de los dueños y preserva configuración/conector.

Validación focal: pruebas backend en `procurement/tests`, unitarias del store/editor, siete flujos E2E, contrato responsive, mapas de vistas y contratos MCP. Máximo 20 casos por lote y dos archivos E2E por invocación. Entrega: PR abierto con CI verde; integración, despliegue y activación posteriores.
