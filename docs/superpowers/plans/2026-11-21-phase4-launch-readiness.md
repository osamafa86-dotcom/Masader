# Marsad Phase 4 (Launch Readiness) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every gap listed after Phase 3 so the platform can launch: measured translation quality, lower cost, hardened security, monitoring and alerts, editorial sampling and assignment, privacy-respecting readership counts, legal pages, verified backups, verified images, load and accessibility checks.

**Spec:** `docs/strategy-plan-ar.md` sections 5.2 (batches), 5.5 (golden set, sampling), 9 (monitoring), 10 (risks); the post-Phase-3 gap list.

## Global Constraints

- Brand shown to readers defaults to «مصادر» (the repository name); configurable with `MARSAD_SITE_NAME` / `NEXT_PUBLIC_SITE_NAME`. Internal package names stay `marsad`.
- Golden-set evaluation never publishes anything and records cost per run.
- Batch translation only for items that are not urgent (importance at or below `BATCH_MAX_IMPORTANCE`, default 3); results go through the same QA and review routing as synchronous ones.
- Editor accounts: 5 failed logins in 15 minutes lock that email (and that client address) for 15 minutes; TOTP two-factor available to every editor and enforceable for all with `REQUIRE_EDITOR_2FA`.
- Public forms (subscribe, account login, feedback, view beacon) limited per client address.
- Readership counts store no IP, no cookie, no user agent: only (document, day, count).
- Alerts are emailed to `ALERT_EMAILS`, each alert key at most once per 12 hours.

## Review Focus

1. Locked-out email still locked even with a correct password until the window passes.
2. A wrong or replayed TOTP code (same 30-second step used twice) is refused.
3. Batch result missing a paragraph → retried synchronously, never published incomplete.
4. Worker silent for over 10 minutes → `/api/health?strict=1` returns 503.
5. Bot user agents do not inflate readership counts.

### Task 1: Brand name
### Task 2: Golden-set evaluation (`marsad eval`)
### Task 3: Batch translation via Message Batches
### Task 4: Security hardening
### Task 5: Monitoring and alerts
### Task 6: Editorial sampling and assignment
### Task 7: Readership counts and "most read"
### Task 8: Legal pages
### Task 9: Ops verification (restore, images, load, accessibility)
### Task 10: Docs
