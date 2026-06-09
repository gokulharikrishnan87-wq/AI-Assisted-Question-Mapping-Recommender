#!/bin/bash

echo "🚀 Starting Enhanced Mapper Copilot UI"
echo "========================================"
echo
echo "✨ New Features:"
echo "  - SLCP Key, Number, Section for all matches"
echo "  - Top 5 alternatives shown"
echo "  - Mapping rule removed"
echo "  - Enhanced export with full metadata"
echo
echo "Starting on http://localhost:8501"
echo

export PROVIDER=local
export EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
export EMBEDDING_DIMENSION=384

/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m streamlit run ui_enhanced.py --server.port 8501 --server.headless true
