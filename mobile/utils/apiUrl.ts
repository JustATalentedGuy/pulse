type ApiUrlOptions = {
  autoHost: boolean;
  configuredNativeUrl?: string;
  configuredWebUrl?: string;
  devServerHostUri?: string | null;
  isDev: boolean;
  platform: string;
  port: string;
};

export function getDevServerHostname(hostUri?: string | null) {
  if (!hostUri) return undefined;

  try {
    const url = new URL(
      hostUri.includes('://') ? hostUri : `http://${hostUri}`,
    );
    return url.hostname;
  } catch {
    return undefined;
  }
}

export function resolveApiBaseUrl({
  autoHost,
  configuredNativeUrl,
  configuredWebUrl,
  devServerHostUri,
  isDev,
  platform,
  port,
}: ApiUrlOptions) {
  if (platform === 'web') {
    return configuredWebUrl ?? configuredNativeUrl;
  }

  const devServerHostname = getDevServerHostname(devServerHostUri);
  if (isDev && autoHost && devServerHostname) {
    return `http://${devServerHostname}:${port}`;
  }

  return configuredNativeUrl;
}
