# Release v0.2.0 - Active Trigger & Layered Exploration

**Release Date**: 2026-03-20  
**Codename**: "Curious Depth"  
**Status**: ✅ Production Ready

---

## 🎯 What's New

### 1. Three-Layer Exploration System

Curious Agent now supports **three depths of exploration**:

| Depth | Time | What It Does | Use Case |
|-------|------|--------------|----------|
| **shallow** | ~30s | Web search only | Quick overview, trend checking |
| **medium** | ~3-5min | Web search + arXiv paper analysis | Research papers, technical details |
| **deep** | ~10-15min | All layers + LLM-powered insights | Deep research, comparative analysis |

**Example**:
```bash
python3 curious_agent.py --run --depth shallow  # Quick scan
python3 curious_agent.py --run --depth medium   # Paper analysis
python3 curious_agent.py --run --depth deep     # Full research
```

### 2. Active Trigger System

Beyond cron scheduling, v0.2.0 introduces **three trigger modes**:

#### ⏰ Scheduled Triggers
```bash
# Add to crontab for automated exploration
crontab -e
# 0 9 * * * cd /root/dev/curious-agent && python3 curious_agent.py --run --depth shallow  # Morning scan
# 0 21 * * * cd /root/dev/curious-agent && python3 curious_agent.py --run --depth deep   # Evening deep dive
```

#### 🔗 Auto-Queue from Findings
Exploration now automatically extracts new keywords from findings and queues them for future exploration:
- Discovers "transformer" while exploring "attention mechanisms" → auto-queues "transformer"
- Tracks source: `"auto: found in attention mechanisms exploration"`
- Avoids duplicates

#### 💬 API Trigger
```bash
curl -X POST http://10.1.0.13:4849/api/curious/trigger \
  -H "Content-Type: application/json" \
  -d '{"topic": "knowledge graph embedding", "depth": "medium"}'

# Response: {"status": "accepted", "estimated_time": "3-5分钟"}
# Exploration runs in background, results notified via existing channels
```

### 3. arXiv Integration

**Layer 2** now includes intelligent arXiv paper processing:

- **Smart URL Detection**: Recognizes arXiv URLs in search results
- **Metadata Fetching**: Uses arXiv API for paper info (no download needed)
- **Relevance Scoring**: Calculates topic relevance (0-1 score)
- **Selective Download**: Only downloads PDFs for highly relevant papers (>0.6 score)
- **PDF Analysis**: Extracts text from first 2 pages using PyPDF2
- **Key Findings**: Identifies methodology, contributions, limitations

### 4. LLM-Powered Insights

**Layer 3** leverages Minimax M2.7 for deep analysis:

- **Multi-Paper Comparison**: Analyzes 2-3 papers simultaneously
- **Structured Output**:
  - Methodology comparison table
  - Core contribution summary
  - Cross-paper trend observations
  - Research field recommendations
  - "Worth deep dive" assessment
- **Smart Prompting**: Context-aware prompts based on paper metadata

### 5. Enhanced Data Model

**curiosity_queue** now includes:
```json
{
  "topic": "knowledge graph embedding",
  "depth": "medium",
  "source": "auto: found in transformer exploration"
}
```

**exploration_log** captures:
```json
{
  "exploration_depth": "deep",
  "layers_explored": [1, 2, 3],
  "papers_analyzed": ["2401.02009", "2503.17822"],
  "duration_seconds": 720
}
```

---

## 📊 Performance Improvements

| Metric | v0.1 | v0.2.0 | Improvement |
|--------|------|---------|-------------|
| Avg exploration time | Fixed ~30s | Configurable (30s-15min) | 30x flexibility |
| Knowledge sources | Web only | Web + arXiv papers | 2x sources |
| Insight quality | Search snippets | LLM-generated analysis | Significant |
| Automation | Cron only | 3 trigger modes | 3x flexibility |
| Auto-discovery | ❌ | ✅ | New feature |

---

## 🛠️ Technical Changes

### New Files
- `core/arxiv_analyzer.py` - arXiv paper analysis (167 lines)
- `core/llm_client.py` - Minimax LLM integration (108 lines)
- 8 new test files (1,429 lines total)

### Modified Files
- `curious_agent.py` - Added `--depth` parameter
- `core/explorer.py` - Three-layer architecture
- `core/curiosity_engine.py` - Auto-queue functionality
- `curious_api.py` - New `/api/curious/trigger` endpoint
- `README.md` - Comprehensive documentation update

### Dependencies
```bash
pip install arxiv PyPDF2
```

### Environment Variables
```bash
export BOCHA_API_KEY="your-bocha-key"      # Existing
export MINIMAX_API_KEY="your-minimax-key"  # New for v0.2
```

---

## 🧪 Testing

**Test Coverage**: 128 tests (100% pass rate)
- 101 unit tests
- 10 integration tests  
- 17 E2E tests

**Verification**:
```bash
# Run all tests
python -m pytest tests/ -v

# Quick smoke test
python3 curious_agent.py --run --depth shallow
```

---

## 🚀 Migration Guide

### From v0.1 to v0.2.0

1. **Install new dependencies**:
   ```bash
   pip install arxiv PyPDF2
   ```

2. **Add Minimax API key** (for deep exploration):
   ```bash
   export MINIMAX_API_KEY="your-key"
   ```

3. **Update cron jobs** (optional):
   ```bash
   # Instead of
   */30 * * * * python3 curious_agent.py --run
   
   # Use
   0 9 * * * python3 curious_agent.py --run --depth shallow
   0 21 * * * python3 curious_agent.py --run --depth deep
   ```

4. **Backward compatibility**: All v0.1 features continue to work

---

## 🎯 Use Cases

### Researcher Tracking New Papers
```bash
# Morning: Quick scan of overnight papers
0 9 * * * cd /root/dev/curious-agent && python3 curious_agent.py --run --depth shallow

# Evening: Deep dive into interesting findings
0 21 * * * cd /root/dev/curious-agent && python3 curious_agent.py --run --depth deep
```

### Developer Exploring New Tech
```bash
# Trigger immediate exploration
curl -X POST http://10.1.0.13:4849/api/curious/trigger \
  -d '{"topic": "Rust async runtime", "depth": "medium"}'
```

### Continuous Learning Agent
- Set up both cron jobs
- Let auto-queue build curiosity queue organically
- Review daily/weekly reports

---

## 🐛 Known Issues

- **PDF extraction**: PyPDF2 may fail on scanned/image-based PDFs
- **LLM timeout**: Deep exploration may fail if Minimax API is slow (>60s)
- **Rate limiting**: arXiv API has usage limits (be respectful)

---

## 🔮 What's Next (v0.3 Preview)

- **Persistent storage**: SQLite instead of JSON
- **Multi-agent collaboration**: Multiple Curious Agents working together
- **Web UI enhancements**: Real-time progress tracking
- **Custom LLM providers**: OpenAI, Anthropic, local models
- **Knowledge graph visualization**: Interactive graph UI

---

## 🙏 Contributors

- **weNix**: Design and implementation
- **OpenCode**: AI-powered development assistance
- **omo-broker**: Architecture review and validation

---

## 📄 License

MIT License - See LICENSE file for details

---

**Full Changelog**: Compare with v0.1.0 tag