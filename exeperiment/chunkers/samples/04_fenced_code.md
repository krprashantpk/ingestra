---
description: Code fences, language labels, and literal Markdown inside longer fences.
---

# Code examples

## Python record processing

The following block is longer than 2048 tokens and must split at the default token
size. Inspect whether each embedding fragment repeats the Python fence.

```python
"""Prepare fictional document summaries without external services."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Review:
    """Describe the outcome of a document review."""

    identifier: str
    accepted: bool
    explanation: str


def describe_review(review: Review) -> str:
    """Return a readable review summary."""
    status = "accepted" if review.accepted else "needs revision"
    return f"{review.identifier}: {status}. {review.explanation}"


def describe_reviews(reviews: list[Review]) -> list[str]:
    """Return summaries in the supplied document order."""
    return [describe_review(review) for review in reviews]


reviews = [
    Review("DOC-101", True, "The supplied evidence supports the claim."),
    Review("DOC-102", False, "The revision date is missing."),
    Review("DOC-103", True, "The required attachments are present."),
    Review("DOC-1001", True, 'Revision identity: two drafts share a title but have different revision dates; reviewer should compare the stable identifier before accepting the newer draft; expected outcome: the original submission remains traceable after the title changes.'),
    Review("DOC-1002", False, 'Attachment recovery: the summary cites an attachment that was not supplied; reviewer should request the missing attachment without deleting the incomplete record; expected outcome: the next reviewer can distinguish missing evidence from contradictory evidence.'),
    Review("DOC-1003", False, "Ownership handoff: the current owner is unavailable during the next review window; reviewer should assign a named replacement and preserve the previous owner's observations; expected outcome: the replacement can continue without repeating every completed step."),
    Review("DOC-1004", True, 'Claim qualification: a conclusion is broader than the observation used to support it; reviewer should keep the qualification next to the claim and request a narrower conclusion; expected outcome: the published explanation does not imply stronger evidence than was collected.'),
    Review("DOC-1005", False, 'Duplicate detection: separate collections contain documents with similar display names; reviewer should inspect identity and revision metadata before merging any records; expected outcome: unrelated documents are not combined merely because their titles resemble each other.'),
    Review("DOC-1006", False, 'Publication readiness: a draft decision appears in the queue before approval is complete; reviewer should keep the draft visible to reviewers but withhold it from publication; expected outcome: readers can distinguish a provisional recommendation from a completed decision.'),
    Review("DOC-1007", True, 'Reference correction: a reference points to an earlier version of the supporting material; reviewer should update the reference while retaining the earlier citation in the history; expected outcome: future readers can reconstruct which evidence supported each version.'),
    Review("DOC-1008", False, "Calculation review: a comparison mixes one-time preparation with recurring effort; reviewer should separate the two categories and ask the author to explain the time horizon; expected outcome: the review states the comparison's limits without inventing missing amounts."),
    Review("DOC-1009", False, "Access verification: a reviewer can read a summary but cannot open a supporting record; reviewer should route the access question to the collection owner without sharing private content; expected outcome: permissions remain the owner's responsibility and the request is recorded."),
    Review("DOC-1010", True, 'Terminology alignment: two sections use the same label for different review states; reviewer should ask the author to define the distinction before renaming the displayed labels; expected outcome: the vocabulary remains consistent without erasing a meaningful difference.'),
    Review("DOC-1011", False, 'Scope boundary: a follow-up request introduces work outside the agreed review scope; reviewer should record the new question separately and identify who can authorize additional work; expected outcome: the current decision remains tied to the evidence actually inspected.'),
    Review("DOC-1012", False, 'Correction history: a published record needs a correction after a reader reports an omission; reviewer should add a dated correction linked to the original decision rather than replacing history; expected outcome: readers can tell what changed and why the earlier explanation was incomplete.'),
    Review("DOC-1013", True, 'Page attribution: a quotation is correct but its source page is not recorded; reviewer should attach the source page before copying the observation into the decision note; expected outcome: a later reader can inspect the complete surrounding explanation.'),
    Review("DOC-1014", False, 'Review deadline: the desired completion date arrives before the missing evidence; reviewer should communicate the unresolved dependency instead of recording an unsupported approval; expected outcome: the status reflects available evidence rather than calendar pressure.'),
    Review("DOC-1015", False, 'Collection mapping: the author selected a destination collection with a different naming convention; reviewer should confirm the destination with its owner while preserving the external identifier; expected outcome: moving the document does not sever its relationship to earlier revisions.'),
    Review("DOC-1016", True, 'Alternative interpretation: two observations support different explanations of the same event; reviewer should document both interpretations and identify what additional evidence would distinguish them; expected outcome: uncertainty is visible instead of being hidden behind a confident summary.'),
    Review("DOC-1017", False, 'Notification clarity: the author received a request that does not identify the affected revision; reviewer should send a corrected request containing the stable identifier and specific missing detail; expected outcome: the author can respond to the right question without guessing which draft was reviewed.'),
    Review("DOC-1018", False, 'Archive continuity: an archived draft still contains the clearest explanation of a past decision; reviewer should retain the historical explanation alongside the newer record; expected outcome: archiving changes visibility without discarding the reasoning behind earlier work.'),
    Review("DOC-1019", True, 'Readable export: an exported table loses the relationship between a group label and its rows; reviewer should inspect both rendered and raw representations before accepting the export; expected outcome: merged-cell relationships remain recoverable even when a fragment needs neighboring context.'),
    Review("DOC-1020", False, "Final reconciliation: the queue status and the final decision note disagree; reviewer should reconcile the status with the signed decision and record the reason for the correction; expected outcome: the document's visible state and retained explanation describe the same outcome."),
    Review("DOC-1021", False, 'Revision identity: two drafts share a title but have different revision dates; reviewer should compare the stable identifier before accepting the newer draft; expected outcome: the original submission remains traceable after the title changes.'),
    Review("DOC-1022", True, 'Attachment recovery: the summary cites an attachment that was not supplied; reviewer should request the missing attachment without deleting the incomplete record; expected outcome: the next reviewer can distinguish missing evidence from contradictory evidence.'),
    Review("DOC-1023", False, "Ownership handoff: the current owner is unavailable during the next review window; reviewer should assign a named replacement and preserve the previous owner's observations; expected outcome: the replacement can continue without repeating every completed step."),
    Review("DOC-1024", False, 'Claim qualification: a conclusion is broader than the observation used to support it; reviewer should keep the qualification next to the claim and request a narrower conclusion; expected outcome: the published explanation does not imply stronger evidence than was collected.'),
    Review("DOC-1025", True, 'Duplicate detection: separate collections contain documents with similar display names; reviewer should inspect identity and revision metadata before merging any records; expected outcome: unrelated documents are not combined merely because their titles resemble each other.'),
    Review("DOC-1026", False, 'Publication readiness: a draft decision appears in the queue before approval is complete; reviewer should keep the draft visible to reviewers but withhold it from publication; expected outcome: readers can distinguish a provisional recommendation from a completed decision.'),
    Review("DOC-1027", False, 'Reference correction: a reference points to an earlier version of the supporting material; reviewer should update the reference while retaining the earlier citation in the history; expected outcome: future readers can reconstruct which evidence supported each version.'),
    Review("DOC-1028", True, "Calculation review: a comparison mixes one-time preparation with recurring effort; reviewer should separate the two categories and ask the author to explain the time horizon; expected outcome: the review states the comparison's limits without inventing missing amounts."),
    Review("DOC-1029", False, "Access verification: a reviewer can read a summary but cannot open a supporting record; reviewer should route the access question to the collection owner without sharing private content; expected outcome: permissions remain the owner's responsibility and the request is recorded."),
    Review("DOC-1030", False, 'Terminology alignment: two sections use the same label for different review states; reviewer should ask the author to define the distinction before renaming the displayed labels; expected outcome: the vocabulary remains consistent without erasing a meaningful difference.'),
    Review("DOC-1031", True, 'Scope boundary: a follow-up request introduces work outside the agreed review scope; reviewer should record the new question separately and identify who can authorize additional work; expected outcome: the current decision remains tied to the evidence actually inspected.'),
    Review("DOC-1032", False, 'Correction history: a published record needs a correction after a reader reports an omission; reviewer should add a dated correction linked to the original decision rather than replacing history; expected outcome: readers can tell what changed and why the earlier explanation was incomplete.'),
    Review("DOC-1033", False, 'Page attribution: a quotation is correct but its source page is not recorded; reviewer should attach the source page before copying the observation into the decision note; expected outcome: a later reader can inspect the complete surrounding explanation.'),
    Review("DOC-1034", True, 'Review deadline: the desired completion date arrives before the missing evidence; reviewer should communicate the unresolved dependency instead of recording an unsupported approval; expected outcome: the status reflects available evidence rather than calendar pressure.'),
    Review("DOC-1035", False, 'Collection mapping: the author selected a destination collection with a different naming convention; reviewer should confirm the destination with its owner while preserving the external identifier; expected outcome: moving the document does not sever its relationship to earlier revisions.'),
    Review("DOC-1036", False, 'Alternative interpretation: two observations support different explanations of the same event; reviewer should document both interpretations and identify what additional evidence would distinguish them; expected outcome: uncertainty is visible instead of being hidden behind a confident summary.'),
    Review("DOC-1037", True, 'Notification clarity: the author received a request that does not identify the affected revision; reviewer should send a corrected request containing the stable identifier and specific missing detail; expected outcome: the author can respond to the right question without guessing which draft was reviewed.'),
    Review("DOC-1038", False, 'Archive continuity: an archived draft still contains the clearest explanation of a past decision; reviewer should retain the historical explanation alongside the newer record; expected outcome: archiving changes visibility without discarding the reasoning behind earlier work.'),
    Review("DOC-1039", False, 'Readable export: an exported table loses the relationship between a group label and its rows; reviewer should inspect both rendered and raw representations before accepting the export; expected outcome: merged-cell relationships remain recoverable even when a fragment needs neighboring context.'),
    Review("DOC-1040", True, "Final reconciliation: the queue status and the final decision note disagree; reviewer should reconcile the status with the signed decision and record the reason for the correction; expected outcome: the document's visible state and retained explanation describe the same outcome."),
    Review("DOC-1041", False, 'Revision identity: two drafts share a title but have different revision dates; reviewer should compare the stable identifier before accepting the newer draft; expected outcome: the original submission remains traceable after the title changes.'),
    Review("DOC-1042", False, 'Attachment recovery: the summary cites an attachment that was not supplied; reviewer should request the missing attachment without deleting the incomplete record; expected outcome: the next reviewer can distinguish missing evidence from contradictory evidence.'),
    Review("DOC-1043", True, "Ownership handoff: the current owner is unavailable during the next review window; reviewer should assign a named replacement and preserve the previous owner's observations; expected outcome: the replacement can continue without repeating every completed step."),
    Review("DOC-1044", False, 'Claim qualification: a conclusion is broader than the observation used to support it; reviewer should keep the qualification next to the claim and request a narrower conclusion; expected outcome: the published explanation does not imply stronger evidence than was collected.'),
    Review("DOC-1045", False, 'Duplicate detection: separate collections contain documents with similar display names; reviewer should inspect identity and revision metadata before merging any records; expected outcome: unrelated documents are not combined merely because their titles resemble each other.'),
    Review("DOC-1046", True, 'Publication readiness: a draft decision appears in the queue before approval is complete; reviewer should keep the draft visible to reviewers but withhold it from publication; expected outcome: readers can distinguish a provisional recommendation from a completed decision.'),
    Review("DOC-1047", False, 'Reference correction: a reference points to an earlier version of the supporting material; reviewer should update the reference while retaining the earlier citation in the history; expected outcome: future readers can reconstruct which evidence supported each version.'),
    Review("DOC-1048", False, "Calculation review: a comparison mixes one-time preparation with recurring effort; reviewer should separate the two categories and ask the author to explain the time horizon; expected outcome: the review states the comparison's limits without inventing missing amounts."),
    Review("DOC-1049", True, "Access verification: a reviewer can read a summary but cannot open a supporting record; reviewer should route the access question to the collection owner without sharing private content; expected outcome: permissions remain the owner's responsibility and the request is recorded."),
    Review("DOC-1050", False, 'Terminology alignment: two sections use the same label for different review states; reviewer should ask the author to define the distinction before renaming the displayed labels; expected outcome: the vocabulary remains consistent without erasing a meaningful difference.'),
    Review("DOC-1051", False, 'Scope boundary: a follow-up request introduces work outside the agreed review scope; reviewer should record the new question separately and identify who can authorize additional work; expected outcome: the current decision remains tied to the evidence actually inspected.'),
    Review("DOC-1052", True, 'Correction history: a published record needs a correction after a reader reports an omission; reviewer should add a dated correction linked to the original decision rather than replacing history; expected outcome: readers can tell what changed and why the earlier explanation was incomplete.'),
    Review("DOC-1053", False, 'Page attribution: a quotation is correct but its source page is not recorded; reviewer should attach the source page before copying the observation into the decision note; expected outcome: a later reader can inspect the complete surrounding explanation.'),
    Review("DOC-1054", False, 'Review deadline: the desired completion date arrives before the missing evidence; reviewer should communicate the unresolved dependency instead of recording an unsupported approval; expected outcome: the status reflects available evidence rather than calendar pressure.'),
    Review("DOC-1055", True, 'Collection mapping: the author selected a destination collection with a different naming convention; reviewer should confirm the destination with its owner while preserving the external identifier; expected outcome: moving the document does not sever its relationship to earlier revisions.'),
    Review("DOC-1056", False, 'Alternative interpretation: two observations support different explanations of the same event; reviewer should document both interpretations and identify what additional evidence would distinguish them; expected outcome: uncertainty is visible instead of being hidden behind a confident summary.'),
    Review("DOC-1057", False, 'Notification clarity: the author received a request that does not identify the affected revision; reviewer should send a corrected request containing the stable identifier and specific missing detail; expected outcome: the author can respond to the right question without guessing which draft was reviewed.'),
    Review("DOC-1058", True, 'Archive continuity: an archived draft still contains the clearest explanation of a past decision; reviewer should retain the historical explanation alongside the newer record; expected outcome: archiving changes visibility without discarding the reasoning behind earlier work.'),
    Review("DOC-1059", False, 'Readable export: an exported table loses the relationship between a group label and its rows; reviewer should inspect both rendered and raw representations before accepting the export; expected outcome: merged-cell relationships remain recoverable even when a fragment needs neighboring context.'),
    Review("DOC-1060", False, "Final reconciliation: the queue status and the final decision note disagree; reviewer should reconcile the status with the signed decision and record the reason for the correction; expected outcome: the document's visible state and retained explanation describe the same outcome."),
    Review("DOC-1061", True, 'Revision identity: two drafts share a title but have different revision dates; reviewer should compare the stable identifier before accepting the newer draft; expected outcome: the original submission remains traceable after the title changes.'),
    Review("DOC-1062", False, 'Attachment recovery: the summary cites an attachment that was not supplied; reviewer should request the missing attachment without deleting the incomplete record; expected outcome: the next reviewer can distinguish missing evidence from contradictory evidence.'),
    Review("DOC-1063", False, "Ownership handoff: the current owner is unavailable during the next review window; reviewer should assign a named replacement and preserve the previous owner's observations; expected outcome: the replacement can continue without repeating every completed step."),
    Review("DOC-1064", True, 'Claim qualification: a conclusion is broader than the observation used to support it; reviewer should keep the qualification next to the claim and request a narrower conclusion; expected outcome: the published explanation does not imply stronger evidence than was collected.'),
    Review("DOC-1065", False, 'Duplicate detection: separate collections contain documents with similar display names; reviewer should inspect identity and revision metadata before merging any records; expected outcome: unrelated documents are not combined merely because their titles resemble each other.'),
    Review("DOC-1066", False, 'Publication readiness: a draft decision appears in the queue before approval is complete; reviewer should keep the draft visible to reviewers but withhold it from publication; expected outcome: readers can distinguish a provisional recommendation from a completed decision.'),
    Review("DOC-1067", True, 'Reference correction: a reference points to an earlier version of the supporting material; reviewer should update the reference while retaining the earlier citation in the history; expected outcome: future readers can reconstruct which evidence supported each version.'),
    Review("DOC-1068", False, "Calculation review: a comparison mixes one-time preparation with recurring effort; reviewer should separate the two categories and ask the author to explain the time horizon; expected outcome: the review states the comparison's limits without inventing missing amounts."),
    Review("DOC-1069", False, "Access verification: a reviewer can read a summary but cannot open a supporting record; reviewer should route the access question to the collection owner without sharing private content; expected outcome: permissions remain the owner's responsibility and the request is recorded."),
    Review("DOC-1070", True, 'Terminology alignment: two sections use the same label for different review states; reviewer should ask the author to define the distinction before renaming the displayed labels; expected outcome: the vocabulary remains consistent without erasing a meaningful difference.'),
    Review("DOC-1071", False, 'Scope boundary: a follow-up request introduces work outside the agreed review scope; reviewer should record the new question separately and identify who can authorize additional work; expected outcome: the current decision remains tied to the evidence actually inspected.'),
    Review("DOC-1072", False, 'Correction history: a published record needs a correction after a reader reports an omission; reviewer should add a dated correction linked to the original decision rather than replacing history; expected outcome: readers can tell what changed and why the earlier explanation was incomplete.'),
    Review("DOC-1073", True, 'Page attribution: a quotation is correct but its source page is not recorded; reviewer should attach the source page before copying the observation into the decision note; expected outcome: a later reader can inspect the complete surrounding explanation.'),
    Review("DOC-1074", False, 'Review deadline: the desired completion date arrives before the missing evidence; reviewer should communicate the unresolved dependency instead of recording an unsupported approval; expected outcome: the status reflects available evidence rather than calendar pressure.'),
    Review("DOC-1075", False, 'Collection mapping: the author selected a destination collection with a different naming convention; reviewer should confirm the destination with its owner while preserving the external identifier; expected outcome: moving the document does not sever its relationship to earlier revisions.'),
    Review("DOC-1076", True, 'Alternative interpretation: two observations support different explanations of the same event; reviewer should document both interpretations and identify what additional evidence would distinguish them; expected outcome: uncertainty is visible instead of being hidden behind a confident summary.'),
    Review("DOC-1077", False, 'Notification clarity: the author received a request that does not identify the affected revision; reviewer should send a corrected request containing the stable identifier and specific missing detail; expected outcome: the author can respond to the right question without guessing which draft was reviewed.'),
    Review("DOC-1078", False, 'Archive continuity: an archived draft still contains the clearest explanation of a past decision; reviewer should retain the historical explanation alongside the newer record; expected outcome: archiving changes visibility without discarding the reasoning behind earlier work.'),
    Review("DOC-1079", True, 'Readable export: an exported table loses the relationship between a group label and its rows; reviewer should inspect both rendered and raw representations before accepting the export; expected outcome: merged-cell relationships remain recoverable even when a fragment needs neighboring context.'),
    Review("DOC-1080", False, "Final reconciliation: the queue status and the final decision note disagree; reviewer should reconcile the status with the signed decision and record the reason for the correction; expected outcome: the document's visible state and retained explanation describe the same outcome."),
    Review("DOC-1081", False, 'Revision identity: two drafts share a title but have different revision dates; reviewer should compare the stable identifier before accepting the newer draft; expected outcome: the original submission remains traceable after the title changes.'),
    Review("DOC-1082", True, 'Attachment recovery: the summary cites an attachment that was not supplied; reviewer should request the missing attachment without deleting the incomplete record; expected outcome: the next reviewer can distinguish missing evidence from contradictory evidence.'),
    Review("DOC-1083", False, "Ownership handoff: the current owner is unavailable during the next review window; reviewer should assign a named replacement and preserve the previous owner's observations; expected outcome: the replacement can continue without repeating every completed step."),
    Review("DOC-1084", False, 'Claim qualification: a conclusion is broader than the observation used to support it; reviewer should keep the qualification next to the claim and request a narrower conclusion; expected outcome: the published explanation does not imply stronger evidence than was collected.'),
    Review("DOC-1085", True, 'Duplicate detection: separate collections contain documents with similar display names; reviewer should inspect identity and revision metadata before merging any records; expected outcome: unrelated documents are not combined merely because their titles resemble each other.'),
    Review("DOC-1086", False, 'Publication readiness: a draft decision appears in the queue before approval is complete; reviewer should keep the draft visible to reviewers but withhold it from publication; expected outcome: readers can distinguish a provisional recommendation from a completed decision.'),
    Review("DOC-1087", False, 'Reference correction: a reference points to an earlier version of the supporting material; reviewer should update the reference while retaining the earlier citation in the history; expected outcome: future readers can reconstruct which evidence supported each version.'),
]
summaries = describe_reviews(reviews)
```

## Literal Markdown

This four-backtick fence contains a shorter fence and a page marker. Neither
the heading nor page 99 should become document structure.

````markdown
# A heading inside an example

```text
This shorter fence does not close the outer example.
```

<!-- InputPageNumber: 99 -->

| Example | Value |
|---------|-------|
| Alpha   | One   |
````

## JSON configuration

```json
{
  "collection": "reviewed-documents",
  "retain_source": true,
  "review_states": ["received", "assigned", "complete"]
}
```
