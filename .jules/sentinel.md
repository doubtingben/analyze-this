## 2025-02-18 - [HIGH] Missing Content Security Policy
**Vulnerability:** The application was missing a `Content-Security-Policy` header, relying solely on `X-Content-Type-Options` and `X-Frame-Options`. This left it vulnerable to XSS (if content injection bypasses escaping) and data exfiltration.
**Learning:** Even with modern frameworks like FastAPI and Jinja2 (autoescape), a CSP is critical defense-in-depth. However, legacy frontend code often requires `unsafe-inline` for scripts and styles, making strict CSP adoption difficult without refactoring.
**Prevention:** Always implement a baseline CSP in middleware early in the project. Use `script-src 'self' ...` and restrict `object-src` to `'none'`.
