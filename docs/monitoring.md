# Monitoreo: primer alcance

El panel `/panel/monitoring` centraliza observaciones del VPS
`vps-projectapp-prod` y sus proyectos activos ProjectApp, Mimittos y Tenndalux.
No incorpora staging, otros VPS, buzones de correo ni cuentas externas de
Healthchecks/UptimeRobot. Los correos actuales siguen funcionando.

## Estado del requerimiento

La implementación del módulo está integrada en `main` desde el
[PR #393](https://github.com/WeAreProjectApp/projectapp/pull/393). Los cambios
de iconos están integrados desde el
[PR #407](https://github.com/WeAreProjectApp/projectapp/pull/407).
Esto acredita disponibilidad del código; la recepción real debe comprobarse en
el entorno desplegado. Una instalación sin casos puede estar sana, sin configurar
o sin recibir datos: el listado vacío por sí solo no permite distinguirlo.

### Decisiones que ya representa la implementación

| Pregunta del primer alcance | Comportamiento vigente |
| --- | --- |
| ¿Qué se verifica? | Recepción, asociación al recurso y fuente correctos, reintentos sin duplicados, separación proyecto/servidor, seguimiento persistente y salud de las fuentes. Los criterios se detallan más abajo. |
| ¿Sobre qué proyectos? | ProjectApp (`projectapp`), Mimittos (`mimittos_project`) y Tenndalux (`tenndalux_project`), en `vps-projectapp-prod`. El vínculo opcional con un proyecto comercial se configura explícitamente. |
| ¿Qué icono cambia para distinguir Monitoreo y Hosting? | Monitoreo usa una lupa; Hosting conserva la base de datos. |
| ¿Qué conjunto de iconos se usa? | El componente SVG existente `SidebarIcon`, compartido por la navegación. Propuestas usa una bolsa con monedas, sin signo de peso/dólar; no se incorporó un emoji con alas ni una dependencia nueva. |
| ¿Qué incluye el MVP? | Casos y reportes paginados, filtros, evidencia, estados, notas, historial y estado de las fuentes. No hay asignaciones ni notificaciones nuevas. |
| ¿De dónde llegan los eventos? | De productores del toolkit y exportadores de las aplicaciones, mediante una cola local que entrega a la API autenticada. No se importan desde el correo. |
| ¿Qué significa seguimiento? | Pasar entre Pendiente, En revisión y Resuelto; agregar notas con autor/fecha y consultar la historia de entregas y cambios. |
| ¿Se elimina el correo? | No. Convive con el panel y conserva sus destinatarios, horarios y cooldown. |
| ¿Qué otros monitoreos se contemplan? | Alertas del servidor, healthcheck, integridad, resumen semanal/MySQL, diagnóstico, tráfico, QA, restauración, drift, heartbeat SMTP, avisos SSH y salud del colector. Su configuración y activación se verifican por fuente. |

La librería del código es **django-silk (Silk)**, correspondiente a las consultas
lentas y posibles N+1 mencionadas como «Sync» en el requerimiento. El inventario
de productores y su significado se mantiene en
`vps-ops-toolkit/docs/projectapp-monitoring.md`.

## Uso del panel

1. Ingresar como administrador del panel y abrir **Monitoreo**.
2. Elegir **Proyectos**, **Servidores** o **Reportes**. Filtrar por recurso,
   fuente, severidad, estado, texto o fechas; las páginas tienen 25 registros.
3. Abrir un caso para consultar evidencia e historial. Cambiar entre Pendiente,
   En revisión y Resuelto, o agregar una nota con autor y fecha.
4. Si otra persona o una nueva observación actualizó el caso, el guardado devuelve
   conflicto: actualizar el detalle antes de decidir nuevamente.
5. Consultar **Estado de las fuentes**: Sin datos, Actualizada, Atrasada o
   Deshabilitada. Un panel sin casos no demuestra que un colector esté funcionando.

La recuperación técnica no cierra el caso. Una detección observada después de
su cierre manual lo reabre; una entrega histórica retrasada no lo reabre. Una
huella identifica un caso dentro de su fuente y recurso; no se fusionan casos
entre proyectos ni entre fuentes. No hay asignaciones ni notificaciones nuevas.

Los reportes son informativos y se conservan 90 días. Los hallazgos se atienden
en casos separados, con enlace al reporte cuando la fuente lo ofrece. Se conserva
el historial de casos/notas y los recibos de idempotencia aunque expire el reporte.
Los resúmenes exportados pueden estar limitados y saneados; el original queda en
el VPS. El panel renderiza todo como texto, nunca como HTML recibido.

## Contrato de ingestión

`POST /api/monitoring/v1/ingest/` requiere `Authorization: Bearer <credencial>`.
La credencial se almacena como hash, tiene recursos autorizados y se puede revocar.
Los endpoints administrativos usan sesión Django + CSRF e `IsAdminUser`, no JWT.

```json
{
  "schema_version": 1,
  "external_id": "delivery-unique-id",
  "server": "vps-projectapp-prod",
  "resource": "projectapp",
  "source": "silk",
  "kind": "detection",
  "observed_at": "2026-09-19T12:00:00Z",
  "fingerprint": "stable-rule-and-route",
  "title": "Posible N+1 en listado",
  "severity": "warning",
  "evidence": {"route": "api/projects/", "query_count": 20, "threshold": 10}
}
```

- Tipos: `detection`, `recovery`, `report`, `heartbeat`. Severidades: `info`,
  `warning`, `critical`. El cuerpo completo no puede superar 128 KiB.
- Detección requiere huella y título; recuperación requiere huella; reporte
  requiere título/texto; heartbeat requiere `enabled` y admite `error`.
- Evidencia: objeto plano limitado a métricas/ruta/regla/resultado, máximo
  8.000 caracteres JSON. No admite objetos anidados, SQL ni cabeceras como claves.
  Los productores deben sanear valores: la allowlist no reemplaza esa obligación.
- Misma fuente + `external_id` + contenido: respuesta 200 con `duplicate=true`.
  Contenido distinto con el mismo identificador: 409, sin sobrescribir el recibo.
  Nueva entrega: 201. La cola sólo elimina tras confirmar un `id` en 200/201.
- `report_id` opcional identifica el `external_id` de un reporte entregado antes,
  en la misma fuente; nunca un ID de otro proyecto.
- Las fechas de observación deciden la condición actual; la recepción queda
  registrada por separado. Se rechazan fechas más de cinco minutos en el futuro.

`PATCH /api/monitoring/resources/:id/` con `{"project": <id>}` vincula un
recurso técnico con `accounts.Project` de manera explícita. `null` desvincula.
No se infieren relaciones por nombre ni se crean proyectos de negocio al importar
el inventario. Una relación duplicada devuelve 409.

## Criterios de verificación

Las pruebas aisladas validan el comportamiento del código. La revisión operativa
valida que el productor y la API estén conectados en el servidor desplegado.
Ambas evidencias son necesarias para declarar el primer alcance operativo.

| Criterio | Evidencia mínima |
| --- | --- |
| Recepción | Una entrega obtiene confirmación 200/201 con ID y se refleja en el recurso/fuente esperados. Registrar última recepción y observación por cada proyecto y por el servidor. |
| Asociación | Un evento de proyecto aparece en Proyectos y uno del host en Servidores. Un reporte o una credencial de otro recurso no puede asociarse al caso. |
| Duplicados | Reenviar la misma entrega conserva su ID y no aumenta las detecciones. Reutilizar su identificador con contenido distinto devuelve conflicto. |
| Seguimiento | El cambio de estado y la nota conservan autor/fecha al reabrir el detalle. Un guardado con versión antigua no pisa el estado vigente. |
| Recuperación | La recuperación técnica no cierra el caso manualmente. Una nueva detección posterior al cierre lo reabre; una entrega histórica anterior no lo reabre. |
| Salud | Cada fuente distingue Sin datos, Actualizada, Atrasada y Deshabilitada. Contrastar fechas, errores del colector y pendientes/rechazos de la cola. |
| Silk | Verificar la activación real por proyecto y, si está activo, la recepción del export saneado. Una fuente deshabilitada no acredita recepción; una muestra sin hallazgos no demuestra recuperación. |
| Interfaz | Abrir Monitoreo desde la navegación; cambiar entre proyectos, servidores y reportes; consultar detalle, guardar estado/nota y comprobar errores recuperables. Revisar también los iconos de Propuestas y Hosting. |

No provocar caídas, restauraciones ni avisos reales para validar el módulo.
Los reintentos, conflictos y cambios de seguimiento se prueban en el entorno
aislado; una prueba controlada contra la instalación sigue el runbook operativo.
La inspección del servidor debe registrar resultados por recurso y fuente sin
copiar tokens, SQL, datos personales ni contenido de reportes al documento.

Resultado de la revisión del 2026-09-28:
[verificación del primer alcance](audits/2026-09-28-monitoring-first-scope.md).

## Despliegue y seguridad

No ejecutar `migrate`, provisión de inventario, generación de tokens, fake data ni
cambios de `.env` desde un worktree: su `.env` apunta a producción.
El deploy normal aplica las migraciones de `monitoring`. Después, el operador
sigue `vps-ops-toolkit/docs/projectapp-monitoring.md` para crear inventario y
credencial, instalar la cola/colector y realizar las pruebas de entrega.

La tarea Huey de retención elimina como máximo cuatro lotes de 500 por tabla y
corrida, sin una transacción que abarque todo el historial. Los listados omiten
textos/evidencia grandes en SQL y cargan sus relaciones sin consultas por fila.

Silk se mantiene apagado hasta el rollout autorizado: muestra inicial del 5 %,
máximo de 1.000 solicitudes, sin cuerpos HTTP, profiler ni EXPLAIN. Se excluyen
rutas sensibles y se exportan rutas parametrizadas y métricas, nunca SQL ni
parámetros. **Silk puede almacenar valores SQL localmente**: el filtro del export
no sanea retroactivamente su base. Antes de activarlo, revisar privacidad y
retención local, observar ProjectApp durante 24 horas y luego habilitar los otros
proyectos por separado. El muestreo indica posibles N+1; no confirma su causa ni
permite inferir recuperación sólo porque no volvió a aparecer en la muestra.

`create_fake_monitoring` sólo funciona con `FAKE_DATA_ALLOWED=True` e
`IS_PRODUCTION=False`; sirve para entornos aislados. No se ejecuta en este VPS.

## Límites de este MVP

No es una plataforma de series temporales, APM completo ni remediación automática.
El módulo nuevo no forma parte del registro MCP; no se exponen casos, notas,
credenciales ni reportes por conectores MCP en este alcance.
No cambia umbrales, horarios, reinicios ni destinatarios de monitores existentes.
La caída de ProjectApp impide ver el panel; la cola local y los correos actuales
mantienen la continuidad. La salud del colector y la cola también se inspeccionan
localmente; no se presume entrega por haber escrito un archivo.
