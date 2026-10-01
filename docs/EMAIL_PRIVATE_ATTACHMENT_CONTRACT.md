# Adjuntos privados en el historial común de correos

El gateway y la captura común admiten `private_attachments=True` como argumento
opcional del servicio. Es una decisión del servidor; no se incorpora a los
formularios, cargas de archivos ni schemas MCP existentes.

```python
EmailDeliveryGateway.send(message, template_key=template_key, private_attachments=True)
```

La captura conserva cuerpo y adjuntos antes del transporte. Con esta opción,
los adjuntos se escriben en el storage `private`, bajo
`private-email-history/<delivery_id>/`. El nombre persistido permite resolver
ese mismo storage después de volver a consultar la fila. Las rutas de descarga
del historial mantienen su autorización administrativa y entregan los bytes
retenidos mediante `FileResponse`.

Una captura que recibe `resend_of` con algún adjunto privado conserva privados
los adjuntos del nuevo envío, aunque el llamador omita la opción. Esto también
aplica al servicio de reenvío del historial, que utiliza el snapshot retenido.
Un archivo privado ausente nunca se busca en el storage público.

Los adjuntos históricos con prefijo `email-history/` mantienen su storage
original; tampoco cambia el comportamiento predeterminado de los otros envíos.
El campo sigue siendo `models.FileField` con el mismo contrato de migración.
La selección del storage utiliza únicamente un `FieldFile` específico y el
prefijo persistido, sin columnas ni migraciones nuevas.

La regresión focal vive en
`backend/content/tests/services/test_email_snapshot_private_attachments.py`:
captura privada, lectura después de recarga, descarga autorizada y rechazo
anónimo, reenvío privado, compatibilidad histórica y limpieza cuando la captura
falla antes del transporte. Las pruebas usan correo en memoria y archivos
temporales; no contactan SMTP.
