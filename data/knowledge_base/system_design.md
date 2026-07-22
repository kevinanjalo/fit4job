# System Design Fundamentals

Start from requirements: expected traffic, data volume, latency targets and
consistency needs drive every other decision. Scale reads with caching and
replication; scale writes with partitioning and asynchronous processing.
Understand the trade-off triangle between consistency, availability and
partition tolerance, and choose per use case rather than globally. Use load
balancers for horizontal scaling, message queues to decouple producers from
consumers, and CDNs for static content. Design data models around access
patterns; denormalisation is acceptable when reads dominate. For search and
matching workloads, precompute embeddings or indexes offline and serve them
from memory-resident structures for low latency. Plan for failure: timeouts,
retries with backoff, circuit breakers, idempotent operations and observability
(structured logs, metrics, traces) are baseline requirements, not extras.
