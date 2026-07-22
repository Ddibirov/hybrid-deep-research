---
status: confirmed
topic: Current state of open-source AI agent frameworks in 2026
slug: open-source-ai-agent-frameworks-2026
rounds: 1
sources_count: 18
social_signals: 4
verification: passed
generated_at: 2026-07-22T12:05:00Z
---

# Open-Source AI Agent Frameworks in 2026 — Research Report

## Executive Summary

The open-source AI agent framework landscape has undergone a major consolidation between 2025 and mid-2026. Microsoft placed AutoGen and Semantic Kernel into maintenance mode in favor of a unified Agent Framework (MAF). LangChain reached 1.0 and sits at 142k GitHub stars, but faces growing criticism for over-engineering. CrewAI has emerged as the largest independent agent framework (~51k stars) with steady production adoption. New entrants — OpenAI Agents SDK (~26k stars), Mastra (22k stars, TypeScript-native), and PydanticAI (~15.5k stars) — are challenging incumbents with lighter, more focused designs. The community is increasingly skeptical of heavyweight abstractions, favoring frameworks that are modular, independently governed, and easy to reason about.

## Key Findings

### 1. LangChain / LangGraph Ecosystem

**LangChain reached version 1.3.14 on PyPI as of July 2026**, following the landmark LangChain 1.0 release on October 17, 2025 which consolidated core APIs and added Pydantic 2 support [1]. The ecosystem now includes sandbox integrations (Modal, Daytona, Runloop), server-side provider tools (file search, code interpreter, MCP connector), and a `moderateContent` option on ChatOpenAI [2].

**LangGraph 1.0 shipped alongside LangChain 1.0** on October 22, 2025, described by the team as "the first stable major release in the durable agent framework space" [3]. It powers production systems at Uber, LinkedIn, and Klarna. The key design decision is a graph-based execution model where every node, edge, and checkpoint is inspectable and resumable. Current version: LangGraph 1.2.9 (July 10, 2026) [4].

**Criticism persists around complexity.** A widely-cited Hacker News thread describes an intern building a RAG Q&A system with raw Python instead of LangChain and succeeding — validating the choice to avoid the framework's abstraction layers [5]. Common complaints include too many layers (chains, callbacks, runnables), vendor lock-in concerns (LangSmith, LangGraph Hub), and teams preferring direct API calls or lighter alternatives like LlamaIndex or Vercel AI SDK. Paradoxically, LangChain itself warned about AI agent memory lock-in creating vendor monopolies [6], while critics note its own ecosystem creates a similar platform dependency.

### 2. CrewAI — The Independent Leader

**CrewAI has grown from ~15k stars in early 2025 to ~51k stars by mid-2026**, making it the largest standalone agent framework outside the LangChain and Microsoft ecosystems [7]. The latest stable release is 1.14.3 (April 24, 2026), with steady PyPI releases through July 2026 [8].

Key differentiators:
- **Framework-independent**: Built entirely from scratch, not layered on LangChain or any other framework
- **Role-based multi-agent model**: Define crews with specific roles; the framework handles task delegation and result aggregation
- **CrewAI Flows**: Event-driven control alongside classic role-based crews, enabling production-grade orchestration
- **CLI & deployment tools**: Git init for generated projects, CLI deploy improvements, project scaffolding

The community praises CrewAI's intuitive mental model, production-readiness, and independence from corporate fragmentation. It is described as "lean, lightning-fast" and "the leading alternative to heavier frameworks" for production deployments in 2026 [9]. The commercial platform (CrewAI AMP/Discovery) is also gaining enterprise traction.

### 3. AutoGen → AG2 → Microsoft Agent Framework — A Three-Way Split

The AutoGen ecosystem has fragmented significantly:

- **Microsoft AutoGen** (~55.8k stars, 8.2k forks) — entered **maintenance mode** in October 2025 when Microsoft launched its Agent Framework. No new features; bug fixes and security patches only [10].

- **AG2** (community fork at `ag2ai/ag2`) — the community-managed successor that now owns the legacy `autogen` PyPI package name. Latest version **v0.12.2** as of mid-2026, shipping nine multi-agent orchestration patterns and MCP client support. This is the migration path for existing AutoGen users who don't want to move to MAF [11].

- **Microsoft Agent Framework (MAF)** 1.0 — reached general availability on April 3, 2026, described as "a production-ready release: stable APIs, and a commitment to long-term support" [12]. It unifies Semantic Kernel's enterprise foundations with AutoGen's multi-agent orchestration into a single Python and .NET SDK with full MCP and A2A protocol support. Install: `pip install agent-framework`.

The fragmentation has frustrated the community significantly. As one analysis puts it: "In 2026, picking an agent framework means parsing three names that sound interchangeable: Microsoft AutoGen (maintenance), AG2 (community fork that ships the legacy autogen PyPI package), and Microsoft Agent Framework (the production successor Microsoft wants new projects on)" [13].

### 4. Emergent Frameworks

**OpenAI Agents SDK** (March 2025, 26k+ stars) — the production successor to Swarm. Uses simple primitives: "Routines" (agent + tools) and "Handoffs" (control transfer). The April 2026 "Next Evolution" update added native sandbox execution (E2B, Modal), a long-horizon harness for multi-day runs, and a subagent primitive [14]. It is provider-agnostic (OpenAI Responses API + 100+ other LLMs).

**Mastra** (TypeScript, 22k+ stars, 1.8M monthly npm downloads) — launched 1.0 in January 2026. Built by the team behind Gatsby.js. Ships everything in one package: workflows, memory, RAG, evals, MCP connections. Its memory system scored 94.87% on LongMemEval [15].

**Agno** (formerly Phidata, 41.1k stars, v2.7.3) — rebranded from Phidata in January 2025. Apache-2.0 licensed Python framework [16].

**PydanticAI** (~15.5k stars) — built by the Pydantic team. Leverages Pydantic's validation layer for structured agent outputs [17].

**Dify** (~134k stars) — open-source LLM app platform with visual workflow builder, RAG pipeline, and agent capabilities. Not a pure agent framework but a popular platform for building agentic applications [18].

### 5. GitHub Star Comparison (mid-2026)

| Framework | GitHub Stars | Language | Status |
|-----------|-------------|----------|--------|
| LlamaIndex | ~193k* | Python | Active |
| LangChain | ~142k | Python | Active (v1.3.14) |
| Dify | ~134k | Python/TS | Active |
| AutoGen | ~55.8k | Python | Maintenance mode |
| CrewAI | ~51k | Python | Active (v1.14.3) |
| Agno (Phidata) | ~41.1k | Python | Active (v2.7.3) |
| LangGraph | ~38k | Python | Active (v1.2.9) |
| Semantic Kernel | ~28k | Python/.NET | Maintenance mode |
| OpenAI Agents SDK | ~26k | Python | Active (v0.17.1) |
| Mastra | ~22k | TypeScript | Active (v1.0) |
| PydanticAI | ~15.5k | Python | Active |

*\*LlamaIndex star count includes ecosystem repos*

## Community Pulse

**What developers are saying (Reddit, HN, X):**

- **CrewAI is the pragmatic choice for new projects in 2026.** Developers praise its independence, straightforward mental model, and production focus. The r/AI_Agents community describes it as "set up agents, give them a task and they will do everything" versus AutoGen which "needs more work designing tasks" — but notes that extra control is exactly what production users want [19].

- **The AutoGen/AG2/MAF split has caused genuine pain.** Naming confusion, package ownership disputes, and the "Microsoft put AutoGen in maintenance and shipped Agent Framework 1.0" narrative have driven many developers to CrewAI or LangChain as safer bets.

- **Skepticism toward heavyweight frameworks is growing.** A recurring theme across HN and Reddit in 2025-2026: developers increasingly prefer minimal abstractions, direct API calls, or lightweight frameworks. The OpenAI Agents SDK's small primitive set is frequently cited as the right philosophy.

- **Mastra is gaining mindshare in the TypeScript community.** As the only purpose-built TypeScript-native agent framework, it's filling a gap that Python-dominated frameworks left open.

- **No clear "winner" — and that's OK.** The consensus is that the framework choice depends heavily on the use case: graph-based state management (LangGraph), lightweight agent loops (OpenAI Agents SDK), role-based teams (CrewAI), enterprise .NET (MAF), or TypeScript-native (Mastra).

## Contradictions & Uncertainties

- **GitHub stars vs actual production use.** Stars are a proxy for interest, not production adoption. LangChain's 142k stars and CrewAI's 51k don't necessarily reflect who's running what in production. Survey data from mid-2026 is limited.

- **LangChain's value proposition remains contested.** The framework has massive adoption and ecosystem breadth, yet vocal critics argue it's over-engineered for anything beyond simple use cases. Both positions have valid evidence.

- **Microsoft Agent Framework is too new to evaluate.** MAF 1.0 shipped in April 2026 — too recent to assess real-world adoption, stability, or community reception. Its long-term success is uncertain.

- **AG2's long-term viability.** As a community fork without corporate backing, AG2's ability to sustain development alongside MAF is an open question.

## Sources

[1] LangChain Release Notes — https://docs.langchain.com/oss/python/releases/changelog (2026, official docs)
[2] LangChain v0.3 Announcement — https://www.langchain.com/blog/announcing-langchain-v0-3 (2025, official blog)
[3] AgenticWire: AI Agent Framework Status 2026 — https://www.agenticwire.news/article/ai-agent-framework-status-2026 (June 2026, news)
[4] LangGraph 1.0 Coverage — https://cosmo-edge.com/langgraph-v1-langchain-ecosystem-maturity/ (2026, analysis)
[5] LangChain Criticisms Analysis — https://shashankguda.medium.com/challenges-criticisms-of-langchain-b26afcef94e7 (Mar 2025, blog)
[6] LangChain Memory Lock-in Warning — https://blockchain.news/news/langchain-ai-agent-memory-lock-in-warning (Apr 2026, news)
[7] CrewAI Platform Statistics — https://www.getpanto.ai/blog/crewai-platform-statistics (2026, analysis)
[8] CrewAI PyPI — https://pypi.org/project/crewai/ (2026, official)
[9] CrewAI Production Guide — https://www.decisioncrafters.com/crewai-build-autonomous-multi-agent-teams/ (2026, analysis)
[10] Microsoft Agent Framework Announcement — https://www.microsoft.com/en-us/research/articles/introducing-microsoft-agent-framework/ (Oct 2025, official)
[11] AG2 Documentation — https://github.com/ag2ai/ag2 (2026, repo)
[12] MAF 1.0 Release — https://devblogs.microsoft.com/agent-framework/maf-1-0-ga/ (Apr 2026, official blog)
[13] Agent Frameworks 2026 Guide — https://www.agenticwire.news/article/agent-frameworks-2026-autogen-ag2-guide (June 2026, news)
[14] OpenAI Agents SDK — https://github.com/openai/openai-agents-python (2026, repo)
[15] Mastra Documentation — https://github.com/mastra-ai/mastra (2026, repo)
[16] Agno Framework — https://github.com/agno-agi/agno (2026, repo)
[17] PydanticAI — https://github.com/pydantic/pydantic-ai (2026, repo)
[18] Dify — https://github.com/langgenius/dify (2026, repo)
[19] CrewAI vs AutoGen Discussion — https://www.reddit.com/r/AI_Agents/comments/1ar0sr8/crewai_vs_autogen/ (2025-2026, Reddit)
[20] AI Agent Frameworks Compared 2026 — https://cordum.io/blog/ai-agent-frameworks-comparison (2026, analysis)
[21] LangChain Ecosystem Tools — https://www.decisioncrafters.com/langgraph-build-resilient-agents/ (2026, analysis)
[22] Semantic Kernel Stars — https://www.jbinternational.co.uk/article/view/4678 (May 2026, news)
[23] AutoGen in 2026 Case Study — https://medium.com/@jolalf/autogen-in-2026-case-study-096df38066db (2026, blog)
[24] Agent Framework EVAL — https://dev.to/ultraduneai/eval-004-ai-agent-frameworks-langgraph-vs-crewai-vs-autogen-vs-smolagents-vs-openai-agents-sdk-190l (2026, analysis)
