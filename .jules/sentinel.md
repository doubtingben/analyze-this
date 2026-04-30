## 2024-04-06 - XSS in Metrics and Notes Rendering
**Vulnerability:** User-controlled strings (e.g. `config.label` and `error.message`) were directly injected into `innerHTML` using template literals in `backend/static/app.js` (lines 987, 1066, 2268), posing a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** In vanilla JS apps, injecting data into `innerHTML` via template strings is a common vector. While `textContent` is preferred, when mixing tags, a helper like `escapeHtml()` must be explicitly called on the variables before interpolation.
**Prevention:** Always use `escapeHtml()` or `textContent` for dynamic values inside DOM components rendering logic, especially error messages or status labels derived from APIs.

## 2024-04-30 - Session Fixation and State Pollution on Logout
**Vulnerability:** The `/logout` endpoint merely removed the `user` object from the session using `request.session.pop('user', None)`, leaving behind all other session state (like `CSRF_KEY`).
**Learning:** Partially clearing a session dictionary is an anti-pattern. While removing the user invalidates authentication, leftover session tokens like CSRF could be reused, leading to potential session fixation or state pollution risks if the same session cookie is reused by another user.
**Prevention:** Always use `request.session.clear()` to completely obliterate session data on logout.
