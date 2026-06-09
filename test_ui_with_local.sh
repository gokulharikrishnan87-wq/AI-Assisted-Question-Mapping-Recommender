#!/bin/bash
# Test Streamlit UI with local embeddings

echo "=== Testing Streamlit UI with Local Embeddings ==="
echo

# Create .env file for local provider
cat > .env << EOF
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EOF

echo "✓ Created .env configuration for local provider"
echo
echo "Configuration:"
cat .env
echo
echo "Starting Streamlit UI..."
echo "Open your browser to: http://localhost:8501"
echo
echo "Press Ctrl+C to stop"
echo

streamlit run src/mapper_copilot/ui.py
