# DataHub demo runbook

Use this path for the judged demo. It shows the product first and the technical proof only when it supports the buying story.

## Before recording

```powershell
.\scripts\proof.cmd doctor -Contract
.\scripts\proof.cmd demo -Assert -Artifacts .artifacts/proof
```

Then start PostgreSQL, the host API, and the web app using the commands in the [README](../README.md#run-locally). Confirm:

- <http://localhost:3000/sira> loads;
- the DataHub connector is healthy;
- the starter mission returns a recommendation;
- the right inspector shows DataHub facts, requirements, causal check, and receipt reread;
- the browser console has no application errors.

## Presenter path

1. Open `/sira` and choose **Choose a customer-support AI for our actual data stack**.
2. State the job: SIRA helps the buyer choose software; SEIL supplies comparable seller evidence; DataHub supplies the buyer's private technical context.
3. Show the recommendation and the requirements derived from DataHub.
4. Open the causal check. Explain that removing only the PII classification changes which option qualifies, while an unrelated change does not.
5. Show that restoring the PII tag restores the original result and hashes.
6. Show the receipt reread. Explain that SIRA records the decision and its hashes back in DataHub so the exact result can be checked later.

Use product roles, not fictional names: **privacy-safe option** and **cheaper option**.

## Safe claims

- DataHub metadata changes the eligible choice.
- The counterfactual, negative control, restoration, decision calculation, and writeback/reread are real local operations.
- The company, products, prices, metadata contents, and test inputs are synthetic.
- SEIL evidence is repository-curated for this demo; this is not a live vendor marketplace.
- The deterministic decision engine selects the result; an LLM does not decide eligibility.

Do not claim a real purchase, production deployment, customer data, live independent seller endpoints, or an immutable receipt stored in DataHub.

## Fallback

If the live UI fails, stop retrying after one refresh. Use the native DataHub screenshots in [`docs/screenshots/submission`](screenshots/submission/README.md) and describe the last asserted local run. Do not present a stale artifact as a fresh live result.
