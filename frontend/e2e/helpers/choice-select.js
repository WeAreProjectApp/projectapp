export async function selectChoiceOption(page, combobox, name) {
  await combobox.click()
  const option = page.getByRole('listbox').getByRole('option', { name, exact: true })
  await option.click()
}
