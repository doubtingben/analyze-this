## 2024-04-06 - XSS in Metrics and Notes Rendering
**Vulnerability:** User-controlled strings (e.g. `config.label` and `error.message`) were directly injected into `innerHTML` using template literals in `backend/static/app.js` (lines 987, 1066, 2268), posing a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** In vanilla JS apps, injecting data into `innerHTML` via template strings is a common vector. While `textContent` is preferred, when mixing tags, a helper like `escapeHtml()` must be explicitly called on the variables before interpolation.
**Prevention:** Always use `escapeHtml()` or `textContent` for dynamic values inside DOM components rendering logic, especially error messages or status labels derived from APIs.

## 2024-04-24 - Session Fixation and State Pollution in Logout
**Vulnerability:** The `/logout` endpoint merely popped the `user` object from the session via `request.session.pop('user', None)` instead of destroying the entire session, leaving other session data (like `csrf_token`) intact.
**Learning:** Partially clearing a session dictionary does not invalidate the session cookie or clear other security-sensitive states (like CSRF tokens). This can lead to session fixation or state pollution vulnerabilities if the same browser is used to log in again.
**Prevention:** Always use `request.session.clear()` when logging out a user to ensure the session is completely destroyed and a fresh session is established upon the next login.
