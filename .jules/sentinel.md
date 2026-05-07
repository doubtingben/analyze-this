## 2024-04-06 - XSS in Metrics and Notes Rendering
**Vulnerability:** User-controlled strings (e.g. `config.label` and `error.message`) were directly injected into `innerHTML` using template literals in `backend/static/app.js` (lines 987, 1066, 2268), posing a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** In vanilla JS apps, injecting data into `innerHTML` via template strings is a common vector. While `textContent` is preferred, when mixing tags, a helper like `escapeHtml()` must be explicitly called on the variables before interpolation.
**Prevention:** Always use `escapeHtml()` or `textContent` for dynamic values inside DOM components rendering logic, especially error messages or status labels derived from APIs.

## 2024-05-18 - Insecure Session Management on Logout
**Vulnerability:** The `/logout` endpoint merely removed the `user` key from the session dictionary via `request.session.pop('user', None)`, leaving other potential session data (e.g., OAuth states, CSRF tokens, intermediate flow states) intact. This partial teardown opens the door to state pollution or session fixation risks if the same session cookie is reused.
**Learning:** Popping specific keys is insufficient for securely terminating a user's session. Any residual state tied to the session cookie can be unexpectedly carried over to subsequent interactions or a newly logged-in user.
**Prevention:** Always use `request.session.clear()` in logout handlers to completely destroy the session state and enforce a clean slate.
