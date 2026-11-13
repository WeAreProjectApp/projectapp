# Contratos de programas en el Gestor de documentos

PA-255 (Building with Us) y PA-256 (Células / Building on Demand) comparten el
contrato vigente entre su módulo y un documento estable del Gestor. No se crea
otra copia editable ni se importa un PDF como fuente contractual.

## Uso

En la pestaña Contrato de cada módulo se puede leer el contenido, previsualizar
y descargar el PDF. «Editar en el Gestor de documentos» abre el documento
vinculado. El editor permite cambiar contenido y presentación y exige un motivo.
Al guardar se actualizan la revisión, el historial privado y el PDF; el enlace
de regreso abre el contrato del módulo. Al volver a la pestaña o recuperar el
foco del navegador se vuelven a consultar el contrato y su historial.

La identidad, carpeta, cliente/proyecto, idioma y visibilidad permanecen
protegidos. Tampoco se habilitan archivo, eliminación, duplicación o movimiento
del documento contractual. Las otras tres plantillas de propuestas conservan
su comportamiento de sólo lectura.

## API y MCP

- `GET /api/documents/<id>/detail/` y `read_document` devuelven la fuente vigente,
  variante, versión, fecha de sincronización, ETag y capacidades de edición.
- `PATCH /api/documents/<id>/update/` exige `if_match` y `change_note` para estos
  contratos. Admite `content_markdown`, `text_formats` para ese contenido,
  `include_portada`, `include_subportada`, `include_contraportada` y `template_style`.
- `update_document` del MCP Documentos admite la misma operación, con `markdown`
  como nombre canónico del contenido. No admite ambos alias a la vez.
- Los MCP de Programas y sus compatibilidades mantienen las operaciones
  contractuales existentes, su vista previa y confirmación. Todos delegan en el
  mismo escritor del dominio; una edición invalida las lecturas previas de las
  demás vías.
- El ETag documental incluye la revisión contractual además de la fecha del
  documento. Los candados siguen el orden contrato → espejo → documento antes
  de actualizar presentación o crear una revisión.
- Sin versión: HTTP 428. Versión superada: HTTP 409 (`STALE_VERSION`). Contenido
  o campos no permitidos: HTTP 400. Fallo de sincronización: HTTP 503
  (`MIRROR_SYNC_FAILED`). Un fallo revierte revisión, presentación, PDF y nota.
- Un guardado sin cambios no añade una revisión. Cambiar presentación sí crea
  una revisión y regenera el PDF, incluso si el texto no cambió.

Los permisos administrativos existentes y la sesión/CSRF del Panel se mantienen.
La fuente contractual usa la gramática editorial `markdown_html_v1` en editor,
consulta y PDF, sin permitir HTML activo.

## Vínculos y despliegue

No requiere migraciones. Se reutilizan los documentos existentes en Contratos.
Si falta el vínculo, el módulo informa el estado sin ofrecer un enlace roto.
Su inicialización o reparación sigue siendo una operación explícita mediante
las herramientas y comandos existentes de cada programa. Las lecturas no
aprovisionan documentos y esta entrega no modifica datos productivos.

## Validación

Las pruebas automatizadas se ejecutan exclusivamente en CI: guardado y lectura
compartidos, motivo/versión obligatorios, formato, no-op, presentación, permisos,
campos protegidos, conflicto con MCP y reversión tras fallo del PDF. El recorrido
de navegador cubre el acceso desde el módulo, la edición y el regreso, además
de la conservación del borrador ante conflicto y error.

CI y sus simulaciones HTTP no acreditan validación manual en DEV. El traspaso
manual debe identificar PR, SHA servido, entorno aislado y ambos documentos
ficticios; nunca se prueba este guardado sobre contratos reales de clientes.

La revisión jurídica, participación, incumplimiento, propiedad intelectual,
salida y discrepancia sobre consumo permanecen fuera de esta entrega. La
existencia del documento o de sus revisiones no atribuye aprobación ni firma.
