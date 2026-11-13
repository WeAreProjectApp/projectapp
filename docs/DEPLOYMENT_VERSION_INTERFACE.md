# PA-267 · Interfaz de versión para el reconciliador del VPS

## Responsabilidades y evidencia de partida

El despliegue de ProjectApp lo realiza `/deploy-and-check` del toolkit
`vps-ops-toolkit`, mediante `scripts/deployment/deploy-project.sh`, como
`ryzepeck` y dentro de una operación de Integrity de tipo `deploy`. La copia
preparada, los intercambios de artefactos y la recuperación pertenecen a ese
procedimiento. `scripts/deploy.sh` está retirado y siempre termina con código 2.

Carlos confirmó este punto a partir de la lectura de PROD hecha por sa4 el
13-11-2026 (reporte sellado identificado en el encargo como `454469a9…`). Según
esa evidencia, la versión inicial `b01448a2…` coincidía entre HEAD, el ledger
en fase `complete` y el motor de Integrity con `head_matches=true`. Son
referencias abreviadas recibidas en el encargo, no nuevos cotejos de esta sesión
ni valores que se puedan usar como SHA completos en el protocolo.

El registrador de GitHub Deployments se implementa en otra sesión del toolkit.
Será un reconciliador externo a la transacción: no habrá llamadas a GitHub,
cola de registro ni claves privadas dentro de ProjectApp. La clave de la App
no puede ser legible por el usuario del runtime; su custodia se resuelve aparte.

## Contrato de lectura, versión 1

- Producción: `https://www.projectapp.co`.
- Environment de GitHub: `production`.
- Backend: `GET https://www.projectapp.co/api/version/`.
- Frontend: `GET https://www.projectapp.co/version.json`.
- Ambos admiten HEAD y rechazan otros métodos con 405.
- Tipo: `application/json`. Caché: `Cache-Control` incluye `no-store`.
- Sin sesión ni credenciales; sólo se expone identidad pública del código.

Respuesta acreditable (200):

```json
{"schema_version":1,"project":"projectapp","commit":"<SHA hexadecimal completo de 40 caracteres>"}
```

El marcador de ejemplo no es un SHA válido. El consumidor exige versión de
esquema 1, proyecto exacto y commit de 40 caracteres `[0-9a-f]`. No debe seguir
redirecciones a portadas ni aceptar HTML, respuestas 503 o commits nulos.

Un manifiesto ausente, ilegible, mayor de 4096 bytes o inválido responde 503 con:

```json
{"schema_version":1,"project":"projectapp","commit":null}
```

La ruta `/version.json` es explícita y nunca cae en el HTML de la SPA.
`/api/health/` mantiene su contrato y no se convierte en una prueba de versión.

### Origen e intercambio

`npm --prefix frontend run build:django` resuelve la identidad **antes** de
iniciar la generación. En el stage sin `.git`, usa
`FLEET_INTEGRITY_TARGET_PROJECT=projectapp` y `FLEET_INTEGRITY_TARGET_COMMIT`,
ya exportados por el procedimiento real. Para una copia exportada se admite
`PROJECTAPP_BUILD_COMMIT`; si ambas fuentes existen, deben coincidir. Un checkout
Git de desarrollo/CI puede resolver su propio HEAD durante el build, siempre
que no tenga cambios en archivos versionados y coincida con un SHA explícito.
No se busca un repositorio padre ni el HEAD del clon publicado desde el stage.

Tras validar el resultado de Nuxt y los recursos PWA, se genera
`frontend/.output/public/version.json`. Viaja a
`backend/static/frontend/version.json` con el frontend y a
`backend/staticfiles/frontend/version.json` con `collectstatic --clear`.
Permanece dentro de las cuatro raíces de artefactos existentes; no se añade
una raíz de publicación. Un fallo de generación no cambia el manifiesto servido.

El backend captura la copia de `STATIC_ROOT/frontend/version.json` al
inicializar Django, antes de cargar URLs de forma diferida. Ese valor permanece
en memoria durante la vida del proceso, incluso si era desconocido. El endpoint
del frontend lee la copia del directorio servido en cada petición. Ninguno
consulta Git, variables con un SHA alternativo, la base de datos ni GitHub
durante las peticiones. La metadata se fija durante el build; no es un sello
criptográfico ni sustituye las verificaciones del motor de Integrity.

### Uso por el reconciliador y PA-266

Comparar cada respuesta con el SHA completo acreditado por Integrity. Antes
de registrar una publicación, el reconciliador debe comprobar también
`head_matches=true`, ausencia de operaciones abiertas y el cierre acreditado
del despliegue o la recuperación correspondiente. El control de salud por sí
solo no acredita éxito: el cierre puede rechazarse y su abort restaurar la
versión anterior. Un ledger en curso o fallido no debe interpretarse como
publicación nueva sólo por su `target_commit`.

En el camino confirmado no se utiliza `--skip-frontend`: los cuatro artefactos
se preparan desde el mismo commit y se intercambian en una sola transacción.
Una discrepancia entre backend, frontend y SHA acreditado bloquea la
confirmación; no se debe corregir copiando el valor de un componente al otro.
Una respuesta aislada tampoco certifica todos los workers: PA-266 conserva
el cotejo de procesos, reinicios y estado del motor. La recuperación de una
publicación anterior debe anunciar el SHA restaurado, no el objetivo fallido.

Las revisiones anteriores que no tengan estos endpoints/manifiestos pueden
responder 404 o 503. No se reconstruye su identidad desde un HEAD no servido.

## Controles del guion retirado: destino propuesto

| Control | Responsable y ubicación propuesta |
|---|---|
| `check-template-deploy.py`: exige 401 JSON con `detail` no vacío en la API administrativa | Script conservado en ProjectApp; la sesión del toolkit debe conectarlo tras el reinicio y antes del cierre de Integrity. El HTML de una portada no pasa. |
| Instalar Chromium compatible con la dependencia Python Playwright | Preparación de dependencias del toolkit. Las bibliotecas del SO pasan por el aprovisionamiento autorizado; el binario/caché deben ser accesibles al usuario efectivo de Huey. Repetir cuando cambie la versión de Playwright. |
| Arranque headless de Chromium | Preflight del runtime preparado antes de publicar, con el usuario, intérprete y caché que usará el servicio. |
| Git, dependencias, migraciones, build, estáticos y reinicios | Procedimiento transaccional existente; no se duplican en el repositorio. |

Interfaz del chequeo HTTP conservado: desde la raíz del proyecto,
`backend/venv/bin/python scripts/check-template-deploy.py --url https://www.projectapp.co`.
Su salida 0 acredita exclusivamente esa comprobación; una salida distinta
debe impedir el cierre satisfactorio según la integración del toolkit.

Comprobación de Chromium propuesta para el preflight, después de preparar su
instalación y sus dependencias:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    browser.close()
```

Estos destinos son un traspaso a la sesión del toolkit. Este cambio no acredita
que los controles hayan sido incorporados allí ni ejecutados en PROD.

## Eventos GitHub: revisión del repositorio

Inventario de workflows revisados:

| Workflow | Disparadores |
|---|---|
| `ci.yml` | `pull_request`, `push` |
| `fake-data-contract.yml` | `pull_request`, `workflow_dispatch` |
| `mysql-migration-compat.yml` | `pull_request`, `push` |
| `project-collaboration.yml` | `workflow_call`, invocado por el CI del repositorio |
| `responsive-acceptance.yml` | `pull_request`, `push`, `schedule`, `workflow_dispatch` |
| `test-quality-gate.yml` | `pull_request`, `push` |

La revisión de código versionado no encontró consumidores de los eventos
`deployment` o `deployment_status`, handlers de cabeceras GitHub asociados ni
llamadas al API Deployments. Los workflows no ejecutan un despliegue del VPS.
Registrar un deployment no dispara otro despliegue **por medio de este
repositorio**. El guard `check:deployment-events` rechaza ambos disparadores en
sus formas YAML escalar, lista o mapa; la validación usa un parser YAML.

Esto no certifica webhooks de organización, otras Apps o servicios externos.
El webhook inactivo de una App no prueba su ausencia. La revisión externa
previa a activar el registrador sigue con Carlos/PA-266 y la sesión del toolkit;
no requiere dar permisos adicionales a la App de Deployments.

## Validación y entrega

Las pruebas de retiro del guion, respuestas HTTP, congelación de identidad,
build y política de eventos se ejecutan exclusivamente en CI. El job
`deployment-contract` prueba el stage sin Git y la política YAML. El job PWA
existente comprueba el manifiesto del build real y su copia tras collectstatic;
las pruebas del backend comprueban los endpoints sin datos productivos.

La entrega es un PR abierto con SHA exacto y CI verde, sin merge. PA-266 valida
el conjunto sobre el VPS en su ventana autorizada; este documento no acredita
instalación, despliegue ni registro real en GitHub.
