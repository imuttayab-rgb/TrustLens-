# Verification evidence

These are synthetic, pre-deployment checks. Read `../development/SECURITY_FIX_REPORT.md` for scope and unverified items. Evidence does not contain the user’s database or live credentials.

- `python-final.log`: 709 passed, 35 skipped; optional OpenCV test file excluded.
- `security-and-setup-final.log`: 38 new security tests plus 13 launcher/update contracts (subset of the full suite).
- `frontend-regression.log`: 137 tests.
- `database-regression.log`: migrations and 32 real SQL state checks on PGlite.
- `security-results.json`, `route-access.csv`: focused API probes and authorization inventory.
- `browser-results.json`, `document-header-results.json`: production-build browser/document security checks.
- `web-build.log`, `admin-build.log`: production builds, with cached font fixture.
- `call-controls.log`, `chat-voice-ui.log`: real UI, synthetic API/media adapters.
- `backup-crypto.log`: synthetic multi-chunk encrypted backup roundtrip, not a volume restore.
- `schema-check.log`: unchanged generated API contract (161 paths).

No screenshot, microphone recording or local private environment is shipped here.
