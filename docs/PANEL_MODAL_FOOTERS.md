# Pies de acciones de los modales del panel

Fecha: 2026-09-27. Alcance: todos los modales del panel que tienen acciones
inferiores, incluidos los cortos y las confirmaciones. Referencia: PA-150,
integrado en #423. Barrido realizado sobre `7bb78e29` y esta rama.

## Contrato

- `BaseModal` ofrece un slot opcional `footer`; allí vive `BaseModalActions`.
  El cuerpo desplaza, el pie no se encoge ni se superpone a los campos.
- En escritorio la altura es natural hasta `90dvh`. Debajo de 640 px el modal
  ocupa `100dvh`, las acciones se apilan y se reserva el área segura inferior.
- Se conservan todas las acciones, condiciones de habilitación, carga y
  validación. Un botón submit exterior usa `form` asociado a un `useId()` local.
- Los asistentes presentan el pie que corresponde al paso activo. Las vistas
  con correo/PDF mantienen sus regiones de desplazamiento independientes.
- Los modales sin pie, acciones internas de secciones, menús emergentes,
  drawers y visores públicos no reciben botones nuevos.

## Inventario del componente común

Las filas representan archivos; cuando uno contiene varios modales se indica
cuántos adoptan el pie compartido. “Sin pie global” significa que las acciones
están en la cabecera o junto al contenido al que pertenecen; no requiere moverlas.
Los contenedores compartidos cubren también sus consumidores de estadísticas,
confirmaciones y acciones contables.

| Archivo bajo `frontend/` | Modales | Estado |
|---|---:|---|
| `components/AdditionalModules/CatalogOrderModal.vue` | 1 | Pie compartido |
| `components/AdditionalModules/CatalogSelectionModal.vue` | 1 | Pie compartido |
| `components/AdditionalModules/CatalogView.vue` | 1 | Sin pie global |
| `components/AdditionalModules/CategoryManagerModal.vue` | 1 | Pie compartido mientras se crea o edita una categoría; el formulario conserva su validación. |
| `components/AdditionalModules/ModuleFormModal.vue` | 1 | Pie compartido |
| `components/AdditionalModules/ShareHistoryModal.vue` | 1 | Sin pie global |
| `components/BusinessProposal/admin/ContractParamsModal.vue` | 1 | Pie compartido |
| `components/BusinessProposal/admin/ProposalActionsModal.vue` | 1 | Sin pie global |
| `components/BusinessProposal/admin/ProposalFormalizationModal.vue` | 1 | Pie compartido |
| `components/BusinessProposal/admin/ProposalMultiSendModal.vue` | 1 | Pie compartido |
| `components/BusinessProposal/admin/ProposalResendModal.vue` | 1 | Pie compartido |
| `components/ConfirmModal.vue` | 1 | Pie compartido |
| `components/Tasks/TaskFormModal.vue` | 1 | Pie compartido |
| `components/WebAppDiagnostic/ConfidentialityParamsModal.vue` | 1 | Pie compartido |
| `components/WebAppDiagnostic/DiagnosticActionsModal.vue` | 1 | Sin pie global |
| `components/accounting/AccountingNoteModal.vue` | 1 | Pie compartido |
| `components/accounting/AccountingRowActionsModal.vue` | 1 | Pie compartido |
| `components/accounting/AdSpendFormModal.vue` | 1 | Pie compartido |
| `components/accounting/BulkAssignModal.vue` | 1 | Pie compartido |
| `components/accounting/CardSnapshotFormModal.vue` | 1 | Pie compartido |
| `components/accounting/CollectionAccountDetailModal.vue` | 1 | Pie compartido |
| `components/accounting/CollectionAccountFormModal.vue` | 1 | Pie compartido |
| `components/accounting/CollectionActionsModal.vue` | 1 | Pie compartido |
| `components/accounting/EmailBodyModal.vue` | 1 | Pie compartido |
| `components/accounting/ExpenseFormModal.vue` | 1 | Pie compartido |
| `components/accounting/HostingActionsModal.vue` | 1 | Pie compartido |
| `components/accounting/HostingCyclesModal.vue` | 1 | Pie compartido |
| `components/accounting/HostingFormModal.vue` | 1 | Pie compartido |
| `components/accounting/IncomeActionsModal.vue` | 1 | Pie compartido |
| `components/accounting/IncomeBulkSettleModal.vue` | 1 | Pie compartido |
| `components/accounting/IncomeClientTotalsModal.vue` | 1 | Pie compartido |
| `components/accounting/IncomeDetailModal.vue` | 1 | Pie compartido |
| `components/accounting/IncomeFormModal.vue` | 1 | Pie compartido |
| `components/accounting/IncomeLiquidateModal.vue` | 1 | Pie compartido |
| `components/accounting/IncomeMuteModal.vue` | 1 | Pie compartido |
| `components/accounting/PocketMovementActionsModal.vue` | 1 | Pie de cierre de menú. |
| `components/accounting/PocketMovementAllocationsModal.vue` | 1 | Pie compartido |
| `components/accounting/PocketMovementFormModal.vue` | 1 | Pie compartido |
| `components/accounting/ReceivablesModal.vue` | 1 | Pie compartido |
| `components/accounting/RecurringActionsModal.vue` | 1 | Pie compartido |
| `components/accounting/RecurringCategoriesModal.vue` | 1 | Pie compartido |
| `components/accounting/RecurringMuteModal.vue` | 1 | Pie compartido |
| `components/accounting/RecurringPaymentFormModal.vue` | 1 | Pie compartido |
| `components/accounting/StatementHeaderFormModal.vue` | 1 | Pie compartido |
| `components/base/BaseRowActionsModal.vue` | 1 | Pie de cierre de menú. |
| `components/base/PdfPreviewModal.vue` | 1 | Sin pie global |
| `components/clients/ClientArchiveModal.vue` | 1 | Pie compartido |
| `components/clients/ClientEmailsModal.vue` | 1 | Pie compartido |
| `components/clients/ClientReassignModal.vue` | 1 | Pie compartido |
| `components/communications/CommunicationFolderPanel.vue` | 1 | Pie compartido |
| `components/communications/CommunicationWorkspaceModal.vue` | 2 | El compositor del hilo ya ocupa una zona inferior fija; el modal de mover carpeta adopta el slot. |
| `components/emails/EmailResendModal.vue` | 1 | Pie compartido |
| `components/history/EntityHistoryRecordModal.vue` | 1 | Sin pie global |
| `components/panel/defaults/ProposalDefaultsPanel.vue` | 2 | Pie compartido |
| `components/panel/documents/DeleteFolderModal.vue` | 1 | Pie compartido |
| `components/panel/documents/DocumentClientNoteModal.vue` | 1 | Pie compartido |
| `components/panel/documents/DocumentStateSelector.vue` | 1 | Pie compartido |
| `components/panel/documents/DocumentThreadIndexModal.vue` | 1 | Paginación ya separada del cuerpo desplazable; se conserva. |
| `components/panel/documents/DocumentThreadModal.vue` | 1 | Pie compartido |
| `components/panel/documents/FolderChangeClientModal.vue` | 1 | Pie compartido |
| `components/panel/documents/FolderFormModal.vue` | 1 | Pie compartido |
| `components/panel/projects/ProjectAccessModal.vue` | 1 | Sin pie global |
| `components/panel/projects/ProjectAssignUnlinkedModal.vue` | 1 | Pie compartido |
| `components/panel/projects/ProjectBrandModal.vue` | 1 | Sin pie global |
| `components/panel/projects/ProjectChangeClientModal.vue` | 1 | Pie compartido |
| `components/panel/projects/ProjectFormModal.vue` | 1 | Pie compartido |
| `components/panel/projects/ProjectStateTransitionModal.vue` | 1 | Pie compartido |
| `components/panel/proposal/ProposalSectionsTab.vue` | 1 | Sin pie global |
| `components/panel/qr-cards/DownloadQrModal.vue` | 1 | Pie compartido |
| `components/panel/states/StateHistoryModal.vue` | 1 | Sin pie global |
| `components/pwa/PanelPwaHost.vue` | 1 | Sin pie global |
| `components/secureLinks/SecureLinkDetailModal.vue` | 1 | Sin pie global |
| `components/secureLinks/SecureLinkFormModal.vue` | 1 | Pie compartido |
| `components/stats/StatsModal.vue` | 1 | Pie compartido |
| `pages/panel/accounting/statements.vue` | 1 | Pie compartido |
| `pages/panel/additional-modules/index.vue` | 1 | Sin pie global |
| `pages/panel/admins/index.vue` | 1 | Pie compartido |
| `pages/panel/clients/index.vue` | 2 | Pie compartido |
| `pages/panel/communications/index.vue` | 1 | Pie compartido |
| `pages/panel/diagnostics/[id]/edit.vue` | 1 | Pie compartido |
| `pages/panel/diagnostics/index.vue` | 1 | Sin pie global |
| `pages/panel/linkedin/index.vue` | 1 | Pie compartido |
| `pages/panel/linktrees/index.vue` | 1 | Pie compartido |
| `pages/panel/mcps/index.vue` | 2 | Pie compartido |
| `pages/panel/monitoring/index.vue` | 1 | Pie compartido |
| `pages/panel/projects/index.vue` | 1 | Sin pie global |
| `pages/panel/proposals/[id]/edit.vue` | 3 | 1 con pie compartido; 2 sin pie global |
| `pages/panel/proposals/create.vue` | 1 | Pie compartido |
| `pages/panel/proposals/index.vue` | 3 | 2 con pie compartido; 1 sin pie global |
| `pages/panel/qr-cards/index.vue` | 1 | Pie compartido |
| `pages/panel/secure-links/index.vue` | 1 | Pie compartido |
| `pages/panel/styleguide.vue` | 2 | Pie compartido |

## Diálogos con estructura propia

| Diálogo | Resultado del barrido |
|---|---|
| Renombrar documento | Formulario en columna; cuerpo desplazable, Guardar/Cancelar separados dentro del mismo formulario. |
| Mover documento | Cuerpo desplazable con elección de carpeta y cliente; Cancelar separado. |
| Gestionar carpetas | Contenido y creación de carpeta desplazables; Cerrar separado. |
| Enviar documento por correo | Cuerpo desplazable; pie de envío y de confirmación posterior apilado en móvil. Incluye el pie del selector interno de adjuntos. |
| Adjuntar desde Documentos | Cuerpo desplazable y pie separado; pantalla completa y acciones apiladas en móvil. |
| Editor de adjunto Markdown | Dos regiones independientes y pie separado; altura dinámica en móvil. |
| Vista previa de sincronización | Encabezado y diferencias en el cuerpo desplazable; Cancelar/Aplicar siempre visibles. |
| Restaurar plantilla de correo / secciones | Dos confirmaciones migradas al modal común con pie separado. |
| Confirmación de propuesta creada | Migrada al modal común; advertencias desplazables y opciones finales separadas. |
| Vista previa de sección / Markdown, métricas, vista previa de correo de defaults, preview móvil del blog | Sin pie de acciones; se conservan. |

## Verificación

Las pruebas de geometría miden las acciones antes del clic, evitando que el
autoscroll de Playwright enmascare un pie fuera de pantalla. Se cubren los cinco
perfiles oficiales y una altura reducida, formularios con submit exterior,
notas extensas y asistentes. Las pruebas usan APIs simuladas; no envían correos
ni modifican datos del servicio. Los lotes se limitan a 20 casos y dos archivos
E2E. El detalle de ejecuciones y resultados se entrega en el PR.
