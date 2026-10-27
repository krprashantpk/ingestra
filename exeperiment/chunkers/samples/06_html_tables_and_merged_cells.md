---
description: HTML tables with explicit headers, row groups, and merged cells.
---

# Grouped review workload

## Team assignments

HTML is intentional here because pipe tables cannot express merged cells.
The paired rows in each team group share a label through a rowspan.

<table>
  <thead>
    <tr><th>Team</th><th>Document</th><th>Review action</th></tr>
  </thead>
  <tbody>
    <tr><td rowspan="2">Research</td><td>DOC-201</td><td>Check the primary observation and its supporting notes.</td></tr>
    <tr><td>DOC-202</td><td>Compare the revised interpretation with the original question.</td></tr>
    <tr><td rowspan="2">Operations</td><td>DOC-203</td><td>Confirm that the workflow has a named owner.</td></tr>
    <tr><td>DOC-204</td><td>Document the handoff between the two review stages.</td></tr>
    <tr><td rowspan="2">Finance</td><td>DOC-205</td><td>Inspect the assumptions used in the comparison.</td></tr>
    <tr><td>DOC-206</td><td>Separate recurring costs from one-time preparation.</td></tr>
    <tr><td rowspan="2">Support</td><td>DOC-207</td><td>Check the explanation shown when an attachment is absent.</td></tr>
    <tr><td>DOC-208</td><td>Verify that the follow-up request identifies the document.</td></tr>
    <tr><td rowspan="2">Publishing</td><td>DOC-209</td><td>Confirm that the final summary matches the decision.</td></tr>
    <tr><td>DOC-210</td><td>Retain the revision history with the published record.</td></tr>
    <tr><td rowspan="2">Editorial batch 001</td><td>DOC-211</td><td>two drafts share a title but have different revision dates; inspect a signed revision log and the original submission receipt.</td></tr>
    <tr><td>DOC-212</td><td>Follow-up: compare the stable identifier before accepting the newer draft; expected outcome: the original submission remains traceable after the title changes.</td></tr>
    <tr><td rowspan="2">Intake batch 002</td><td>DOC-213</td><td>the summary cites an attachment that was not supplied; inspect the attachment manifest and the author&#x27;s list of supporting records.</td></tr>
    <tr><td>DOC-214</td><td>Follow-up: request the missing attachment without deleting the incomplete record; expected outcome: the next reviewer can distinguish missing evidence from contradictory evidence.</td></tr>
    <tr><td rowspan="2">Operations batch 003</td><td>DOC-215</td><td>the current owner is unavailable during the next review window; inspect a handoff note identifying the completed checks and remaining questions.</td></tr>
    <tr><td>DOC-216</td><td>Follow-up: assign a named replacement and preserve the previous owner&#x27;s observations; expected outcome: the replacement can continue without repeating every completed step.</td></tr>
    <tr><td rowspan="2">Research batch 004</td><td>DOC-217</td><td>a conclusion is broader than the observation used to support it; inspect the original observation and the conditions under which it was recorded.</td></tr>
    <tr><td>DOC-218</td><td>Follow-up: keep the qualification next to the claim and request a narrower conclusion; expected outcome: the published explanation does not imply stronger evidence than was collected.</td></tr>
    <tr><td rowspan="2">Catalog batch 005</td><td>DOC-219</td><td>separate collections contain documents with similar display names; inspect external identifiers and the collection membership history.</td></tr>
    <tr><td>DOC-220</td><td>Follow-up: inspect identity and revision metadata before merging any records; expected outcome: unrelated documents are not combined merely because their titles resemble each other.</td></tr>
    <tr><td rowspan="2">Publishing batch 006</td><td>DOC-221</td><td>a draft decision appears in the queue before approval is complete; inspect the approval checklist and the final reviewer&#x27;s decision note.</td></tr>
    <tr><td>DOC-222</td><td>Follow-up: keep the draft visible to reviewers but withhold it from publication; expected outcome: readers can distinguish a provisional recommendation from a completed decision.</td></tr>
    <tr><td rowspan="2">Documentation batch 007</td><td>DOC-223</td><td>a reference points to an earlier version of the supporting material; inspect the cited record identifier and the replacement document&#x27;s revision log.</td></tr>
    <tr><td>DOC-224</td><td>Follow-up: update the reference while retaining the earlier citation in the history; expected outcome: future readers can reconstruct which evidence supported each version.</td></tr>
    <tr><td rowspan="2">Finance batch 008</td><td>DOC-225</td><td>a comparison mixes one-time preparation with recurring effort; inspect the assumptions register and the itemized comparison worksheet.</td></tr>
    <tr><td>DOC-226</td><td>Follow-up: separate the two categories and ask the author to explain the time horizon; expected outcome: the review states the comparison&#x27;s limits without inventing missing amounts.</td></tr>
    <tr><td rowspan="2">Administration batch 009</td><td>DOC-227</td><td>a reviewer can read a summary but cannot open a supporting record; inspect the workspace membership list and the record&#x27;s intended audience.</td></tr>
    <tr><td>DOC-228</td><td>Follow-up: route the access question to the collection owner without sharing private content; expected outcome: permissions remain the owner&#x27;s responsibility and the request is recorded.</td></tr>
    <tr><td rowspan="2">Editorial batch 010</td><td>DOC-229</td><td>two sections use the same label for different review states; inspect the glossary and examples from each affected section.</td></tr>
    <tr><td>DOC-230</td><td>Follow-up: ask the author to define the distinction before renaming the displayed labels; expected outcome: the vocabulary remains consistent without erasing a meaningful difference.</td></tr>
    <tr><td rowspan="2">Research batch 011</td><td>DOC-231</td><td>a follow-up request introduces work outside the agreed review scope; inspect the original review question and the list of excluded material.</td></tr>
    <tr><td>DOC-232</td><td>Follow-up: record the new question separately and identify who can authorize additional work; expected outcome: the current decision remains tied to the evidence actually inspected.</td></tr>
    <tr><td rowspan="2">Support batch 012</td><td>DOC-233</td><td>a published record needs a correction after a reader reports an omission; inspect the reader&#x27;s question and the prior publication snapshot.</td></tr>
    <tr><td>DOC-234</td><td>Follow-up: add a dated correction linked to the original decision rather than replacing history; expected outcome: readers can tell what changed and why the earlier explanation was incomplete.</td></tr>
    <tr><td rowspan="2">Documentation batch 013</td><td>DOC-235</td><td>a quotation is correct but its source page is not recorded; inspect the paged packet and the location of the quoted observation.</td></tr>
    <tr><td>DOC-236</td><td>Follow-up: attach the source page before copying the observation into the decision note; expected outcome: a later reader can inspect the complete surrounding explanation.</td></tr>
    <tr><td rowspan="2">Operations batch 014</td><td>DOC-237</td><td>the desired completion date arrives before the missing evidence; inspect the intake timestamp and the outstanding information request.</td></tr>
    <tr><td>DOC-238</td><td>Follow-up: communicate the unresolved dependency instead of recording an unsupported approval; expected outcome: the status reflects available evidence rather than calendar pressure.</td></tr>
    <tr><td rowspan="2">Catalog batch 015</td><td>DOC-239</td><td>the author selected a destination collection with a different naming convention; inspect the collection rules and the author&#x27;s original document identifier.</td></tr>
    <tr><td>DOC-240</td><td>Follow-up: confirm the destination with its owner while preserving the external identifier; expected outcome: moving the document does not sever its relationship to earlier revisions.</td></tr>
    <tr><td rowspan="2">Research batch 016</td><td>DOC-241</td><td>two observations support different explanations of the same event; inspect the observation notes and each explanation&#x27;s stated assumptions.</td></tr>
    <tr><td>DOC-242</td><td>Follow-up: document both interpretations and identify what additional evidence would distinguish them; expected outcome: uncertainty is visible instead of being hidden behind a confident summary.</td></tr>
    <tr><td rowspan="2">Support batch 017</td><td>DOC-243</td><td>the author received a request that does not identify the affected revision; inspect the outgoing message and the current revision&#x27;s open questions.</td></tr>
    <tr><td>DOC-244</td><td>Follow-up: send a corrected request containing the stable identifier and specific missing detail; expected outcome: the author can respond to the right question without guessing which draft was reviewed.</td></tr>
    <tr><td rowspan="2">Publishing batch 018</td><td>DOC-245</td><td>an archived draft still contains the clearest explanation of a past decision; inspect the archived discussion and the published revision&#x27;s decision summary.</td></tr>
    <tr><td>DOC-246</td><td>Follow-up: retain the historical explanation alongside the newer record; expected outcome: archiving changes visibility without discarding the reasoning behind earlier work.</td></tr>
    <tr><td rowspan="2">Documentation batch 019</td><td>DOC-247</td><td>an exported table loses the relationship between a group label and its rows; inspect the original grouped register and the exported text.</td></tr>
    <tr><td>DOC-248</td><td>Follow-up: inspect both rendered and raw representations before accepting the export; expected outcome: merged-cell relationships remain recoverable even when a fragment needs neighboring context.</td></tr>
    <tr><td rowspan="2">Intake batch 020</td><td>DOC-249</td><td>the queue status and the final decision note disagree; inspect the last state transition and the reviewer&#x27;s completion checklist.</td></tr>
    <tr><td>DOC-250</td><td>Follow-up: reconcile the status with the signed decision and record the reason for the correction; expected outcome: the document&#x27;s visible state and retained explanation describe the same outcome.</td></tr>
    <tr><td rowspan="2">Editorial batch 021</td><td>DOC-251</td><td>two drafts share a title but have different revision dates; inspect a signed revision log and the original submission receipt.</td></tr>
    <tr><td>DOC-252</td><td>Follow-up: compare the stable identifier before accepting the newer draft; expected outcome: the original submission remains traceable after the title changes.</td></tr>
    <tr><td rowspan="2">Intake batch 022</td><td>DOC-253</td><td>the summary cites an attachment that was not supplied; inspect the attachment manifest and the author&#x27;s list of supporting records.</td></tr>
    <tr><td>DOC-254</td><td>Follow-up: request the missing attachment without deleting the incomplete record; expected outcome: the next reviewer can distinguish missing evidence from contradictory evidence.</td></tr>
    <tr><td rowspan="2">Operations batch 023</td><td>DOC-255</td><td>the current owner is unavailable during the next review window; inspect a handoff note identifying the completed checks and remaining questions.</td></tr>
    <tr><td>DOC-256</td><td>Follow-up: assign a named replacement and preserve the previous owner&#x27;s observations; expected outcome: the replacement can continue without repeating every completed step.</td></tr>
    <tr><td rowspan="2">Research batch 024</td><td>DOC-257</td><td>a conclusion is broader than the observation used to support it; inspect the original observation and the conditions under which it was recorded.</td></tr>
    <tr><td>DOC-258</td><td>Follow-up: keep the qualification next to the claim and request a narrower conclusion; expected outcome: the published explanation does not imply stronger evidence than was collected.</td></tr>
    <tr><td rowspan="2">Catalog batch 025</td><td>DOC-259</td><td>separate collections contain documents with similar display names; inspect external identifiers and the collection membership history.</td></tr>
    <tr><td>DOC-260</td><td>Follow-up: inspect identity and revision metadata before merging any records; expected outcome: unrelated documents are not combined merely because their titles resemble each other.</td></tr>
    <tr><td rowspan="2">Publishing batch 026</td><td>DOC-261</td><td>a draft decision appears in the queue before approval is complete; inspect the approval checklist and the final reviewer&#x27;s decision note.</td></tr>
    <tr><td>DOC-262</td><td>Follow-up: keep the draft visible to reviewers but withhold it from publication; expected outcome: readers can distinguish a provisional recommendation from a completed decision.</td></tr>
    <tr><td rowspan="2">Documentation batch 027</td><td>DOC-263</td><td>a reference points to an earlier version of the supporting material; inspect the cited record identifier and the replacement document&#x27;s revision log.</td></tr>
    <tr><td>DOC-264</td><td>Follow-up: update the reference while retaining the earlier citation in the history; expected outcome: future readers can reconstruct which evidence supported each version.</td></tr>
    <tr><td rowspan="2">Finance batch 028</td><td>DOC-265</td><td>a comparison mixes one-time preparation with recurring effort; inspect the assumptions register and the itemized comparison worksheet.</td></tr>
    <tr><td>DOC-266</td><td>Follow-up: separate the two categories and ask the author to explain the time horizon; expected outcome: the review states the comparison&#x27;s limits without inventing missing amounts.</td></tr>
    <tr><td rowspan="2">Administration batch 029</td><td>DOC-267</td><td>a reviewer can read a summary but cannot open a supporting record; inspect the workspace membership list and the record&#x27;s intended audience.</td></tr>
    <tr><td>DOC-268</td><td>Follow-up: route the access question to the collection owner without sharing private content; expected outcome: permissions remain the owner&#x27;s responsibility and the request is recorded.</td></tr>
    <tr><td rowspan="2">Editorial batch 030</td><td>DOC-269</td><td>two sections use the same label for different review states; inspect the glossary and examples from each affected section.</td></tr>
    <tr><td>DOC-270</td><td>Follow-up: ask the author to define the distinction before renaming the displayed labels; expected outcome: the vocabulary remains consistent without erasing a meaningful difference.</td></tr>
    <tr><td rowspan="2">Research batch 031</td><td>DOC-271</td><td>a follow-up request introduces work outside the agreed review scope; inspect the original review question and the list of excluded material.</td></tr>
    <tr><td>DOC-272</td><td>Follow-up: record the new question separately and identify who can authorize additional work; expected outcome: the current decision remains tied to the evidence actually inspected.</td></tr>
    <tr><td rowspan="2">Support batch 032</td><td>DOC-273</td><td>a published record needs a correction after a reader reports an omission; inspect the reader&#x27;s question and the prior publication snapshot.</td></tr>
    <tr><td>DOC-274</td><td>Follow-up: add a dated correction linked to the original decision rather than replacing history; expected outcome: readers can tell what changed and why the earlier explanation was incomplete.</td></tr>
    <tr><td rowspan="2">Documentation batch 033</td><td>DOC-275</td><td>a quotation is correct but its source page is not recorded; inspect the paged packet and the location of the quoted observation.</td></tr>
    <tr><td>DOC-276</td><td>Follow-up: attach the source page before copying the observation into the decision note; expected outcome: a later reader can inspect the complete surrounding explanation.</td></tr>
    <tr><td rowspan="2">Operations batch 034</td><td>DOC-277</td><td>the desired completion date arrives before the missing evidence; inspect the intake timestamp and the outstanding information request.</td></tr>
    <tr><td>DOC-278</td><td>Follow-up: communicate the unresolved dependency instead of recording an unsupported approval; expected outcome: the status reflects available evidence rather than calendar pressure.</td></tr>
    <tr><td rowspan="2">Catalog batch 035</td><td>DOC-279</td><td>the author selected a destination collection with a different naming convention; inspect the collection rules and the author&#x27;s original document identifier.</td></tr>
    <tr><td>DOC-280</td><td>Follow-up: confirm the destination with its owner while preserving the external identifier; expected outcome: moving the document does not sever its relationship to earlier revisions.</td></tr>
    <tr><td rowspan="2">Research batch 036</td><td>DOC-281</td><td>two observations support different explanations of the same event; inspect the observation notes and each explanation&#x27;s stated assumptions.</td></tr>
    <tr><td>DOC-282</td><td>Follow-up: document both interpretations and identify what additional evidence would distinguish them; expected outcome: uncertainty is visible instead of being hidden behind a confident summary.</td></tr>
    <tr><td rowspan="2">Support batch 037</td><td>DOC-283</td><td>the author received a request that does not identify the affected revision; inspect the outgoing message and the current revision&#x27;s open questions.</td></tr>
    <tr><td>DOC-284</td><td>Follow-up: send a corrected request containing the stable identifier and specific missing detail; expected outcome: the author can respond to the right question without guessing which draft was reviewed.</td></tr>
    <tr><td rowspan="2">Publishing batch 038</td><td>DOC-285</td><td>an archived draft still contains the clearest explanation of a past decision; inspect the archived discussion and the published revision&#x27;s decision summary.</td></tr>
    <tr><td>DOC-286</td><td>Follow-up: retain the historical explanation alongside the newer record; expected outcome: archiving changes visibility without discarding the reasoning behind earlier work.</td></tr>
    <tr><td rowspan="2">Documentation batch 039</td><td>DOC-287</td><td>an exported table loses the relationship between a group label and its rows; inspect the original grouped register and the exported text.</td></tr>
    <tr><td>DOC-288</td><td>Follow-up: inspect both rendered and raw representations before accepting the export; expected outcome: merged-cell relationships remain recoverable even when a fragment needs neighboring context.</td></tr>
    <tr><td rowspan="2">Intake batch 040</td><td>DOC-289</td><td>the queue status and the final decision note disagree; inspect the last state transition and the reviewer&#x27;s completion checklist.</td></tr>
    <tr><td>DOC-290</td><td>Follow-up: reconcile the status with the signed decision and record the reason for the correction; expected outcome: the document&#x27;s visible state and retained explanation describe the same outcome.</td></tr>
    <tr><td rowspan="2">Editorial batch 041</td><td>DOC-291</td><td>two drafts share a title but have different revision dates; inspect a signed revision log and the original submission receipt.</td></tr>
    <tr><td>DOC-292</td><td>Follow-up: compare the stable identifier before accepting the newer draft; expected outcome: the original submission remains traceable after the title changes.</td></tr>
    <tr><td rowspan="2">Intake batch 042</td><td>DOC-293</td><td>the summary cites an attachment that was not supplied; inspect the attachment manifest and the author&#x27;s list of supporting records.</td></tr>
    <tr><td>DOC-294</td><td>Follow-up: request the missing attachment without deleting the incomplete record; expected outcome: the next reviewer can distinguish missing evidence from contradictory evidence.</td></tr>
    <tr><td rowspan="2">Operations batch 043</td><td>DOC-295</td><td>the current owner is unavailable during the next review window; inspect a handoff note identifying the completed checks and remaining questions.</td></tr>
    <tr><td>DOC-296</td><td>Follow-up: assign a named replacement and preserve the previous owner&#x27;s observations; expected outcome: the replacement can continue without repeating every completed step.</td></tr>
    <tr><td rowspan="2">Research batch 044</td><td>DOC-297</td><td>a conclusion is broader than the observation used to support it; inspect the original observation and the conditions under which it was recorded.</td></tr>
    <tr><td>DOC-298</td><td>Follow-up: keep the qualification next to the claim and request a narrower conclusion; expected outcome: the published explanation does not imply stronger evidence than was collected.</td></tr>
    <tr><td colspan="2">Total documents</td><td>98 fictional documents are represented.</td></tr>
  </tbody>
</table>

## A headerless table

This table uses row labels rather than column headers. The chunker should not
invent a repeated column header from the first row.

<table>
  <tr><td>Collection</td><td>Internal review examples</td></tr>
  <tr><td>Owner</td><td>Document services team</td></tr>
  <tr><td>Retention</td><td>Keep the source with the review record</td></tr>
  <tr><td>Visibility</td><td>Fictional demonstration data only</td></tr>
  <tr><td>Audit setting 001</td><td>Revision identity: compare the stable identifier before accepting the newer draft; the original submission remains traceable after the title changes.</td></tr>
  <tr><td>Audit setting 002</td><td>Attachment recovery: request the missing attachment without deleting the incomplete record; the next reviewer can distinguish missing evidence from contradictory evidence.</td></tr>
  <tr><td>Audit setting 003</td><td>Ownership handoff: assign a named replacement and preserve the previous owner&#x27;s observations; the replacement can continue without repeating every completed step.</td></tr>
  <tr><td>Audit setting 004</td><td>Claim qualification: keep the qualification next to the claim and request a narrower conclusion; the published explanation does not imply stronger evidence than was collected.</td></tr>
  <tr><td>Audit setting 005</td><td>Duplicate detection: inspect identity and revision metadata before merging any records; unrelated documents are not combined merely because their titles resemble each other.</td></tr>
  <tr><td>Audit setting 006</td><td>Publication readiness: keep the draft visible to reviewers but withhold it from publication; readers can distinguish a provisional recommendation from a completed decision.</td></tr>
  <tr><td>Audit setting 007</td><td>Reference correction: update the reference while retaining the earlier citation in the history; future readers can reconstruct which evidence supported each version.</td></tr>
  <tr><td>Audit setting 008</td><td>Calculation review: separate the two categories and ask the author to explain the time horizon; the review states the comparison&#x27;s limits without inventing missing amounts.</td></tr>
  <tr><td>Audit setting 009</td><td>Access verification: route the access question to the collection owner without sharing private content; permissions remain the owner&#x27;s responsibility and the request is recorded.</td></tr>
  <tr><td>Audit setting 010</td><td>Terminology alignment: ask the author to define the distinction before renaming the displayed labels; the vocabulary remains consistent without erasing a meaningful difference.</td></tr>
  <tr><td>Audit setting 011</td><td>Scope boundary: record the new question separately and identify who can authorize additional work; the current decision remains tied to the evidence actually inspected.</td></tr>
  <tr><td>Audit setting 012</td><td>Correction history: add a dated correction linked to the original decision rather than replacing history; readers can tell what changed and why the earlier explanation was incomplete.</td></tr>
  <tr><td>Audit setting 013</td><td>Page attribution: attach the source page before copying the observation into the decision note; a later reader can inspect the complete surrounding explanation.</td></tr>
  <tr><td>Audit setting 014</td><td>Review deadline: communicate the unresolved dependency instead of recording an unsupported approval; the status reflects available evidence rather than calendar pressure.</td></tr>
  <tr><td>Audit setting 015</td><td>Collection mapping: confirm the destination with its owner while preserving the external identifier; moving the document does not sever its relationship to earlier revisions.</td></tr>
  <tr><td>Audit setting 016</td><td>Alternative interpretation: document both interpretations and identify what additional evidence would distinguish them; uncertainty is visible instead of being hidden behind a confident summary.</td></tr>
  <tr><td>Audit setting 017</td><td>Notification clarity: send a corrected request containing the stable identifier and specific missing detail; the author can respond to the right question without guessing which draft was reviewed.</td></tr>
  <tr><td>Audit setting 018</td><td>Archive continuity: retain the historical explanation alongside the newer record; archiving changes visibility without discarding the reasoning behind earlier work.</td></tr>
  <tr><td>Audit setting 019</td><td>Readable export: inspect both rendered and raw representations before accepting the export; merged-cell relationships remain recoverable even when a fragment needs neighboring context.</td></tr>
  <tr><td>Audit setting 020</td><td>Final reconciliation: reconcile the status with the signed decision and record the reason for the correction; the document&#x27;s visible state and retained explanation describe the same outcome.</td></tr>
  <tr><td>Audit setting 021</td><td>Revision identity: compare the stable identifier before accepting the newer draft; the original submission remains traceable after the title changes.</td></tr>
  <tr><td>Audit setting 022</td><td>Attachment recovery: request the missing attachment without deleting the incomplete record; the next reviewer can distinguish missing evidence from contradictory evidence.</td></tr>
  <tr><td>Audit setting 023</td><td>Ownership handoff: assign a named replacement and preserve the previous owner&#x27;s observations; the replacement can continue without repeating every completed step.</td></tr>
  <tr><td>Audit setting 024</td><td>Claim qualification: keep the qualification next to the claim and request a narrower conclusion; the published explanation does not imply stronger evidence than was collected.</td></tr>
  <tr><td>Audit setting 025</td><td>Duplicate detection: inspect identity and revision metadata before merging any records; unrelated documents are not combined merely because their titles resemble each other.</td></tr>
  <tr><td>Audit setting 026</td><td>Publication readiness: keep the draft visible to reviewers but withhold it from publication; readers can distinguish a provisional recommendation from a completed decision.</td></tr>
  <tr><td>Audit setting 027</td><td>Reference correction: update the reference while retaining the earlier citation in the history; future readers can reconstruct which evidence supported each version.</td></tr>
  <tr><td>Audit setting 028</td><td>Calculation review: separate the two categories and ask the author to explain the time horizon; the review states the comparison&#x27;s limits without inventing missing amounts.</td></tr>
  <tr><td>Audit setting 029</td><td>Access verification: route the access question to the collection owner without sharing private content; permissions remain the owner&#x27;s responsibility and the request is recorded.</td></tr>
  <tr><td>Audit setting 030</td><td>Terminology alignment: ask the author to define the distinction before renaming the displayed labels; the vocabulary remains consistent without erasing a meaningful difference.</td></tr>
  <tr><td>Audit setting 031</td><td>Scope boundary: record the new question separately and identify who can authorize additional work; the current decision remains tied to the evidence actually inspected.</td></tr>
  <tr><td>Audit setting 032</td><td>Correction history: add a dated correction linked to the original decision rather than replacing history; readers can tell what changed and why the earlier explanation was incomplete.</td></tr>
  <tr><td>Audit setting 033</td><td>Page attribution: attach the source page before copying the observation into the decision note; a later reader can inspect the complete surrounding explanation.</td></tr>
  <tr><td>Audit setting 034</td><td>Review deadline: communicate the unresolved dependency instead of recording an unsupported approval; the status reflects available evidence rather than calendar pressure.</td></tr>
  <tr><td>Audit setting 035</td><td>Collection mapping: confirm the destination with its owner while preserving the external identifier; moving the document does not sever its relationship to earlier revisions.</td></tr>
  <tr><td>Audit setting 036</td><td>Alternative interpretation: document both interpretations and identify what additional evidence would distinguish them; uncertainty is visible instead of being hidden behind a confident summary.</td></tr>
  <tr><td>Audit setting 037</td><td>Notification clarity: send a corrected request containing the stable identifier and specific missing detail; the author can respond to the right question without guessing which draft was reviewed.</td></tr>
  <tr><td>Audit setting 038</td><td>Archive continuity: retain the historical explanation alongside the newer record; archiving changes visibility without discarding the reasoning behind earlier work.</td></tr>
  <tr><td>Audit setting 039</td><td>Readable export: inspect both rendered and raw representations before accepting the export; merged-cell relationships remain recoverable even when a fragment needs neighboring context.</td></tr>
  <tr><td>Audit setting 040</td><td>Final reconciliation: reconcile the status with the signed decision and record the reason for the correction; the document&#x27;s visible state and retained explanation describe the same outcome.</td></tr>
  <tr><td>Audit setting 041</td><td>Revision identity: compare the stable identifier before accepting the newer draft; the original submission remains traceable after the title changes.</td></tr>
  <tr><td>Audit setting 042</td><td>Attachment recovery: request the missing attachment without deleting the incomplete record; the next reviewer can distinguish missing evidence from contradictory evidence.</td></tr>
  <tr><td>Audit setting 043</td><td>Ownership handoff: assign a named replacement and preserve the previous owner&#x27;s observations; the replacement can continue without repeating every completed step.</td></tr>
  <tr><td>Audit setting 044</td><td>Claim qualification: keep the qualification next to the claim and request a narrower conclusion; the published explanation does not imply stronger evidence than was collected.</td></tr>
  <tr><td>Audit setting 045</td><td>Duplicate detection: inspect identity and revision metadata before merging any records; unrelated documents are not combined merely because their titles resemble each other.</td></tr>
  <tr><td>Audit setting 046</td><td>Publication readiness: keep the draft visible to reviewers but withhold it from publication; readers can distinguish a provisional recommendation from a completed decision.</td></tr>
  <tr><td>Audit setting 047</td><td>Reference correction: update the reference while retaining the earlier citation in the history; future readers can reconstruct which evidence supported each version.</td></tr>
  <tr><td>Audit setting 048</td><td>Calculation review: separate the two categories and ask the author to explain the time horizon; the review states the comparison&#x27;s limits without inventing missing amounts.</td></tr>
  <tr><td>Audit setting 049</td><td>Access verification: route the access question to the collection owner without sharing private content; permissions remain the owner&#x27;s responsibility and the request is recorded.</td></tr>
  <tr><td>Audit setting 050</td><td>Terminology alignment: ask the author to define the distinction before renaming the displayed labels; the vocabulary remains consistent without erasing a meaningful difference.</td></tr>
  <tr><td>Audit setting 051</td><td>Scope boundary: record the new question separately and identify who can authorize additional work; the current decision remains tied to the evidence actually inspected.</td></tr>
  <tr><td>Audit setting 052</td><td>Correction history: add a dated correction linked to the original decision rather than replacing history; readers can tell what changed and why the earlier explanation was incomplete.</td></tr>
</table>

## A nested table inside a cell

<table>
<tr><th>Packet</th><th>Nested observation</th></tr>
<tr><td>DOC-NESTED</td><td><table><tr><td>Evidence</td><td>Retain the inner record.</td></tr></table>

# This is cell content, not a document heading
</td></tr>
</table>

The paragraph after the outer closing tag is normal document text again.
