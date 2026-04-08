## 2024-04-06 - XSS in Metrics and Notes Rendering
**Vulnerability:** User-controlled strings (e.g. `config.label` and `error.message`) were directly injected into `innerHTML` using template literals in `backend/static/app.js` (lines 987, 1066, 2268), posing a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** In vanilla JS apps, injecting data into `innerHTML` via template strings is a common vector. While `textContent` is preferred, when mixing tags, a helper like `escapeHtml()` must be explicitly called on the variables before interpolation.
**Prevention:** Always use `escapeHtml()` or `textContent` for dynamic values inside DOM components rendering logic, especially error messages or status labels derived from APIs.
## 2024-04-09 - SSRF Vulnerability in Podcast Feed Generation
**Vulnerability:** The `_extract_remote_text` function in `backend/podcast_content.py` used `requests.get` with `allow_redirects=True` to fetch remote podcast sources. It did not validate the URL's resolved IP address, leaving the application vulnerable to Server-Side Request Forgery (SSRF) against internal services (e.g., AWS Metadata IP `169.254.169.254`, `localhost`, etc.). Additionally, an attacker could bypass naive checks by providing a URL that redirects to a private IP.
**Learning:** Using `requests` with default redirect following is insecure when fetching user-provided URLs. Validating the initial URL is insufficient; every redirect must be validated. Furthermore, validating the IP address and then making the request with the original hostname is vulnerable to Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding attacks.
**Prevention:**
1. Use `httpx.Client(follow_redirects=False)` (or manual redirect handling with `requests`) to intercept and validate each redirect.
2. Resolve the hostname to an IP address using `socket.gethostbyname` and validate it using `ipaddress` (explicitly checking for `0.0.0.0`, private, loopback, link-local, and unspecified addresses).
3. To prevent DNS rebinding, construct the HTTP request to connect directly to the validated IP string (e.g., `http://93.184.216.34`), but preserve the original `Host` header to ensure the target server processes the request correctly.
4. When handling redirects manually, carefully resolve relative `Location` headers using `urllib.parse.urljoin`.
