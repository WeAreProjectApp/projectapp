/** Transport is injected: Panel keeps session/CSRF; Platform keeps its JWT client. */
export function createRequirementPackagesApi(transport, projectId) {
  const root = `requirement-packages/projects/${projectId}/`;
  const retries = new Map();
  const get = async (path) => (await transport.get(path)).data;
  const post = async (path, values = {}) => {
    const key = path + JSON.stringify(values);
    if (!retries.has(key)) retries.set(key, crypto.randomUUID());
    const response = await transport.post(path, {
      ...values,
      request_id: retries.get(key),
    });
    retries.delete(key);
    return response.data;
  };
  return {
    overview: (language, pages = {}) =>
      get(root + "?" + new URLSearchParams({ language, ...pages })),
    request: (id) => get(`${root}requests/${id}/`),
    createRequest: (data) => post(`${root}requests/`, data),
    evaluate: (id, expected_version) =>
      post(`${root}requests/${id}/evaluate/`, { expected_version }),
    offer: (id, data) => post(`${root}requests/${id}/offer/`, data),
    decide: (id, data) => post(`${root}requests/${id}/decide/`, data),
    context: () => get(`${root}evaluation-context/`),
    createOrder: (data) => post(`${root}orders/`, data),
    checkout: (id) => post(`${root}orders/${id}/checkout/`),
    verify: (id, transaction_id) =>
      post(`${root}orders/${id}/verify/`, { transaction_id }),
    confirmExternal: (id, data) =>
      post(`${root}orders/${id}/confirm-external/`, data),
    reverse: (id, reason) =>
      post(`${root}movements/${id}/reverse/`, { reason }),
    settings: (data) => post(`${root}settings/`, data),
    examples: (language, global = false) =>
      get(
        `${global ? "requirement-packages/" : root}examples/?language=${language}`,
      ),
    saveExamples: (data, language, global = false) =>
      post(
        `${global ? "requirement-packages/" : root}examples/?language=${language}`,
        data,
      ),
    exampleHistory: (language, global = false, offset = 0) =>
      get(
        `${global ? "requirement-packages/" : root}examples/history/?language=${language}&offset=${offset}`,
      ),
  };
}

export function packageError(error) {
  const data = error?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (data && typeof data === "object")
    return Object.values(data).flat().map(String).join(" · ");
  return error?.message || "No pudimos completar la operación.";
}
