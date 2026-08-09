"""L1 - Primitives.

A small, fixed set of generic tools with explicit contracts. Primitives
report what happened; they never decide whether a *goal* succeeded (that
judgment belongs to L2). A primitive that cannot be proven standalone is
never called by the executor.
"""
