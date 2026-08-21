## What

## Why

## How

## Testing

- [ ] Unit tests added or updated
- [ ] Integration tests where I/O or SQL changed
- [ ] Verified manually against a running stack

## Checklist

- [ ] Migration reviewed line by line, and `downgrade()` works (if schema changed)
- [ ] `make codegen` run (if the API contract changed)
- [ ] Docs updated (if behaviour or architecture changed)
- [ ] New env vars added to `.env.example` **and** `docs/12`
- [ ] No secrets, no PII, no real CNIC images committed
- [ ] `make ci` passes locally

## Extra scrutiny required?

- [ ] Touches CNIC / selfie / biometric data → security review against `docs/15`
- [ ] Changes scoring weights or thresholds → simulation output attached
- [ ] Adds a public API field → confirmed PII-free and non-breaking
