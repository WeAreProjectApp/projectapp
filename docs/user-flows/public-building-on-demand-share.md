### FLOW: `public-building-on-demand-share`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Abrir Compartir Building on Demand y pulsar Copiar enlace; si el portapapeles rechaza la copia, consultar el aviso y el enlace disponible para copiar manualmente.
- **Outcomes:** `success`, `failure`
- **Result:** El diálogo conserva la URL actual y muestra «Enlace copiado» tras copiarla al portapapeles. Si la copia falla, aparece «No pudimos copiar el enlace. Selecciónalo y cópialo manualmente.» y el enlace permanece visible. Se puede cerrar el diálogo sin perder la presentación.
- **Evidence:** `frontend/components/BuildingOnDemand/ProgramView.vue:252`; `frontend/components/PublicDocumentShareButton.vue:47`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Gap:** El rechazo de la opción de compartir con otras aplicaciones tiene un aviso visible propio; no se da por cubierto al probar el rechazo del portapapeles.
