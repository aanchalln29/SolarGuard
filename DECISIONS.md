# SolarGuard — Approved Architecture Decisions

**Project owners:** Tanushree Burde and Aanchal Nasre  
**Date:** 2026-10-17  
**Status:** Approved scope baseline; detailed SRS and dataset feasibility pending

## Approved decisions

1. **Maintenance intelligence:** Use a transparent, rules-based maintenance priority system. Do not present the existing synthetic Random Forest output as measured degradation or validated degradation forecasting. Do not invent sensor readings.
2. **Image classification:** Investigate four baseline categories: Normal, Dusty, Bird-Dropping, and Cracked / Surface Damage (provisional name). Provide an Unable to assess / Retake photo outcome. The exact damage label and quality/uncertainty thresholds remain subject to data audit and evaluation; never automatically relabel all Physical Damage images as Cracked.
3. **Audience:** Support individual solar owners and professional teams in one platform, with appropriately simplified versus detailed workflows and enforced ownership/access controls.
4. **Maintenance workflow:** Support issues with Open, In Progress, and Resolved states, maintenance action history, and optional follow-up inspections. A detected condition should not automatically be treated as verified physical damage.
5. **Training:** Develop and run real-image model experiments in Google Colab when suitable GPU resources are available; export model, class mapping, preprocessing metadata, and evaluation reports. Use local CPU inference initially if benchmarking supports it.
6. **Brand:** Follow `BRAND_GUIDELINES.md` for SolarGuard UI and content, subject to accessibility and usability testing.

## Grounding in current MVP audit

Antigravity's audit reports a working Django/SQLite prototype with login, uploads, inspection reports, dashboard, and three passing tests. It also reports synthetic-image training, a missing CNN artifact, synthetic tabular degradation output, no cross-user data isolation, and insecure development settings. Treat these as reported findings to verify before changing code.

## Decisions deliberately deferred

- Actual dataset license, provenance, image-level labels, duplicates, class counts and split strategy.
- Whether the fourth class is specifically Cracked or broader Visible Surface Damage.
- Final model architecture, image resolution, confidence thresholds, out-of-distribution handling, and quality benchmarks.
- Exact owner/professional onboarding, site/panel association, team permissions, and whether quick inspection requires registration.
- Transparent maintenance priority rule inputs, weights, exceptions, and wording.
- Model artifact distribution, hosting, storage retention, and deployment provider.

## Implementation guardrails

- Preserve the existing MVP and create a backup/branch before modifications.
- Do not present synthetic predictions as validated real-image AI. Mark mocks clearly.
- Do not silently fall back from missing real model to synthetic classifier.
- Enforce server-side object ownership; do not rely on a UI toggle for authorization.
- Validate uploads by content, size, and decoding, not just filename.
- Move secrets to environment variables; production must disable DEBUG and restrict ALLOWED_HOSTS.
- Avoid committing raw datasets, secrets, or large model artifacts to Git.
- Work in reviewable milestones, run tests, and wait for owner approval at each gate.

## Next gate

Prepare `docs/REVISED_SRS_DRAFT.md`, `docs/DATA_AUDIT_PLAN.md`, and `docs/IMPLEMENTATION_PLAN.md` **without changing application code**. The draft SRS must distinguish approved decisions from unresolved requirements. The dataset plan must include exact license/provenance verification, per-class file counts, representative samples, duplicate detection, physical-damage label review, group-aware train/validation/test splits, and independent real-world evaluation. Await project-owner review before implementation.
