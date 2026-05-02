## 2024-04-06 - XSS in Metrics and Notes Rendering
**Vulnerability:** User-controlled strings (e.g. `config.label` and `error.message`) were directly injected into `innerHTML` using template literals in `backend/static/app.js` (lines 987, 1066, 2268), posing a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** In vanilla JS apps, injecting data into `innerHTML` via template strings is a common vector. While `textContent` is preferred, when mixing tags, a helper like `escapeHtml()` must be explicitly called on the variables before interpolation.
**Prevention:** Always use `escapeHtml()` or `textContent` for dynamic values inside DOM components rendering logic, especially error messages or status labels derived from APIs.
## 2024-05-02 - Session Fixation Risk in Logout
**Vulnerability:** The `/logout` endpoint in `backend/main.py` only popped the `user` key from the session dictionary (`request.session.pop('user', None)`), leaving other session data intact. This could lead to session fixation or state pollution vulnerabilities.
**Learning:** Completely destroying the session state is essential upon logout to ensure no residual data (such as temporary tokens, cached states, or stale permissions) is left behind.
**Prevention:** Always use `request.session.clear()` to completely invalidate the session rather than relying on deleting individual keys when authenticating out.
