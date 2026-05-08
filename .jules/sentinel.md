## 2024-04-06 - XSS in Metrics and Notes Rendering
**Vulnerability:** User-controlled strings (e.g. `config.label` and `error.message`) were directly injected into `innerHTML` using template literals in `backend/static/app.js` (lines 987, 1066, 2268), posing a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** In vanilla JS apps, injecting data into `innerHTML` via template strings is a common vector. While `textContent` is preferred, when mixing tags, a helper like `escapeHtml()` must be explicitly called on the variables before interpolation.
**Prevention:** Always use `escapeHtml()` or `textContent` for dynamic values inside DOM components rendering logic, especially error messages or status labels derived from APIs.

## 2024-05-08 - [Error Message Leakage via Condition Bypass]
**Vulnerability:** The application was exposing potentially sensitive internal tracebacks or exception messages on failed file uploads by bypassing general error handling explicitly for `APP_ENV == "development"`.
**Learning:** Even conditional exception dumping like `if APP_ENV == "development": return detail = f"Error: {str(e)}"` creates significant risk because environmental variables are prone to misconfiguration, misinterpretation across staging environments, or explicit runtime injection.
**Prevention:** Never surface unhandled or raw exceptions to end users over API endpoints regardless of the current deployment environment. Instead, rely solely on server-side log output (`print()`, `logger.exception()`, telemetry tools) to inspect errors during development.
