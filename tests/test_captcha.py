"""Tests for CAPTCHA detection and site key extraction."""

import pytest
from knowscraper.anti_detection.captcha import detect_captcha, extract_site_key, CaptchaType


RECAPTCHA_V2_HTML = """
<html><body>
<div class="g-recaptcha" data-sitekey="6LeAbc123DEFghiJKL"></div>
<script src="https://www.google.com/recaptcha/api.js"></script>
</body></html>
"""

RECAPTCHA_V3_HTML = """
<html><body>
<script src="https://www.google.com/recaptcha/api.js?render=6LeXYZ456abcDEF789"></script>
</body></html>
"""

HCAPTCHA_HTML = """
<html><body>
<div class="h-captcha" data-sitekey="abc-123-def-456"></div>
<script src="https://js.hcaptcha.com/1/api.js"></script>
</body></html>
"""

CLOUDFLARE_HTML = """
<html><body>
<div id="challenge-stage">
<div class="cf-turnstile" data-sitekey="0x4AAAAAAA_cf_key"></div>
Cloudflare Ray ID: 1234567890abc
</div>
</body></html>
"""

CLEAN_HTML = """
<html><body>
<h1>Normal page without CAPTCHA</h1>
<p>Just regular content here.</p>
</body></html>
"""


class TestDetectCaptcha:
    def test_detects_recaptcha_v2(self):
        result = detect_captcha(RECAPTCHA_V2_HTML)
        assert result == CaptchaType.RECAPTCHA_V2

    def test_detects_hcaptcha(self):
        result = detect_captcha(HCAPTCHA_HTML)
        assert result == CaptchaType.HCAPTCHA

    def test_detects_cloudflare(self):
        result = detect_captcha(CLOUDFLARE_HTML)
        assert result == CaptchaType.CLOUDFLARE

    def test_no_captcha_returns_unknown(self):
        result = detect_captcha(CLEAN_HTML)
        assert result == CaptchaType.UNKNOWN

    def test_empty_html(self):
        assert detect_captcha("") == CaptchaType.UNKNOWN

    def test_case_insensitive(self):
        html = '<div class="G-RECAPTCHA" data-sitekey="abc"></div>'
        result = detect_captcha(html)
        assert result == CaptchaType.RECAPTCHA_V2

    def test_detects_recaptcha_v3(self):
        result = detect_captcha(RECAPTCHA_V3_HTML)
        assert result in (CaptchaType.RECAPTCHA_V3, CaptchaType.RECAPTCHA_V2)


class TestExtractSiteKey:
    def test_extracts_recaptcha_v2_key(self):
        key = extract_site_key(RECAPTCHA_V2_HTML, CaptchaType.RECAPTCHA_V2)
        assert key == "6LeAbc123DEFghiJKL"

    def test_extracts_hcaptcha_key(self):
        key = extract_site_key(HCAPTCHA_HTML, CaptchaType.HCAPTCHA)
        assert key == "abc-123-def-456"

    def test_extracts_cloudflare_key(self):
        key = extract_site_key(CLOUDFLARE_HTML, CaptchaType.CLOUDFLARE)
        assert key == "0x4AAAAAAA_cf_key"

    def test_extracts_recaptcha_v3_key(self):
        key = extract_site_key(RECAPTCHA_V3_HTML, CaptchaType.RECAPTCHA_V3)
        assert key == "6LeXYZ456abcDEF789"

    def test_returns_none_when_no_key(self):
        key = extract_site_key(CLEAN_HTML, CaptchaType.RECAPTCHA_V2)
        assert key is None

    def test_returns_none_for_unknown_type(self):
        key = extract_site_key(RECAPTCHA_V2_HTML, CaptchaType.UNKNOWN)
        assert key is None
