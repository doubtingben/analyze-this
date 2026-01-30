## 2025-05-15 - CORS Misconfiguration Pattern
**Vulnerability:** The backend was configured with `allow_origins=["*"]` AND `allow_credentials=True`. This allows any site to potentially exploit users' authenticated sessions, although browsers usually block `*` with credentials.
**Learning:** Developers often use `*` for convenience in development but forget to restrict it in production. Starlette allows this configuration even if specs discourage it.
**Prevention:** Use `allow_origin_regex` for localhost in development, and strict env-var based `allow_origins` list in production.

## 2025-05-18 - Jinja2 Autoescape Default Trap
**Vulnerability:** XSS in dashboard due to `jinja2.Template()` defaulting to `autoescape=False`.
**Learning:** Unlike `jinja2.Environment` (which often defaults to autoescape for .html extensions), using `Template()` directly on a string does not enable auto-escaping by default. Manual escaping via string replacement (`replace("'", "\\'")`) is insufficient for HTML attribute contexts.
**Prevention:** Always use `Template(source, autoescape=True)` when rendering user input. Prefer `data-*` attributes for passing data to JavaScript event handlers over inline string interpolation.

## 2026-01-27 - IDOR in AI Analysis Workflow
**Vulnerability:** IDOR/SSRF in `share_item` endpoint allowing users to analyze arbitrary files in storage by manipulating the `content` path in the JSON payload.
**Learning:** Background workers (like AI analysis) often run with elevated privileges (service accounts). If the input to these workers (e.g. file path) is not validated at the entry point (API), the worker becomes a confused deputy. Blindly trusting `content` field from client, even for file uploads, is dangerous if the client can specify the path directly (via API) instead of the server generating it.
**Prevention:** Enforce strict ownership validation on all file paths referenced in API requests. If the server generates the path (e.g. upload), ensure the client cannot override it with a custom value. For `image` types where the backend reads the file, validate the path prefix.

## 2026-02-17 - Confused Deputy in Google Auth
**Vulnerability:** The backend accepted any valid Google Access Token via the `userinfo` endpoint without verifying the token was issued to the application (Client ID). This allowed a "Confused Deputy" attack where a malicious app could trick a user into logging in, then use the user's token to impersonate them on our backend.
**Learning:** Google's `userinfo` endpoint validates the token signature but DOES NOT restrict which app the token was issued to. Access Tokens are opaque bearers of authority; verifying their *origin/audience* is critical when used for authentication.
**Prevention:** For Access Tokens, always use the `tokeninfo` endpoint to verify the `aud` claim matches your Client ID before trusting the token. Prefer ID Tokens (verified locally) where possible.
