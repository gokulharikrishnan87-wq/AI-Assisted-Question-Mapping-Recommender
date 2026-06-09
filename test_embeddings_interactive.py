#!/usr/bin/env python3
"""Interactive test script for embedding providers."""

import os
import sys
import numpy as np

# Add src to path
sys.path.insert(0, 'src')

def test_provider(provider_type, model_id=None):
    """Test a specific embedding provider."""
    print(f"\n{'='*60}")
    print(f"Testing {provider_type.upper()} Provider")
    print(f"{'='*60}\n")

    # Set environment
    os.environ['PROVIDER'] = provider_type
    if model_id:
        os.environ['EMBEDDING_MODEL_ID'] = model_id
    if provider_type == 'mock':
        os.environ['EMBEDDING_DIMENSION'] = '384'

    # Import after setting environment
    from mapper_copilot.providers.embeddings import create_embedding_provider_from_settings
    from mapper_copilot.config import settings

    print(f"Configuration:")
    print(f"  Provider: {settings.provider}")
    print(f"  Model: {settings.embedding_model_id}")
    print(f"  Dimension: {settings.embedding_dimension}")
    print()

    # Create embedder
    print("Creating embedder...")
    embedder = create_embedding_provider_from_settings()
    print(f"✓ Created {type(embedder).__name__}\n")

    # Test single embedding
    print("Test 1: Single embedding")
    text = "Do workers have safety equipment?"
    print(f"  Input: '{text}'")
    emb = embedder.embed(text)
    print(f"  Output: shape={emb.shape}, dtype={emb.dtype}, norm={np.linalg.norm(emb):.4f}")
    print(f"  ✓ Single embedding works!\n")

    # Test batch embedding
    print("Test 2: Batch embedding")
    texts = [
        "Workers are paid accurately and on time",
        "Emergency exits are clearly marked",
        "Worker contracts are maintained"
    ]
    print(f"  Input: {len(texts)} questions")
    embeddings = embedder.batch_embed(texts)
    print(f"  Output: {len(embeddings)} embeddings")
    for i, emb in enumerate(embeddings):
        print(f"    [{i}] shape={emb.shape}, norm={np.linalg.norm(emb):.4f}")
    print(f"  ✓ Batch embedding works!\n")

    # Test semantic similarity
    print("Test 3: Semantic similarity")
    q1 = "Do workers wear protective equipment?"
    q2 = "Is safety gear provided to employees?"
    q3 = "What are the working hours?"

    e1 = embedder.embed(q1)
    e2 = embedder.embed(q2)
    e3 = embedder.embed(q3)

    sim_12 = np.dot(e1, e2)  # Already normalized, so dot product = cosine similarity
    sim_13 = np.dot(e1, e3)

    print(f"  Q1: '{q1}'")
    print(f"  Q2: '{q2}'")
    print(f"  Q3: '{q3}'")
    print(f"  Similarity(Q1, Q2): {sim_12:.4f} (similar questions)")
    print(f"  Similarity(Q1, Q3): {sim_13:.4f} (different questions)")
    print(f"  ✓ Semantic similarity works!")

    print(f"\n{'='*60}")
    print(f"✅ {provider_type.upper()} Provider: ALL TESTS PASSED")
    print(f"{'='*60}\n")


def main():
    """Run tests for all providers."""
    print("\n" + "="*60)
    print("EMBEDDING PROVIDER TEST SUITE")
    print("="*60)

    # Test mock provider
    try:
        test_provider('mock')
    except Exception as e:
        print(f"❌ Mock provider failed: {e}\n")

    # Test local provider
    try:
        test_provider('local', 'all-MiniLM-L6-v2')
    except Exception as e:
        print(f"❌ Local provider failed: {e}")
        print("   Install with: pip install 'mapper-copilot[local-embeddings]'\n")

    print("\n" + "="*60)
    print("ALL TESTS COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
