import featureCatalog from '../../../contracts/platform-features.json';

export function getApiPath(requestUrl) {
  const url = new URL(requestUrl);
  return url.pathname.replace(/^\/api\//, "");
}

function paginatedDocumentFixture(result, requestUrl) {
  if (!result || Number(result.status || 200) >= 400 || typeof result.body !== 'string') {
    return result;
  }
  let rows;
  try {
    rows = JSON.parse(result.body);
  } catch {
    return result;
  }
  if (!Array.isArray(rows)) return result;

  const params = new URL(requestUrl).searchParams;
  const pageSize = Number(params.get('page_size')) || 10;
  const requestedPage = Number(params.get('page')) || 1;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const page = Math.min(Math.max(1, requestedPage), totalPages);
  const start = (page - 1) * pageSize;
  return {
    ...result,
    body: JSON.stringify({
      results: rows.slice(start, start + pageSize),
      count: rows.length,
      page,
      page_size: pageSize,
      total_pages: totalPages,
    }),
  };
}

export async function mockApi(page, handler) {
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const apiPath = getApiPath(route.request().url());
    const method = route.request().method();
    let result = await handler({ route, apiPath, method });

    // New availability boundary: ordinary fixture accounts inherit the catalogue.
    // Scenario-specific handlers take precedence, including deliberate failures.
    if (!result && apiPath === 'platform/features/' && method === 'GET') {
      const user = await page.evaluate(() => JSON.parse(localStorage.getItem('platform_user') || 'null'));
      result = { status: 200, contentType: 'application/json', body: JSON.stringify({
        user_id: user?.user_id, catalog_version: featureCatalog.version,
        features: Object.fromEntries(featureCatalog.features.map(item => [item.key, item.default_enabled])),
      }) };
    }

    // Document-manager specs predating server pagination expose their fixture
    // through the legacy array endpoint. Reuse that data while each spec is
    // migrated independently; an explicit browse envelope always wins.
    if (!result && apiPath === 'documents/browse/' && method === 'GET') {
      result = await handler({ route, apiPath: 'documents/', method });
    }
    if (apiPath === 'documents/browse/' && method === 'GET') {
      result = paginatedDocumentFixture(result, route.request().url());
    }

    if (result) {
      return route.fulfill(result);
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "{}",
    });
  });
}
