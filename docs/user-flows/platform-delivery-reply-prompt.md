### Platform: preparar y revisar una respuesta fundamentada

Fuente: `DeliveryPromptWorkbench.vue`, `DeliveryWorkspace.vue` y
`accounts.services.delivery_authoring`.

El administrador abre «Preparar respuesta» en una etapa publicada. El contrato y
alcance se obtienen de esa etapa; el prompt distingue las fuentes contractuales de
las guías, rondas, decisiones y conversación pública. No aparecer en una guía no
demuestra que un pedido esté fuera del contrato, y una conversación no modifica
el acuerdo por sí sola.

Cada pedido se clasifica como dentro, fuera o indeterminado, con citas que el
servidor verifica contra las fuentes conservadas. Una fuente incompleta o una
incertidumbre bloquea una conclusión definitiva fuera del alcance. Validar la
cita acredita su existencia, no su interpretación.

La respuesta es un borrador editable. Usarlo no envía un mensaje; el administrador
revisa el texto final y lo envía mediante la acción manual existente, con documento
opcional. Una edición posterior exige revisar de nuevo. Las firmas y conformidades
del cliente permanecen intactas.

`delivery-reply-prompt.spec.js` cubre envío manual sin adjuntos, revisión del texto
editado, rechazo de una clasificación fuera del alcance con fuentes incompletas y
consulta de la conversación pública que originó el prompt.
