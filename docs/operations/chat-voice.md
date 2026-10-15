> Complete organized edition: use `START_HERE.md` / `scripts/local/start.sh` for a fresh laptop. Patch-installer commands below describe earlier incremental releases. The complete package already contains chat, recorded voice, calls and call controls.

# Chat and recorded voice — release v1

## Participant rules

- Text edit and delete for everyone expire 60 seconds after server acceptance. Edits do not reset that deadline. Audio cannot be edited after sending.
- Delete for everyone hides text/audio from both participants; original records remain retained. Copies already seen, heard, downloaded or captured cannot be recalled.
- Clear whole chat affects only the requesting participant, across devices. It has a server-enforced ten-second Undo. Cleared history stays hidden; later messages appear normally.
- Existing conversations stay writable for 72 hours after a listing becomes sold/inactive. Inactive-to-inactive transitions do not reset the deadline. Reactivating a listing reopens chat. New conversations require an active public listing.
- After closure, messages remain readable, audio remains playable, and support reporting remains available. The header shows the closing time and a reminder during the last 24 hours. This reminder is in the chat interface, not an external email/SMS notification.
- Recording: hold/release or tap for hands-free, slide left to cancel, slide up to lock, pause/resume, preview/discard/re-record, upload progress/retry. Maximum five minutes and 12 MB. There is no view-once option.
- Playback: waveform, seek, 1×/1.5×/2×, remembered position during the current tab session, sequential playback of loaded voice messages, persistent player across client-side navigation, reply, forward, and separate played/read status.
- A hard reload or closing the tab ends in-memory recording/playback. Full native-app earpiece/proximity behavior is not implemented in the browser.

## Retained data and staff access

Original message fields, edits, voice metadata, audit entries and support links are protected by database triggers against update/delete as appropriate. The application does not expire chat records. This protects ordinary application operations, not a database superuser who deliberately disables triggers or drops storage.

Voices have a private original object and an AAC playback object. Both are encrypted with the existing application encryption key and use per-message authenticated encryption. They are outside the identity-media purge job. Participant audio endpoints check membership, per-user clearing and deletion/moderation before returning bytes. Storage keys and historical versions are never returned by participant endpoints.

New-message notifications contain generic text, not copies of private messages. Inbox previews and reply quotes reflect edits/deletions and the requesting user's clear cutoff.

Support cases appear in the existing admin Reports queue. `moderation:read` is required to inspect retained records/audio; `moderation:resolve` is required to hide a message from users. These accesses and actions are recorded. Support hiding preserves originals.

## Install and migration

Run the supplied self-contained installer from Git Bash with the existing local stack running. It checks patch compatibility, preserves source and image references, builds overlays on the installed API/worker images, builds web/admin, pauses writes briefly, takes an encrypted database backup, applies migration `202610132130`, and checks readiness/authentication.

The API image needs FFmpeg. The layer installer installs it if missing; the full source Dockerfile also includes it. No paid voice API is required for recorded messages. The web document permits same-origin microphone use; browsers still require permission and HTTPS, except localhost.

Historical inactive listings receive a new 72-hour grace at migration, because the old schema did not record reliable status-change times. Subsequent transitions use database timestamps.

Rollback retains the additive migration/schema. The recovery script refuses to run the old API after retained-chat activity exists, because old code could expose original messages. In that case repair forward; do not downgrade or delete the data tables.

## Backups, monitoring and restore

From the checkout, with the stack running:

```bash
bash scripts/chat_backup.sh /path/to/independent-backups
```

The backup includes an encrypted PostgreSQL custom dump, encrypted chat rows, encrypted original/playback voice files, and an authenticated checksum manifest. The script verifies archive contents and that the database dump can be listed. Copy the result to a separate disk or host. Keep all current/previous encryption keys separately; database/audio backups alone cannot replace a lost key.

Use the host scheduler to run this nightly and alert on nonzero exit. Scheduling and remote storage must be configured on the actual live server; this package does not claim that they are already running.

Monitor voice growth using the existing compose environment:

```bash
docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production exec -T api python -m trustlens_api.modules.messaging.archive status --warn-bytes 10737418240
```

The command returns exit code 2 at the threshold. The metric counts original audio bytes; budget additional space for playback copies, encryption, database indexes, versions and independent backups. Configure actual disk alerts as well. Do not configure expiration/lifecycle deletion for the `chat-voice/` prefix.

Before going live, rehearse a restore into an EMPTY disposable deployment with the same encryption keys. Use `chat_archive decrypt` to pipe the database dump to `pg_restore` on that empty database, then copy the archive into the API container and run `chat_archive verify` followed by `chat_archive restore-objects`. Object restore adds missing objects and refuses to overwrite different existing bytes. Verify user counts, message counts, edited/deleted/cleared views, and original/playback audio checksums. Never test a restore over the working database.

For migration to the live server, stop writes or perform a final synchronized transfer; move database, object storage and keys; verify HTTPS/microphone, two-account messaging, private audio access, and backups before switching traffic. Enable encrypted disks/database storage, TLS and independent backup storage at the host/provider layer. Those infrastructure controls cannot be activated without access to that server.

## Scope

This release adds recorded voice messages and the agreed retention policy. Live in-platform calling requires a separate calling/signalling/TURN setup and is not part of this release.
