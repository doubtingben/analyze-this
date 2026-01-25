## 2025-05-15 - CORS Misconfiguration Pattern
**Vulnerability:** The backend was configured with `allow_origins=["*"]` AND `allow_credentials=True`. This allows any site to potentially exploit users' authenticated sessions, although browsers usually block `*` with credentials.
**Learning:** Developers often use `*` for convenience in development but forget to restrict it in production. Starlette allows this configuration even if specs discourage it.
**Prevention:** Use `allow_origin_regex` for localhost in development, and strict env-var based `allow_origins` list in production.
