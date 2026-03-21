## 2025-02-18 - [HIGH] Missing Content Security Policy
**Vulnerability:** The application was missing a `Content-Security-Policy` header, relying solely on `X-Content-Type-Options` and `X-Frame-Options`. This left it vulnerable to XSS (if content injection bypasses escaping) and data exfiltration.
**Learning:** Even with modern frameworks like FastAPI and Jinja2 (autoescape), a CSP is critical defense-in-depth. However, legacy frontend code often requires `unsafe-inline` for scripts and styles, making strict CSP adoption difficult without refactoring.
**Prevention:** Always implement a baseline CSP in middleware early in the project. Use `script-src 'self' ...` and restrict `object-src` to `'none'`.

## 2025-02-18 - [MEDIUM] Error Message Information Leakage
**Vulnerability:** The application was catching exceptions during file uploads and returning the raw exception message to the user (`detail=f"File upload failed: {str(e)}"`). This could leak sensitive internal details (e.g., file paths, connection strings, library versions) in production environments.
**Learning:** Always sanitize error messages in production. Use a generic message for the user and log the detailed error internally. Environment-specific error details (e.g., `APP_ENV == 'development'`) can be useful for debugging but must be strictly controlled.
**Prevention:** Implement a standard error handling pattern that checks the environment and returns generic messages in production.
## 2025-03-21 - SSRF Mitigation with `follow_redirects` Bypass
**Vulnerability:** A Server-Side Request Forgery (SSRF) vulnerability existed in `_fetch_url_text` in `worker_podcast_derivative.py`. The endpoint fetched external URLs directly without validating if the hostname resolved to an internal/private IP address.
**Learning:** Even when adding URL validation (resolving the hostname and checking against private IP ranges), using `httpx.get(url, follow_redirects=True)` completely bypasses the mitigation. An attacker can supply a safe external URL that immediately redirects (301/302) to an internal IP (like `169.254.169.254`). The HTTP client will follow the redirect without re-validating the new URL, defeating the protection.
**Prevention:** To prevent this, `follow_redirects` must be set to `False`. Redirects must be handled manually, extracting the `Location` header and recursively passing it through the exact same SSRF validation checks before fetching it.
