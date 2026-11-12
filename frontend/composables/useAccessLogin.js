import { create_request, get_request } from '~/stores/services/request_http';
import { usePlatformApi } from '~/composables/usePlatformApi';

export function useAccessLogin(surface) {
  let csrf = '';
  const options = () => ({
    skipAuth: true, skipRefresh: true, headers: { 'X-CSRFToken': csrf },
    // These endpoints are outside the platform client's /api/accounts/ base.
    ...(surface === 'platform' ? { baseURL: '/' } : {}),
  });
  async function config() {
    const response = surface === 'panel'
      ? await get_request('auth/config/')
      : await usePlatformApi().get('/api/auth/config/', options());
    csrf = response.data.csrf_token;
    return response.data;
  }
  async function post(operation, payload) {
    const url = `auth/${surface}/${operation}/`;
    const response = surface === 'panel'
      ? await create_request(url, payload, options())
      : await usePlatformApi().post(`/api/${url}`, payload, options());
    return response.data;
  }
  return { config, post };
}
