# Progressive company-context capture

The SIRA Decisions inspector links to a focused capture form backed by the existing authenticated `qualification_list_company_context` and `qualification_create_company_context` operations. People can save one detail at a time as a note, stack item, requirement, constraint, policy, or preference. Each save is immutable version 1, records a human-readable change reason, and uses an idempotency key that stays stable across a retry of the same draft.

The context API accepts an exact JSON object for `payload`. This UI uses a small payload convention:

```json
{
  "capture_source": "USER_ENTERED",
  "capture_status": "UNKNOWN | INFERRED | USER_CONFIRMED",
  "value": "The user-entered context detail"
}
```

`USER_CONFIRMED` means only that the user marked the entry confirmed. SIRA has not independently verified it. Older records without this payload convention are shown with “Provenance not recorded.”

The screen handles initial load, empty list, stale list after refresh failure, and retry states. A failed create retains the draft and retries with the same idempotency key; editing the draft creates a new key. Successful creation invalidates and reloads the list.

The existing chat endpoint does not consume this list automatically, and the app does not yet bind selected context-item IDs into a qualification mission. The panel says so explicitly. Treat this as saved company memory, not context already applied to the current chat or decision. The next integration must provide explicit selection/pinning and show the exact context version attached to the mission.
