# Marsad Phase 3 (Platform) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open Marsad to institutions and power users: a versioned public API with keys and rate limits, editor-curated thematic dossiers, monthly trend reports, sources in French/Russian/Hebrew/Chinese, and reader accounts with a saved library and alerts.

**Architecture:** `/v1` is a separate FastAPI sub-application (own OpenAPI docs) sharing the engine's database and rights serializers; Caddy exposes it next to the website. Rate limits use a per-minute counter row in Postgres, so they hold across processes. Trend statistics are computed from tags and keywords; the monthly narrative is drafted by the model from those numbers only and published by an editor. Reader accounts use passwordless email links through the existing mailer.

**Tech Stack:** Phase 2 stack. No new services.

**Spec:** `docs/strategy-plan-ar.md` section 8, "المرحلة 3".

## Global Constraints

- The public API applies exactly the same rights rules as the website: body text only for `full` items, never for summary-level items.
- API keys are shown once at creation and stored only as SHA-256 hashes; revoked keys stop working immediately.
- Default rate limit 60 requests/minute per key (configurable per client); `429` with `Retry-After` when exceeded.
- Model-drafted text (dossier introductions, trend narratives) is always a draft that an editor must publish; trend narratives may only use the numbers they are given.
- Non-English sources keep the original-language text and are translated directly into Arabic (no pivot through English); Arabic-language sources are summarised but not translated.
- Reader accounts hold the minimum: email, saved items, alert preferences. A reader can delete the account and all its data at once.

## Review Focus

1. Revoked or unknown API key → 401; correct key over the limit → 429 with Retry-After; limits counted across processes.
2. A summary-level item fetched through `/v1` never includes body text.
3. Trend report for a month with no data → an explicit empty state, not a division-by-zero or an invented narrative.
4. Hebrew source shown in the parallel view → original column right-to-left; French/Russian left-to-right.
5. A magic-link token used twice, expired, or belonging to someone else → refused.

### Task 1: Schema
### Task 2: Public API v1, keys, rate limits, admin endpoints
### Task 3: Dossiers with suggestions and model-drafted introductions
### Task 4: Trend statistics and monthly reports
### Task 5: Multi-language sources and per-language glossary
### Task 6: Reader accounts (magic link, library, alerts, deletion)
### Task 7: Web: developers page, dossiers, trends, account, editor tools
### Task 8: Ops (Caddy /v1 route), README, e2e
