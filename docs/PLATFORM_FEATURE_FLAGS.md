# Feature flags de Plataforma · PA-263

## Administración

Panel → Plataforma → Feature flags (`/panel/platform/feature-flags`). Una cuenta
activa con acceso administrativo del Panel configura Global o selecciona un
cliente mediante búsqueda por nombre, correo o empresa. Cada tarjeta muestra
clave, valor global, excepción, resultado efectivo y procedencia. El guardado es
inmediato por tarjeta; un conflicto obliga a recargar. Historial conserva actor,
cliente, antes/después y versión.

**Excepción del cliente → global guardado → valor inicial del catálogo.**
Heredar elimina la excepción, incluso si tenía el mismo valor que el global.
Todas las capacidades ordinarias comienzan habilitadas; chatbot, reportes por voz
y audio del chatbot comienzan deshabilitados. Un flag jamás concede permisos,
habilita credenciales ausentes ni cambia cuotas, publicaciones o preparación
técnica. Modelo de datos conserva su condición previa de disponibilidad.

## Catálogo y puntos de control

La fuente compartida es `contracts/platform-features.json`: claves estables,
etiquetas ES/EN, módulos, referencias del Mapa de vistas, rutas, controles de ayuda
y nombres de endpoints. Las entradas sin página propia identifican sus componentes.
No crear claves desde el Panel ni reutilizar una clave para otra finalidad.

`accounts.feature_permissions` añade la evaluación después de los permisos DRF
existentes a las rutas de cuentas. Conserva autorización por registro; las
descargas de evidencia compartidas resuelven primero su propietario y clase de
ticket. IA y Ayuda evalúan además en sus servicios: capacidades, acciones, fuentes,
historial y trabajos pendientes antes de llamar proveedores. La biblioteca de
Documentos y los documentos de Entregas son capacidades de entrada distintas;
sus endpoints corresponden al flag del módulo que los ofrece.

La autenticación JWT lee las preferencias del cliente y el global junto con el
perfil vigente, mediante relaciones y una subconsulta. Ese resultado pertenece
solo a la petición autenticada; no se guarda en el token ni se comparte entre
peticiones. Los servicios fuera de HTTP vuelven a leer su propio corte. El
inventario incluye los endpoints de Entrega generados por tipo de documento.

Nuxt consume el mismo inventario para navegación de escritorio/móvil, pestañas,
enlaces directos y controles asociados. La API propia devuelve exclusivamente
la cuenta autenticada. El estado en memoria se liga a `user_id`, se descartan
respuestas de cuentas anteriores y se revalida al navegar o recuperar el foco.
El servidor decide en cada operación. No se promete difusión instantánea entre
pestañas; una denegación de API invalida la disponibilidad de la superficie.
Si la evaluación falla, las funcionalidades controladas siguen bloqueadas y el
cliente puede volver a la estructura básica de Proyectos.

Acceso, recuperación, perfil, estructura y resumen de proyectos y administración
interna están inventariados como exclusiones. Un cliente bloqueado vuelve a
Proyectos. Los administradores conservan soporte autorizado; una sesión
impersonada evalúa al cliente. Apagar una función no elimina datos ni cancela
obligaciones financieras, webhooks o trabajos comerciales automáticos.

## Persistencia y compatibilidad

Migración aditiva `accounts.0093_platform_feature_flags`; la aplica el deploy,
nunca la sesión desde el worktree. La configuración inicial no importa los
interruptores anteriores: aplica los valores iniciales acordados. Credenciales,
cuotas, contenido y progreso de Ayuda permanecen independientes.

Las páginas de IA y Ayuda enlazan al administrador central. Sus endpoints/MCP
anteriores conservan adaptadores: valores globales escriben globales; booleanos
por cliente crean excepciones. Los campos legados sólo conservan proyecciones y
versiones para compatibilidad; ninguna evaluación los usa como otra fuente.
El contrato Proyectos pasa a 6.0.0 por el cambio de precedencia.

## API y MCP

- `GET /api/platform/features/`: valores efectivos propios, JWT y `no-store`.
- `GET/PATCH /api/platform/features/admin/`: catálogo y globales, sesión/CSRF.
- `GET .../admin/clients/`: búsqueda paginada.
- `GET/PATCH .../admin/clients/<user_id>/`: excepciones y resultado efectivo.
- `GET .../admin/events/`: auditoría paginada, con filtro opcional de cliente.

PATCH admite `expected_version` y `values` por clave conocida. Global acepta
booleanos; cliente también `null` para heredar. Claves desconocidas, tipos
incorrectos y cuerpos vacíos se rechazan sin cambios. Versiones superadas dan
409; una operación deshabilitada da 403 con `code=feature_disabled`.

El conector `projects` publica `get_platform_feature_flags`,
`update_platform_feature_flags`, `list_platform_feature_clients`,
`get_platform_client_feature_flags`, `update_platform_client_feature_flags` y
`list_platform_feature_events`. Las escrituras conservan vista previa,
confirmación, permisos y versión a través del mismo servicio del Panel.

## Regla prospectiva de entrega y QA

Para cada capacidad nueva o modificada, Implementación declara clave existente,
alta de clave o exclusión justificada; revisa módulo/vista, navegación, enlace
directo, API, descargas y accesos indirectos. Una clave nueva ordinaria parte
habilitada; las de IA/audio parten deshabilitadas. Los servicios técnicos y
permisos siguen siendo condiciones separadas.

CI ejecuta `scripts/check_platform_features.py`: detecta vistas, endpoints y
capacidades sin clasificación, referencias inexistentes y controles duplicados.
Las pruebas negativas del inventario introducen omisiones en copias de la
configuración; no se retira un control real para fabricar evidencia.

QA coteja catálogo, clave, funcionalidad real y aplicación global/por cliente.
Una declaración estática no acredita el recorrido. Las brechas se entregan a
Backlog con SHA, entorno, rol, reproducción y efecto; Backlog deduplica y registra
TO DO en la ficha consolidada de la ronda cuando corresponda. sync-knowledge
coordina publicación canónica; esta implementación no publica en Slack.

Automatizadas sólo en CI. La pausa de QA manual y servicios se mantiene. Frontend
y su mismo DevQA validarán sobre un único SHA/entorno autorizado: valores
iniciales, ambos globales, ambas excepciones, retirada, dos clientes, persistencia,
permisos, acceso directo, MCP y detección de brecha. El generador canónico añade
el cliente `[QA] Perfil limited` con Documentos/Bugs apagados; los demás heredan.


## Evidencia de implementación

El PR #587 incorpora las pruebas de estas capacidades. Las pruebas antiguas de
interruptores en las páginas IA/Ayuda pasan a sus funciones actuales (cuotas y
contenido); la disponibilidad, fallos y conflictos se cubren en la pantalla
central. La precedencia anterior global-Y-cliente se sustituye explícitamente
por la excepción del cliente; los casos se actualizan a ese contrato.

La regla prospectiva también está en las fuentes canónicas del toolkit
(`682d82aa`, incluido en `master` por `7a2c61a9`), con espejo Codex renderizado.
No se propagó runtime ni se publicó en Slack.
