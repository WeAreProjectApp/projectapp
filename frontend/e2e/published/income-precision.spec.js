import { test, expect } from './fixtures.js'
import { ADMIN_ACCOUNTING_INCOME_CRUD, ADMIN_ACCOUNTING_INCOME_BULK_SETTLE } from '../helpers/flow-tags.js'

test.use({ storageState: process.env.PUBLISHED_PANEL_STATE })

const incomesPath = '/es-co/panel/accounting/incomes'
const apiPath = '/api/accounting/incomes/'
const previewPath = apiPath + 'settlement-preview/'
const detailTags = [...ADMIN_ACCOUNTING_INCOME_CRUD, '@role:admin', '@outcome:success']
const settlementTags = [...ADMIN_ACCOUNTING_INCOME_BULK_SETTLE, '@role:admin', '@outcome:success']
const fixtures = () => JSON.parse(process.env.PUBLISHED_INCOMES)
const query = page => Object.fromEntries(new URL(page.url()).searchParams)

function responseFor(page, method, path) {
  return page.waitForResponse(response =>
    response.request().method() === method && new URL(response.url()).pathname === path)
}

async function visitIncomes(page) {
  // quality: allow-deep-link (start at the panel list URL from the reported case)
  const list = responseFor(page, 'GET', apiPath)
  await page.goto(incomesPath, { waitUntil: 'domcontentloaded' })
  const response = await list
  expect(response.status()).toBe(200)
  return (await response.json()).results
}

async function filterNovember(page) {
  await page.getByTestId('filter-tabs-tab-all').click()
  await page.getByRole('button', { name: /^Filtros\b/ }).click()
  const panel = page.getByTestId('accounting-filter-panel')
  await panel.getByRole('button', { name: 'Mes', exact: true }).click()
  await panel.getByPlaceholder('Desde', { exact: true }).fill('2025-11-01')
  await expect.poll(() => query(page).periodAfter).toBe('2025-11-01')
  await panel.getByPlaceholder('Hasta', { exact: true }).fill('2025-11-30')
  await expect.poll(() => query(page).periodBefore).toBe('2025-11-30')
  await panel.getByRole('button', { name: 'Mes', exact: true }).click()
  await panel.getByTestId('accounting-filter-kind-expected').click()
  await expect.poll(() => query(page)).toEqual({
    accounting_incomeTab: 'all', kind: 'expected', periodAfter: '2025-11-01', periodBefore: '2025-11-30',
  })
}

function visibleRowIds(page) {
  return page.getByTestId(/^accounting-row-\d+$/).filter({ visible: true }).evaluateAll(rows =>
    rows.map(row => Number(row.dataset.testid.split('-').pop())).sort((a, b) => a - b))
}

const detailCases = [
  { key: 'unpaid', total: '999999999999.99', paid: '0.00', pending: '999999999999.99',
    totalText: '$999.999.999.999,99 COP', paidText: '$0 COP', pendingText: '$999.999.999.999,99 COP' },
  { key: 'partial', total: '119.03', paid: '50.25', pending: '68.78',
    totalText: '$119,03 COP', paidText: '$50,25 COP', pendingText: '$68,78 COP' },
]

async function checkDetail(page, id, values, action) {
  const reading = responseFor(page, 'GET', apiPath + id + '/detail/')
  await action()
  const response = await reading
  expect(response.status()).toBe(200)
  const { income } = await response.json()
  expect(income).toMatchObject({
    id, total_amount: values.total, paid_amount: values.paid, pending_amount: values.pending,
  })
  await expect.poll(() => query(page).income).toBe(String(id))
  const detail = page.getByTestId('income-detail-modal')
  await expect(detail.getByTestId('income-detail-total')).toHaveText(values.totalText)
  await expect(detail.getByTestId('vat-total')).toHaveText(values.totalText)
  await expect(detail.getByTestId('income-detail-paid')).toHaveText(values.paidText)
  await expect(detail.getByTestId('income-detail-pending')).toHaveText(values.pendingText)
  return income
}

function cents(amount) {
  // Serialized money has a fixed scale of two. Compare the sum in whole cents.
  return BigInt(amount.replace('.', ''))
}

for (const item of detailCases) {
  test('matches the stored ' + item.key + ' balance on open and reload', { tag: detailTags }, async ({ page }) => {
    const seed = fixtures()
    const id = seed[item.key]
    const rows = await visitIncomes(page)
    expect(rows.find(row => row.id === id)).toMatchObject({
      total_amount: item.total, paid_amount: item.paid, pending_amount: item.pending,
    })
    await filterNovember(page)
    const filters = query(page)
    const expectedRows = [seed.unpaid, seed.partial].sort((a, b) => a - b)
    await expect.poll(() => visibleRowIds(page)).toEqual(expectedRows)
    await expect(page.getByTestId('accounting-row-' + id)).toContainText(item.totalText)

    const open = () => page.getByTestId('income-open-' + id).filter({ visible: true }).click()
    const reload = () => page.reload({ waitUntil: 'domcontentloaded' })
    for (const action of [open, reload]) {
      const income = await checkDetail(page, id, item, action)
      expect(cents(income.paid_amount) + cents(income.pending_amount)).toBe(cents(income.total_amount))
    }
    await page.keyboard.press('Escape')
    await expect(page.getByTestId('income-detail-modal')).toHaveCount(0)
    await expect.poll(() => query(page)).toEqual(filters)
    await expect.poll(() => visibleRowIds(page)).toEqual(expectedRows)
  })
}

test('keeps inapplicable balances empty on a liquid income', { tag: detailTags }, async ({ page }) => {
  const { payment } = fixtures()
  await visitIncomes(page)
  await page.getByTestId('filter-tabs-tab-all').click()
  const item = { total: '50.25', paid: null, pending: null, totalText: '$50,25 COP', paidText: '—', pendingText: '—' }
  await checkDetail(page, payment, item, () => page.getByTestId('income-open-' + payment).filter({ visible: true }).click())
  await checkDetail(page, payment, item, () => page.reload({ waitUntil: 'domcontentloaded' }))
})

async function openSettlement(page, id, totalText) {
  const writes = []
  page.on('request', request => {
    const path = new URL(request.url()).pathname
    if (request.method() === 'POST' && path.startsWith(apiPath)) writes.push(path)
  })
  // Fail closed even if the form accidentally dispatches a real settlement.
  await page.route(/\/api\/accounting\/incomes\/(?:bulk-settle|\d+\/settle)\/$/, route => route.abort())
  await expect(page.getByTestId('accounting-row-' + id).filter({ visible: true })).toContainText(totalText)
  await page.getByTestId('income-actions-' + id).filter({ visible: true }).click()
  const actions = page.getByTestId('income-actions-modal')
  await expect(actions).toContainText(totalText)
  const opening = responseFor(page, 'POST', previewPath)
  await actions.getByTestId('income-action-liquidate-' + id).click()
  const response = await opening
  expect(response.status()).toBe(200)
  expect(writes).toEqual([previewPath])
  return { initial: await response.json(), writes }
}

async function checkRemainder(page, carlos, gustavo, remainder) {
  const header = page.getByTestId('income-liquidate-participations-toggle')
  await expect(header).toContainText('Carlos ' + carlos)
  await expect(header).toContainText('Gustavo ' + gustavo)
  await expect(header.getByTestId('income-liquidate-projectapp-remainder')).toHaveText('ProjectApp ' + remainder)
  await expect(page.getByTestId('partner-split-remainder')).toHaveText('Bolsillo ProjectApp: ' + remainder)
  await expect(page.getByTestId('partner-split-remainder')).toBeVisible()
  await header.click()
  await expect(header).toHaveAttribute('aria-expanded', 'false')
  await expect(header.getByTestId('income-liquidate-projectapp-remainder')).toHaveText('ProjectApp ' + remainder)
  await header.click()
}

async function checkVat(scope, amounts) {
  await expect(scope.getByTestId('vat-base')).toHaveText(amounts.base)
  await expect(scope.getByTestId('vat-tax')).toHaveText(amounts.tax)
  await expect(scope.getByTestId('vat-total')).toHaveText(amounts.total)
}

async function reviewThenCancel(page, id, draft, amounts, recipient) {
  const row = draft.initial.rows.find(item => item.income_id === id)
  expect(row.confirmation).toMatchObject({ can_send: true, recipient })
  expect(Number(row.amount)).toBeGreaterThan(0)
  const paid = page.getByTestId('income-liquidate-paid')
  await expect(paid).toHaveValue(amounts.input)
  expect(Number((await paid.inputValue()).replace(',', '.'))).toBeGreaterThan(0)
  const label = page.getByTestId('income-liquidate-confirmation-' + id)
  await expect(label).toContainText(recipient)
  const checkbox = label.getByRole('checkbox')
  await expect(checkbox).toBeEnabled()
  await expect(checkbox).toBeChecked()

  const reviewing = responseFor(page, 'POST', previewPath)
  await page.getByTestId('income-liquidate-submit').click()
  const response = await reviewing
  expect(response.status()).toBe(200)
  expect(response.request().postDataJSON()).toMatchObject({
    total_amount: Number(amounts.input.replace(',', '.')), send_payment_confirmation: true, confirmation_income_ids: [id],
  })
  await expect(page.getByRole('heading', { name: 'Revisar y liquidar' })).toBeVisible()
  const review = page.getByTestId('income-liquidate-review')
  await checkVat(review, amounts)
  await expect(review.getByTestId('income-liquidate-review-recipient')).toContainText(recipient)
  await page.getByRole('button', { name: 'Volver a editar' }).click()
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
  await expect(page.getByTestId('income-liquidate-form')).toHaveCount(0)
  expect(draft.writes).toEqual([previewPath, previewPath])
}

const amounts = {
  '119.03': { total: '$119,03 COP', base: '$100,03 COP', tax: '$19 COP', input: '119,03', remainder: '$1,03 COP' },
  '119.06': { total: '$119,06 COP', base: '$100,05 COP', tax: '$19,01 COP', input: '119,06', remainder: '$1,06 COP' },
}
const screens = [
  { name: 'dark desktop', dark: true, viewport: { width: 1536, height: 639 } },
  { name: 'light mobile', dark: false, viewport: { width: 390, height: 844 } },
]
for (const screen of screens) {
  test.describe(screen.name, () => {
    test.use({ viewport: screen.viewport })
    test.beforeEach(async ({ page }) => {
      await page.addInitScript(dark => localStorage.setItem('projectapp-dark-mode', JSON.stringify(dark)), screen.dark)
      await visitIncomes(page)
      await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains('dark'))).toBe(screen.dark)
    })
    for (const [amount, detail] of Object.entries(amounts)) {
      test('previews the VAT on ' + amount + ' before cancellation', { tag: settlementTags }, async ({ page }) => {
        const { review, recipient } = fixtures()
        const id = review[amount]
        const draft = await openSettlement(page, id, detail.total)
        await page.getByTestId('income-liquidate-participations-toggle').click()
        await checkRemainder(page, '$59 COP', '$59 COP', detail.remainder)
        await page.getByTestId('income-liquidate-vat-toggle-' + id).click()
        await checkVat(page.getByTestId('income-liquidate-vat-' + id), detail)
        await reviewThenCancel(page, id, draft, detail, recipient)
      })
    }
    test('keeps the manual remainder when editing the received amount', { tag: settlementTags }, async ({ page }) => {
      const { review } = fixtures()
      const draft = await openSettlement(page, review['119.03'], amounts['119.03'].total)
      await page.getByTestId('income-liquidate-participations-toggle').click()
      await page.getByTestId('partner-split-auto').click()
      await page.getByTestId('partner-split-carlos').fill('50,25')
      await page.getByTestId('partner-split-gustavo').fill('60,50')
      await checkRemainder(page, '$50,25 COP', '$60,50 COP', '$8,28 COP')
      await page.getByTestId('income-liquidate-paid').fill('119')
      await checkRemainder(page, '$50,25 COP', '$60,50 COP', '$8,25 COP')
      await expect(page.getByTestId('income-liquidate-summary')).toContainText('Falta: $0,03 COP')
      await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
      await expect(page.getByTestId('income-liquidate-form')).toHaveCount(0)
      expect(draft.writes).toEqual([previewPath])
    })
  })
}

test('leaves no remainder for an even whole amount', { tag: settlementTags }, async ({ page }) => {
  await visitIncomes(page)
  const draft = await openSettlement(page, fixtures().review['120.00'], '$120 COP')
  const header = page.getByTestId('income-liquidate-participations-toggle')
  await expect(header).toContainText('Carlos $60 COP')
  await expect(header).toContainText('Gustavo $60 COP')
  await header.click()
  await expect(page.getByTestId('partner-split-carlos')).toHaveValue('60')
  await expect(page.getByTestId('partner-split-gustavo')).toHaveValue('60')
  await expect(page.getByTestId('income-liquidate-projectapp-remainder')).toHaveCount(0)
  await expect(page.getByTestId('partner-split-remainder')).toHaveCount(0)
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
  await expect(page.getByTestId('income-liquidate-form')).toHaveCount(0)
  expect(draft.writes).toEqual([previewPath])
})
