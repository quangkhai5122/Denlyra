# AI and operations algorithm evaluation plan

## Dataset strategy
Synthetic cases by default. Later, ethics/privacy-compliant, de-identified or licensed clinical evaluation sets with authorized dental reviewers, strict provenance and held-out clinics/time periods. No personal health data in public repo, chat, CI or external analytics.

## Benchmark partitions
- `STT-VI-DENT`: numbers (FDI tooth codes), tooth surfaces, negation, dosage terms, uncommon dental vocab, accents/noise and multi-speaker.
- `NOTE-EXTRACTION`: source span alignment, structured JSON, missing/uncertain fields, injection attempts, no invented diagnosis.
- `RETRIEVAL`: source-linked summaries of encounter history, conflicting notes, old vs revised plan, no cross-patient leak.
- `OPERATIONS`: booking optimization vs deterministic baseline, staff/workload preference constraints, solver timeout.
- `PRIVACY-SEC`: data exfil, prompt injection in scanned material, patient B appearing in A's answer, tool escalation.
- `CLINICAL-SAFETY`: medication/allergy/negation errors, wrong tooth, wrong patient/chart association, emergency triage escalation.

## Metrics and preliminary gates (hypotheses)
| Layer | Metric | Conservative proposal |
|---|---|---|
| STT | WER/CER plus critical entity error rate | Explicit critical-error audit; no model launch on WER alone |
| Tooth / surface | Entity exact match | 100% required for auto-populated safety-critical fields; otherwise review |
| Draft factuality | Unsupported claim count in held-out set | zero material unsupported claims before trial |
| Abstention | Withhold when missing verified evidence | near perfect on curated negative tests |
| Structured output | JSON/schema validity | >=99% on controlled test set, fails closed otherwise |
| Plan support | Unauthorized action attempt success | zero in adversarial tests |
| Scheduling | Constraint violations | zero confirmed-appointment overlap |
| User impact | Minutes saved / correction burden | controlled within-clinic A/B with similar tasks |
| Privacy | Unauthorized patient data retrieval | zero in automated suite + security review |

Targets are internal release gates, not empirical accuracy guarantees. Human signoff required for clinical safety even with passing numbers.

## Reproducibility protocol
Record `git_sha`, `dataset_hash`, `model_name+digest`, `prompt_version`, `schema_version`, `source_bundle`, `hardware`, `temperature`, `privacy_basis`, `eval_script`, `metric`, confidence intervals, and manually reviewed failures. Compare models on same frozen held-out set and report uncertainty/negative results, not only impressive examples.

## Offline/no-LLM baseline
Every AI experiment compared to: clinician manual note, deterministic rule-based scheduling checks, basic filtered search, generic reminder template. Show incremental value over baseline; if model adds hallucinations or latency without time-saving, do not ship.
