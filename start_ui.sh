#!/bin/bash

echo "🚀 Starting Mapper Copilot UI with Local Embeddings"
echo "=================================================="
echo

# Check files exist
if [ ! -f "RSC Questions.xlsx" ]; then
    echo "❌ Error: RSC Questions.xlsx not found"
    exit 1
fi

if [ ! -f "slcp_data_dictionary.json" ]; then
    echo "❌ Error: slcp_data_dictionary.json not found"
    exit 1
fi

echo "✓ Data files present"
echo "  - RSC Questions.xlsx"
echo "  - slcp_data_dictionary.json"
echo

# Set environment variables
export PROVIDER=local
export EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
export EMBEDDING_DIMENSION=384

echo "✓ Configuration set"
echo "  - Provider: $PROVIDER"
echo "  - Model: $EMBEDDING_MODEL_ID"
echo

echo "Starting Streamlit on http://localhost:8501"
echo "Press Ctrl+C to stop"
echo

# Start streamlit
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m streamlit run ui_local_test.py --server.port 8501 --server.headless true
