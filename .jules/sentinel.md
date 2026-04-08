## 2024-04-06 - XSS in Metrics and Notes Rendering
**Vulnerability:** User-controlled strings (e.g. `config.label` and `error.message`) were directly injected into `innerHTML` using template literals in `backend/static/app.js` (lines 987, 1066, 2268), posing a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** In vanilla JS apps, injecting data into `innerHTML` via template strings is a common vector. While `textContent` is preferred, when mixing tags, a helper like `escapeHtml()` must be explicitly called on the variables before interpolation.
**Prevention:** Always use `escapeHtml()` or `textContent` for dynamic values inside DOM components rendering logic, especially error messages or status labels derived from APIs.
