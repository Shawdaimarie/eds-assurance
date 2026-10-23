# Public research register and engineering priorities

Reviewed: **2026-10-23**. These are public technical sources, not access to company internals. Descriptions below are original summaries. No third-party implementation has been copied into this project. Source relevance does not imply institutional affiliation, hiring qualification, or endorsement.

## Source-to-project connections

| Organization | Primary source | Engineering connection | Status here |
|---|---|---|---|
| Anthropic | [Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) | Evaluation needs explicit tasks, observable behavior, and useful failure analysis | Deterministic task coverage and reports implemented; live agent evaluation deferred |
| Anthropic | [Claude Code sandboxing](https://www.anthropic.com/research/claude-code-sandboxing) and [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | Permission boundaries and typed model results belong in the system design | Messages adapter implemented and mock-tested; no execution sandbox or tools |
| OpenAI | [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | Typed contracts reduce ambiguity in machine-consumed results | Responses adapter implemented and mock-tested; credentialed live verification pending |
| xAI / Grok | [Structured outputs](https://docs.x.ai/developers/model-capabilities/text/structured-outputs) | Structured responses need local validation and explicit model selection | Responses adapter implemented and mock-tested; tool execution deferred |
| NVIDIA | [Evaluating AI guardrails](https://developer.nvidia.com/blog/measuring-the-effectiveness-and-performance-of-ai-guardrails-in-generative-ai-applications/) | Measure control outcomes together with operating cost and latency | Client telemetry collection and cost estimates implemented; NVIDIA model integration and guardrail classifiers deferred |
| Tesla | [Tesla AI careers](https://www.tesla.com/careers/search) | Current work includes inference infrastructure, autonomy, geometric vision, and robotics | Guides later physical-AI specialization; no Tesla integration |
| NASA | [JSTAR digital twins](https://www.nasa.gov/jstar-digital-twins/) and [NOS3](https://github.com/nasa/nos3) | Simulate operational conditions and faults before physical deployment | Future telemetry/fault-injection adapter; no spacecraft software or flight capability |
| Stanford | [CS336](https://cs336.stanford.edu/) | Implementation-heavy study of language models, data, systems optimization, and evaluation | Advanced learning reference, subject to prerequisites; no enrollment or affiliation asserted |
| Harvard | [Computer science research areas](https://seas.harvard.edu/computer-science) | AI, security, data management, architecture, systems, and robotics are connected research disciplines | Research orientation; no collaboration or affiliation asserted |

## Current hiring evidence

- [OpenAI infrastructure security](https://openai.com/careers/software-engineer-infrastructure-security-us-remote/): identity, key management, secure proxies, Kubernetes, and reliable distributed infrastructure.
- [Anthropic post-training evaluations](https://job-boards.greenhouse.io/anthropic/jobs/5198255008): measurement quality, regressions, statistics, Python, and production observability.
- [Anthropic data infrastructure](https://job-boards.greenhouse.io/anthropic/jobs/4973067008): traceable data processing, distributed reliability, validation, and training pipelines.
- [Google DeepMind role descriptions](https://deepmind.google/careers/): research engineering spans experimentation, mathematical reasoning, model implementation, and distributed computing.
- [NVIDIA GEAR](https://research.nvidia.com/labs/gear/): simulation and synthetic data support embodied-agent research.

These examples establish relevance, not a measured ranking of vacancy counts or a prediction that a specific position will remain open.

## Projected priorities: engineering hypotheses

Over the next 12–36 months, the following are reasonable hypotheses inferred from current public work and requirements. They must be revisited with evidence rather than presented as certain market forecasts.

1. **Evaluation and observability:** expanding AI use increases the value of detecting regressions, comparing methods, and attributing failures.
2. **Identity and permission boundaries:** greater tool use makes application-controlled authorization and isolation more consequential.
3. **Data provenance:** reproducibility depends on knowing which evidence, transformations, and policies produced a result.
4. **Inference efficiency:** useful performance comparisons need consistent workloads and measured quality/cost tradeoffs.
5. **Simulation and fault testing:** robotics and aerospace create a later application domain for the same measurement and verification discipline.

## Keeping the work useful

For each meaningful release, record the source URL, review date, research question, experimental configuration, baseline, results, and limitations. Recheck changing provider APIs and open roles before describing them as current. Refresh this register when architecture depends on a changed source; a 90-day review is a useful planning interval, not an automated monitor in this repository.

Publish a technical result only when the experiment is reproducible. Keep synthetic demonstrations explicitly labeled, report negative results, and retain the distinction between a research hypothesis and observed behavior.
