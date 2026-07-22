# Software Engineering Practice

Software engineering is programming integrated over time: decisions must
account for how code will be read, changed and operated for years. Optimise
for readability first, since code is read far more often than it is written.
Keep modules deep: a small, simple interface hiding substantial functionality
reduces the cognitive load on every caller. Complexity accumulates through
dependencies and obscurity, so eliminate special cases, name things precisely,
and document the why, not the what. Invest in automated testing at multiple
levels; small hermetic tests catch regressions cheaply, while integration
tests validate behaviour across boundaries. Code review exists to share
knowledge and maintain a consistent standard, not to gatekeep. Prefer
incremental, reversible changes; large risky changes should be split behind
flags. Treat build, deployment and monitoring as part of the product.
