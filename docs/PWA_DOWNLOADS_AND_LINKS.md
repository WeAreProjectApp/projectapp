# Descargas y enlaces desde ProjectApp instalada

El panel instalado mantiene la pantalla al descargar contratos, borradores,
PDF comerciales/técnicos, acuerdos de confidencialidad, adjuntos y CSV de
analítica. La descarga indica que está en curso y permite reintentar un error.
El nombre viene del servidor cuando está disponible. Las vistas previas de
PDF e imágenes se abren en los visores existentes del panel.

Los enlaces públicos y externos solicitan una pestaña del navegador. Chrome
puede abrir ProjectApp en su lugar si la instalación tiene activada la captura
de enlaces: el ámbito actual de la PWA es todo el sitio, para incluir ambos
idiomas y el login. `target="_blank"` no anula esa preferencia.

## Elegir el navegador para los enlaces

En el computador donde instalaste ProjectApp:

1. Abre Chrome y entra en `chrome://apps`.
2. Busca ProjectApp y abre su configuración desde el menú contextual. También
   puede estar disponible «Información de la aplicación» en el menú de la PWA.
3. Si tu versión ofrece la opción de abrir enlaces compatibles en ProjectApp,
   desactívala o selecciona abrirlos en el navegador. El nombre y la ubicación
   de esta opción dependen de la versión y del sistema operativo.
4. Abre ProjectApp desde su acceso directo y prueba un enlace público. Debe
   aparecer en una pestaña de Chrome y conservar la ventana del panel.

La preferencia es local a ese perfil de Chrome y también afecta los enlaces
internos abiertos desde fuera. No requiere cambiar ni reinstalar ProjectApp.
Si la opción no aparece o Chrome sigue capturando enlaces, registra su versión
y sistema operativo: la corrección acotada no puede imponer este ajuste desde
la web. Mientras tanto, copiar el enlace y pegarlo en una pestaña normal permite
abrirlo en el navegador.

Referencia: [gestión de navegación de PWA en Chrome](https://developer.chrome.com/docs/capabilities/pwa-navigation-management).

## Comprobación en la aplicación instalada

Esta comprobación usa una instalación real; una prueba de Playwright que
simule `display-mode: standalone` no acredita el tipo de ventana de Chrome.

- Descargar contrato final, borrador, PDF comercial/técnico, acuerdo de
  confidencialidad y CSV: se conserva la pantalla y no aparece otra ventana.
- Confirmar el nombre del archivo, incluidos espacios y acentos; repetir con
  un contrato de producto y uno de servicio.
- Pulsar dos veces durante una descarga: se inicia una sola petición.
- Simular una desconexión y reintentar: se ve un error y después se descarga.
- Abrir una vista previa: cerrar el visor devuelve al mismo documento.
- Abrir un enlace público y otro externo con la captura desactivada: aparecen
  en Chrome. Navegar entre secciones internas sigue dentro de ProjectApp.
- Repetir el recorrido en español e inglés y en una pestaña normal.

## Contrato técnico

`usePanelDownload` usa el cliente de sesión del panel para `/api/` y peticiones
del mismo origen para archivos. Rechaza respuestas vacías, HTML/JSON y tipos
incompatibles con el documento esperado. No mezcla JWT de la plataforma ni
envía credenciales a terceros. Un cambio de destino o desmontaje cancela la
petición del control. Los enlaces conservan `href` y `download` como soporte
nativo; su activación normal descarga un Blob sin navegar.

El manifiesto, el worker, las rutas públicas y la autenticación no cambian.
No se cachean documentos ni se añaden dependencias. Los tests focales de
`PanelDownloadLink`, contratos y confidencialidad verifican los archivos y
la ausencia de ventanas nuevas; la comprobación del ajuste local de Chrome
debe registrarse por separado después del despliegue.

## Evidencia de esta entrega — 2026-09-29

Se instaló el manifiesto real mediante CDP en Chrome for Testing
151.0.7922.34, Linux con Xvfb, usando un perfil y directorios XDG temporales.
Una página local de instalación expuso el manifiesto para evitar depender de
la sesión del instalador; después se abrió el editor real de Nuxt, con API
simulada y sin datos productivos. No se simuló `display-mode`.

- Ventana instalada: `display-mode: standalone` verdadero.
- Descarga: bytes exactos, nombre `contrato español.pdf`, misma URL y ninguna
  ventana adicional.
- Con `linkCapturing: false` en ese perfil: el enlace público abrió una ventana
  con `display-mode: standalone` falso; la PWA original siguió en modo instalado.
- La instalación temporal se desinstaló al terminar. La preferencia del Chrome
  del operador permanece pendiente de configurar en su propio computador.

Esta evidencia verifica el manejo nativo de ventanas de ese navegador; no
sustituye la comprobación posterior al despliegue en la versión del operador.
