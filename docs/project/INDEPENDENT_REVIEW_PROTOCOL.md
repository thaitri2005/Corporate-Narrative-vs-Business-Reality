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
