# Knowledge Base

This directory holds the retrieval corpus used by the RAG module. The shipped
documents are original summaries of widely accepted software engineering and
career-preparation principles, organised by theme. They are inspired by the
topics covered in well-known industry references (software engineering
practice, system design, resume writing, interview preparation, information
retrieval, and developer roadmaps) but contain no reproduced text from any
book.

The chunks are embedded with the platform's SBERT encoder and stored in a
persistent ChromaDB vector store (CHROMA_PATH, default models_store/chroma).
On startup only files that are new or changed since they were stored are
re-embedded, and deleted files are removed from the store.

To extend or correct the knowledge base, use Admin > RAG Knowledge Base
(add, edit or delete a document; only that document is re-embedded), or edit
the Markdown files here and click "Sync changes from disk"
(POST /api/v1/admin/rag/sync). "Rebuild vector store"
(POST /api/v1/admin/rag/rebuild) re-embeds everything from scratch.
