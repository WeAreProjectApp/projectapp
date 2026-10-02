import { vatBreakdown } from '~/utils/accountingVat'

describe('vatBreakdown', () => {
  it('separates a total that includes nineteen percent VAT', () => {
    // Fails if a total-with-VAT capture stops deriving the client-visible base and tax amounts.
    expect(vatBreakdown('119.00', '19')).toEqual({
      base: '100.00',
      vat: '19.00',
      total: '119.00',
    })
  })

  it('rounds an included-VAT amount to whole cents', () => {
    // Fails if an included total leaves a fractional cent or assigns it to the wrong displayed amount.
    expect(vatBreakdown('0.05', '19')).toEqual({
      base: '0.04',
      vat: '0.01',
      total: '0.05',
    })
  })

  it('adds rounded VAT to a before-VAT amount', () => {
    // Fails if a base amount no longer produces the total that the collection account will send.
    expect(vatBreakdown('100.05', '19', 'before_vat')).toEqual({
      base: '100.05',
      vat: '19.01',
      total: '119.06',
    })
  })

  it('keeps a zero VAT rate as an explicit tax-free breakdown', () => {
    // Fails if the explicit "Sin IVA" choice is confused with an unrecorded VAT rate.
    expect(vatBreakdown('45', '0')).toEqual({
      base: '45.00',
      vat: '0.00',
      total: '45.00',
    })
  })

  it('keeps an unknown VAT rate separate from a zero VAT rate', () => {
    // Fails if historical records without a VAT rate are presented as tax-free.
    expect(vatBreakdown('45', null)).toEqual({
      base: null,
      vat: null,
      total: '45.00',
    })
  })

  test.each([
    ['a third decimal in the amount', '45.001', '19'],
    ['a rate above one hundred percent', '45', '100.01'],
  ])('rejects %s', (_label, amount, rate) => {
    // Fails if malformed financial input produces a misleading preview instead of being rejected.
    expect(vatBreakdown(amount, rate)).toBeNull()
  })
})
