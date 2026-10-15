# TrustLens — supplied Browse reference

This update implements the user's `02_marketplace_search(1).png` as the visual reference. It does not introduce an alternative design. It follows the reference's desktop hierarchy and proportions: white/teal/navy navigation, upper query/location search, breadcrumb and location heading, compact left filters, applied chips inside the bordered results panel, grid/list and sort controls, landscape images, price before title, seller/check/message/trust row, and centred pagination. Browse displays six actual listings per page, three per row on wide screens. It adapts to two and then one column on smaller screens; mobile filters remain collapsible.

## Install

After the previous Browse v1 update has completed, save the new installer in Downloads and run in Git Bash:

```bash
bash "$HOME/Downloads/TrustLens_Browse_Design_Update.sh"
```

Wait for `BROWSE DESIGN UPDATE COMPLETE`, then open http://localhost:3000/browse and hard refresh with Ctrl+Shift+R. The light theme corresponds to the supplied image. On desktop, language/theme controls for Browse are available at the bottom of the Categories menu; the existing mobile controls remain. Signed-in navigation continues to show the real session's actions.

The installer backs up the actual source and currently running web image under `.git/trustlens-browse-design-backups/<stamp>/`. It reports the exact recovery script path. Unknown edits stop before source changes. A failed build/health check invokes recovery. Repeat installs with unchanged source skip the rebuild. Recovery also refuses to overwrite newer edits.

Seven paths are packaged: the Browse page, two local components, its stylesheet, SiteNav and its Browse-specific stylesheet, and this document. Only web is built/restarted. API keys/settings, approved FAQs, database/uploads, verification flags, dependency versions, Next configuration, API, worker and admin are not updated. No model/search provider requests are made by this installer.

## Data and working controls

The reference's sample images, prices, seller handles, 1,248 count and trust scores are not fabricated into live results. The card uses actual listing data and real seller verification flags. Identity and phone icons are verification indicators; the envelope opens the existing seller-message flow. Unknown scores show Not scored, and low scores retain their risk colour. Sold/reserved states remain visible. Favourites use the existing authenticated flow; listing photos/titles and seller handles have separate accessible links.

Top location selection provides province → searchable city → area. Choosing a new location clears stale nearby coordinates. Existing smart query/category suggestions, URL filters, price validation, sorting, back/forward synchronisation, saved searches, recently viewed, assistant, loading/retry/empty states and grid/list remain. Less-common For parts filtering and saved/recent utilities are accessible below the primary results. Nearby radius depends on a successful browser geolocation request; the existing laptop Next Permissions-Policy is not changed by this design patch.

## Verification

Changed TSX files are linted and TypeScript checked; existing Browse URL/price tests run. The production Next build is checked separately from inherited lint errors elsewhere in the baseline. The shipped package adds no lint bypass. Installer simulation covers first/repeat installation, web-only service scope, unknown-source/prerequisite rejection, build/health failure recovery, rollback with newer-edit protection, CRLF and paths with spaces, and unchanged environment/FAQ bytes.

Visual limitation: the local browser runtime cannot launch in this environment, and the cloud browser cannot access the user's localhost. Therefore no live laptop screenshot comparison or pixel-difference check is claimed. The layout is implemented from the supplied reference; final rendered alignment should be assessed on the user's browser at the intended viewport. Actual inventory, logged-in state, fonts and viewport affect what is displayed.
