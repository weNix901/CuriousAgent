# Phase 3 Setup Guide

## Environment Variables

Curiosity Decomposer requires the following environment variables:

### Required (both for 2-Provider validation)

```bash
export BOCHA_API_KEY="your-bocha-key"
export SERPER_API_KEY="your-serper-key"
```

## Provider Configuration

**Configured Providers: Bocha + Serper**

| Provider | Best For | Validation Role |
|----------|----------|----------------|
| Bocha | Chinese queries | Primary |
| Serper | Academic/technical | Secondary |

Both providers required for 2-Provider validation threshold.

## Configuration Options

```yaml
# curious-agent.yaml
deccomposer:
  max_candidates: 7        # LLM 生成候选数量上限（范围 5-7）
  min_candidates: 5        # LLM 生成候选数量下限
  max_depth: 2             # 递归分解深度限制（默认 2，0=无限）
  verification_threshold: 2  # 需要 2 个 Provider 验证通过
```

## Testing

Verify setup:

```bash
cd /root/dev/curious-agent
python3 -c "
from core.provider_registry import init_default_providers
from core.curiosity_decomposer import CuriosityDecomposer

registry = init_default_providers()
print(f'Enabled providers: {[p.name for p in registry.get_enabled()]}')
"
```

Expected output shows both providers enabled: `['bocha', 'serper']`.
