import { emptyReceipt, receiptPayload } from '~/utils/hostingReceipt'

const period = { income_id: 41, hosting_record_id: 9 }

describe('receiptPayload', () => {
  // Falla si los espacios de una referencia estable se conservan y la misma
  // transferencia queda registrada como otro pago desde la segunda pantalla.
  it('normalizes a stable receipt and pins it to the hosting income', () => {
    const payload = receiptPayload({
      issuer: ' Banco Aurora ', reference: ' TRX-250 ', entries: [],
    }, [period])

    expect(payload).toEqual({
      issuer: 'Banco Aurora', reference: 'TRX-250',
      entries: [{ income_id: 41, hosting_record_id: 9 }],
    })
  })

  // Falla si un asiento ya acreditado exige inventar una segunda referencia
  // en vez de enviar la selección inequívoca al conciliador.
  it('allows a selected existing liquid without an invented receipt reference', () => {
    const payload = receiptPayload({
      issuer: '', reference: '', entries: [{ income_id: 41, liquid_id: 73 }],
    }, [period])

    expect(payload).toEqual({ entries: [{ income_id: 41, hosting_record_id: 9, liquid_id: 73 }] })
  })

  // Falla si un formulario parcial transforma un pago manual ambiguo en un
  // abono acreditado sin fuente y folio estables.
  it.each([
    [{ issuer: 'Banco Aurora', reference: '', entries: [] }],
    [{ issuer: '', reference: 'TRX-250', entries: [] }],
  ])('rejects an incomplete receipt identity', (receipt) => {
    expect(receiptPayload(receipt, [period])).toBeNull()
  })

  it('starts a new receipt form with no identity or evidence aliases', () => {
    expect(emptyReceipt()).toEqual({ issuer: '', reference: '', entries: [] })
  })
})
