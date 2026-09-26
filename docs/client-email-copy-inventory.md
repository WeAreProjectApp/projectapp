# Inventario universal de correos salientes

**Actualizado:** 2026-08-28

**Fuente ejecutable:** `backend/content/services/outbound_email_inventory.py`

**Punto único de salida:** `backend/content/services/email_delivery_service.py`

Este inventario enumera **todo correo que ProjectApp puede emitir hoy**, sin
importar módulo, tipo de destinatario o sensibilidad. El gateway sólo acepta
claves registradas aquí; por eso una salida nueva no puede pasar a producción
sin declarar su familia y queda cubierta por la regla de copia por
construcción.

## Inventario completo (58 canales)

| # | Familia configurable | Clave de plantilla | Salida / disparador |
|---:|---|---|---|
| 1 | Propuestas | `proposal_sent_client` | Envío o reenvío individual de una propuesta. |
| 2 | Propuestas | `proposal_multi_sent_client` | Envío agrupado de varias propuestas del mismo cliente. |
| 3 | Propuestas | `proposal_reminder` | Recordatorio automático de propuesta vigente. |
| 4 | Propuestas | `proposal_urgency` | Aviso de urgencia con descuento. |
| 5 | Propuestas | `proposal_urgency_no_discount` | Aviso de urgencia sin descuento. |
| 6 | Propuestas | `proposal_accepted_client` | Confirmación de propuesta aceptada. |
| 7 | Propuestas | `proposal_finished_client` | Confirmación de propuesta o proyecto finalizado. |
| 8 | Propuestas | `proposal_rejected_client` | Confirmación de propuesta rechazada. |
| 9 | Propuestas | `proposal_reengagement` | Reactivación posterior al rechazo o la inactividad. |
| 10 | Propuestas | `proposal_abandonment_followup` | Seguimiento por abandono de la propuesta. |
| 11 | Propuestas | `proposal_investment_interest_followup` | Seguimiento por interés en inversión. |
| 12 | Propuestas | `proposal_scheduled_followup` | Seguimiento comercial programado. |
| 13 | Propuestas | `proposal_negotiation_confirmation` | Confirmación al cliente de solicitud de negociación. |
| 14 | Propuestas | `magic_link` | Enlace de acceso a propuestas. |
| 15 | Propuestas | `proposal_response_notification` | Aviso interno de respuesta a una propuesta. |
| 16 | Propuestas | `proposal_first_view_notification` | Aviso interno de primera apertura. |
| 17 | Propuestas | `proposal_comment_notification` | Aviso interno de comentario. |
| 18 | Propuestas | `proposal_revisit_alert` | Alerta interna por nueva visita. |
| 19 | Propuestas | `proposal_share_notification` | Aviso interno de propuesta compartida. |
| 20 | Propuestas | `proposal_stakeholder_detected` | Detección interna de otro interesado. |
| 21 | Propuestas | `seller_inactivity_escalation` | Escalamiento por inactividad comercial. |
| 22 | Propuestas | `proposal_negotiation_notification` | Aviso interno de negociación. |
| 23 | Propuestas | `post_rejection_revisit_alert` | Alerta de visita posterior al rechazo. |
| 24 | Propuestas | `daily_pipeline_digest` | Resumen diario del pipeline comercial. |
| 25 | Propuestas | `proposal_post_expiration_visit` | Visita posterior al vencimiento. |
| 26 | Propuestas | `proposal_stage_warning_notification` | Aviso de etapa próxima a vencer. |
| 27 | Propuestas | `proposal_stage_overdue_notification` | Aviso de etapa vencida. |
| 28 | Diagnósticos | `diagnostic_initial_sent` | Envío inicial de diagnóstico técnico. |
| 29 | Diagnósticos | `diagnostic_final_sent` | Entrega del diagnóstico terminado. |
| 30 | Diagnósticos | `diagnostic_custom_email` | Correo compuesto desde un diagnóstico. |
| 31 | Diagnósticos | `diagnostic_documents_sent` | Envío de documentos del diagnóstico. |
| 32 | Documentos y comunicaciones | `proposal_documents_sent` | Envío de documentos adjuntos de una propuesta. |
| 33 | Documentos y comunicaciones | `branded_email` | Correo manual con marca desde Emails. |
| 34 | Documentos y comunicaciones | `proposal_email` | Correo manual asociado a una propuesta. |
| 58 | Documentos y comunicaciones | `secure_link_received_team` | Aviso interno de enlace seguro creado por un cliente; no incluye el enlace ni el contenido. |
| 35 | Cuentas de cobro | `collection_account_sent` | Emisión, reenvío o retry manual de una cuenta de cobro. |
| 36 | Contabilidad | `accounting_change` | Aviso interno de cambio contable. |
| 37 | Contabilidad | `accounting_card_reminder` | Recordatorio interno de tarjeta. |
| 38 | Contabilidad | `accounting_statement_reminder` | Recordatorio interno de extracto. |
| 39 | Contabilidad | `accounting_payment_calendar` | Calendario interno de pagos y vencimientos. |
| 40 | Contabilidad | `payment_status_team` | Aviso interno del estado de un pago. |
| 41 | Plataforma | `document_signed_client` | Confirmación al cliente de documento firmado. |
| 42 | Plataforma | `client_flow_first_login_team` | Aviso interno de primer ingreso del cliente. |
| 43 | Plataforma | `client_flow_email_validated_team` | Aviso interno de correo validado. |
| 44 | Plataforma | `client_flow_document_signed_team` | Aviso interno de firma completada. |
| 45 | Tareas y operación | `task_deadline_notification` | Aviso de fecha límite de una tarea. |
| 46 | Tareas y operación | `task_alert_notification` | Alerta operativa de una tarea. |
| 47 | Tareas y operación | `generic_internal_notification` | Notificación interna genérica. |
| 48 | Tareas y operación | `frontend_build_failure` | Alerta por fallo del build frontend. |
| 49 | Tareas y operación | `linkedin_token_expiry` | Alerta por vencimiento del token de LinkedIn. |
| 50 | Tareas y operación | `proposal_notification_diagnostic` | Diagnóstico operativo del canal de propuestas. |
| 51 | Seguridad y acceso | `client_invitation` | Invitación de cliente con acceso inicial. |
| 52 | Seguridad y acceso | `admin_invitation` | Invitación de administrador con acceso inicial. |
| 53 | Seguridad y acceso | `password_changed` | Confirmación de cambio de contraseña. |
| 54 | Seguridad y acceso | `verification_code_onboarding` | Código OTP de onboarding. |
| 55 | Seguridad y acceso | `verification_code_password_reset` | Código OTP de recuperación de contraseña. |
| 56 | Seguridad y acceso | `verification_code_email_validation` | Código OTP de validación de correo. |

## Política de copia y trazabilidad

1. El correo principal se intenta primero. Una falla principal conserva el
   comportamiento de error/retry del flujo que lo originó.
2. Después de un envío principal exitoso, el gateway resuelve los destinatarios
   activos cuya configuración incluya la familia del canal.
3. Cada destinatario interno recibe un sobre independiente, sólo en `BCC`; su
   dirección no aparece en los encabezados visibles del correo principal.
4. La lista se deduplica contra `to`, `cc` y `bcc` del mensaje original. Si una
   dirección ya era destinataria, se registra una copia `skipped` y no se envía
   por segunda vez.
5. Una falla al resolver o entregar una copia no bloquea, no cambia y no
   reintenta el correo principal. Queda registrada de forma independiente.
6. `EmailLog.delivery_id` agrupa la fila principal y sus intentos `copy`; todos
   referencian el mismo snapshot exacto capturado antes del SMTP.
7. El Historial global muestra destinatario, estado, error, familia, cuerpo,
   enlaces, peso y adjuntos exactos. Un fallo al guardar esa evidencia bloquea
   el envío principal.
8. Por decisión de producto, el cuerpo completo también se conserva para los
   correos de Seguridad y acceso. Cualquier administrador autorizado para el
   panel de Emails puede consultarlo; la interfaz lo advierte expresamente.

## Configuración y volumen

La lista vive en **Panel → Emails → Configuración → Copias de todos los
correos** y es independiente de los destinatarios de avisos internos. Cada
fila puede pausarse, eliminarse o limitarse a ocho familias:

- Propuestas
- Diagnósticos
- Documentos y comunicaciones
- Cuentas de cobro
- Contabilidad
- Plataforma
- Tareas y operación
- Seguridad y acceso

Al crear un destinatario quedan seleccionadas las ocho familias; el punto de
partida es “copiar todo”, pero la segmentación permite reducir volumen sin
cambiar código. Cada correo principal puede producir hasta un envío SMTP
adicional por destinatario configurado. Se debe vigilar cuota, ruido de bandeja
y almacenamiento del historial.

## Activación de `carlos18bp@gmail.com`

La migración `content.0225` crea o reactiva esta dirección en
`EmailCopyRecipient` con las ocho familias. Así el despliegue no depende de una
alta manual para cumplir la notificación solicitada; después sigue siendo una
fila administrable desde Configuración. La validación operativa debe confirmar
que la traza BCC del primer correo posterior al despliegue figura como Enviado.

## Evidencia de completitud

- La prueba parametrizada compara exactamente las 56 claves, familia por
  familia, con este inventario ejecutable.
- El gateway rechaza cualquier clave no registrada y exige una clasificación
  explícita, incluso para avisos internos o de seguridad.
- Un guard estático recorre el backend productivo y falla ante imports o
  llamadas SMTP directas fuera del gateway.
- Las pruebas del gateway cubren envío principal, BCC, múltiples copias,
  deduplicación, copia omitida, fallo de configuración, fallo SMTP de copia,
  fallo principal, adjuntos, HTML, cuerpo persistido y seguridad.
- Las pruebas API cubren historial global, filtros, trazas anidadas, acceso al
  cuerpo y permisos de administrador; las pruebas de interfaz cubren CRUD,
  segmentación, advertencias y consulta de la traza.
