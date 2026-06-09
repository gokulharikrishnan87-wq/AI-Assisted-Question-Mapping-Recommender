"""Debug why fp-oc-1 is not showing up."""
import json
from mapper_copilot.providers.embeddings import create_embedding_provider
from mapper_copilot.providers.vector_store import NumpyVectorStore
from mapper_copilot.providers.retrieval import BM25Index, HybridRetriever

# Load SLCP data
with open('slcp_data_dictionary.json') as f:
    data = json.load(f)

slcp_metadata = []
for key, value in data.items():
    if isinstance(value, dict) and 'question' in value and value.get('question', '').strip():
        slcp_metadata.append({
            'key': key,
            'number': value.get('number', ''),
            'section': value.get('section', ''),
            'subsection': value.get('subsection', ''),
            'question': value.get('question', '').strip(),
        })

print(f"Loaded {len(slcp_metadata)} SLCP questions\n")

# Build components with local embeddings
embedder = create_embedding_provider(provider='local', model_id='all-MiniLM-L6-v2')
slcp_texts = [meta['question'] for meta in slcp_metadata]

print("Embedding SLCP questions (this will take a moment)...")
embeddings = embedder.batch_embed(slcp_texts)
print(f"Created {len(embeddings)} embeddings\n")

# Build vector store
metadata_list = [
    {
        'slcp_question': meta['question'],
        'key': meta['key'],
        'number': meta['number'],
        'section': meta['section'],
        'subsection': meta.get('subsection', ''),
    }
    for meta in slcp_metadata
]

vector_store = NumpyVectorStore()
vector_store.index(embeddings, metadata_list)

# Build BM25 index
bm25_corpus = [
    f"{meta['key']} {meta['number']} {meta['question']}"
    for meta in slcp_metadata
]
bm25_index = BM25Index(bm25_corpus, list(range(len(slcp_metadata))))

# Create retriever
retriever = HybridRetriever(
    embedding_provider=embedder,
    vector_store=vector_store,
    bm25_index=bm25_index,
    k_retrieve=40,  # Retrieve 40 candidates
    use_bm25=True,
    section_prior_weight=0.1,
)

# Test query
rsc_question = "The facility has a business license for legal operation."
rsc_metadata = {
    'section': '1. Business Ethics',
    'lll_key': '1.02',
    'reference_data': ''
}

print("="*80)
print(f"RSC Question: {rsc_question}")
print("="*80)

# Retrieve candidates
candidates = retriever.retrieve(rsc_question, rsc_metadata)

print(f"\nRetrieved {len(candidates)} candidates\n")

# Find fp-oc-1 in results
fp_oc_1_rank = None
for i, cand in enumerate(candidates, 1):
    if cand['key'] == 'fp-oc-1':
        fp_oc_1_rank = i
        print(f"✅ FOUND fp-oc-1 at rank #{i}")
        print(f"   Score: {cand.get('embedding_score', 0):.3f}")
        print(f"   Question: {cand['question']}")
        break

if fp_oc_1_rank is None:
    print("❌ fp-oc-1 NOT FOUND in top 40 candidates!")
    print("\nSearching in ALL candidates...")
    # Search full database
    all_results = vector_store.query(embedder.embed(rsc_question), top_k=len(slcp_metadata))
    for i, (metadata, score) in enumerate(all_results, 1):
        if metadata.get('key') == 'fp-oc-1':
            print(f"   Found at rank #{i} in full dense retrieval")
            print(f"   Score: {score:.3f}")
            break

print("\n" + "="*80)
print("Top 10 candidates from hybrid retrieval:")
print("="*80)
for i, cand in enumerate(candidates[:10], 1):
    print(f"\n{i}. [{cand['key']}] {cand.get('number', 'N/A')} — Score: {cand.get('embedding_score', 0):.3f}")
    print(f"   {cand['section']}")
    print(f"   {cand['question'][:80]}...")

