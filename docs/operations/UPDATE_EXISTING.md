# Isi laptop ki existing installation update karna

Yeh poora project hai; purani chat/voice patch scripts dobara chalane ki zaroorat nahi. **Existing checkout ke upar ZIP manually overwrite na karein.** Updater source backup, build aur encrypted database backup sambhalta hai.

1. Docker Desktop start karein aur apna purana TrustLens stack running rakhein. API, worker, web aur admin running hon.
2. Nayi ZIP alag folder, misaal `C:\Projects\TrustLens-Final`, mein extract karein.
3. Extracted **TrustLens** folder mein Git Bash kholein. Apne pehle logs wale path ke liye:

```bash
bash scripts/local/update-existing.sh "$HOME/Documents/TrustLens" trustlens
```

Agar purana folder/project name alag hai to woh path/name dein. Updater container ke Compose file label ko target folder se match karta hai; kisi doosray checkout ko update nahi karta.

4. `UPDATE COMPLETE` ke baad http://localhost:3000 par Ctrl+Shift+R karein. Phir original `Documents/TrustLens` folder se:

```bash
bash scripts/local/doctor.sh --wait
```

Accounts, listings, chat, voice, `.env.production`, encryption/API/media keys aur Docker volumes preserve hote hain. Naye accounts/demo data automatically seed nahi hota. Source aur encrypted DB snapshot original checkout ki `.trustlens-update-backups/<timestamp>` directory mein milta hai. Keys ka alag secure backup bhi rakhein.

## Update ke andar kya hota hai

Purani `API_PORT=127.0.0.1:8000` jaisi settings ab automatically numeric port mein
convert hoti hain, kyun ke naya Compose bind IP alag add karta hai. Loopback
protection, custom ports aur explicit common bind address preserve hote hain;
conflicting interfaces par updater mutation se pehle rukta hai. Sirf six public
port settings ka format badalta hai; secrets, URLs aur baqi settings ke bytes
unchanged rehte hain. Original env ka private backup `private-config/.env.production`
mein save hota hai aur rollback par restore hota hai.

Windows ke slow Docker bind mounts par verification, backup aur copying ke
counters har 100 files ke baad print hote hain. Source stage mein database
migration ya service restart nahi hota.

- Release checksum verification aur managed-source backup.
- API, worker, web aur admin builds jab purana app chal raha hota hai.
- Builds pass hon to API/worker stop, PostgreSQL dump, authenticated encryption aur full-byte verification.
- Migrations/reference data, updated services, readiness check.
- Build failure par source/images restore; pehle se chalti services stop nahi hotin. Later failure par previous app images/source restore karke restart ki koshish hoti hai. Rollback ka output zaroor dekhein; script rollback success ka andaza laga kar `OK` nahi likhta.

Database downgrade/reset aur volume deletion update ka hissa nahi. Migrations ki additive changes rollback par retain ho sakti hain. Agar setup interrupt ho, pehle backup/log dekhein; database reset karke retry na karein. Update ke final phase mein brief downtime hota hai, aur in-progress calls end ho sakti hain.

Windows Docker execution is build environment mein available nahi thi. Launcher contract tests pass hain; actual laptop engine check aur two-way microphone test apne computer par complete karein.

## Baad mein

Original folder se `START_LOCAL.bat` / `STOP_LOCAL.bat` use karein. Successful update project name save karta hai, is liye start command existing `trustlens` volumes use karega. Purana project stop kiye baghair fresh `trustlens-clean` installation ko same ports par start na karein.

Doosray laptop par **fresh** setup ke liye extracted folder mein `START_LOCAL.bat` chalayein. Fresh laptop ki database alag hogi. Purana data bhi move karna ho to `TRANSFER.md` follow karein; aam source ZIP mein private environment ya database shamil na karein.
