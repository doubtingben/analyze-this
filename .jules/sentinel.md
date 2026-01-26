## 2025-05-15 - CORS Misconfiguration Pattern
**Vulnerability:** The backend was configured with `allow_origins=["*"]` AND `allow_credentials=True`. This allows any site to potentially exploit users' authenticated sessions, although browsers usually block `*` with credentials.
**Learning:** Developers often use `*` for convenience in development but forget to restrict it in production. Starlette allows this configuration even if specs discourage it.
**Prevention:** Use `allow_origin_regex` for localhost in development, and strict env-var based `allow_origins` list in production.

## 2025-05-18 - Jinja2 Autoescape Default Trap
**Vulnerability:** XSS in dashboard due to `jinja2.Template()` defaulting to `autoescape=False`.
**Learning:** Unlike `jinja2.Environment` (which often defaults to autoescape for .html extensions), using `Template()` directly on a string does not enable auto-escaping by default. Manual escaping via string replacement (`replace("'", "\\'")`) is insufficient for HTML attribute contexts.
**Prevention:** Always use `Template(source, autoescape=True)` when rendering user input. Prefer `data-*` attributes for passing data to JavaScript event handlers over inline string interpolation.
