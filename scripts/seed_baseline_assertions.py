#!/usr/bin/env python3
"""Seed baseline assertions for cold start mitigation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.embedding_service import EmbeddingService, EmbeddingConfig
from core.assertion_index import AssertionIndex

BASELINE_ASSERTIONS = [
    "Machine learning is a subset of artificial intelligence",
    "Deep learning uses neural networks with multiple layers",
    "Supervised learning requires labeled training data",
    "Transformers use self-attention mechanisms",
    "Large language models are trained on vast text corpora",
    "Neural networks consist of interconnected nodes",
    "Gradient descent optimizes model parameters",
    "Backpropagation computes gradients in neural networks",
    "Natural language processing deals with human language",
    "Computer vision processes and analyzes images",
    "APIs enable communication between software systems",
    "Databases store structured information persistently",
    "Version control tracks changes to source code",
    "REST APIs use HTTP methods for communication",
    "Microservices are independently deployable services",
    "Peer review evaluates scientific research quality",
    "ArXiv is a preprint repository for scientific papers",
    "Citations measure research impact and influence",
    "Abstracts summarize research paper contents",
    "Literature reviews survey existing research",
    "Linear algebra deals with vectors and matrices",
    "Calculus studies rates of change and accumulation",
    "Probability theory models uncertainty",
    "Statistics analyzes data to infer patterns",
    "Optimization finds the best solution among alternatives",
]

def seed_assertions():
    print(f"Seeding {len(BASELINE_ASSERTIONS)} baseline assertions...")
    config = EmbeddingConfig(provider="volcengine")
    embedding_service = EmbeddingService(config)
    index = AssertionIndex()
    
    success_count = 0
    for i, assertion in enumerate(BASELINE_ASSERTIONS, 1):
        try:
            embedding = embedding_service.embed(assertion)[0]
            index.insert(text=assertion, embedding=embedding, topic="baseline", source_topic="baseline_seed")
            success_count += 1
            print(f"  [{i}/{len(BASELINE_ASSERTIONS)}] ✓ {assertion[:60]}...")
        except Exception as e:
            print(f"  [{i}/{len(BASELINE_ASSERTIONS)}] ✗ Failed: {e}")
    
    print(f"\n✅ Baseline seeding complete: {success_count}/{len(BASELINE_ASSERTIONS)} assertions added")
    stats = index.get_stats()
    print(f"📊 Index stats: {stats}")

if __name__ == "__main__":
    seed_assertions()
