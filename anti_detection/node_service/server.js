/**
 * KnowScraper - Anti-Detection Microservice
 *
 * Runs as a local HTTP server. Python calls this to:
 *  - Make HTTP requests with real browser TLS fingerprints (via got-scraping)
 *  - Generate realistic browser-consistent headers
 *  - Generate browser fingerprints for injection into Playwright
 *
 * Port: 9119 (configurable via PORT env var)
 */

import express from 'express';
import { gotScraping } from 'got-scraping';
import { HeaderGenerator } from 'header-generator';
import { FingerprintGenerator } from 'fingerprint-generator';

const app = express();
app.use(express.json({ limit: '10mb' }));

const headerGenerator = new HeaderGenerator({
  browsers: [
    { name: 'chrome', minVersion: 115, maxVersion: 130 },
    { name: 'firefox', minVersion: 110, maxVersion: 125 },
    { name: 'safari', minVersion: 16, maxVersion: 17 },
  ],
  devices: ['desktop', 'mobile'],
  operatingSystems: ['windows', 'macos', 'linux', 'android', 'ios'],
});

const fingerprintGenerator = new FingerprintGenerator({
  browsers: [{ name: 'chrome', minVersion: 115 }],
  devices: ['desktop'],
  operatingSystems: ['windows', 'macos'],
});

/**
 * POST /fetch
 * Makes an HTTP request with real browser TLS fingerprint.
 *
 * Body: { url, method, headers, payload, proxy, sessionToken, timeout }
 * Returns: { status, headers, body, url }
 */
app.post('/fetch', async (req, res) => {
  const {
    url,
    method = 'GET',
    headers = {},
    payload = undefined,
    proxy = undefined,
    session_token = undefined,
    timeout = 30000,
  } = req.body;

  if (!url) {
    return res.status(400).json({ error: 'url is required' });
  }

  try {
    const options = {
      method,
      headers,
      timeout: { request: timeout },
      throwHttpErrors: false,
      followRedirect: true,
    };

    if (payload) {
      options.body = typeof payload === 'string' ? payload : JSON.stringify(payload);
    }

    if (proxy) {
      options.proxyUrl = proxy;
    }

    // sessionToken must be an object in got-scraping v4; session management is handled in Python
    if (session_token && typeof session_token === 'object') {
      options.sessionToken = session_token;
    }

    const response = await gotScraping(url, options);

    res.json({
      status: response.statusCode,
      headers: response.headers,
      body: response.body,
      url: response.url,
    });
  } catch (err) {
    res.status(500).json({ error: err.message, type: err.constructor.name });
  }
});

/**
 * POST /headers
 * Generate realistic browser-consistent HTTP headers.
 *
 * Body: { browser?, os?, device?, locale? }
 * Returns: { headers }
 */
app.post('/headers', (req, res) => {
  const { browser, os, device, locale } = req.body || {};

  try {
    const constraints = {};
    if (browser) constraints.browsers = [{ name: browser }];
    if (os) constraints.operatingSystems = [os];
    if (device) constraints.devices = [device];
    if (locale) constraints.locales = [locale];

    const headers = headerGenerator.getHeaders(constraints);
    res.json({ headers });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * POST /fingerprint
 * Generate a full browser fingerprint for Playwright injection.
 *
 * Body: { browser?, os?, device? }
 * Returns: { fingerprint, headers }
 */
app.post('/fingerprint', (req, res) => {
  const { browser, os, device } = req.body || {};

  try {
    const constraints = {};
    if (browser) constraints.browsers = [{ name: browser, minVersion: 115 }];
    if (os) constraints.operatingSystems = [os];
    if (device) constraints.devices = [device];

    const { fingerprint, headers } = fingerprintGenerator.getFingerprint(constraints);
    res.json({ fingerprint, headers });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /health
 */
app.get('/health', (_, res) => {
  res.json({ status: 'ok', service: 'knowscraper-anti-detection' });
});

const PORT = parseInt(process.env.PORT || '9119', 10);
app.listen(PORT, '127.0.0.1', () => {
  console.log(`[KnowScraper] Anti-detection service running on http://127.0.0.1:${PORT}`);
});
