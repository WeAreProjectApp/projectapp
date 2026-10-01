/** Open a project action through the shared table/card kebab. */
export async function openProjectAction(page, projectId, action) {
  await page.getByTestId(`project-actions-${projectId}`).click();
  await page.getByTestId(`project-actions-${action}`).click();
}
