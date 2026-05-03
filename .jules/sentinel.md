## 2024-04-06 - XSS in Metrics and Notes Rendering
**Vulnerability:** User-controlled strings (e.g. `config.label` and `error.message`) were directly injected into `innerHTML` using template literals in `backend/static/app.js` (lines 987, 1066, 2268), posing a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** In vanilla JS apps, injecting data into `innerHTML` via template strings is a common vector. While `textContent` is preferred, when mixing tags, a helper like `escapeHtml()` must be explicitly called on the variables before interpolation.
**Prevention:** Always use `escapeHtml()` or `textContent` for dynamic values inside DOM components rendering logic, especially error messages or status labels derived from APIs.

## 2024-05-24 - Command Injection in MCP Workspace
**Vulnerability:** In `backend/mcp_workspace.py`, the `workspace_run_command` tool accepted a raw string command and passed it directly to `subprocess.run` with `shell=True`. This permitted malicious clients to execute arbitrary commands by appending shell metacharacters (e.g., `command && malicious_command`).
**Learning:** Using `shell=True` with unvalidated user input is a textbook Command Injection vector. While convenient for executing complex string commands, it overrides standard process isolation.
**Prevention:** To safely execute dynamic commands, use `shell=False` and supply the command as a list of strings. If the command originates as a single string, parse it safely into arguments using `shlex.split()`.
