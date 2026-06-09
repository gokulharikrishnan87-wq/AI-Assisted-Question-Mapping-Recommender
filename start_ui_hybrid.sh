#!/bin/bash
# Start Mapper Copilot UI with Hybrid Retrieval

echo "🚀 Starting Mapper Copilot with Hybrid Retrieval..."
echo ""
echo "Configuration:"
echo "  - Provider: mock (HashingEmbedder + MockLLM)"
echo "  - Hybrid Retrieval: ENABLED (BM25 + Dense)"
echo "  - K_RETRIEVE: 40 candidates"
echo "  - Reranker: Claude API (llm)"
echo "  - Section Prior: 0.1 (soft boost)"
echo ""
echo "Data Files:"
echo "  - RSC: RSC Questions.xlsx (288 questions)"
echo "  - SLCP: slcp_data_dictionary.json (2,111 questions)"
echo ""
echo "Starting Streamlit UI..."
echo "=========================================="
echo ""

cd /Users/manju_na/AI-Assisted-Question-Mapping-Recommender
streamlit run src/mapper_copilot/ui.py
