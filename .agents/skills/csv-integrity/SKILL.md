---
name: csv-integrity
description: Use when building or reviewing CSV ingestion, inference, input validation, malformed row recovery and data-quality reporting for Prooflytics.
---
# CSV integrity skill
1. Review FR-02 in PRD and docs/ACCEPTANCE.md before editing.
2. Define strict byte/encoding/size boundary, avoid silent errors.
3. Preserve raw cells, source row positions, explicit error reasons.
4. Use deterministic type inference with documented thresholds, distinguishing missing from invalid.
5. If parser cannot recover after malformed quote, reject visibly; don't pretend records were recovered.
6. Test normal, ragged, blank, invalid date, odd category, non-UTF8, oversize, malformed quote, quoted delimiters.
7. Reconcile accepted/rejected/issue counts; show actual pytest output.
