# Transcript corpus contract

> Schema version: 1.0  
> Implementation: `src/cnbr/transcripts/normalize.py`

STRUX supplies call dates but not reliable start times or reported fiscal-quarter labels. The
normalization stage therefore preserves `call_date` at day precision and marks fiscal mapping
`pending`; it never manufactures a UTC timestamp or infers fiscal year from the calendar date.

## Calls

One row per source ticker/date with deterministic `call_id`, durable `company_id`, source revision
and row locator, participant/utterance counts, unknown-speaker count, and fiscal-mapping status.

## Participants

One row per source-listed participant plus a flagged synthetic row for each speaker observed in
speech but absent from that list. Source `Executive` and `Analyst` positions map directly;
`Operator` is an exact-name rule; source `Other` and unresolved names remain `unknown`. No fuzzy
name match silently assigns a role.

## Utterances

One row per source speech string. `sequence_no` is contiguous within each call, with prepared
remarks followed by Q&A exactly as represented by STRUX. Each row retains source turn/segment
coordinates, normalized and raw speaker names, participant reference, section, canonical role,
normalized text, text SHA-256, whitespace word count, exact-duplicate flag, and quality flags.

Canonical utterances are not overlapping model chunks. Later chunking must use a derivative table
with a parent utterance ID so quarterly aggregation cannot double count overlap.

## Quality and privacy rules

- Exact duplicate text of at least the configured word threshold is flagged, never silently removed.
- Unmatched speakers, inferred analyst labels, source footers, inaudible markers, blanks, and very
  short segments remain visible through flags.
- Transcript text remains in ignored/DVC-managed data and cannot enter logs, manifests, tests, or
  public reports. Tests use synthetic text only.
