### FLOW: `admin-accounting-hostings`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/hostings`
- **Description:** Client hosting registry: monthly value, payment modality, validity and billing contact, with KPI cards and modal CRUD. New records offer exactly quarterly, semiannual and every-9-month modalities; `payment_per_cycle` is derived from the monthly value. Legacy monthly/annual rows remain readable as historical values but cannot be selected for new records. Estado is inline; ciclos/total pagado are read-only and computed from cycle history. Cliente and Proyecto remain separate linked columns. Every row leads with a single three-dots button at every width (after the selection checkbox); its menu opens with **Detalle e historial** and **Ver nota** (when present), then cycles, cuenta de cobro, emails, edit and delete. On a phone Valor/mes groups under Cliente so the row fits without a horizontal scroll.
- **Responsive acceptance:** At 412×915, 835×1195, 1195×835, 1440×900 and 2560×1440, both validity dates remain complete without overlapping Ciclos. The range may wrap between dates, retaining partial/missing-date placeholders. Grouped values remain accessible on narrow screens and the cycle count still opens the selected hosting’s history.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-expenses-hostings.spec.js`

#### IVA opcional

IVA editable del pago por ciclo, 19% al crear y null histórico. Total incluido por defecto o base antes del impuesto; las siguientes cuentas heredan el porcentaje y muestran el desglose sin recalcular ciclos históricos.
