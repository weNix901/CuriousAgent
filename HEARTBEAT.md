# Heartbeat Tasks for Curious Agent

## Dream Agent Tasks

Run Dream Agent to generate new curiosity topics from existing knowledge graph.

- [ ] Generate curiosity topics using L1-L4 pipeline
- [ ] Add high-quality topics to the curiosity queue

## Instructions

When heartbeat triggers:
1. Run DreamAgent.run() to analyze KG nodes
2. Collect L4 topics and add to queue
3. Log results to dream_traces.db