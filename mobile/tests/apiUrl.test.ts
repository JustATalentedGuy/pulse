import {
  getDevServerHostname,
  resolveApiBaseUrl,
} from '@/utils/apiUrl';

test('extracts the LAN hostname from the Metro host URI', () => {
  expect(getDevServerHostname('192.168.1.5:8081')).toBe('192.168.1.5');
});

test('uses the Metro hostname for a native development build', () => {
  expect(
    resolveApiBaseUrl({
      autoHost: true,
      configuredNativeUrl: 'http://192.168.1.2:8000',
      configuredWebUrl: 'http://127.0.0.1:8000',
      devServerHostUri: '192.168.1.5:8081',
      isDev: true,
      platform: 'android',
      port: '8000',
    }),
  ).toBe('http://192.168.1.5:8000');
});

test('keeps the localhost URL for web', () => {
  expect(
    resolveApiBaseUrl({
      autoHost: true,
      configuredNativeUrl: 'http://192.168.1.5:8000',
      configuredWebUrl: 'http://127.0.0.1:8000',
      devServerHostUri: '192.168.1.5:8081',
      isDev: true,
      platform: 'web',
      port: '8000',
    }),
  ).toBe('http://127.0.0.1:8000');
});
