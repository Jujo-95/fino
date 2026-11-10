# Report submission contract and historical Nébula failure

## Observed evidence

The latest Nébula 2.0 conversation with report-save attempts is `0c87a0a85a244fa1b5ab5959bc94b6a7`, turn `adec5dc9ffe6424583d0770cb0ddd793`. There are 16 save_report calls: 14 failures, a successful save at 2026-10-21 20:30:52 UTC (`8c90da58051d75a09da758bad63a66c3`), then another failed save. The newer conversation was cancelled without save attempts.

All 15 errors were input validation failures: structured_report was a string, while the generated LangChain schema required a dictionary. Inspection of checkpointed raw tool arguments additionally found missing object-closing braces inside tickets.proposedActions. The original validation happened before the storage function ran. These were not NVIDIA transport retries or filesystem errors.

The first failed payload contains three findings and three proposed ticket actions. By the eventual successful native-object call, the model had reduced proposed actions to one. Repeated error messages echoed the entire Markdown/JSON draft, adding avoidable context. The historical persisted report is retained as evidence; this fix does not recalculate its financial findings.

## Changes

- Native Pydantic tool schema explicitly describes report metadata, summary, findings and tickets. These sections are required; arbitrary text is not accepted as the structured document.
- Well-formed serialized JSON is decoded before LangChain input validation. The compatibility adapter also handles an exact JSON code fence.
- JSON syntax repair uses json-repair with a small schema for the problematic proposed-action nesting. It makes no model call. Repairs must preserve all scalar-token counts and primitive key/value associations. Repairs that add/drop fields or values, duplicate keys, nonfinite numbers and incomplete report sections are rejected.
- Markdown must be nonempty; actual line breaks are preserved and CRLF normalized.
- Scope validation checks root client_id/clientId and nested report.clientId/client_id against the immutable active client.
- The report audit records native_object, decoded_json_text or syntax_repaired. Original tool arguments remain in the LangGraph checkpoint.
- Validation feedback is compact, gives the correct native-object form, and never echoes the report draft.
- A successful same-turn receipt is reused before validating a redundant save, preventing duplicate reports and rewrite loops. A requested later revision uses a new turn/job.
- Two failed save validations stop the turn before another model call. Incomplete jobs remain failed, never completed.
- Prior-turn failed save-call pairs are omitted from subsequent model input, while the checkpoint/audit stays intact. The current turn's compact error remains available for correction.

Dependency reference: https://github.com/mangiucugna/json_repair (schema extra declared explicitly in pyproject and uv.lock).

## Verification

`work/replay_nebula_save.py` reads the original 16 calls and validates all of them locally. It then sends the very first historically failing call through the actual typed save tool in a temporary workspace: one invocation creates Markdown and JSON, retaining all three findings and all three proposed actions. The original workspace/report is not modified and no NVIDIA request is made.

Regression tests cover native/serialized/fenced/malformed inputs, preservation of values and proposals, unsafe repair rejection, compact errors, stopping the loop, cached receipts and historical-context compaction. Existing report jobs/cancellation tests remain part of the full suite.
