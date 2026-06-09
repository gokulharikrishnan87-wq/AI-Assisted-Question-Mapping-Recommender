#!/bin/bash
# Quick script to start Streamlit UI with local embeddings

echo "🚀 Starting Mapper Copilot UI with Local Embeddings"
echo

# Create .env file for local provider
cat > .env << 'ENVEOF'
# Local embedding provider configuration
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Other settings (defaults)
LOG_LEVEL=INFO
VECTOR_STORE_TYPE=numpy
RETRIEVE_TOP_K=10
ENVEOF

echo "✓ Configuration saved to .env:"
echo "  PROVIDER=local"
echo "  EMBEDDING_MODEL_ID=all-MiniLM-L6-v2"
echo

echo "Starting Streamlit..."
echo "→ Open your browser to: http://localhost:8501"
echo "→ Press Ctrl+C to stop"
echo

streamlit run src/mapper_copilot/ui.py
