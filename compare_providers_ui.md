# Comparing Mock vs Local Embeddings in UI

## Test 1: Mock Provider (Default)

```bash
# Terminal 1
cat > .env << EOF
PROVIDER=mock
EMBEDDING_DIMENSION=384
EOF

streamlit run src/mapper_copilot/ui.py --server.port 8501
```

Open http://localhost:8501 and note:
- ⚡ Very fast (no model loading)
- 📊 Confidence scores based on hashing
- 🎲 Deterministic but not semantic

## Test 2: Local Provider (Semantic)

```bash
# Terminal 2 (or stop Terminal 1 first)
cat > .env << EOF
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EOF

streamlit run src/mapper_copilot/ui.py --server.port 8502
```

Open http://localhost:8502 and note:
- 🧠 Semantic understanding
- 📈 Better confidence scores for similar questions
- 🎯 More accurate mappings

## Side-by-Side Comparison

Test the same RSC question with both:

**Example:** "Do workers have access to protective equipment?"

### Mock Provider
- Maps based on character/hash similarity
- Fast but simplistic
- Good for testing infrastructure

### Local Provider
- Maps based on semantic meaning
- Understands "protective equipment" = "safety gear"
- Production-ready semantic matching

## When to Use Each

| Provider | Use Case | Speed | Quality |
|----------|----------|-------|---------|
| **Mock** | Testing, CI/CD, Development | ⚡⚡⚡ | ⭐⭐ |
| **Local** | Production, Demos, Offline | ⚡⚡ | ⭐⭐⭐⭐ |
| **Bedrock** | Production with AWS | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ |
