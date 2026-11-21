import { execFileSync } from 'node:child_process'
import { test as base, expect } from '../helpers/test.js'

// CI builds and collects the artifact before starting this Django live server.
// Check both identities over HTTP, from the origin the browser actually visits.
export const test = base.extend({
  context: async ({ context, baseURL }, use) => {
    const origin = new URL(baseURL).origin
    await context.route(url => ['https:', 'http:'].includes(url.protocol) && url.origin !== origin,
      route => route.abort())
    await use(context)
  },
})

test.beforeEach(async ({ request }) => {
  const commit = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim()
  for (const url of ['/version.json', '/api/version/']) {
    const response = await request.get(url)
    expect(response.status()).toBe(200)
    expect(await response.json()).toEqual({ schema_version: 1, project: 'projectapp', commit })
  }
})

export { expect }
