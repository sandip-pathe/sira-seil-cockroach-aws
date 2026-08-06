# CoCo + Snowflake build evidence

Date: 6 August 2026
Branch: `snowflake-hackathon`
CoCo CLI: `1.1.53`

## Meaningful CoCo work

- CoCo performed the live account preflight and made 44 SQL tool calls in session
  `62b26912-6367-4123-a455-e78908801914`.
- CoCo generated and executed the governed-table, document-evidence, Cortex Search,
  and decision-ledger foundation in session
  `94f2e357-dacf-46c5-99ba-406617fd7a6a` (36 live SQL calls).
- CoCo uploaded both seller documents, diagnosed the required `SNOWFLAKE_SSE`
  stage encryption after the first parse failed, reran `AI_PARSE_DOCUMENT`
  successfully, and created the reviewed claim bindings.
- CoCo stopped at its tool-iteration limit before producing the Snowpark procedure.
  Codex resumed the same design, uploaded the vendored evaluator bundle through
  Snowsight, registered the procedure, and ran the causal proof.

The local CoCo histories are evidence of genuine use and are intentionally not
committed because they can contain account metadata.

## Live objects and results

- `SIRA_HACKATHON` with `GOVERNED`, `EVIDENCE`, `DECISION`, and `AGENT_APP`.
- `SIRA_HACK_XS_WH`: X-Small, 60-second auto-suspend.
- 16 initial tables/views plus persisted `DOCUMENT_PARSE_RESULTS` lineage.
- Two products, three offers, eight versioned company facts, two seller documents,
  six chunks, two reviewed claim bindings, and one Cortex Search service.
- `DECISION.RUN_SIRA_DECISION(VARCHAR)` is a Snowpark Python 3.12 procedure.
- Context v1 selected `prod_notesync_b`; its cited seller evidence showed MeetAI's
  HubSpot tier costs USD 120, above the private USD 100 cap.
- Context v2 removed only the private HubSpot requirement and selected the cheaper
  `prod_meetai_a` USD 80 offer.
- The v1 run produced an RFC-8785-compatible input hash and decision hash, five
  citations (three buyer facts and two seller chunks). The original live approval
  proof was bound to the decision hash; the final migration additionally binds new
  approvals to organization, request, and run IDs.

## Final migration gate

The application configuration targets account locator `ERJAVEX-TG61158`. The
authenticated Snowsight tab available during final review was account `AN78325`, so
the tenant-scope and parser-lineage forward migration was not applied to the target
account from that browser. Apply `05_decision_ledger.sql`, `06_snowpark_evaluator.sql`,
and `08_ingest_seller_evidence.sql` in the target account before deploying this
branch. This is an external account-access gate, not a passing live result.

## Real failures and fixes

1. `AI_PARSE_DOCUMENT` rejected the default client-side encrypted stage. Fixed by
   using `ENCRYPTION=(TYPE='SNOWFLAKE_SSE')`.
2. The first procedure DDL used an unsupported trailing `COMMENT` clause. Removed it.
3. Snowflake's import loader could not resolve the nested handler/package modules.
   The handler was placed at the archive root and made self-contained while the full
   deterministic source and pinned `rfc8785` package remain in the staged bundle.

No result above is simulated. The first failed calls remain visible in Snowflake
query history and the CoCo conversation history.

## Cost posture

- One X-Small warehouse only; no scheduled tasks.
- 10-credit warehouse resource monitor, 60-second suspend.
- Search target lag is one day over six tiny chunks.
- Two parsing calls and two evaluator calls were used for the final proof.
- Snowsight displayed the full USD 400 trial balance during the final run; billing
  can lag, so account usage remains the authoritative cost source.
