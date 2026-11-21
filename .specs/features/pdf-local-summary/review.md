# Review: local PDF summary

**Verdict:** Changes requested.

## Finding

- **[P2] Use the standard TextRank damping weights.** In the PageRank iteration, the uniform base probability was `0.85 / N` and graph propagation used `0.15`, which made sentence centrality too weak. Use `(1 - damping) / N` as the base and `damping` for weighted graph propagation. Add a regression case where a related group should outrank unrelated sentences.

The review also checked the page and sentence limits, the no-selectable-text error with no output, source sentence preservation, the bilingual disclosure, and the absence of any hosted inference path.

**Fix pass:** closed. The ranking now uses the standard damping equation, and the regression test verifies that 12 central energy-policy sentences rank ahead of three unrelated sentences. Full pytest, Ruff, JavaScript syntax, plan validation, and `git diff --check` passed after the fix.
