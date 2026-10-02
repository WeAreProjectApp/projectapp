/** UI affordance only: the API independently verifies this signed JWT claim. */
export function hasPersonalPlatformSession(token) {
  try {
    const encoded = token.split('.')[1].replaceAll('-', '+').replaceAll('_', '/')
    return !JSON.parse(atob(encoded)).impersonated_by
  } catch { return false }
}
