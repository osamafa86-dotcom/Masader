# Marsad Phase 2 (Research Depth) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the MVP into a research tool: academic journals as abstract-based summaries with issue tables of contents, robust PDF reports and manual import, semantic search and related items, author pages, three citation formats, a reviewed weekly newsletter with topic/keyword alerts, and frequency-ranked glossary proposals.

**Architecture:** Same two apps. New engine modules: `marsad/journals.py`, `marsad/embed.py`, `marsad/citations.py`, `marsad/newsletter/`. pgvector stores one embedding per document. Email goes out through SMTP (any provider), sent by the worker in batches after an editor approves a digest draft.

**Tech Stack:** Phase 1 stack + pgvector (Postgres extension and `pgvector` Python package), Voyage AI embeddings over HTTP (`voyage-3.5`, 1024 dims), stdlib `smtplib`.

**Spec:** `docs/strategy-plan-ar.md` section 8, "المرحلة 2"; sections 2 (journal rows 6, 11, 12, 17, 18), 5.5, 7.

## Global Constraints

- Journal sources use `content_mode: abstract`: the article page is never downloaded; the summary is built from the feed abstract only and must not claim anything the abstract does not state.
- An item-level licence (e.g. an open-access article under CC BY) can raise one document to `full`, only with recorded evidence, and only an editor can set it.
- Embeddings: provider `voyage` (needs `VOYAGE_API_KEY`) or `fake` (tests/demo). If no provider is configured, everything falls back to keyword search and tag-based related items; nothing breaks.
- Newsletter: double opt-in; every email has a one-click unsubscribe link and `List-Unsubscribe` header; no digest is sent without an editor pressing "send"; a subscriber with topic/source/keyword preferences receives only matching items and no email if nothing matches.
- Subscriber emails are personal data: never shown in public API responses, never logged in full.
- Rights rules from phase 1 still apply everywhere, including the newsletter (summary-level items link out; no body text in email).

## Review Focus

1. A journal feed item whose description is only "Volume 41, Issue 6, Page 1-25" (no abstract) → not summarised; marked failed with a clear reason instead of an invented summary.
2. Same subscriber submits the form twice, or confirms twice → one row, idempotent, no second confirmation storm.
3. Unsubscribe token from one subscriber cannot unsubscribe another; unknown token → 404.
4. Embedding provider down or key missing → document still publishes; search and related items still return results.
5. Two-column PDF with footnotes → paragraphs come out in reading order without footnote text mixed in.

---

### Task 1: Schema
`documents.meta` (journal, volume, issue, pages, doi, open_access), `documents.item_license`, `documents.item_rights_evidence`, `sources.content_mode`, `authors`, `document_authors`, `doc_embeddings(document_id, model, vector(1024))`, `glossary_terms.proposal_count`, `glossary_terms.example_document_id`, `subscribers`, `digests`, `digest_deliveries`. Migration creates extension `vector`.

### Task 2: Journals
Feed metadata (prism:volume/number/startingPage, dc:identifier DOI, "Open Access" markers) → `Entry.meta`; abstract-only pipeline path; abstract-only prompt flag; Review Focus 1; item licence override endpoint; issue TOC API `GET /api/sources/{slug}/issues` and `GET /api/sources/{slug}/issues/{volume}/{issue}`; activate journal and remaining RSS sources in seed (Janes stays off).

### Task 3: PDF and manual import
`citation_pdf_url` / "download PDF" link following for short HTML pages; column-aware block ordering and footnote removal by font size (Review Focus 5); `POST /api/editor/import {url, source_slug}`.

### Task 4: Authors and citations
Author rows from document authors (slug from name), `GET /api/authors/{slug}`; citations of the original (APA 7, Chicago author-date, BibTeX) and of the Arabic translation.

### Task 5: Embeddings
`Embedder` protocol, `VoyageEmbedder`, `FakeEmbedder`; embed on publish (and backfill CLI); hybrid search (FTS + vector, reciprocal rank fusion) behind `mode=semantic`; `GET /api/articles/{id}/related` (vector, fallback tag overlap); Review Focus 4.

### Task 6: Newsletter and alerts
Subscribe (double opt-in), confirm, preferences, unsubscribe; SMTP mailer + fake mailer; weekly digest draft auto-created by worker; editor edits intro, removes items, sends; worker delivers per-subscriber filtered emails in batches; Review Focus 2, 3.

### Task 7: Glossary proposals
`proposal_count`, `example_document_id`; editor list sorted by frequency.

### Task 8: Web
Journal pages with issue TOCs; author pages; citation box with copy buttons; semantic search toggle; related items; subscribe form + confirm/unsubscribe/preferences pages; editor: import form, licence override, digest review/send, proposals with counts.

### Task 9: Ops and docs
pgvector Postgres image in compose; new env vars; README; e2e additions.
