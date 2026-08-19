# Live Verification Evidence

STATUS: PASS
LIVE_URL: http://127.0.0.1:6060
VERIFIED_AT_UTC: 2026-08-19T00:50:06Z
APPROVED_BY: raumontalvo

## Scope Checked
- Home EN: /index.html
- Home ES: /es/index.html
- App EN: /application.html
- App ES: /es/application.html

## Validation Notes
- Functional checks:
  - Ran scripts/verify-live-site.sh against http://127.0.0.1:6060.
  - All required routes returned HTTP 200.
- Browser/device coverage:
  - Local live server rendered and was opened via BROWSER command.
  - Lighthouse run executed 3 passes per page for EN/ES home and app pages.
- Known limitations accepted for release:
  - Verification used local live endpoint; replace LIVE_URL with deployed preview URL before final promotion to main if required by release policy.

## Gate Rule
Before opening a PR to main:
- Set STATUS to PASS.
- Fill LIVE_URL, VERIFIED_AT_UTC, and APPROVED_BY.
