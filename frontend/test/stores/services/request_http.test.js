/**
 * Tests for the request_http service.
 *
 * Covers: getCookie, makeRequest (all HTTP methods + unsupported),
 * error propagation, exported wrappers: get_request, create_request,
 * patch_request, put_request, delete_request.
 */
let get_request, create_request, patch_request, put_request, delete_request;
let mockAxios;

beforeEach(() => {
  jest.resetModules();

  mockAxios = {
    get: jest.fn().mockResolvedValue({ data: 'get-data', status: 200 }),
    post: jest.fn().mockResolvedValue({ data: 'post-data', status: 201 }),
    patch: jest.fn().mockResolvedValue({ data: 'patch-data', status: 200 }),
    put: jest.fn().mockResolvedValue({ data: 'put-data', status: 200 }),
    delete: jest.fn().mockResolvedValue({ data: null, status: 204 }),
  };

  jest.doMock('axios', () => ({ __esModule: true, default: mockAxios }));

  const mod = require('../../../stores/services/request_http');
  get_request = mod.get_request;
  create_request = mod.create_request;
  patch_request = mod.patch_request;
  put_request = mod.put_request;
  delete_request = mod.delete_request;
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('get_request', () => {
  it('sends GET request to /api/<url>', async () => {
    const result = await get_request('products/');

    expect(mockAxios.get).toHaveBeenCalledWith('/api/products/', expect.objectContaining({
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }));
    expect(result.data).toBe('get-data');
  });
});

describe('create_request', () => {
  it('sends POST request with payload', async () => {
    const payload = { name: 'Test' };

    const result = await create_request('contacts/', payload);

    expect(mockAxios.post).toHaveBeenCalledWith(
      '/api/contacts/',
      payload,
      expect.objectContaining({ headers: expect.any(Object) })
    );
    expect(result.data).toBe('post-data');
  });
});

describe('patch_request', () => {
  it('sends PATCH request with payload', async () => {
    const payload = { title: 'Updated' };

    const result = await patch_request('blog/1/', payload);

    expect(mockAxios.patch).toHaveBeenCalledWith(
      '/api/blog/1/',
      payload,
      expect.objectContaining({ headers: expect.any(Object) })
    );
    expect(result.data).toBe('patch-data');
  });
});

describe('put_request', () => {
  it('sends PUT request with payload', async () => {
    const payload = { title: 'Replaced' };

    const result = await put_request('blog/1/', payload);

    expect(mockAxios.put).toHaveBeenCalledWith(
      '/api/blog/1/',
      payload,
      expect.objectContaining({ headers: expect.any(Object) })
    );
    expect(result.data).toBe('put-data');
  });
});

describe('delete_request', () => {
  it('sends the explicit deletion confirmation in the request body', async () => {
    const payload = { force: true, confirmation: 'DELETE', impact_token: 'reviewed' };

    await delete_request('projects/7/delete/', payload);

    expect(mockAxios.delete).toHaveBeenCalledWith(
      '/api/projects/7/delete/',
      expect.objectContaining({ data: payload, headers: expect.any(Object) })
    );
  });

  it('sends DELETE request', async () => {
    const result = await delete_request('blog/1/');

    expect(mockAxios.delete).toHaveBeenCalledWith(
      '/api/blog/1/',
      expect.objectContaining({ headers: expect.any(Object) })
    );
    expect(result.status).toBe(204);
  });
});

describe('error handling', () => {
  it.each([
    'secure-links/create/',
    'secure-links/public/create/',
    'secure-links/public/reveal/',
  ])('does not log sensitive request failures for %s', async (url) => {
    const log = jest.spyOn(console, 'error').mockImplementation(() => {});
    const error = Object.assign(new Error('Request failed'), {
      config: { data: { fields: { password: 'private-value' }, token: 'private-token' } },
      response: { status: 500, data: '<html>private traceback</html>' },
    });
    mockAxios.post.mockRejectedValue(error);

    await expect(create_request(url, error.config.data)).rejects.toBe(error);

    expect(log).not.toHaveBeenCalled();
  });

  it('propagates axios errors', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    const error = new Error('Network error');
    mockAxios.get.mockRejectedValue(error);

    await expect(get_request('fail/')).rejects.toThrow('Network error');
  });

  it('propagates POST errors', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    mockAxios.post.mockRejectedValue(new Error('Validation failed'));

    await expect(create_request('fail/', {})).rejects.toThrow('Validation failed');
  });

  it('throws on unsupported HTTP method', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.resetModules();

    jest.doMock('axios', () => ({ __esModule: true, default: mockAxios }));
    const { __test_makeRequest } = require('../../../stores/services/request_http');

    await expect(__test_makeRequest('TRACE', 'test/')).rejects.toThrow('Unsupported method: TRACE');
  });
});

describe('create_request with FormData', () => {
  it('omits Content-Type header when params is FormData', async () => {
    jest.resetModules();
    jest.doMock('axios', () => ({ __esModule: true, default: mockAxios }));
    const mod = require('../../../stores/services/request_http');

    const formData = new FormData();
    formData.append('file', 'data');
    await mod.create_request('upload/', formData);

    const callArgs = mockAxios.post.mock.calls[0];
    expect(callArgs[2].headers['Content-Type']).toBeUndefined();
  });
});

describe('getCookie (via CSRF header)', () => {
  it('includes X-CSRFToken header from document.cookie', async () => {
    Object.defineProperty(document, 'cookie', {
      value: 'csrftoken=abc123; other=value',
      writable: true,
    });

    jest.resetModules();
    jest.doMock('axios', () => ({ __esModule: true, default: mockAxios }));
    const mod = require('../../../stores/services/request_http');

    await mod.get_request('test/');

    expect(mockAxios.get).toHaveBeenCalledWith('/api/test/', expect.objectContaining({
      headers: expect.objectContaining({ 'X-CSRFToken': 'abc123' }),
    }));

    document.cookie = '';
  });

  it('handles missing csrftoken cookie', async () => {
    Object.defineProperty(document, 'cookie', {
      value: 'other=value',
      writable: true,
    });

    jest.resetModules();
    jest.doMock('axios', () => ({ __esModule: true, default: mockAxios }));
    const mod = require('../../../stores/services/request_http');

    await mod.get_request('test/');

    expect(mockAxios.get).toHaveBeenCalledWith('/api/test/', expect.objectContaining({
      headers: expect.objectContaining({ 'X-CSRFToken': null }),
    }));

    document.cookie = '';
  });

  it('handles empty document.cookie', async () => {
    Object.defineProperty(document, 'cookie', {
      value: '',
      writable: true,
    });

    jest.resetModules();
    jest.doMock('axios', () => ({ __esModule: true, default: mockAxios }));
    const mod = require('../../../stores/services/request_http');

    await mod.get_request('test/');

    expect(mockAxios.get).toHaveBeenCalledWith('/api/test/', expect.objectContaining({
      headers: expect.objectContaining({ 'X-CSRFToken': null }),
    }));
  });

  it('returns null when typeof document is undefined (SSR context)', async () => {
    const origDescriptor = Object.getOwnPropertyDescriptor(global, 'document');
    // JSDOM in later versions doesn't allow redefining document. We temporarily set it to null instead of deleting
    const origDoc = global.document;
    global.document = undefined;

    jest.resetModules();
    jest.doMock('axios', () => ({ __esModule: true, default: mockAxios }));
    const mod = require('../../../stores/services/request_http');

    await mod.get_request('test/');

    expect(mockAxios.get).toHaveBeenCalledWith('/api/test/', expect.objectContaining({
      headers: expect.objectContaining({ 'X-CSRFToken': null }),
    }));

    if (origDescriptor) {
      global.document = origDoc;
    }
  });
});
