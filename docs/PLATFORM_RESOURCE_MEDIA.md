# Archivos privados de recursos de Platform

Esta entrega prepara la retirada de los enlaces públicos de los recursos. El
código se verifica en un entorno aislado; el cierre en el servidor requiere
desplegar backend, frontend y nginx, y comprobar HTTP en ese entorno. Los tests
locales no acreditan un despliegue.

## Qué cambia

| Familia | Nuevas cargas | Descarga |
|---|---|---|
| Archivo actual | `platform-resources/current/`, privado | JWT, propietario o administrador de Platform |
| Versiones | `platform-resources/versions/`, privado | Mismo permiso; versión hija del recurso seleccionado |
| Adjuntos | `platform-resources/attachments/`, privado | Mismo permiso; adjunto hijo del recurso seleccionado |
| Archivos del cliente | `platform-resources/client_uploads/`, privado | Mismo permiso; archivo hijo del recurso seleccionado |

Los DTO conservan `file_url`, que ahora contiene una ruta **relativa**:
`/api/accounts/projects/<project>/deliverables/<resource>/files/<kind>/`.
Los hijos usan `?file_id=<id>`; `current` no acepta ese parámetro. La pantalla
descarga con su cliente JWT y un Blob, sin tokens en la URL. Las respuestas usan
`FileResponse`, MIME y nombre originales, `no-store` y `nosniff`. El límite
previo de materialización de 25 MB permanece en MCP; no limita el stream JWT.

Los permisos existentes se conservan. Un cliente Django staff no obtiene el rol
administrador de Platform ni accede a recursos ajenos o archivados. Los datos
retenidos mantienen sesión, `IsAdminUser` y comprobación de contexto y registro
antes de abrir el archivo; no se sustituye su permiso por el de Platform.

## Transición histórica

`accounts.0081` cambia el almacenamiento futuro y permite nombres de 500
caracteres. No mueve bytes ni reescribe nombres históricos. Depende de
`accounts.0080` y de la unión `content.0285`.

Un nombre `deliverables/...` lee **exclusivamente** su original en storage
público, después de autorizar el registro. `platform-resources/...` lee
exclusivamente storage privado. No se busca en otra raíz si el original falta.
El storage de recursos no ofrece `.url`; el DTO construye la ruta de API.

Nginx devuelve 404 a `/media/deliverables` y `/media/deliverables/...` antes
del alias general. Django aplica el mismo rechazo antes de media DEBUG y del
catch-all de Nuxt. Esa retirada funciona antes de convertir los archivos.
Otra media pública sigue usando su alias normal.

## Guion operativo

Estas commands se ejecutan desde el checkout desplegado con el intérprete del
servicio y `--settings=projectapp.settings_prod`. **No se ejecutan desde un
worktree ni contra datos reales durante QA.** Sólo los tests con settings de
test, SQLite y raíces temporales aisladas ejercitan su escritura local.

1. Desplegar y comprobar la retirada HTTP, el backend y la pantalla JWT antes
   de convertir. Conservar backup y originales.
2. Reservar una **ventana de mantenimiento**. La conversión mantiene bloqueos
   de proyectos, contextos retenidos, padres e hijos mientras verifica y copia;
   las escrituras de recursos pueden esperar. Revisar volumen y espacio libre.
3. Ejecutar `inventory_platform_resource_media --manifest <ruta-privada.json>`.
   La ruta debe estar directamente bajo `PRIVATE_MEDIA_ROOT/migration_manifests`.
   Crea un archivo privado nuevo sin sobrescribir otro inventario. La salida
   informa SHA-256, archivos y bloqueados, sin imprimir registros ni bytes.
   Incluye las cuatro familias, registros sin proyecto y sus descendientes.
   Un padre sin archivo aporta su propiedad a los hijos sin generar una entrada
   propia de archivo.
4. Revisar el manifest privado: modelo, id, referencia, SHA-256, tamaño,
   propietario, contexto retenido y destino. Un original perdido bloquea la
   conversión; recuperarlo del backup y generar un inventario nuevo.
5. Validar sin aplicar con `privatize_platform_resource_media --manifest
   <misma-ruta> --manifest-sha256 <sha-revisado>`. Cambios de selección,
   referencia, propietario o bytes exigen un inventario nuevo.
6. Aplicar esa misma command con `--apply` y el SHA literal revisado. Cada copia
   privada temporal se verifica antes de publicar exclusivamente su destino,
   sin reemplazar una copia existente. Se revalidan registros bajo bloqueo antes
   de cambiar las referencias. Propietario y conservación permanecen iguales.
7. Comprobar las cuatro familias, datos retenidos y retirada pública. Repetir
   el mismo manifest es idempotente: verifica destinos convertidos sin duplicar.

## Recuperación

Un fallo revierte las referencias y limpia sólo las nuevas copias sin
referencias. Originales y backups **no se borran**. Una copia privada incompatible
no se reemplaza automáticamente. El manifest permanece inmutable para revisar
o reanudar.

Un rollback conserva tanto la retirada de nginx/Django como el lector autorizado
de nombres privados e históricos. No volver a una versión que publique URLs de
storage ni reabrir el alias para compensar una descarga rota. Recuperar el
original o la copia verificada bajo esa protección.

## QA

- Anónimo, propietario, cliente ajeno y administrador para las cuatro familias;
  incluir cliente staff, archivados, ids malformados e hijos de otro recurso.
- Bytes, MIME, nombre y headers originales; DTO relativo sin credenciales.
- SQLite y media temporales: convertir, conservar originales y repetir. Cambiar
  dueño, referencia, bytes o manifest debe rechazar; un fallo de disco revierte.
- Datos retenidos y padre sin archivo con hijos: permiso de sesión antes y
  después de convertir, sin ofrecer un proyecto operativo nuevo.
- Nginx **aislado en localhost**, con el fragmento real del template: rechazar
  URLs históricas para anónimo, propietario y ajeno, comprobar la API JWT y otra
  media pública. `PLATFORM_MEDIA_NGINX_BINARY` permite señalar un binario local;
  los tests no instalan nginx ni modifican el servicio.
- Después del deploy, repetir HTTP en el destino y registrar el resultado. La
  evidencia local no cierra por sí sola los enlaces del servidor.
