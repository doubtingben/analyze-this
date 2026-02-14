## 2025-02-18 - [HIGH] Missing Content Security Policy
**Vulnerability:** The application was missing a `Content-Security-Policy` header, relying solely on `X-Content-Type-Options` and `X-Frame-Options`. This left it vulnerable to XSS (if content injection bypasses escaping) and data exfiltration.
**Learning:** Even with modern frameworks like FastAPI and Jinja2 (autoescape), a CSP is critical defense-in-depth. However, legacy frontend code often requires `unsafe-inline` for scripts and styles, making strict CSP adoption difficult without refactoring.
**Prevention:** Always implement a baseline CSP in middleware early in the project. Use `script-src 'self' ...` and restrict `object-src` to `'none'`.

## 2025-02-18 - [MEDIUM] Error Message Information Leakage
**Vulnerability:** The application was catching exceptions during file uploads and returning the raw exception message to the user (`detail=f"File upload failed: {str(e)}"`). This could leak sensitive internal details (e.g., file paths, connection strings, library versions) in production environments.
**Learning:** Always sanitize error messages in production. Use a generic message for the user and log the detailed error internally. Environment-specific error details (e.g., `APP_ENV == 'development'`) can be useful for debugging but must be strictly controlled.
**Prevention:** Implement a standard error handling pattern that checks the environment and returns generic messages in production.
