"""Test hybrid retrieval manually to see actual results."""
import json
from mapper_copilot.providers.embeddings import HashingEmbedder
from mapper_copilot.providers.vector_store import NumpyVectorStore
from mapper_copilot.providers.retrieval import BM25Index, HybridRetriever
from mapper_copilot.providers.rerankers import LocalCrossEncoderReranker

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
            'question': value.get('question', '').strip(),
        })

print(f"Loaded {len(slcp_metadata)} SLCP questions\n")

# Build components
embedder = HashingEmbedder(embedding_dim=512)
slcp_texts = [meta['question'] for meta in slcp_metadata]
embeddings = embedder.batch_embed(slcp_texts)

metadata_list = [
    {
        'slcp_question': meta['question'],
        'key': meta['key'],
        'number': meta['number'],
        'section': meta['section'],
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
    k_retrieve=40,
    use_bm25=True,
    section_prior_weight=0.1,
)

# Create reranker
reranker = LocalCrossEncoderReranker()

# Test questions
test_cases = [
    {
        'question': 'The facility has a business license for legal operation.',
        'metadata': {'section': '1. Business Ethics', 'lll_key': '1.02', 'reference_data': ''}
    },
    {
        'question': 'Business License and other documents of the facility required for legal operation are valid and match with actual operation (sector, address etc.).',
        'metadata': {'section': '1. Business Ethics', 'lll_key': '1.03', 'reference_data': ''}
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"Test {i}: {test['question'][:80]}...")
    print('='*80)
    
    # Hybrid retrieval
    candidates = retriever.retrieve(test['question'], test['metadata'])
    print(f"\n🔍 Hybrid Retrieval returned {len(candidates)} candidates")
    
    # Rerank
    reranked = reranker.rerank(test['question'], candidates, top_k=5)
    print(f"🎯 Cross-Encoder Reranked to top {len(reranked)}")
    
    print("\n📋 Top 5 Matches:")
    for rank, cand in enumerate(reranked, 1):
        print(f"\n  {rank}. [{cand['key']}] Score: {cand['llm_score']:.3f}")
        print(f"     Section: {cand['section']}")
        print(f"     Question: {cand['question'][:100]}...")

