# Infra — Firestore rules & indexes

Deny-all client access: the backend uses the Firebase Admin SDK, which bypasses
security rules. All client data flows through the REST API (`/v1/...`).

## Deploy

```bash
firebase deploy --only firestore:rules,firestore:indexes --project $PROJECT_ID
```

## Verify

```bash
firebase firestore:indexes --project $PROJECT_ID
```

Lists the composite indexes from `firestore.indexes.json` (insurance_claims
collection-group, diary_entries, orders, vyapari_rates_pending,
transport_bookings). If the Firestore emulator or production logs report
`FAILED_PRECONDITION` / "requires an index" for any query, add the printed
index definition here and redeploy.
