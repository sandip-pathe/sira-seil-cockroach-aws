# Entry and session continuity

The sign-in gate remembers the current same-tab path, query, and hash in `sessionStorage` before redirecting. The intent expires after 30 minutes, is consumed after successful sign-in or guest entry, and is accepted only for an allowlisted route in the selected workspace. External URLs, sign-in loops, cross-workspace routes, malformed values, and oversized targets are rejected. Exchange intent follows its explicit `mode`, so seller exchange links return to SEIL.

After sign-in, the user returns to the remembered task. Direct SIRA and SEIL entry links still fall back to their selected workspace when there is no remembered task. The sign-in page only displays a continuation message for a recent, same-workspace, supported task. Route parameters stay in same-tab storage rather than being copied into the sign-in URL.

Guest access remains limited to the current browser and cannot authorize purchases. Linking Google uses Firebase `linkWithPopup` on the anonymous Firebase user, retaining that Firebase identity if linking succeeds. It does not migrate or guarantee persistence for unsaved UI state or drafts; the settings flow says so and reports a failed link while leaving the guest tab active. Durable mission and evidence records continue to depend on their supported server-backed flows.

Browser checks cover correct workspace selection, untrusted-target rejection, and the continuation cue. Firebase popup success, expiry against a live configured session, and cross-device persistence were not exercised because this environment has no Firebase credentials. The development guest bypass also prevents a live signed-out auth-gate redirect test here.
