/**
 * Drives the source half of BaseRichTextEditor so E2E flows keep writing the
 * same persisted source that the visual editor renders.
 */
export async function fillRichTextSource(editor, value) {
  await editor.getByRole('tab', { name: /^(Fuente|Source)$/ }).click();
  const source = editor.getByTestId('rich-text-source-input');
  await source.fill(value);
  return source;
}

export function richTextEditorByPlaceholder(page, placeholder) {
  return page.getByPlaceholder(placeholder).locator('..');
}
