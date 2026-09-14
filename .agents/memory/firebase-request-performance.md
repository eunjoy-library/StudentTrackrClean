---
name: Firebase request performance
description: Performance constraints for synchronous Firestore-backed user flows.
---

Firestore calls in synchronous Flask request paths should be scoped to the smallest document/subcollection possible, and the same validation should not be fetched repeatedly during one user action.

**Why:** Network round trips are much slower than local work, and repeated sequential reads made attendance actions feel slow even when the app server and client network connection were healthy.

**How to apply:** Cache slowly changing settings briefly, use student-scoped attendance records for attendance checks, and keep the final server-side validation while removing redundant client-side confirmation calls.