# Focused development and portfolio roadmap

Target professional direction: **software engineering for secure AI infrastructure, evaluation, and data systems**. Essential Digital Solution is the public home for the engineering work. Employment and professional development are the primary objective; this is not a freelance lead-generation plan.

Progress is defined by evidence and milestones. No timeline or senior hiring readiness can be established without a verified background and operating experience.

## Milestone 1 — Inspectable foundation (implemented)

Strict data contracts, pinned evidence, tenant-scoped API, scoped credentials, deterministic evaluation, transactional reports, audit verification, synthetic fixtures, tests, and container configuration.

Public outputs: source repository, architecture, threat model, reproducible fixture report, and explicit limitations. This demonstrates the foundation and should not be described as a production deployment or a model-accuracy benchmark.

## Milestone 2 — Model integration and observations (adapters implemented; live verification pending)

OpenAI, Anthropic, and xAI adapters now follow reviewed public contracts, with exact model selection, client wall-clock latency, usage, hashes, bounded calls, and private partial ledgers. Offline HTTP mocks exercise their contracts and failure cases. A curated public documentation pack is included. Configure a provider key and execute the first reviewed live smoke run, then expand to held-out evaluation cases. Apply account-side spending controls; collector limits are not a hard dollar cap.

Add independently checked semantic labels and calibrated graders. Compare graders against a human-labeled sample, report disagreement, and separate citation correctness from answer entailment. Add multiple trials and uncertainty estimates where the experiment supports them.

Completion evidence still needed: a reproducible credentialed provider experiment, independently reviewed semantic labels, measured error rates, and documented failure cases. No paid requests or live provider checks occurred during v0.2 development because keys were unavailable.

## Milestone 3 — Operated cloud pilot

A schema-validated Render Blueprint, readiness endpoint, SQLite backup command, and tested restore workflow are now prepared. Next, publish the standalone repository, verify remote CI, select a target workspace, and operate one instance in one region behind a TLS gateway. Establish identity, secret custody, approved dataset/policy hashes, external audit checkpoints, backup retention, monitoring, and a retained incident record.

Measure sustained workloads, concurrency limits, storage growth, and recovery. Migrate to managed PostgreSQL, object storage, and durable queued workers when measurements justify it. Add idempotent run submission before aggressive retries or distributed workers.

Completion evidence: observed service levels with a measurement window, load/failure results, recovery procedure, operating cost, and an honest account of who used the system.

## Milestone 4 — Systems or physical-AI specialization

Choose one branch based on demonstrated depth and target roles:

| Branch | Technical work | Evidence to publish |
|---|---|---|
| AI systems | Batched inference, memory profiling, caching, controlled throughput experiments | Comparable workload, hardware configuration, quality and latency/cost tradeoffs |
| AI security | Workload identity, scoped tool execution, isolation, external audit anchors | Threat model, adversarial cases, bypass analysis, detection/containment limits |
| Data infrastructure | Versioned transformations, deduplication, distributed workers, restart recovery | Lineage graph, correctness checks, replay tests, scaling measurements |
| Simulation/autonomy | Public simulator integration, sensor streams, fault injection, scenario evaluation | Scenario manifest, seeded runs, baseline detectors, false alarm and missed-event rates |

Simulation results must be distinguished from real hardware validation. NASA and robotics interests become more credible through specific components and measured results than through broad claims about futuristic transportation.

## GitHub and professional profiles

Use a concise, factual project description:

> Building EDS Assurance, an independent reference platform for reproducible AI evaluation, evidence provenance, tenant access controls, and audit verification at Essential Digital Solution.

Pin the main repository and link the tested report, architecture, and security model. Add original technical notes and meaningful open-source contributions as they are completed. List the actual depth of contribution and collaborators. Do not use “senior,” “production-grade,” university affiliations, or employer affiliations as substitutes for demonstrated experience.

For senior applications, prepare examples of architecture decisions, production ownership, incident response, technical leadership, and cross-team impact. Repository quality supplements these examples; it cannot create an employment history.

## Website integration

Add a project page linking the repository, methodology, report, and limitations. Separate implemented, experimental, planned, and observed-in-production capabilities. Tie each performance number to a named system, workload, measurement window, and reproducible evidence.

The current site displays different uptime figures on its homepage and Practice page. Reconcile their service definitions and measurement windows before using them as hiring or customer evidence. Cite documented findings and actual collaborations precisely; references to public university resources do not imply an institutional relationship.
