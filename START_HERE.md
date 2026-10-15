# TrustLens isi aur doosray laptop par chalana

Yeh **complete project source** hai. Purani V1/V2/V3 patch files dobara laganay ki zaroorat nahi.

## Isi laptop par pehle se TrustLens installed hai

ZIP alag folder mein extract karein. Naye extracted **TrustLens** folder ke Git Bash mein:

```bash
bash scripts/local/update-existing.sh "$HOME/Documents/TrustLens" trustlens
```

Purana Docker stack running rakhein. Yeh existing project update karta hai aur uske data/keys/volumes preserve karta hai. Detail aur failure recovery: [UPDATE_EXISTING.md](docs/operations/UPDATE_EXISTING.md). **Neeche fresh setup doosray/new laptop ke liye hai.**

Security changes aur exact passing/pending checks: [SECURITY_FIX_REPORT.md](docs/development/SECURITY_FIX_REPORT.md).

## Kya chahiye?

- Docker Desktop running ho; Windows par WSL 2 aur virtualization enabled ho, Linux containers select hon.
- Git for Windows, jis ke sath Git Bash aur OpenSSL milte hain.
- Pehli build ke liye internet: container images, packages, fonts aur worker ke model weights download hotay hain.
- Is stack ke liye **16 GB RAM, 4 CPU cores aur 30 GB free SSD space recommended** hain. Yeh practical recommendation hai, measured minimum guarantee nahi. Docker ko kafi RAM dein; kam memory par build fail ho sakti hai.
- Current Chrome/Edge/Firefox/Safari. Voice test ke liye microphone/headphones.

Docker route par host mein Node, Python, PostgreSQL, Redis, MinIO ya LiveKit alag install karna zaroori nahi. Sab containers mein aata hai. Core local chat/calls ke liye paid API key nahi chahiye. AI demo mode enabled hai; iska result real identity verification ka proof nahi.

Official installers: [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) · [Git for Windows](https://git-scm.com/downloads/win).

## Pehli dafa

1. ZIP ko `C:\Projects\TrustLens` jaisi **nayi directory** mein extract karein. Purani working directory ke upar overwrite na karein.
2. Docker Desktop khol kar engine ready hone dein.
3. Agar isi laptop par purana TrustLens chal raha hai to usay uske normal stop command se stop karein; dono default ports use karte hain. Uska data/delete/reset command mat chalayein.
4. `START_LOCAL.bat` double-click karein. Agar Windows `bash` ke liye WSL khol raha ho, Git Bash mein project folder khol kar neeche command chalayein:

```bash
bash scripts/local/start.sh
```

5. `TRUSTLENS READY` ke baad http://localhost:3000 kholein. Admin http://localhost:3001, email links/verification http://localhost:8025 par hain.
6. Apna account register karein; email verification link aur local phone OTP preview Mailpit mein milega. Local preview real phone-number ownership verify nahi karta; public use ke liye actual SMS provider chahiye. Sample accounts chahiye hon to **sirf demo database par**:

```bash
bash scripts/local/demo.sh
```

Sample admin/seller/buyer logins `CREDENTIALS.dev.md` mein hain. Demo seed real verification evidence ka replacement nahi; chat ke profile/verification gates alag apply hote hain.

First build connection aur laptop ke mutabiq waqt leti hai. Build output ke aakhri wrapper error se pehle jo actual error ho woh dekhein. Fail ho to issue resolve karke **same command** rerun karein; completed Docker layers reuse hongi. Existing `.env.production` aur keys regenerate nahi hotin.

## Rozana commands

| Kaam | Command / file |
| --- | --- |
| Start / rebuild | `START_LOCAL.bat` / `bash scripts/local/start.sh` |
| Stop, data retain | `STOP_LOCAL.bat` / `bash scripts/local/stop.sh` |
| Health check | `CHECK_LOCAL.bat` / `bash scripts/local/doctor.sh` |
| Logs | `bash scripts/local/logs.sh` |

Start script `trustlens-clean` project aur images use karta hai. `.env.production` private hai. Isay delete karna keys rotate kar sakta hai aur purana encrypted data unreadable ho sakta hai. ZIP share karein; apni generated private configuration public share na karein.

## Voice aur calls

- Same computer par do eligible accounts alag browsers mein use karein.
- Dono microphones allow karein. Call accept, two-way audio, microphone mute, received sound, device selection, minimize aur end check karein.
- Supported browsers mein speaker/headset selection aati hai; mobile OS/browser apni routing control kar sakta hai.
- Local config same-machine calling ke liye hai. **Laptop A ka localhost, laptop B ka localhost nahi hota.** Har fresh installation ki database alag hogi.
- Ek common platform par multiple laptops/phones chalane ke liye shared server, HTTPS, reachable WSS/LiveKit aur TURN/firewall configuration chahiye. Sirf localhost ko LAN IP mein badalna microphone/calling ke liye kaafi nahi.
- Browser poora band ho to native phone call jaisi guaranteed ringing nahi. Web Push optional hai; real VAPID contact ki configuration `docs/operations/voice-calls.md` mein hai.

## Agar setup ruk jaye

| Problem | Kya karein |
| --- | --- |
| Docker engine unavailable | Docker Desktop start karein; WSL 2 / Linux containers check karein |
| Port in use | Old stack ko normal stop karein; deletion ki zaroorat nahi |
| Download / font / model error | Internet, DNS/proxy check karke rerun karein |
| Build killed / out of memory | Docker RAM/disk allocation barhayein; other heavy applications band karein |
| Migration / readiness failure | `bash scripts/local/logs.sh`; database reset na karein |
| Setup already running | Running setup finish hone dein. Agar process waqai band ho chuka hai, empty `.trustlens-setup-lock` directory hata kar rerun karein |
| Microphone unavailable | Permission, browser support aur localhost/HTTPS check karein |

Actual Docker Desktop installation aur real-device two-way audio is release environment mein execute nahi ho sake. Automated source/build/migration/UI checks ki exact list `docs/development/REFACTOR_REPORT.md` mein hai.

Purana data bhi transfer karna ho to [TRANSFER.md](docs/operations/TRANSFER.md) parhein. Source ZIP mein aapke Windows laptop ki database ya uploads nahi hain.
