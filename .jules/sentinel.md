## 2025-02-18 - [HIGH] Missing Content Security Policy
**Vulnerability:** The application was missing a `Content-Security-Policy` header, relying solely on `X-Content-Type-Options` and `X-Frame-Options`. This left it vulnerable to XSS (if content injection bypasses escaping) and data exfiltration.
**Learning:** Even with modern frameworks like FastAPI and Jinja2 (autoescape), a CSP is critical defense-in-depth. However, legacy frontend code often requires `unsafe-inline` for scripts and styles, making strict CSP adoption difficult without refactoring.
**Prevention:** Always implement a baseline CSP in middleware early in the project. Use `script-src 'self' ...` and restrict `object-src` to `'none'`.

## 2025-02-18 - [MEDIUM] Error Message Information Leakage
**Vulnerability:** The application was catching exceptions during file uploads and returning the raw exception message to the user (`detail=f"File upload failed: {str(e)}"`). This could leak sensitive internal details (e.g., file paths, connection strings, library versions) in production environments.
**Learning:** Always sanitize error messages in production. Use a generic message for the user and log the detailed error internally. Environment-specific error details (e.g., `APP_ENV == 'development'`) can be useful for debugging but must be strictly controlled.
**Prevention:** Implement a standard error handling pattern that checks the environment and returns generic messages in production.

## 2025-03-17 - [HIGH] Incomplete HTML Escaping Allows Reflected XSS
**Vulnerability:** The `escapeHtml` function in `backend/static/app.js` relied solely on assigning to `textContent` and reading `innerHTML`. While this escapes `<`, `>`, and `&`, it does not escape quotes (`"` or `'`). Because the result was interpolated directly into HTML attributes (e.g. `value="${escapeHtml(...)}"`), it allowed attackers to break out of attributes and inject malicious payloads.
**Learning:** Using `textContent` then `innerHTML` is insufficient if the output is used in attribute contexts. Quotes must be explicitly escaped when rendering dynamic data in HTML attributes via template strings.
**Prevention:** Ensure that manual escaping functions cover all five crucial characters (`<`, `>`, `&`, `"`, `'`), or prefer using standard DOM manipulation (`element.value = ...`) over template literals for attributes.
