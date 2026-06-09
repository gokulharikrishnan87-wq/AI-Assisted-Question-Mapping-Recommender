#!/usr/bin/env python3
"""
Simple Streamlit demo for local embeddings (no data files needed).

Run with: streamlit run demo_local_embeddings.py
"""

import os
import sys
import numpy as np
import streamlit as st

# Add src to path
sys.path.insert(0, 'src')

# Set environment for local provider
os.environ['PROVIDER'] = 'local'
os.environ['EMBEDDING_MODEL_ID'] = 'all-MiniLM-L6-v2'
os.environ['EMBEDDING_DIMENSION'] = '384'

from mapper_copilot.providers.embeddings import create_embedding_provider_from_settings
from mapper_copilot.config import settings


# Page config
st.set_page_config(
    page_title="Local Embeddings Demo",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Local Sentence Embeddings Demo")
st.markdown("**Testing local sentence-transformers without AWS credentials**")

st.divider()

# Show configuration
with st.expander("⚙️ Configuration", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Provider", settings.provider)
    with col2:
        st.metric("Model", settings.embedding_model_id)
    with col3:
        st.metric("Dimensions", settings.embedding_dimension)

st.divider()

# Initialize embedder
@st.cache_resource
def get_embedder():
    """Load the embedding model (cached)."""
    with st.spinner("Loading sentence-transformers model..."):
        embedder = create_embedding_provider_from_settings()
    return embedder

try:
    embedder = get_embedder()
    st.success(f"✅ Model loaded: {type(embedder).__name__}")
except Exception as e:
    st.error(f"❌ Failed to load model: {e}")
    st.info("Install with: `pip install 'mapper-copilot[local-embeddings]'`")
    st.stop()

st.divider()

# Test 1: Single Text Embedding
st.header("1️⃣ Single Text Embedding")

text_input = st.text_input(
    "Enter text to embed:",
    value="Do workers have safety equipment?",
    key="single_text"
)

if st.button("Generate Embedding", key="single_btn"):
    with st.spinner("Generating embedding..."):
        embedding = embedder.embed(text_input)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Shape", embedding.shape)
    with col2:
        st.metric("Data Type", str(embedding.dtype))
    with col3:
        st.metric("L2 Norm", f"{np.linalg.norm(embedding):.4f}")

    with st.expander("View embedding values"):
        st.write(embedding[:10])
        st.caption(f"Showing first 10 of {len(embedding)} dimensions")

st.divider()

# Test 2: Semantic Similarity
st.header("2️⃣ Semantic Similarity Test")

col1, col2 = st.columns(2)

with col1:
    question1 = st.text_area(
        "Question 1:",
        value="Do workers have access to protective equipment?",
        height=100,
        key="q1"
    )

with col2:
    question2 = st.text_area(
        "Question 2:",
        value="Is safety gear provided to employees?",
        height=100,
        key="q2"
    )

question3 = st.text_input(
    "Question 3 (different topic):",
    value="What are the working hours?",
    key="q3"
)

if st.button("Calculate Similarity", key="similarity_btn"):
    with st.spinner("Computing embeddings..."):
        e1 = embedder.embed(question1)
        e2 = embedder.embed(question2)
        e3 = embedder.embed(question3)

    # Calculate cosine similarities (embeddings are already normalized)
    sim_12 = float(np.dot(e1, e2))
    sim_13 = float(np.dot(e1, e3))
    sim_23 = float(np.dot(e2, e3))

    st.subheader("Results:")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Q1 ↔ Q2 (Similar)",
            f"{sim_12:.4f}",
            delta=None,
            help="Should be HIGH (similar questions)"
        )
        if sim_12 > 0.7:
            st.success("✅ High similarity detected!")
        else:
            st.warning("⚠️ Lower than expected")

    with col2:
        st.metric(
            "Q1 ↔ Q3 (Different)",
            f"{sim_13:.4f}",
            delta=None,
            help="Should be LOWER (different topics)"
        )
        if sim_13 < sim_12:
            st.success("✅ Correctly identified as different!")
        else:
            st.warning("⚠️ Should be lower than Q1↔Q2")

    with col3:
        st.metric(
            "Q2 ↔ Q3 (Different)",
            f"{sim_23:.4f}",
            delta=None,
            help="Should be LOWER (different topics)"
        )

    st.info(
        "**How it works:** Questions with similar *meaning* get higher similarity scores "
        "(closer to 1.0), even if they use different words. Questions about different "
        "topics get lower scores."
    )

st.divider()

# Test 3: Batch Processing
st.header("3️⃣ Batch Embedding Test")

questions_text = st.text_area(
    "Enter multiple questions (one per line):",
    value="""Workers are paid accurately and on time
Emergency exits are clearly marked
Worker contracts are maintained
Safety equipment is provided
Training programs are available""",
    height=150,
    key="batch_input"
)

if st.button("Process Batch", key="batch_btn"):
    questions = [q.strip() for q in questions_text.split('\n') if q.strip()]

    with st.spinner(f"Processing {len(questions)} questions..."):
        embeddings = embedder.batch_embed(questions)

    st.success(f"✅ Generated {len(embeddings)} embeddings")

    # Show statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Batch Size", len(embeddings))
    with col2:
        st.metric("Embedding Dim", embeddings[0].shape[0])
    with col3:
        norms = [np.linalg.norm(e) for e in embeddings]
        st.metric("Avg Norm", f"{np.mean(norms):.4f}")

    # Show pairwise similarities
    st.subheader("Pairwise Similarities:")

    similarity_matrix = np.zeros((len(embeddings), len(embeddings)))
    for i in range(len(embeddings)):
        for j in range(len(embeddings)):
            similarity_matrix[i, j] = np.dot(embeddings[i], embeddings[j])

    import pandas as pd
    df = pd.DataFrame(
        similarity_matrix,
        columns=[f"Q{i+1}" for i in range(len(questions))],
        index=[f"Q{i+1}" for i in range(len(questions))]
    )

    st.dataframe(df.style.background_gradient(cmap='RdYlGn', vmin=0, vmax=1))

    with st.expander("View questions"):
        for i, q in enumerate(questions, 1):
            st.write(f"**Q{i}:** {q}")

st.divider()

# Footer
st.markdown("---")
st.markdown("""
### 📚 About This Demo

This demo shows the **local sentence-transformers embedding provider** in action:

- ✅ **No AWS credentials needed** - runs completely offline
- ✅ **Semantic understanding** - understands meaning, not just keywords
- ✅ **Fast batch processing** - optimized for multiple texts
- ✅ **L2-normalized embeddings** - ready for cosine similarity

**Model:** `all-MiniLM-L6-v2` (384 dimensions, 120MB)

**Next steps:**
- Test with your own questions
- Compare with mock provider
- Integrate into production app
""")
