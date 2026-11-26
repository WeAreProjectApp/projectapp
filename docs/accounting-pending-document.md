# Documento vinculado pendiente en cuentas de cobro

El interruptor **Dejar documento pendiente** es una decisión explícita al crear una cuenta con proyecto. Permite conservar sólo el tipo de cobro o dejar también el tipo pendiente. No guarda vínculos parciales ni permite volver pendiente una asociación ya completa.

La marca es interna: no bloquea emisión, envío ni liquidación por ese vínculo, ni altera el PDF. PA-72 y las validaciones de período/evidencia de hosting conservan su alcance. Al completar hosting se exige la evidencia vigente de la asociación; no se deducen pagos por importe o fecha.

`CollectionAccountContext.document_pending` identifica la decisión; `pending_by` y `pending_at` son autoría del servidor y se conservan al resolver. `BillingContextEvent` guarda la decisión y su resolución. El tipo omitido se almacena como cadena vacía no nula y se lee como null. La migración `accounts.0090_pending_billing_document` depende de `accounts.0089_appi_client_guides`; sólo se aplica mediante despliegue, nunca desde el worktree.

El listado y detalle muestran una exclamación amarilla con tooltip **Hace falta el documento vinculado** y permiten completar el vínculo con versión y motivo. El filtro y su conteo usan las decisiones explícitas; no convierten históricos sin contexto en decisiones nuevas. El conteo visible del filtro respeta los filtros locales de la tabla. API y MCP devuelven `meta.document_pending_count` dentro de los filtros del servidor.

El radar financiero sólo está disponible para superusuarios; incluye borradores, emitidas y pagadas explícitamente pendientes, excluye anuladas, archivadas y registros retenidos de proyectos eliminados. Al completar se retira del radar en la próxima lectura; volver al Dashboard carga su resumen nuevamente. Que una cuenta deje de mostrarse por estado no borra su decisión auditada.

Panel y MCP administrativos comparten servicios y serializers. Crear/previsualizar admite `document_pending`; consultar y listar devuelve la marca, autor, fecha y versión; `associate_collection_account_context` completa mediante confirmación sensible. Los lectores de clientes conservan el contrato público anterior y no reciben autoría ni la nueva marca interna. Las cuentas sin proyecto rechazan `document_pending=true` y conservan el flujo anterior cuando se omite.

La reasignación reconstruye la marca desde el contexto persistido y conserva propiedad y candados existentes. La autoría `pending_by` está clasificada en `AUTHORSHIP_RELATIONS`; no se reasigna al fusionar clientes. AC8 permanece intacto: informa ausencia de contexto, no decisiones explícitas.

## Cuenta preparada desde Ingresos

El botón **Previsualizar** se habilita cuando se pueden revisar el cliente y su correo, el ingreso, el vínculo de proyecto que corresponda, el concepto, el importe y el plazo. La lista de correcciones lleva al campo correspondiente y conserva lo escrito. En hosting, confirmar el servicio y resolver su período son pasos distintos. El saldo, la identidad y el período que se cobran proceden de la misma resolución que consume la emisión desde Hostings.

**Sin IVA** aplica el 0 % al cálculo. Al desactivarlo se recupera la tasa de edición. **Mostrar IVA** decide si la cuenta, el PDF y el correo incluyen el desglose fiscal. El total contable se conserva en ambas posiciones. Un ingreso con importes fiscales bloqueados permite elegir la presentación del documento.

Con **Sin fecha de vencimiento** apagado, un plazo de cero días vence en la fecha de emisión de Bogotá. Una cuenta emitida e impaga entra en mora al día siguiente. Ocho días suman ocho días calendario y una fecha fija usa el día elegido. Al activar el interruptor, la cuenta queda sin fecha, el correo y el PDF omiten el renglón y la fecha deja de generar mora. Al volver a desactivarlo reaparece el plazo que se estaba editando. Las cuentas anteriores conservan su fecha guardada y sus PDF archivados. Los consumidores que omiten el modo siguen emitiendo sin fecha para el plazo histórico de cero días.

## Coordinación de esta entrega

El contenedor `CollectionAccountProjectContext.vue` se integra por hunks: Cobros mantiene validación/comunicación/visibilidad del pendiente; Contratos mantiene selector/carga/enlace e invalida respuestas ante cambio de intención o desmontaje. El tren de integración verifica activar y desactivar el interruptor durante un enlace, cambios A→B y la vinculación de un PDF privado del proyecto. Los tres PRs se validan combinados antes de integrar.
