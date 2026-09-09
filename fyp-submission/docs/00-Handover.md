# Handover Note

**TrustLens — FYP Documentation Package**
For: Haseeb Ur Rehman (2022F-mulbsswe-043) and Muhammad Muttayab (2022F-mulbsswe-012)
Prepared by: Zohaib Khan (contracted developer) · 2026-08-31

This package documents TrustLens as it actually exists today, for your 8th-semester FYP submission
to Mam Misbha and the FYP evaluation committee at the School of Software Engineering, Minhaj
University Lahore. Read this note first — it's the only file in the package meant to be read in full
in one sitting; everything else you'll dip into as needed.

## What's inside

| File / folder         | What it's for                                                                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `01-Simple-Guide.md`  | Plain-language explanation of the whole project, plus 15 likely viva questions with honest answers. **Read this together before your viva**, even if you skip everything else |
| `02-Index.md`         | This folder's own table of contents, reading paths, and the screenshot gallery                                                                                                |
| `03-SRS.md`           | Software Requirements Specification (IEEE 830) — what the system must do                                                                                                      |
| `04-SDD.md`           | Software Design Document (IEEE 1016) — how it's built, with 20+ diagrams                                                                                                      |
| `05-Test-Cases.md`    | Test Documentation (IEEE 829) — what was actually tested vs. only planned, and the real defect log                                                                            |
| `06-User-Manual.md`   | How to use the finished product, with real screenshots                                                                                                                        |
| `07-Thesis.md`        | The full thesis manuscript — front matter, 8 chapters, references, appendices                                                                                                 |
| `screenshots/`        | The real captured screenshots used throughout the package                                                                                                                     |
| `diagrams/`           | Rendered PNG versions of every Mermaid diagram (used inside the Word thesis)                                                                                                  |
| `pdf/`                | Page-numbered PDF edition of every document above, for reading and printing                                                                                                   |
| `Project_Thesis.docx` | **The actual submission copy** — a bound Word document (A4, Times New Roman, binding margin, roman-then-arabic pagination)                                                    |

## Do these things before you submit

1. **Open `Project_Thesis.docx` in Word, click into the Table of Contents, and press F9 → "Update
   entire table."** No script can compute real page numbers — that only happens inside Word, once,
   by you.
2. **Read `05-Test-Cases.md`'s banner at the very top before you write or say anything about testing
   in your report or viva.** It states plainly how many test cases were actually executed vs. only
   specified. Do not round that number up.
3. **Sign the certificate-of-approval and declaration pages** in the thesis front matter — they have
   real signature-line blocks, left blank intentionally.
4. **Check your institution's exact required wording** on the certificate/declaration pages against
   what's here — this was written from the standard FYP submission form, not a copy of a signed
   institutional template.
5. **Read `05-Test-Cases.md` §6, the defect log, in full.** Two of the fifteen logged defects are
   still open (MFA is unimplemented; the admin panel is incomplete) — know these before a panel
   member finds them for you.
6. **Rehearse `01-Simple-Guide.md` §9's viva questions out loud**, especially the ones about the scam
   classifier's real accuracy and the fact that nothing is deployed publicly yet. Panels ask the
   uncomfortable question; a fluent honest answer defends better than a confident evasive one.

## Do NOT do these things

- **Do not hand-edit any generated file** (`docs/pdf/*.pdf`, `docs/diagrams/*.png`) — they're
  regenerated from the Markdown sources. Edit the `.md` file and rebuild.
- **Do not submit the browser-print PDF of the thesis.** `pdf/07-Thesis.pdf` is a reading/email
  convenience copy. The actual submission copy is `Project_Thesis.docx`, exported to PDF from Word
  _after_ you've updated the Table of Contents.
- **Do not present "51 test cases specified" as "51 test cases passed."** They are different numbers,
  stated separately on purpose in `05-Test-Cases.md`.
- **Do not claim the system is deployed publicly.** It is not, as of this document. Say so plainly if
  asked — the deployment plan is designed and partly rehearsed, not live.
- **Do not claim validated real-world OCR/face-match accuracy.** No consented real CNIC/selfie test
  set has been collected yet — that's still an open item, and it's yours to close (see below).

## Honest status, without spin

The software is genuinely built and working end-to-end for the core journey: a seller can register,
verify email, sign in, complete identity/phone/email/device checks, see an explainable Trust Score
with a full breakdown, appeal it, have a reviewer decide, and see it recompute. A buyer can look up
that score with no account. The engineering is solid — 330 automated tests pass, static analysis is
clean, and the codebase follows a deliberately layered, testable architecture. Two real gaps remain
open and are documented plainly rather than hidden: the admin panel is functionally incomplete
(only the review queue and scoring-model tuning work end-to-end), and MFA for staff accounts is
designed but not implemented. We have **not** independently validated OCR/face-match accuracy
against real documents, and the custom scam classifier is measurably weak on real target-domain text
(1 of 7 real scam ads caught in a manual check) — which is exactly why it is not yet wired into live
scoring. None of this was hidden while writing this package; all of it is written up in
`05-Test-Cases.md` and the SDD's honest-limitations sections, because a report that states its real
gaps plainly is more credible to a supervisor than one that doesn't have any.

**One more thing found live while building this package, worth knowing before your viva:** simply
signing in and browsing between the three demo seller accounts silently overwrites their intended
LOW/MEDIUM/HIGH score spread with a uniform capped HIGH score, because a routine device-fingerprint
check triggers a real score recomputation and the demo seed never stored a selfie file for any of
them. It's logged as DEF-14 in `05-Test-Cases.md` §6 and is not yet fixed — **rehearse your demo
account switching carefully**, or you may find all three sellers showing the same score live in
front of the panel. The scores were restored for this package's own screenshots; they will corrupt
again the next time someone clicks through all three accounts unless DEF-14 is actually fixed.

**What's still yours to do, per `REMAINING.md` Track D in the project root:** collect the real CNIC
and face test images (this is explicitly a student task, not an engineering one — see `REMAINING.md`
Stage 1), rehearse the architecture walkthrough and viva defence, and write and present the final
deck. This documentation package supplies the technical content, diagrams, and measured numbers for
your report; you write and defend it, because you're the ones at the viva.
