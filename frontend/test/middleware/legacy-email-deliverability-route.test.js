global.defineNuxtRouteMiddleware = (fn) => fn;
global.navigateTo = jest.fn((to) => to);

const middleware = require('../../middleware/legacy-email-deliverability-route').default;

describe('legacy email deliverability route', () => {
  afterEach(() => jest.clearAllMocks());

  it.each([
    ['/es-co/panel/proposals/email-deliverability', '/es-co/panel/emails'],
    ['/en-us/panel/proposals/email-deliverability', '/en-us/panel/emails'],
    ['/panel/proposals/email-deliverability', '/es-co/panel/emails'],
    ['/es-co/panel/proposals/email-deliverability/', '/es-co/panel/emails'],
  ])('redirects %s to the email status tab', (path, destination) => {
    const result = middleware({ path, query: {}, hash: '' });

    expect(result).toEqual({ path: destination, query: { tab: 'status' } });
    expect(global.navigateTo).toHaveBeenCalledWith(result, { replace: true, redirectCode: 301 });
  });

  it.each([
    '/es-co/panel/emails',
    '/es-co/panel/proposals/email-deliverability-guide',
    '/es-co/panel/proposals/email-deliverability/42',
  ])('leaves %s untouched', (path) => {
    middleware({ path, query: {}, hash: '' });

    expect(global.navigateTo).not.toHaveBeenCalled();
  });
});
