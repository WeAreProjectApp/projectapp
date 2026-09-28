# Littigio — investigación y reparación documental

## Hechos verificados en producción el 28-09-2026

- Carpeta **80**, raíz activa del perfil cliente **61** (usuario interno **62**).
- Carpeta **124**, manual, sin cliente/proyecto/padre, creada
  **2026-09-28 13:48:31.712457 UTC**; es la única carpeta creada en esa ventana.
- Actividad MCP **18160**: `create_folder` exitoso a las
  **13:48:31.716753 UTC**, credencial 2, principal técnico 68,
  request `378f5dd7-1ba8-4512-b5fb-7d09874e8d81`.
- Revisiones **101–105**: documentos **208, 209, 201, 202, 203**, respectivamente,
  movidos de 80 a 124 por `mcp:documents`, actor 68, entre
  **13:48:36.732965 y 13:48:43.411727 UTC**. Las revisiones muestran únicamente
  el cambio de carpeta. Los eventos MCP **18163–18167** corroboran cada llamada.
- `0270_document_folder_authorship` se aplicó a las
  **21:36:21.797900 UTC**, después de la creación y de los movimientos.
- El servicio actual arrancó a las **22:33:31 UTC**, sobre `b89f033c`.
  El registro cargado publica todos los campos nuevos y no presenta divergencias
  de input schema entre lista y capacidades.

**Conclusión:** el movimiento salió del MCP. La correlación unívoca de creación,
credencial y secuencia identifica el alta por `create_folder`. La carpeta nació
antes de instalar la validación de duplicados y la autoría; la migración marcó
como `unknown` esa fila histórica. La sincronización de clientes no creó ni
trasladó estos documentos. La migración 0270 tampoco mueve contenido.

## Reparación revisada

El alcance autorizado es mover **201, 202, 203, 208 y 209** a 80 y archivar 124.
Los documentos 201–203 no tienen cliente asignado; eso se conserva, al igual que
la asociación existente de 208/209, contenidos, visibilidad, proyectos y fechas
de creación. La reparación cambia ubicación y auditoría de modificación.
La procedencia de 124 sólo se completa contra la evidencia anterior.

Preparar desde el backend del entorno de despliegue, con los settings productivos:

```bash
DJANGO_SETTINGS_MODULE=projectapp.settings_prod venv/bin/python manage.py repair_document_folder --source-folder-id 124 --target-folder-id 80 --client-profile-id 61 --document-ids 201 202 203 208 209 --creation-request-id 378f5dd7-1ba8-4512-b5fb-7d09874e8d81 --manifest /var/backups/projectapp/littigio-repair.json
```

La previsualización no escribe la base. Revisar el manifiesto y conservar un
respaldo previo verificable. Aplicar el mismo manifiesto con `--apply`, su
`--sha256`, el `--actor-id` del administrador y `--backup-ref` al archivo no vacío.
No regenerar un manifiesto silenciosamente si falla la comprobación de estado.
La aplicación rechaza worktrees de sesión. El servicio de reparación es
compatible con el modelo productivo 3.0.0 para mantenimiento previo a 0272.

La operación bloquea filas, verifica las huellas y el conjunto exacto, conserva
el historial y archiva sólo una carpeta vacía. Si falla cualquier paso, se
revierte todo. Un recibo en AccountingChangeLog permite verificar idempotencia.
El origen desconocido se conserva cuando no hay evidencia de creación unívoca.

## Verificación y reversión

Comprobar que 80 contiene los cinco IDs y 124 está vacía/archivada; comparar
contenido y asociaciones contra el respaldo. Confirmar cinco revisiones de
movimiento y el recibo de la reparación. Volver a invocar con el mismo
manifiesto debe informar `changed: false`.

Una reversión operativa exige revisar el estado nuevo; no restaurar un dump
completo encima de escrituras posteriores. Usar las ubicaciones y procedencia
anteriores del respaldo y registrar una nueva operación histórica.

## Estado

Investigación completada. Reparación productiva pendiente de ejecución verificada.
