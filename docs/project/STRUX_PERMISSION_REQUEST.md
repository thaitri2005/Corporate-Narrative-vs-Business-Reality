# STRUX transcript-dataset permission request

> Status: Archived; not required for the currently approved private/local portfolio scope
> Recipient: Yiming Lu, STRUX author/dataset publisher  
> Public professional contact located: `yiming.lu@emory.edu`  
> Do not record permission as granted until a written response and its scope are retained.

The project owner chose on 2026-09-05 to proceed without sending this request, accepting the
unresolved license risk only for private local analysis. This draft is retained as the ready path
if publication scope expands; no permission has been requested or granted.

## Draft email

**Subject:** Permission and license clarification for research use of STRUX Transcripts

Hello Yiming,

I am planning a non-commercial research project on whether within-company changes in earnings-call
narratives are associated with later changes in business fundamentals. The initial study is limited
to S&P 500 Consumer Staples companies and the 2017–2024 period.

The STRUX Transcripts dataset appears well suited to a feasibility study, but I could not find an
explicit dataset license or usage terms on the current Hugging Face dataset card. Before downloading
or processing transcript content, could you please confirm in writing:

1. whether we may download and store the dataset for non-commercial research;
2. whether transformations, NLP feature extraction, embeddings, and model training are permitted;
3. whether transcript text may be sent to third-party model APIs, or must remain local;
4. whether derived row-level features, aggregates, code, and trained weights may be published;
5. whether any raw or excerpted transcript text may be redistributed;
6. required attribution, retention/deletion obligations, and any upstream Motley Fool restrictions;
7. whether a formal license file or versioned terms can be added to the dataset repository.

We will keep raw transcripts out of Git and public releases, preserve source provenance, and honor
any limits you specify. A short reply is useful, though a repository license covering these points
would be preferable for reproducibility.

Thank you,

`[Your name / organization]`  
`[Your monitored contact email]`

## Response-record checklist

- Save the complete written response with date, sender, recipient, and dataset revision.
- Translate each answer into the SRC-001 acquisition/storage/transformation/API/release controls.
- Record unresolved ambiguity; silence is not permission.
- If acceptable, approve SRC-001 and update ADR-003. If declined or unclear at M1, evaluate an
  explicitly licensed replacement source.

## Public references used to route the request

- STRUX project: <https://struxdata.github.io/>
- Dataset publisher page: <https://huggingface.co/datasets/BUILDERlym/STRUX-Transcripts>
- Author CV: <https://builderlym.github.io/assets/CV_Yiming.pdf>
