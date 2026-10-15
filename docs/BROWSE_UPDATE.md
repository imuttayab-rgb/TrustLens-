# TrustLens Browse update

Prepared 4 October 2026 (Asia/Karachi), following the user's confirmation that the City Search update is done.

## What changes

- A clearer search-results header with the current query/category and selected location. Counts come from the existing public listings API. The page no longer labels every result as a verified listing or claims everything is nearby.
- On smaller screens, filters start collapsed behind a visible Filters button with an applied-filter count. The panel expands in the page, has explicit Close/Apply controls, and returns keyboard focus to its toggle when closed. Desktop keeps a dedicated filter column. This is an inline panel, not a modal drawer.
- List view displays a horizontal photo/details card across the results column. Grid view adapts to available width. Shared listing cards have two-line titles, more readable prices and a touch-visible share control. These shared presentation refinements also affect Home, favourites and seller listings. An absent condition is labelled unspecified instead of being assumed Used.
- Sorting returns to page one while retaining filters. Switching grid/list keeps the page. Province/city search is preserved. Choosing a new city and area can be applied together. Reset also clears unapplied draft inputs, while keeping sort/layout preferences.
- Price inputs accept `40000`, `40,000`, zero and up to two decimal places. Negative, malformed, nonfinite and inverted price ranges show feedback and cannot be applied. Invalid price ranges from shared links display an error instead of showing apparently matching results. Invalid page numbers fall back to page one.
- Loading placeholders, retryable errors, useful empty-result actions and an out-of-range page recovery button. Recently viewed items move below results.
- Help me choose and empty-result guidance open the existing assistant with a prepared, editable message carrying the query/category, city, budget and condition. They do not automatically send an AI request.

Search suggestions, real inventory retrieval, favourites/login, pagination, saved searches, existing identity/phone badges and individual seller scores continue to use their existing services. No new product data, fake listings, popularity figures or external prices are added. Nearby remains the existing browser-geolocation feature; this update does not alter server Permissions-Policy or device location permissions.

## Install

Prerequisite: the City Search update is installed. Download `TrustLens_Browse_Update.sh` to Downloads, keep Docker Desktop and your current TrustLens services running, then execute in Git Bash:

```bash
bash "$HOME/Downloads/TrustLens_Browse_Update.sh"
```

After BROWSE UPDATE COMPLETE, open http://localhost:3000/browse and press Ctrl+Shift+R. The installer updates five source/documentation paths and rebuilds/restarts web only. It checks the API, homepage, Browse and assistant-status routes over local HTTP. HTTP success establishes route availability, not complete interactive correctness.

The script checks known source hashes, backs up sources and the running web image, and prints a recovery path under `.git/trustlens-browse-backups/`. Unknown local edits stop preflight. Build/health failures trigger recovery; newer source edits block rollback instead of being overwritten. No key prompt, environment write, database operation, upload change, AI provider call, dependency addition, or API/worker/admin rebuild is included. Existing laptop-only Next/Docker settings and FAQ choices are preserved.

## Verification and limits

Changed-file ESLint and TypeScript checks pass; all 11 Browse URL/price regression tests pass. The production web build passed (36 routes). Installer simulations passed first/repeat installs, web-only build/start, source and prerequisite checks, build/health failure rollback, successful source recovery, protection of newer edits, CRLF and paths with spaces. Environment and FAQ content remained unchanged. Docker was simulated. Production compilation uses `next build --no-lint` with changed-file lint run separately because the source baseline has unrelated settings-page lint errors. No lint-bypass config is shipped.

Interactive desktop/mobile browser verification remains unavailable in this execution environment because Chromium/agent-browser socket creation was denied in the preceding city-search task. This release does not claim new live click or visual checks passed. Windows Docker installation is confirmed only by the user's own installer output.

After installation, review the mobile Filters toggle, a valid/invalid price range, city plus area, both card layouts, sorting from a later page, and no-results recovery. Help me choose should prefill the assistant without sending until you press Send.
