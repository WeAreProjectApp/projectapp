import { integrityDestination, integrityParams } from '../../utils/integrityInputs'

describe('integrityParams', () => {
  it('restores a BaseSelect numeric option before submitting', () => {
    const params = integrityParams({
      client_id: { options: [{ value: 42, label: 'Acme' }] },
    }, { client_id: '42' })

    // Fails if BaseSelect strings reach the API instead of the selected numeric value.
    expect(params).toEqual({ client_id: 42 })
  })

  it('converts an integer folder field without options', () => {
    const params = integrityParams({ folder_id: { type: 'integer' } }, { folder_id: '17' })

    // Fails if a manually entered destination folder is submitted as text.
    expect(params).toEqual({ folder_id: 17 })
  })

  it('omits blank values from the submitted parameters', () => {
    const params = integrityParams({
      reason: { type: 'string' },
      page: { type: 'integer' },
    }, { reason: '', page: '3' })

    // Fails if optional blank fields override the API defaults.
    expect(params).toEqual({ page: 3 })
  })
})

describe('integrityDestination', () => {
  it.each([
    ['content.document', 8, '/panel/documents/8/edit'],
    ['accounts.project', 21, '/panel/projects?highlight=21'],
    ['accounts.userprofile', 34, '/panel/clients?highlight=34'],
    ['content.businessproposal', 55, '/panel/proposals/55/edit'],
    ['content.communicationthread', 89, '/panel/communications?thread=89'],
  ])('routes %s record %i to its panel destination', (model, id, destination) => {
    // Fails if a finding opens a list or editor unrelated to its underlying record.
    expect(integrityDestination({ model, id })).toBe(destination)
  })

  it('returns null for a model without a panel destination', () => {
    // quality: allow-negation-only (pure function null case; the adjacent parameterized test pins each positive destination)
    // Fails if unknown integrity subjects create a misleading broken link.
    expect(integrityDestination({ model: 'accounting.income', id: 13 })).toBeNull()
  })
})
