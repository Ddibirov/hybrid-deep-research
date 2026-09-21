# Model Recommendations

All roles in a research run share one model (set via `delegation.model` or your agent framework's equivalent). Pick a model that balances reasoning quality with cost for your use case.

## Tiers

| Tier | Use when | Requirements |
|------|----------|-------------|
| **Quality** | Exhaustive research, complex synthesis, multi-hop reasoning | Strong reasoning, 128K+ context |
| **Balanced** | Moderate depth, good default for most topics | Good reasoning, 32K+ context |
| **Fast** | Quick scans, surface-level research | Fast inference, 32K+ context |

## Recommended Models (by provider)

### OpenRouter

| Model | Tier | Notes |
|-------|------|-------|
| DeepSeek V3 / V4 | Quality | Strong reasoning, large context |
| Qwen 3 Max | Quality | Excellent analysis |
| Claude Sonnet 4 | Quality | Best synthesis quality |
| GPT-4.1 | Quality | Reliable, good citations |
| Llama 4 Maverick | Balanced | Good value |
| Gemini 2.5 Flash | Fast | Fast, cheap, decent quality |

### OpenAI

| Model | Tier | Notes |
|-------|------|-------|
| GPT-4.1 / o4-mini | Quality | Strong reasoning |
| GPT-4.1-mini | Balanced | Good balance |
| GPT-4.1-nano | Fast | Cheapest OpenAI option |

### Anthropic

| Model | Tier | Notes |
|-------|------|-------|
| Claude Sonnet 4 | Quality | Best for synthesis and nuance |
| Claude Haiku 3.5 | Fast | Fast, affordable |

### Local (Ollama / llama.cpp)

| Model | Tier | Notes |
|-------|------|-------|
| Qwen 3 32B | Balanced | Good local option, needs 24GB+ RAM |
| Llama 3.3 70B | Quality | Needs 48GB+ RAM or GPU |
| Phi-4 14B | Fast | Runs on 16GB RAM |

### Other providers

| Model | Tier | Notes |
|-------|------|-------|
| DeepSeek V4 (DeepSeek API) | Quality | Direct API, cheaper than OpenRouter |
| GLM-5 (Zhipu) | Quality | Strong reasoning, competitive pricing |
| Kimi K2 (Moonshot) | Balanced | Long context, good for research |
| MiMo (Xiaomi) | Fast | Budget option |

## How to Compare Models

1. Run the same research question with model A → save report
2. Switch `delegation.model` to model B
3. Run the same question again → save report
4. Compare: coverage, citation quality, synthesis depth, contradictions found

## Context Window Considerations

- **Web Investigators** need ~8-16K tokens (search results + extraction)
- **Social Investigators** need ~8-16K tokens (API responses + formatting)
- **Synthesist** needs 32K+ tokens (all findings combined)
- **Verifier** needs 32K+ tokens (report + findings for cross-check)

If your model has a small context window (8K), investigators must prune aggressively before returning findings.
