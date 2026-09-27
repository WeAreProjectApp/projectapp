import axios from "axios";

export function getCookie(name) {
  /* c8 ignore next */
  if (typeof document === 'undefined') return null;
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Request endpoint
 * @param {string} method - Type request.
 * @param {string} url - Endpoint
 * @param {object} params - Params.
 * @param {object} [config] - Extra axios config (e.g. { signal } for AbortController).
 * @returns {object} - Data and status from endpoint.
 */
async function makeRequest(method, url, params = {}, config = {}) {
  const csrfToken = getCookie('csrftoken');
  const isFormData = typeof FormData !== 'undefined' && params instanceof FormData;
  const headers = {
    "X-CSRFToken": csrfToken,
    ...(config.headers || {}),
  };
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }

  // Merge axios options. Headers are already merged above so they win.
  const { headers: _ignoredHeaders, ...restConfig } = config;
  const axiosOptions = { headers, ...restConfig };

  try {
    let response;

    switch (method) {
      case "GET":
        response = await axios.get(`/api/${url}`, axiosOptions);
        break;
      case "POST":
        response = await axios.post(`/api/${url}`, params, axiosOptions);
        break;
      case "PATCH":
        response = await axios.patch(`/api/${url}`, params, axiosOptions);
        break;
      case "PUT":
        response = await axios.put(`/api/${url}`, params, axiosOptions);
        break;
      case "DELETE":
        response = await axios.delete(`/api/${url}`, axiosOptions);
        break;
      default:
        throw new Error(`Unsupported method: ${method}`);
    }

    return response;
  } catch (error) {
    // Axios errors contain request bodies (secrets and reveal tokens). The
    // secure-links caller renders a safe message; never log its raw error.
    if (!url.startsWith('secure-links/')) console.error(error);
    throw error;
  }
}

/**
 * Get request.
 * @param {string} url - Endpoint.
 * @param {object} [config] - Extra axios config (e.g. { signal } for AbortController).
 * @returns {object} - Data and status from endpoint.
 */
export async function get_request(url, config = {}) {
  return await makeRequest("GET", url, {}, config);
}

/**
 * Create request.
 * @param {string} url - Endpoint.
 * @param {object} params - Params.
 * @returns {object} - Data and status from endpoint.
 */
export async function create_request(url, params, config = {}) {
  return await makeRequest("POST", url, params, config);
}

/**
 * Patch request.
 * @param {string} url - Endpoint.
 * @param {object} params - Params.
 * @returns {object} - Data and status from endpoint.
 */
export async function patch_request(url, params) {
  return await makeRequest("PATCH", url, params);
}

/**
 * Put request.
 * @param {string} url - Endpoint.
 * @param {object} params - Params.
 * @returns {object} - Data and status from endpoint.
 */
export async function put_request(url, params) {
  return await makeRequest("PUT", url, params);
}

/**
 * Delete request.
 * @param {string} url - Endpoint.
 * @returns {object} - Data and status from endpoint.
 */
export async function delete_request(url) {
  return await makeRequest("DELETE", url);
}

export const __test_makeRequest = makeRequest;
