# Independent annotation review protocol

> Status: ready for one independent second reviewer
> Scope: the existing 24-task refinement packet only

## Purpose

Measure whether the current draft codebook can be applied consistently before taxonomy changes or
a scaled label set. This is an agreement exercise, not a test of the first reviewer and not a
classifier benchmark.

## Reviewer instructions

1. Read `ANNOTATION_CODEBOOK_DRAFT.md` before opening either packet.
2. Review the two existing local HTML files independently. Do not view the first reviewer's
   verdicts, notes, aggregate manifest, or taxonomy-result summary first.
3. Assign exactly one of Yes, No, or Unsure to every task; use a short reasoning note only when it
   helps later adjudication, and never copy transcript text into a note.
4. Download each export and save it in `data/review/` under these exact names:
   `annotation_refinement_matches_second_reviewer_labels.json` and
   `annotation_refinement_controls_second_reviewer_labels.json`.
5. Keep all task pages, exports, and notes local. Do not upload or publish them.

## After review

Run `cnbr annotation-agreement --config configs/data/annotation_refinement_agreement.yaml`.
The result is aggregate-only: exact agreement, three-class Cohen's kappa, strata, disagreement
counts, and hashes. It excludes text, task IDs, reviewer notes, and individual verdicts.

Agreement does not itself freeze the taxonomy. The next decision is a documented adjudication and
locked-holdout allocation based on the observed disagreement pattern.

## Adjudication

Run `cnbr annotation-adjudication --config configs/data/annotation_refinement_adjudication.yaml`.
It creates a restricted local HTML page containing only disagreements, plus a text-free manifest.
Resolve every item and save the downloaded export as
`data/review/annotation_refinement_adjudications.json`. This export remains local and is the input
to the next adjudication-validation step.

## Final balanced pilot

The final pre-freeze packet contains 48 new tasks: eight lexical matches and eight lexical
nonmatches for each retained topic. It is non-overlapping with the earlier pilot and refinement
samples. Candidate topic remains visible because the reviewer must apply a topic-specific
definition; lexical selection mode is not displayed in the local HTML interface.

Both reviewers independently complete `annotation_balanced_matches.html` and
`annotation_balanced_controls.html`, each using the same codebook. Save the first reviewer's
exports as `annotation_balanced_matches_labels.json` and `annotation_balanced_controls_labels.json`;
save the second reviewer's exports with `_second_reviewer_labels` before `.json`. Do not inspect
the other reviewer's decisions before completing both packets.
