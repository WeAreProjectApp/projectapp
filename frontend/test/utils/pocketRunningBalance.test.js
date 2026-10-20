import { withRunningBalance } from '~/utils/pocketRunningBalance'

describe('withRunningBalance', () => {
  it('orders chronologically with a running sum', () => {
    const rows = withRunningBalance([
      {
        id: 2, movement_date: '2026-05-06', created_at: '2026-05-06T10:00:00Z',
        direction: 'out', amount: '40.00',
      },
      {
        id: 1, movement_date: '2026-04-29', created_at: '2026-04-29T10:00:00Z',
        direction: 'in', amount: '100.00',
      },
    ])

    expect(rows.map((row) => row.id)).toEqual([1, 2])
    expect(rows[0].running_balance).toBe(100)
    expect(rows[1].running_balance).toBe(60)
  })

  it('breaks same-day ties by created_at', () => {
    const rows = withRunningBalance([
      {
        id: 2, movement_date: '2026-03-10', created_at: '2026-03-10T12:00:00Z',
        direction: 'out', amount: '30000.00',
      },
      {
        id: 1, movement_date: '2026-03-10', created_at: '2026-03-10T08:00:00Z',
        direction: 'in', amount: '100000.00',
      },
    ])

    expect(rows.map((row) => row.id)).toEqual([1, 2])
    expect(rows[1].running_balance).toBe(70000)
  })

  // Bug caught: equal date and creation time left the resulting balance dependent on API order.
  it('breaks identical timestamps by movement id', () => {
    const rows = withRunningBalance([
      {
        id: 9, movement_date: '2026-03-10', created_at: '2026-03-10T08:00:00Z',
        direction: 'out', amount: '30000.00',
      },
      {
        id: 4, movement_date: '2026-03-10', created_at: '2026-03-10T08:00:00Z',
        direction: 'in', amount: '100000.00',
      },
    ])

    expect(rows.map((row) => row.id)).toEqual([4, 9])
    expect(rows[1].running_balance).toBe(70000)
  })

  it('accumulates only over the rows it is given', () => {
    // The load-bearing case: this is why the page filters BEFORE accumulating.
    // Handed a subset, the first row must start from its own amount instead of
    // carrying the prefix of the movements the filter hid.
    const all = [
      {
        id: 1, movement_date: '2026-04-01', created_at: '2026-04-01T08:00:00Z',
        direction: 'in', amount: '500.00',
      },
      {
        id: 2, movement_date: '2026-04-02', created_at: '2026-04-02T08:00:00Z',
        direction: 'out', amount: '200.00',
      },
      {
        id: 3, movement_date: '2026-04-03', created_at: '2026-04-03T08:00:00Z',
        direction: 'out', amount: '100.00',
      },
    ]

    expect(withRunningBalance(all).map((r) => r.running_balance))
      .toEqual([500, 300, 200])

    const onlyEgresos = withRunningBalance(all.filter((r) => r.direction === 'out'))
    expect(onlyEgresos.map((r) => r.running_balance)).toEqual([-200, -300])
  })

  it('does not mutate the array it is given', () => {
    const all = [
      {
        id: 2, movement_date: '2026-05-06', created_at: '2026-05-06T10:00:00Z',
        direction: 'out', amount: '40.00',
      },
      {
        id: 1, movement_date: '2026-04-29', created_at: '2026-04-29T10:00:00Z',
        direction: 'in', amount: '100.00',
      },
    ]

    withRunningBalance(all)

    expect(all.map((row) => row.id)).toEqual([2, 1])
    expect(all[0].running_balance).toBeUndefined()
  })

  it('treats a non-numeric amount as zero instead of poisoning the sum', () => {
    const rows = withRunningBalance([
      {
        id: 1, movement_date: '2026-04-01', created_at: '2026-04-01T08:00:00Z',
        direction: 'in', amount: '100.00',
      },
      {
        id: 2, movement_date: '2026-04-02', created_at: '2026-04-02T08:00:00Z',
        direction: 'in', amount: null,
      },
    ])

    expect(rows[1].running_balance).toBe(100)
  })
})
