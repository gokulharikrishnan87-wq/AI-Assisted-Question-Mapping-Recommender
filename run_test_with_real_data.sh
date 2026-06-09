#!/bin/bash
echo "🧠 Starting Mapper Copilot with Real Data + Local Embeddings"
echo
echo "Files:"
echo "  ✓ RSC Questions.xlsx ($(wc -l < "RSC Questions.xlsx" 2>/dev/null || echo "?") KB)"
echo "  ✓ slcp_data_dictionary.json ($(wc -c < slcp_data_dictionary.json | awk '{print int($1/1024)}') KB)"
echo
echo "Configuration:"
echo "  Provider: local"
echo "  Model: all-MiniLM-L6-v2"
echo "  Dimensions: 384"
echo
echo "Opening browser to: http://localhost:8501"
echo
echo "⏳ First load will download the model (~120MB) - this is one-time"
echo "📊 Then it will map all RSC questions to SLCP using semantic embeddings"
echo
echo "Press Ctrl+C to stop"
echo

streamlit run ui_local_test.py
