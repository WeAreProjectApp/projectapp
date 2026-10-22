# Building on Demand — video explicativo

Pieza de 60 s, 1920×1080, 30 fps. Mismo pipeline brag v2 de Alianza, voz
`es-CO-SalomeNeural`, música con ducking y subtítulos sincronizados.

## Guion y fuentes

| Tiempo | Escena | Fuente pública |
|---|---|---|
| 0–8 s | Siguiente paso del producto | hero |
| 8–18 s | Célula compartida de siete personas | cell y roles según nivel |
| 18–30 s | Starter, Business y Enterprise; bolsa mensual | tiers y bag |
| 30–42 s | Priorizar, estimar y aprobar; sin alcance ni fecha fija | bag.rules |
| 42–52 s | Servidor, mantenimiento y soporte | hosting |
| 52–60 s | Explorar niveles y estimador; conversar | cta |

Fuente congelada: `../content/building-on-demand.es.js`, API pública versión 1
consultada durante esta entrega. Se contrasta con la siembra `0291` y las
reglas de la base de integración. No se incluyen precios ni datos de clientes.

La apertura está asentada desde el frame cero. Los textos narrados complementan
las tarjetas; las condiciones completas siguen en el programa y su contrato.

## Reproducir

Desde `explainers/`, con el venv de voz en PATH:

```bash
npm run narration -- --video building-on-demand --edition brag-v2
npm run check -- --video building-on-demand --edition brag-v2 --json
npm run poster -- --video building-on-demand --edition brag-v2 --at 0.1
npm run render -- --video building-on-demand --edition brag-v2 --with-narration --music-volume 0.22 --priority 5
npm run export -- --video building-on-demand --edition brag-v2
```

Para refrescar exclusivamente la fuente de este video, usar
`npm run content -- --video building-on-demand --edition brag-v2` y revisar
las afirmaciones del guion antes de regenerar narración y render.

El video y la portada se empaquetan como recurso predeterminado ES. No hay
fallback español para EN. Desde Células › Programa se puede cargar otro MP4,
quitarlo, restaurar esta pieza y cambiar la visibilidad pública sin modificar
las revisiones del programa ni del contrato.
