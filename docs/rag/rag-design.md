# TrackFlow RAG Knowledge Base Design

## Overview

The TrackFlow RAG (Retrieval-Augmented Generation) system allows the commercial team to ask natural-language questions and receive answers generated only from approved company documentation.

Instead of relying on a language model's general knowledge, the application retrieves relevant TrackFlow documentation from Qdrant and uses that retrieved context to generate the final response.

The implementation is separated into four independent responsibilities:

- `setup()` prepares and indexes the knowledge base.
- `embed()` converts text into vector embeddings.
- `retrieve()` searches Qdrant for the most relevant chunks.
- `query()` generates the final answer from the retrieved context.

This separation allows any component to be replaced without changing the others.

---

# Knowledge Base

The indexed documents are stored in:

`docs/company-knowledge-base/`

Documents:

- trackflow-sla-delivery.en.md
- trackflow-returns-policy.en.md
- trackflow-carrier-coverage.en.md
- trackflow-storage-pricing.en.md

These documents were selected because they contain the operational knowledge frequently requested by the commercial team.

---

# Chunking Strategy

The project uses semantic paragraph chunking.

Instead of splitting documents by a fixed number of words or tokens, each business rule remains together inside a single chunk.

This prevents important information such as:

- delivery exceptions
- storage discount approvals
- return policies
- carrier restrictions

from being divided across multiple chunks.

Current indexed chunks:

- Delivery SLA: 4
- Returns Policy: 6
- Carrier Coverage: 4
- Storage Pricing: 4

Total indexed chunks:

18

Each document produces at least three chunks as required.

---

# Embeddings

Embeddings are generated using the dedicated TrackFlow embedding model:

`downtown-miami/openrouter/perplexity/pplx-embed-v1-0.6b`

Embeddings are created:

- during `setup()` while indexing documents
- during `retrieve()` when embedding the user's question

The same embedding model is used in both places to ensure vectors remain comparable.

Embedding vectors contain **1024 dimensions**.

---

# Vector Database

Qdrant is used as the vector database.

Configuration:

- Collection: `trackflow-knowledge-base`
- Distance metric: **Cosine**

Each indexed point contains:

- company
- source_document
- section
- language
- chunk_index
- text

Stable UUID5 identifiers are generated from the company, document name and chunk index.

The `setup()` function recreates the collection before indexing, making the indexing process idempotent and preventing duplicate vectors.

---

# Retrieval

`retrieve()` performs the following steps:

1. Embed the user's question.
2. Query Qdrant.
3. Return the most relevant chunks.

Configuration:

- `k = 5`
- `min_score = 0.30`

Results below the similarity threshold are discarded.

The retrieval layer returns structured chunk metadata internally, but these results are **never exposed by the public API**.

Measured retrieval quality:

**Recall@3 = 100% (8/8 evaluation questions)**

This exceeds the required minimum of **80%**.

---

# Generation

`query()` performs:

1. Retrieval
2. Prompt construction
3. DeepSeek generation

Generation model:

`downtown-miami/openrouter/deepseek/deepseek-v4-flash`

The model receives:

- a TrackFlow-specific system prompt
- the salesperson's question
- only the retrieved TrackFlow chunks

The prompt instructs the model to:

- answer as a TrackFlow salesperson
- only use retrieved context
- never invent policies
- refuse unsupported conditions

---

# Business Guardrails

The generation prompt explicitly enforces TrackFlow business rules.

Examples include:

- Never guarantee delivery during Black Friday, Christmas or January Sales.
- International returns always require manual handling.
- Storage discounts require Miguel Torres approval.
- Manual carrier selection requires Carlos Vega approval.

If the retrieved context does not support a requested condition, the assistant requests confirmation instead of inventing an answer.

---

# API

Endpoint:

`POST /knowledge/query`

Example request:

```json
{
  "question": "Which carrier best covers rural Aragón?"
}
```

Example response:

```json
{
  "answer": "For rural areas of Aragón, SEUR offers the best coverage according to our carrier information."
}
```

Only the generated answer is returned.

Raw retrieval results, similarity scores and chunk metadata are never exposed to the client.

---

# User Interface

The TrackFlow backoffice provides a dedicated `/knowledge` page.

Features include:

- natural-language questions
- loading state
- error handling
- generated answer
- responsive layout
- light mode
- dark mode

---

# Evaluation

Evaluation file:

`data/eval/test-queries.json`

Contains:

- 8 evaluation questions
- coverage for all four documents
- Black Friday scenario
- carrier coverage
- storage pricing
- returns policy
- delivery SLA

Measured Recall@3:

**100%**

---

# Testing

Unit tests verify:

- document loading
- minimum chunk count
- deterministic UUID generation
- empty embedding validation
- retrieval
- generation
- fallback responses
- similarity threshold
- fewer-than-k retrieval

Current result:

**9 tests passed**

---

# Conclusion

The completed TrackFlow RAG system satisfies the milestone requirements by:

- indexing company documentation into Qdrant
- retrieving relevant semantic context
- generating answers using a dedicated LLM
- preventing unsupported business commitments
- exposing a FastAPI endpoint
- providing a responsive backoffice interface
- achieving 100% Recall@3 on the evaluation dataset
- maintaining modular components that can be replaced independently