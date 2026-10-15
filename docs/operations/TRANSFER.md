# Moving TrustLens between computers

## Source-only transfer (the default)

Copy the complete ZIP, extract it into a new directory and follow `START_HERE.md`. The launcher builds the same application and starts an independent database. Do not copy `node_modules`, `.venv`, `.next`, temporary logs or Docker build directories. A new installation generates its own private keys. No previous patch installers are needed.

Two independent localhost installations do not automatically share accounts, listings, chats or calls. To let several computers use one platform, deploy one shared server with HTTPS and reachable LiveKit/WSS/TURN instead of giving each user a separate database.

## Keep the old records too

The source package cannot contain records that exist only in your Windows Docker volumes. A complete data migration must move all of these together:

| Data | Why it is needed |
| --- | --- |
| PostgreSQL dump from the existing installation | Accounts, listings, messages, versions, audit and call metadata |
| All MinIO/S3 buckets and objects | Listing photos, verification files, profile media, encrypted voice originals/playback |
| Original security encryption keys, peppers and JWT configuration | Existing encrypted records and security flows depend on them |
| Redis queue state or an explicit drained/reconciled job plan | Avoid silently losing accepted background jobs |
| Calling configuration / VAPID keys if push continuity is required | Keeps media credentials and push subscriptions consistent |
| Source revision and migration head | Reconstructs the application that owns the data |

Copy the private configuration separately over an encrypted/private channel, not inside the ordinary source ZIP. Preserve original data keys; adjust host-specific public/internal URLs deliberately. A database-only copy will leave broken media references.

The included `scripts/chat_backup.sh` exports an encrypted database dump and retained chat-voice objects, verifies object hashes and authenticates the entire dump stream. It is **not an all-bucket / Redis backup**. On the new `trustlens-clean` edition run it with the matching project:

```bash
TRUSTLENS_LOCAL_PROJECT=trustlens-clean bash scripts/chat_backup.sh /path/to/independent-backups
```

For the old installation, run from its actual checkout with its actual Compose project name (usually `trustlens`). Do not point a backup command at a newly created empty installation and mistake that for the original data.

For a complete move, schedule a write pause, stop API/worker writers, take the database dump, export every object bucket, preserve or drain the job queue, and record the matching private configuration. Restart the original installation after its snapshot. Restore only into an empty isolated destination, verify migration head, user/message counts, object hashes, encrypted voice playback and pending-job handling, then switch users over. Rehearse this before replacing the original laptop. Do not drop tables, downgrade retention migrations, or use `down -v` to “fix” a restore.

This release provides the complete source and fresh-machine launcher. It does not include or claim to have performed a full data restore from your physical Windows machine. Existing legacy destructive reset/restore utilities are not part of the recommended migration path.
