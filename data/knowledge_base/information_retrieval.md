# Information Retrieval and Semantic Matching

Classical retrieval represents documents as sparse term vectors weighted by
term frequency and inverse document frequency, ranking by cosine similarity.
This fails when different words express the same meaning. Dense retrieval
addresses the vocabulary mismatch by encoding text into low-dimensional
semantic vectors with transformer encoders such as SBERT; semantically related
texts land near each other regardless of shared tokens. At scale, exact
nearest-neighbour search is too slow, so approximate indexes such as HNSW
graphs trade a small recall loss for logarithmic query time. Dimensionality
reduction (for example PCA from 384 to 128 dimensions) shrinks memory with
minimal quality loss. Evaluate ranking systems with Precision@K, Mean
Reciprocal Rank and NDCG, and combine semantic similarity with exact skill
overlap for job matching so that hard requirements are not lost.
