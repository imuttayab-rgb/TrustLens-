# TrustLens city search update

Prepared 4 October 2026 (Pakistan time).

## Changes

Home, Browse and Post an Ad share a searchable City picker. Select a province/region, open City and type a name. Only cities in that region are searched. Matches keep the location catalogue's A–Z order. Typing filters the list; click or Enter selects the actual city. Merely typing never becomes a submitted location.

Search ignores case, spaces and punctuation: `Lah` matches Lahore and `Rawal Pindi` matches Rawalpindi. Shortcuts include LHR, KHI, ISB, RWP, FSD, RYK and DGK. The popup includes clear-search and clear-selection controls, match counts, no-results feedback, keyboard arrows and Escape dismissal. Existing values remain readable in both themes. City search is local and makes no AI or internet request.

Changing province still clears the selected city. Post an Ad retains its Other / not listed choice and existing area/map-pin reset behavior. Home's required-city validation and Browse's Apply Filters rules remain in place. The existing API filters by city, so choosing a province alone does not claim province-wide results. The location data is the existing curated GeoNames extract, not every village. See SEARCH_LOCATION_UPDATE.md for data coverage and attribution.

## Install

Download `TrustLens_City_Search_Update.sh` into Windows Downloads. With Docker Desktop and the current TrustLens services running, use Git Bash:

```bash
bash "$HOME/Downloads/TrustLens_City_Search_Update.sh"
```

After CITY SEARCH UPDATE COMPLETE, open http://localhost:3000 and press Ctrl+Shift+R.

This is one cumulative package. It accepts the known AI + Home sources or the previous Search + Location update. If Search + Location is already installed, only web is rebuilt. Otherwise the earlier catalogue/location update is included and API + web are rebuilt. Existing custom edits to packaged paths stop the preflight for review. Do not delete or reset those edits to force installation.

Sources and running image references are backed up under `.git/trustlens-city-backups/`. Failures trigger rollback. The final output gives the recovery script path. Recovery refuses to overwrite newer source edits. No API key entry, environment-file write, database migration, dependency installation, uploaded-file change, worker/admin rebuild, or paid provider call is included. Approved FAQ text and verification flags are preserved.

## Verification

- Changed-file ESLint and web TypeScript checks passed. All 15 existing Browse-parameter and Post-an-Ad helper tests passed.
- Production web build passed with `next build --no-lint`; changed files were linted separately because the inherited settings page has unrelated baseline lint errors. This package adds no lint bypass to project configuration.
- Installer simulations passed against both the AI + Home baseline and Search + Location baseline: install/reinstall, correct service selection, CRLF, paths with spaces, source-conflict protection, build/probe failure recovery, actual rollback, and protection of newer edits. Environment bytes/mtime and approved FAQ bytes remained unchanged. Docker was simulated for these checks.
- Interactive browser verification in this session was blocked by the execution environment's socket permissions; live mobile/keyboard tests for the new custom picker remain unverified. The earlier update's browser results apply to its previous native selector, not this new picker.

The user's Windows Docker deployment is confirmed only by the installer output from that laptop.

The separately supplied `TrustLens_Homepage_Mockup.png` is the recovered original homepage design concept, not a screenshot of this city-search update.
