#!/bin/bash
# Test script for local embedding provider with API

echo "=== Testing Local Embedding Provider with API ==="
echo

# Create temporary .env file
cat > .env.test << EOF
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EOF

echo "✓ Created test configuration (.env.test)"
echo

# Start the API in the background
echo "Starting API server..."
DOTENV_PATH=.env.test uvicorn mapper_copilot.api:app --port 8001 > /tmp/api.log 2>&1 &
API_PID=$!

# Wait for API to start
sleep 3

echo "✓ API started (PID: $API_PID)"
echo

# Test health endpoint
echo "Testing /health endpoint..."
curl -s http://localhost:8001/health | python3 -m json.tool
echo

# Test suggest endpoint
echo "Testing /suggest endpoint with local embeddings..."
curl -s -X POST http://localhost:8001/suggest \
  -H "Content-Type: application/json" \
  -d '{"rsc_question": "Do workers have safety equipment?"}' | python3 -m json.tool
echo

# Test batch suggest
echo "Testing /suggest-batch endpoint..."
curl -s -X POST http://localhost:8001/suggest-batch \
  -H "Content-Type: application/json" \
  -d '{"rsc_questions": ["Are exits marked?", "Do workers have contracts?"]}' | python3 -m json.tool
echo

# Cleanup
echo "Stopping API server..."
kill $API_PID 2>/dev/null
rm -f .env.test

echo
echo "✅ API tests complete!"
