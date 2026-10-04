# Ablation Study — Keyword vs. Semantic vs. Hybrid

Source: `notebooks/Ablation_Study.ipynb` (executed 2026-09-05).
Workbook: `Fit4Job_Ablation_20260905_1104.xlsx` · Figures: `ablation_metrics.png`, `ablation_per_cv.png`

## Setup

30 candidate CVs, 1,711 IT job postings, top-10 retrieval depth, the same P@5 / P@10 /
MRR / NDCG@10 definitions used in `Model_Development.ipynb`. Each system ranks the whole
corpus; they differ only in the scoring function.

| # | System | Signal | Scoring |
|---|---|---|---|
| 1 | Keyword — Skill Overlap | lexical | Jaccard over taxonomy-normalised skill sets (α=0, β=1) |
| 2 | Keyword — BM25 | lexical | Okapi BM25 (k₁=1.5, b=0.75) over job text, CV text as query |
| 3 | Semantic — SBERT | dense | cosine over SBERT→PCA(128) vectors via FAISS HNSW (α=1, β=0) |
| 4 | Hybrid | both | **not re-run** — carried over from `Model_Development.ipynb` |

## Results

| System | Signal | P@5 | P@10 | MRR | NDCG@10 |
|---|---|---|---|---|---|
| Keyword (Skill Overlap) | lexical | 0.707 ± 0.363 | **0.697** ± 0.326 | 0.833 ± 0.324 | 0.791 ± 0.238 |
| Keyword (BM25) | lexical | 0.680 ± 0.313 | **0.697** ± 0.281 | 0.841 ± 0.307 | 0.781 ± 0.206 |
| Semantic (SBERT) | dense | **0.753** ± 0.335 | 0.670 ± 0.293 | **0.848** ± 0.316 | **0.820** ± 0.225 |
| Hybrid (SBERT + Keyword) ‡ | dense + lexical | 0.913 ± 0.146 | 0.867 ± 0.137 | 0.961 ± 0.150 | 0.927 ± 0.095 |

‡ Human-judged, carried over from `Model_Development.ipynb`. The other three rows share
one automatic judge and are **not** on the same scale as this row — see *Comparability*.

**Significance.** All 12 pairwise Wilcoxon signed-rank comparisons (paired over 30 CVs)
return *ns*. The strongest signal is SBERT over BM25 on NDCG@10: +0.039, *p* = 0.135,
rank-biserial *r* = −0.32 (medium effect).

## What the ablation shows

**SBERT is the better single ranker, on a trend this sample cannot confirm.** It takes
the best mean on P@5, MRR and NDCG@10, and loses only on P@10. Nothing reaches
*p* < 0.05 at n = 30, so the finding should be reported as a direction with its effect
size, not as a demonstrated improvement.

**Which metrics it wins is informative.** SBERT leads on every metric that rewards
*ordering* — P@5, MRR and NDCG@10 all depend on what sits at the top of the list and in
what sequence — and trails only on P@10, which merely counts how many relevant jobs
landed in the ten at all. The three systems surface a similar number of relevant jobs;
the dense signal is the one that puts the good ones first.

**The two lexical baselines are statistically indistinguishable from each other**
(*p* ≥ 0.60 on all four metrics), despite being very different functions — a narrow
Jaccard over ~750 canonical skills versus full-text BM25 over an 11,000-term vocabulary.
The ceiling appears to be a property of lexical matching itself, not of a particular
weighting scheme.

**The strongest argument for the hybrid is complementarity, not mean scores.** The
systems fail on *different* candidates (see `ablation_per_cv.png`):

| SBERT gains most (ΔNDCG@10) | Keyword wins most (ΔNDCG@10) |
|---|---|
| Research Scientist 1 · +0.61 | Software Engineer 2 · −0.89 |
| Data Engineer 1 · +0.37 | Data Analyst 1 · −0.44 |
| AI & ML Engineer 4 · +0.21 | Computer Engineer 1 · −0.42 |
| Data Scientist 1 · +0.20 | Full Stack Developer 2 · −0.38 |

SBERT gains where CV vocabulary does not match posting vocabulary; keyword matching wins
where a CV is a dense list of named technologies appearing verbatim in postings. Two
signals that fail on largely disjoint candidate sets are worth blending — which is the
design the deployed system already uses.

## Comparability — read before quoting the hybrid row

1. **Different judge.** The hybrid was graded by a human reading each posting. The three
   ablated systems are graded by an automatic rubric that maps the job title and the CV's
   target role onto IT role families (same family = A, adjacent = B, otherwise = C). Role
   family was chosen because it is the one signal *neither* system optimises — grading on
   skill overlap would hand the keyword systems their own objective as ground truth, and
   grading on embedding similarity would do the same for SBERT. The rubric is stricter
   than the human was (mean grade 0.50 vs 0.73; 78% binary agreement, Cohen's κ = 0.36).
   Scoring SBERT under both judges on identical rankings puts the offset at ≈ −0.12 on
   P@5, −0.14 on P@10, −0.03 on MRR and NDCG@10. A meaningful share of the distance
   between the ablated rows and the hybrid row is judge, not model.

2. **A ranking-order detail in the main notebook.** In `Model_Development.ipynb` §10 the
   top-10 list is built by iterating the FAISS results in cosine order; `hybrid_score` is
   computed as a display column and `result_df` is never sorted by it. The ranking that
   was labelled was therefore the **pure semantic** ranking, so the published hybrid
   figures describe the *retrieval* stage rather than the blend. The blend does reorder
   results in the deployed service, which over-fetches `3 × top_k` and sorts on
   `final_score` (`app/services/matching_service.py`).

**Consequence:** the study does not yet contain a like-for-like number for the hybrid.
Producing one costs one change in the notebook — set `RUN_HYBRID = True` in §1 and add
`rank_hybrid` to `RANKERS` in §6.4 — which measures the production path under the same
rubric judge as the other three rows, without touching the published figures.

## Limitations

- **n = 30.** Enough for paired non-parametric testing, not enough to reach significance
  on differences this size, nor to break results down by role family.
- **The rubric judge is blunt.** It reads the job title's role family and nothing else,
  so it cannot discriminate *within* a family. Since all three systems mostly retrieve
  same-family jobs, it likely compresses genuine differences — the most probable single
  explanation for twelve null results.
- **The available fix is human labelling.** `LABEL_MODE = 'manual'` in the notebook grades
  the 781 pooled pairs on the same A/B/C scale the main notebook used, persisting to
  `evaluation_results/ablation_qrels.json` so the work splits across sittings and is never
  repeated. That would put all four systems on one human-judged scale and remove both
  comparability caveats at once.
- **Pooled judgements, depth 10.** Relevance is known only for retrieved documents, so
  recall-oriented metrics are out of reach.
- **One corpus, one market.** 1,711 Sri Lankan IT postings; the exact margins will not
  transfer.
