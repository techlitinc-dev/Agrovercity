# Backend Summary

Status tracker for Dev A (backend) work, day by day.

## Day 10 — Schemes, Vault, Land Records, Water + Account (Tasks A1–A8)

**Status: implemented — 230/230 tests passing (41 new).**

### Task A1 — Schemes + eligibility engine — DONE

- `models/schemes.py` (GovtScheme/SchemeApplyIn/SchemeApplyOut/PortalEntry), `data/schemes_seed.py` — 6 schemes (PM-KISAN ₹6,000/वर्ष, PMFBY, Soil Health Card, PM-KUSUM, eNAM, PMKSY drip) with Hindi descriptions and data-driven `eligibilityRules` maps; `seed_schemes()` is idempotent and called from startup (wrapped in try/except so missing Firestore credentials don't block boot).
- `services/eligibility.py`: `is_eligible(user, rules)` — maxLandAcres/states/requiresKcc; unknown rules ignored; empty rules → eligible.
- `routers/schemes.py` (farmer/farmLandlord): `GET /schemes?category=&eligibleOnly=` (per-user eligible computed, rules stripped, envelope), `POST /{id}/apply` (404 `SCHEME_NOT_FOUND`, 409 `ALREADY_APPLIED`, 403 `NOT_ELIGIBLE`, 400 `INVALID_DOCUMENT_ID` against `users/{uid}/vault_documents`; applicationId = schemeId), `GET /schemes/portals` (5 https portals).
- Tests (`tests/test_schemes.py`): 6 passed.

### Task A2 — Document vault (Storage signed URLs) — DONE

- `services/storage.py`: `upload_user_file` (blob `vault/{uid}/{uuid}_{filename}`; dev mode writes `backend/.local_uploads/` with warning), `signed_download_url` (60-min; dev `file://`), `delete_blob`. Module docstring covers the AES-256/GMEK badge and the never-log rule.
- `routers/vault.py` (all roles): `POST /documents` (multipart; 415 `UNSUPPORTED_FILE_TYPE` outside JPEG/PNG/PDF; 413 `FILE_TOO_LARGE` over 5 MB; no Aadhaar number field anywhere), `GET /documents` (fresh signed URL per doc, envelope), `DELETE /documents/{id}` (404 `DOCUMENT_NOT_FOUND`; blob + doc removed; 204). Router has zero logger calls (nothing to leak) — covered by the logger-spy test.
- Tests (`tests/test_vault.py`): 5 passed.

### Task A3 — Land-records search behind a swappable adapter — DONE

- `services/land_records/{base,mock_adapter,__init__.py}`: ABC (`search`/`get_by_id`/`get_pdf_url`), 3 mock records (rec-1 Ozarkhed with exact day-file values), registry via `LAND_RECORDS_ADAPTER` env (unknown → raise).
- `routers/land_records.py` (farmer/farmLandlord): `GET /search` (gatNumber regex/village min-3 → 422 envelope; neither → 400 `MISSING_SEARCH_PARAM`; type 712|8A), `GET /{id}/pdf` (404 `RECORD_NOT_FOUND`), `POST /{id}/import` (updates `landAreaAcres` + appends to the user's `landRecords` array).
- Tests (`tests/test_land_records.py`): 6 passed.

### Task A4 — Water intelligence — DONE

- `routers/water.py` (farmer): `GET /schedule` (deterministic moisture via `zlib.crc32(uid+crop)`, 90/30-minute recommendation, user's irrigation method), `GET /groundwater?district=` (400 `MISSING_DISTRICT`; CGWB-style map incl. Nagpur critical; `measuredAt` today), `GET /canal-rotation?canal=` (Gangapur next-Monday 06:00-12:00, Palkhed next-Thursday 12:00-18:00, contains-filter), `POST /pmksy-calculator` (2 acres → ₹1,70,000 / 55% / ₹93,500 / ₹76,500).
- Tests (`tests/test_water.py`): 5 passed.

### Task A5 — Account deletion + FCM devices — DONE

- `services/purge.py`: `purge_user(uid)` deletes all known user subcollections (incl. lease payment subdocs), anonymizes financial docs (`transport_bookings`/`orders` → `userId: "deleted:<uid[:8]>"`), deletes the user doc, calls `firebase_admin.auth.delete_user` (sync); Storage prefixes skipped in dev.
- `routers/users.py`: `DELETE /users/me` — MPIN gate (409 `MPIN_NOT_SET`, 401 `WRONG_MPIN`), Redis rate limit `del_attempts:{uid}` INCR+EXPIRE 3600 → 429 `TOO_MANY_ATTEMPTS` after 3; `POST /v1/devices` (sha256 token-hash doc id, idempotent upsert) and `DELETE /v1/devices/{tokenHash}` (idempotent 204) exposed on a top-level `devices_router` so the path is `/v1/devices` per the day file.
- Tests (`tests/test_account.py`): 4 passed (auth.delete_user mocked; rate-limit uses the live local Redis).

### Task A6 — Consent & privacy center — DONE

- `services/consents.py`: `get_consents` (defaults all false), `put_consents` (full replace + append-only `consent_log` doc per changed flag), `require_data_sharing` (raises `ConsentRequiredError` → routers map to 403 `CONSENT_REQUIRED`; Day 13 saturation will call it).
- `GET/PUT /users/me/consents` (all roles); missing flag → 422 envelope via the Day-9 validation handler. No update/delete path for `consent_log` anywhere.
- Tests (`tests/test_consents.py`): 5 passed.

### Task A7 — Rent reminder scheduled job — DONE

- `services/rent_reminders.py`: `find_due_leases(today)` via a new `db.list_collection_group("land_leases")` helper (returns `{doc, path}`; active lease, current month unpaid, today ≥ 5th); `run_rent_reminders(today)` notifies the landlord (`fcm.notify` — Day 13 will formalize the module; tenant SMS is a Day 13 X4 follow-up) with per-lease+month dedup against the notifications store.
- `POST /jobs/rent-reminders/run` with the Day-9 cron-secret guard.
- Tests (`tests/test_rent_reminders.py`): 5 passed.

### Task A8 — Soil-test booking — DONE

- `routers/soil_tests.py` (farmer/farmLandlord): `POST /book` (optional plotId must be own → 404 `PLOT_NOT_FOUND`; one non-reportReady booking per plot → 409 `SOIL_TEST_ALREADY_BOOKED`; slot pattern `YYYY-MM-DD am|pm`), `GET /` (own bookings, bookedAt desc, envelope).
- Tests (`tests/test_soil_tests.py`): 5 passed.

### Test run (final)

```
$ cd backend && .venv/bin/pytest
230 passed, 36 warnings in 11.66s
  ...prior days 189 | schemes 6 | vault 5 | land_records 6 | water 5
  account 4 | consents 5 | rent_reminders 5 | soil_tests 5
```

### Blockers / notes

- **Redis required for the account rate-limit tests** — the Day-9 style in-memory patch can't count across attempts; the local Redis is used and a conftest autouse fixture now resets the cached client per test (fixes cross-event-loop pollution found in this run).
- **`db.list_collection_group` added** (collection-group query with parent path) for the rent-reminder job; the fake scans path-keyed stores.
- **`services/fcm.py` added early** as a thin facade over the Day-7 notifications service so A7 could depend on the stable `notify` signature (Day 13 formalizes).
- **`/v1/users/devices` duplicates removed** — device routes live only on the top-level `/v1/devices` per the day file.
- Vault/land-records live smoke is limited to route registration (Firebase credentials still absent); all flows covered by tests.
- Live smoke: health 200; 18 new paths registered; unauthed `/v1/schemes` → 401.

## Day 9 — Diary, P&L, Finance, Landlord + Land market (Tasks A1–A8)

**Status: implemented — 189/189 tests passing (42 new).**

### File split (reported per conventions §1.4)

`routers/land.py` (A4 + A8 combined) would exceed 300 lines — split into `routers/land.py` (plots/leases/payments) and `routers/land_market.py` (listings/lease-requests/agreement PDF), sharing helpers in `services/land.py`.

### Task A1 — Diary entries CRUD + PDF report — DONE

- `models/diary.py` (field names per endpoints.md §8), `services/coins.py` (`award_coins` — balance increment + `users/{uid}/coin_ledger` doc; stable signature for Day 13), `services/reports.py` (reportlab diary PDF + `upload_to_storage` — dev mode returns `file://` with a warning when Firebase isn't initialised).
- `routers/diary.py` (farmer/farmLandlord): `GET /entries` (type/category/from/to filters, date desc, envelope), `POST /entries` (201, +15 coins), `DELETE /entries/{id}` (204 / 404 `ENTRY_NOT_FOUND`), `GET /diary/report?from=&to=` (default current month; Storage URL).
- `core/db.py` gains path-based subcollection helpers (`set_subdoc_at`/`get_subdoc_at`/`delete_subdoc_at`/`list_subdocs`) — `query()` only handles top-level collections; flagged as an addition the day file implied ("local helper") but needed across 4 routers.
- PDF validity verified: `file` reports "PDF document, version 1.4".
- Tests (`tests/test_diary.py`): 5 passed.

### Task A2 — P&L endpoints — DONE

- `models/pnl.py`, `data/demo_pnl.py` (Wheat + Onion stand-ins — prototype absent, flagged). `routers/pnl.py` (5 roles): `GET /summary` (zeros when empty), `GET /crops` (seeds the 2 demo crops on first read), `POST /crops/{id}/expenses` (append + recompute totalExpenses/netProfit/roiPercent, 0-division safe), `POST /break-even` (pure `ceil(totalCost / yield)`; pydantic gt=0).
- Tests (`tests/test_pnl.py`): 5 passed — including break-even 50000/20 → 2500 and the 422 envelope for zero yield.

### Task A3 + A6 — Finance endpoints + loan status list — DONE

- `routers/finance.py`: `GET /credit-score` (defaults 650/Silver + tier→limit map), `POST /loan-calculator` (standard EMI formula), `GET /kcc` (404 `KCC_NOT_FOUND`; masked `XXXX-XXXX-<phone last 4>`), `POST /loans/apply` (201, `loan_applications`), `GET /loans` (A6: newest first, envelope, empty = 200).
- **Day-file discrepancy flagged:** the day file's quoted EMI ≈ 4256.44 does not match its own formula — the exact standard-formula EMI for 25000/6/7% is **4252.15**. The formula (the normative spec) is implemented; the test asserts 4252.15 with a comment.
- Tests (`tests/test_finance.py`): 7 passed.

### Task A4 — Landlord plots/leases/rent payments — DONE

- `models/land.py` (Plot/Lease/RentPayment + listing/request models for A8), `routers/land.py`: plots CRUD (201 vacant; delete blocked by active lease → 409 `PLOT_HAS_ACTIVE_LEASE`), leases CRUD (endDate > startDate → 422; create marks plot `leased`; end/delete reverts to `vacant`), payments (duplicate month → 409 `DUPLICATE_PAYMENT_MONTH`; summary with `totalCollectedRupees` + `pendingMonths` from lease start through the current month).
- Tests (`tests/test_land.py`): 7 passed.

### Task A5 — Bank accounts + penny-drop adapter — DONE

- `services/bank_verify/{base,stub,__init__.py}`: `BankVerifyAdapter` ABC + stub (mocked success) + `get_bank_verify_adapter()` via `BANK_VERIFY_ADAPTER` env (default stub; real provider later).
- `routers/bank_accounts.py` (all roles): list (primary first, envelope), create (first account auto-primary, `unverified`), verify (pending → adapter → verified/failed), set-primary (unsets others), delete (204; oldest remaining promoted). Full accountNumber is stored only in `users/{uid}/bank_accounts`; **responses carry the masked form only** (module docstring notes Firestore AES-256/GMEK and the never-log rule).
- Deviation: `test_claim_uses_primary_account_last4` deferred — the Day 11 claims flow doesn't exist yet; the router change is noted as a downstream reference. 6 of 7 tests implemented.
- Tests (`tests/test_bank_accounts.py`): 6 passed.

### Task A7 — Platform settlement engine — DONE

- `models/settlements.py`, `services/settlements.py`: `run_settlements(period_start, period_end)` aggregates delivered `transport_bookings` (fare; earner resolved via `vehicles/{vehicleId}.ownerId`), completed (`booked`) `equipment_bookings` (priceRupees; owner via equipment), completed `broker_deals` (graceful when absent — **no broker-deals collection exists from prior days**; flagged), grouped by earner; commission percentages read from `platform_config/settlements` (seeded on first read — no hardcoded pcts); doc id `st_{role}_{entityId[:8]}_{periodStart}` — pending rows recomputed on rerun, approved/paid untouched.
- `routers/jobs.py`: `POST /jobs/settlements/run` — `X-Cron-Secret` checked against `settings.cron_secret` (new `CRON_SECRET` env; empty dev mode allows with a warning); default period = last ISO week (Mon–Sun). `routers/settlements.py`: per-persona lists (transport/equipmentRental/broker; own rows only, newest period first).
- Tests (`tests/test_settlements.py`): 5 passed.

### Task A8 — Land listings + lease requests + agreement PDF — DONE

- `routers/land_market.py`: `POST /land/listings` (farmLandlord; optional own plotId), `GET /land/listings?near=lat,lng&acres=` (haversine ≤ 25 km, open only), `GET /listings/mine`, `PUT/DELETE /listings/{id}` (owner 403 `NOT_LISTING_OWNER`; leased → 409 `LISTING_HAS_ACTIVE_LEASE`), `POST /land/lease-requests` (farmer; open-only, one pending per farmer per listing → 409s), `GET /lease-requests` (landlord inbox), `accept` (creates the lease from the listing rent + durationMonths, flips listing to `leased`, auto-rejects competing pendings), `reject`.
- L4: `GET /land/leases/{id}/agreement-pdf` — landlord direct, tenant via phone match (a top-level `land_leases_index/{leaseId}` doc is written at accept so the tenant can resolve the lease — flagged as an addition); `build_lease_agreement_pdf` (Hindi heading `कृषि भूमि पट्टा अनुबंध` + both parties) → Storage upload.
- Tests (`tests/test_land_market.py`): 6 passed.

### endpoints.md — section 21 appended

Covers all A4 + A8 land routes plus the A5 bank-account and A7 settlement/job routes in the same table format.

### Test run (final)

```
$ cd backend && .venv/bin/pytest
189 passed, 34 warnings in 8.92s
  ...prior days 147 | diary 5 | pnl 5 | finance 7 | land 7 | bank_accounts 6 | settlements 5 | land_market 6
```

### Blockers / notes

- **`endpoints.md` modified** (section 21) as the day file directs — first doc file change; content follows the established table format.
- **Validation-error envelope:** added a `RequestValidationError` handler in `main.py` so pydantic Field violations (break-even yield 0, loan limits, bad IFSC, bad pincode) return the conventions §6 envelope instead of FastAPI's default shape. All prior tests still green.
- **Deviations flagged:** diary PDF Storage dev-mode detection uses "Firebase not initialised" rather than the day file's `firebase_service_account` (our settings key is a path); `land_leases_index` collection for tenant-side lease resolution; `broker_deals` settlement source is provisional (no broker module exists yet); `reportlab==4.2.5` installed cleanly on Python 3.14.
- Claim-flow `bankAccountLast4` patch is deferred to Day 11 (noted in A5).
- Live smoke: health 200; 32 new routes registered; PDFs verified valid via `file`.

## Day 8 — Equipment + FPO (Tasks A1–A4)

**Status: implemented — 147/147 tests passing (24 new).**

### File split (reported per conventions §1.4)

The day file puts everything in `routers/equipment.py`, which would exceed the 300-line limit. Split into: `app/services/equipment.py` (slot generation, booking creation, waitlist promotion, IST/2h-window helpers, `DEFAULT_SLOTS`), `app/routers/equipment.py` (farmer-facing: list, slots, book, waitlist, cancel), `app/routers/equipment_owner.py` (owner CRUD, fleet, pending inbox, approve/reject), and `app/routers/fpo.py`.

### Task A1 — Equipment slots + booking rules + waitlist + cancel — DONE

- Slots live in `equipment_slots/{equipmentId}_{date}_{slotIndex}`; first GET for a date generates 4 slots from the equipment's `slotTemplate` or `DEFAULT_SLOTS` (exact prototype names/tasks), ordered by parsed start time; date defaults to today IST.
- `POST /equipment/slots/{slotId}/book` (farmer): `SLOT_UNAVAILABLE` 409 unless available; max-2/day rule (same-date bookings in `booked|pending`) → 409 `MAX_SLOTS_PER_DAY` with the Hindi message; FPO machines auto-confirm (`booked`), private → `pending`; +50 `agriCoins` on booking.
- `POST /equipment/slots/{slotId}/waitlist`: doc `equipment_waitlists/{slotId}_{uid}`; duplicate → 409 `ALREADY_WAITLISTED`.
- `DELETE /equipment/bookings/{bookingId}`: owner 403 `NOT_BOOKING_OWNER`; already-cancelled 409 `ILLEGAL_TRANSITION`; ≤2h rule parses the slot start (IST) → 409 `CANCEL_WINDOW_CLOSED`; on success the slot frees and the earliest waitlist entry is promoted with the correct status per `ownerType` (`promotedUserId` returned).
- Tests (`tests/test_equipment.py`): 7 passed.

### Task A2 — Owner CRUD + fleet + FPO — DONE

- Owner endpoints (role equipmentRental): `POST /equipment` (forces `ownerType: "private"`, `distanceKm: 0`, `docStatus: "pending"`), `PUT /equipment/{id}` (owner-only 403 `NOT_EQUIPMENT_OWNER`; slotTemplate validated 1–8 entries × 4 keys → 422), `GET /equipment/owner/fleet` (bookedHoursThisWeek = booked|pending slots in the ISO week × 4, weeklyIncome, status, docStatus).
- `scripts/seed_fpo.py`: `fpos/sahyadri-fpo` + `fpo_pools/pool-1` (380/500, 18%, deadline +10d).
- `backend/app/routers/fpo.py` (farmer): `GET /me` (single-FPO dev mode), `GET /pools`, `POST /pools/{id}/join` (units ≥ 1 else 422; over-target → 409 `POOL_FULL`; member subdoc `fpo_pools/{id}/members/{uid}`), `GET /machinery?week=` (ISO week `YYYY-Www`, default current; 7 days of generated slots for verified FPO machines).
- Tests: `test_equipment_owner.py` 6 passed, `test_fpo.py` 4 passed.

### Task A3 — Approve/reject + waitlist promotion — DONE

- `GET /equipment/bookings/pending`: owner's machines' pending bookings joined with machine name + slot fields.
- `POST /equipment/bookings/{id}/approve` / `reject`: ownership 403 `NOT_EQUIPMENT_OWNER`, pending-only 409 `ILLEGAL_TRANSITION`; approve → booking+slot `booked` + FCM to farmer; reject (reason ≥ 3 chars → 422 envelope) → booking `rejected` + `rejectionReason`, slot freed, waitlist head promoted (new booking with correct status, waitlist doc removed), FCM to both the rejected and the promoted farmer.
- Tests (`tests/test_equipment_approve.py`): 7 passed.

### Task A4 — Machine document verification (KYC) — DONE

- Equipment docs carry `docStatus: pending|verified|rejected` + `rejectionReason`; `EquipmentUpsertRequest` gains optional `rcDocUrl`/`insuranceDocUrl` (mirroring Day 7 vehicles). Admin queue is Day 14 — commented.
- Seeded machines are `verified`; `GET /equipment` returns only verified machines; slots for non-verified → 404 `EQUIPMENT_NOT_FOUND` (no existence leak); owner fleet rows always include `docStatus`.
- Tests: 3 added — pending hidden from list + slots 404, verified visible + slots generate, fleet docStatus.

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
147 passed, 2 warnings in 8.66s
  ...prior days 123 | equipment 7 | equipment_owner 6 | fpo 4 | equipment_approve 7
```

### Blockers / notes

- **Seed scripts blocked on Firestore credentials** (same as prior days); data verified via tests importing the seed constants.
- **New codes flagged:** `NOT_BOOKING_OWNER`, `BOOKING_NOT_FOUND` (equipment), `SLOT_NOT_FOUND` avoided in favour of `SLOT_UNAVAILABLE`/`EQUIPMENT_NOT_FOUND` where the day file named them; `POOL_NOT_FOUND` added for the join path.
- Waitlist promotion does **not** award coins (only direct bookings earn the +50 per the day file).
- Cancel-window determinism: the ≤2h test pins a `12:00 AM` slot start on today's date so the window is always closed regardless of run time.
- Live smoke: health 200; all 14 new routes registered; unauthed `/v1/equipment` → 401.

## Day 7 — Contracts + Transport (Tasks A1–A6)

**Status: implemented — 123/123 tests passing (27 new).**

### Task A1 — Contracts: list/detail + accept (e-sign) — DONE

- `backend/app/models/contracts.py`: `ContractOut`, `AcceptContractRequest` (signatureData base64 PNG, consentTimestamp, mpin).
- `scripts/seed_contracts.py`: 3 open contracts with `termsText` (Hindi + English). **Deviation:** `flutter-prototype/` is absent, so the exact `dummyBuyerContracts` values could not be copied — realistic stand-ins consistent with the model are used; flagged for diff if the prototype appears.
- `backend/app/routers/contracts.py`: `GET /contracts?status=` (envelope; roles farmer/seller/broker), `GET /contracts/{id}` (+termsText, 404 `CONTRACT_NOT_FOUND`), `POST /contracts/{id}/accept` (farmer/seller): `MPIN_NOT_SET` 409 → `WRONG_MPIN` 401 → `CONTRACT_NOT_OPEN` 409 → stores acceptance subdoc `contracts/{id}/acceptances/{uid}` via the new `db.set_subdoc` helper and flips the contract to `accepted` with `acceptedBy`.
- Tests (`tests/test_contracts.py`): 6 passed.

### Task A2 — Transport: vehicles, fare, bookings state machine, owner endpoints — DONE

- `backend/app/models/transport.py`: vehicle/fare/booking/update/owner models (+ accept/reject/availability/POD extensions from A3–A6).
- `backend/app/routers/transport.py`: `GET /vehicles` (3 type constants), `POST /fare-estimate` (unknown type → 422 `UNKNOWN_VEHICLE_TYPE`), `POST /bookings` (farmer/seller; fare = base + perKm×km; `status: "requested"`), `GET /bookings` (transport dispatch view: `requested` OR vehicleId in owner's vehicles; envelope), `PATCH /bookings/{id}` with the transition map (`requested→accepted|cancelled`, `accepted→enRoute|cancelled`, `enRoute→delivered`; illegal → 409 `ILLEGAL_TRANSITION`), owner vehicle CRUD (`POST /vehicles`, `GET /vehicles/my`, `PUT`/`DELETE /vehicles/{id}` with 403 `NOT_VEHICLE_OWNER`, DELETE soft via `active: false`), `GET /vehicles/{id}/calendar` (accepted/enRoute bookings), `PUT /vehicles/{id}/availability`.
- Tests (`tests/test_transport.py`): 16 passed (6 core + 4 KYC + 3 POD + 3 lot-linkage).

### Task A3 — Booking accept/reject with reason + notifications — DONE

- `backend/app/services/notifications.py`: `send_fcm_to_user` — topic `user_{uid}` FCM when the admin SDK is initialised (token-based FCM is Day 13), and ALWAYS an in-app `notifications` doc so the inbox works without FCM.
- `POST /bookings/{id}/accept` (requested only else 409): optional vehicle assignment (owner 403 / verification 422 checks per A4), stores vehicleId/vehicleNo, notifies the farmer (`booking_accepted`). `POST /bookings/{id}/reject`: reason ≥ 3 chars (422 `VALIDATION_ERROR` envelope), sets `cancellationReason` + `cancelledBy: "transporter"`, notifies with the reason in the body. `PATCH` kept for existing clients (commented that accept/reject are canonical).
- Tests (`tests/test_booking_accept.py`): 5 passed.

### Task A4 — Vehicle document verification (KYC) — DONE

- Vehicle docs carry `docStatus: pending|verified|rejected` (+ `rejectionReason`); created as `pending` (admin verify/reject queue is Day 14 A1 — commented). `GET /vehicles/my?verifiedOnly=true` filters. Assignment (POST accept and PATCH accepted with vehicleId) requires `docStatus == "verified"` → 422 `VEHICLE_NOT_VERIFIED`; wrong owner → 403 `NOT_VEHICLE_OWNER`.
- Tests: 4 added — pending on create, unverified accept 422, verified accept ok, verifiedOnly filter.

### Task A5 — Proof of delivery required to mark delivered — DONE

- `UpdateBookingRequest` gains `podPhotos`/`receiverName`; `enRoute → delivered` without ≥1 photo and a non-blank receiver name → 422 `POD_REQUIRED` with fieldErrors naming each missing field. Success stores `pod: {photos, receiverName, deliveredAt}` on the booking, visible in the dispatch list/detail.
- Tests: 3 added — missing POD 422 (both fieldErrors), delivered with POD, POD visible on GET.

### Task A6 — Lot-linked pickups — DONE

- `CreateBookingRequest.lotId` optional: lot must exist and be owned by the booker (404 `LOT_NOT_FOUND`) and `status: "open"` (409 `LOT_NOT_OPEN`); stored on the booking. The transporter dispatch list includes a nested `lot` summary `{crop, quantityQuintals, expectedRate}` (missing lot doc → `lot: null`).
- Tests: 3 added — own open lot stored + summary in dispatch, other farmer's lot 404, sold lot 409.

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
123 passed, 2 warnings in 8.52s
  ...prior days 96 | contracts 6 | transport 16 | booking_accept 5
```

### Blockers / notes

- **Seed script blocked on Firestore credentials** (same as prior days); contract data verified via tests importing the seed constants.
- **`set_subdoc` added to `core/db.py`** for the contract-acceptance subcollection (mirrors the Day-3 `role_profiles` approach; testable via the fake-db fixture).
- **`BOOKING_NOT_FOUND` (404)** is a new code for missing bookings — not in the conventions named list, flagged.
- **Contract seed values are stand-ins** (prototype absent) — see Task A1 note.
- Live smoke: health 200; all 13 new routes registered (contracts + transport incl. accept/reject, calendar, availability); unauthed `/v1/contracts` → 401.

## Day 6 — Marketplace + payments (Tasks A1–A4)

**Status: implemented — 96/96 tests passing (25 new).**

### Task A1 — Products + certificate + cart — DONE

- `backend/app/models/marketplace.py`: `ProductOut`, `CertificateOut`, `CartItemRequest` (+ `CartItemUpdateRequest`, order models for A2).
- `scripts/seed_products.py`: 3 products (seeds/fertilizer/pesticide, each with `batchNo`) + `certificates` keyed by batchNo (`AGMARK / Ministry of Agriculture`, valid, verifiedAt). Data constants imported by tests.
- `backend/app/routers/marketplace.py` (roles farmer/farmLandlord/transport/seller): `GET /products` (exact category + substring query on title/vernacularTitle, envelope), `GET /products/{id}` (404 `PRODUCT_NOT_FOUND`), `GET /products/{id}/certificate` (404 `CERTIFICATE_NOT_FOUND`), `GET /cart` (`{data: [{productId, quantity, product}], cartTotal}`), `POST /cart/items` (product-exists 404, quantity ≥ 1 → 422; upsert into `carts/{uid}.items` map), `PUT /cart/items/{productId}` (≤ 0 removes), `DELETE /cart/items/{productId}`.
- `core/db.py` gains `delete_doc` (needed for address deletion; flagged as a minimal addition outside the day-file list).
- Tests (`tests/test_marketplace.py`): 6 passed.

### Task A2 — Orders + Razorpay create/verify — DONE

- `backend/app/services/payments.py`: `create_razorpay_order` (dev fake `order_dev_{receipt}` with empty keys; real POST with basic auth otherwise), `verify_razorpay_signature` (HMAC-SHA256 of `order|payment`; dev mode accepts signature `"dev"`), `refund_razorpay_payment` (A3).
- `backend/app/routers/orders.py`: `POST /orders` — idempotency via `idempotency_keys/{key}` (replay returns the original response), validates paymentMethod/items/product existence, computes `total` from current `discountedPrice`, bnpl → 2-installment schedule (`total//2` + remainder), creates the order doc (`status: "placed"`, `refundStatus: "none"`), clears the cart; `GET /orders` (newest first, envelope); `GET /orders/{id}` (404 `ORDER_NOT_FOUND`, 403 not-owner); `POST /payments/razorpay/order` (stores `razorpayOrderId`, returns `keyId: "rzp_test_dev"` in dev); `POST /payments/razorpay/verify` (signature fail → 400 `PAYMENT_SIGNATURE_INVALID`; success → `status: "paid"`).
- Tests (`tests/test_orders.py`): 6 passed — place+cart-cleared, idempotency, bnpl schedule sums to total, list/detail + 403, dev-mode create/verify, bad signature 400.

### Task A3 — Order cancel + Razorpay refund — DONE

- `POST /orders/{id}/cancel` (absent/not-owned → 404 `ORDER_NOT_FOUND`): allowed only in `placed|paid`, else 409 `ORDER_NOT_CANCELLABLE`; sets `cancelledAt`; paid orders get `refundStatus: "requested"`.
- `POST /payments/razorpay/refund`: requires cancelled + requested + paymentId else 409 `REFUND_NOT_APPLICABLE`; dev refund `rfnd_dev_{paymentId}`; sets `refundStatus: "processed"` + `razorpayRefundId`; idempotent replay returns 200 without a second refund call.
- Tests (`tests/test_order_cancel.py`): 6 passed.

### Task A4 — /v1/addresses CRUD + order addressId — DONE

- `backend/app/models/addresses.py`: `AddressRequest` (6-digit pincode validation → 422 `VALIDATION_ERROR`).
- `backend/app/routers/addresses.py` (any authenticated user): `GET /addresses` (default first), `POST /addresses` (201; first address forced default; `isDefault` clears others), `PUT /addresses/{id}` (owner-only → 404 `ADDRESS_NOT_FOUND`; same default rule), `DELETE /addresses/{id}` (204; promotes the oldest remaining address when the default is deleted).
- `POST /orders` accepts optional `addressId`: owner-checked (404 `ADDRESS_NOT_FOUND`), composes `deliveryAddress` as `"{line1}, {village}, {district}, {state} - {pincode}"`; free-text path still works.
- Tests (`tests/test_addresses.py`): 7 passed.

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
96 passed, 2 warnings in 6.15s
  app_config 4 | auth 5 | infra 3 | mpin 5 | users 6 | profiles 6 | referral 4
  role_profiles 5 | reference 6 | weather 3 | mandi 4 | vyapari 10 | lots 6 | history 4
  marketplace 6 | orders 6 | order_cancel 6 | addresses 7
```

### Blockers / notes

- **Seed script blocked on Firestore credentials** (same as prior days) — `DefaultCredentialsError`; data verified via tests importing the seed constants. Rerun once credentials exist.
- **`ORDER_ACCESS_DENIED` (403)** is a new code — the day file mandates 403 for non-owner detail access but names no code; flagged per conventions.
- **`delete_doc` added to `core/db.py`** — required by `DELETE /addresses`; not in the day-file list, flagged as a minimal addition.
- Cart totals sum `discountedPrice × quantity` as floats (the day-file `ProductOut` uses float prices); BNPL installments are integer rupees split `total//2` + remainder so they always sum exactly to `total`.
- Live smoke: health 200; all 14 new routes registered (products/certificate/cart/orders/payments/addresses); unauthed `/v1/products` → 401.

## Day 5 — Mandi (Tasks A1–A5)

**Status: implemented — 71/71 tests passing (24 new).**

### Task A1 — /v1/mandi/prices + /v1/mandi/list + seed script — DONE

- `backend/app/models/mandi.py`: `MandiPriceOut` (id, mandiName, distanceKm, commodity, variety, min/max/modal/msp, trend, changePercent, arrivalsQuintals, updatedAt), `VyapariRateOut`, `CompareResultItem`, `SellerRateRequest`.
- `scripts/seed_mandi.py`: seeds 4 `mandi_prices` (Pimpalgaon/Nashik Dindori/Lasalgaon/Vashi with the day-file prices), 4 `mandis` (district/state/approx coords), 3 `vyapari_rates`, and 360 `mandi_price_history` rows (A5). Data constants are imported by tests — single source of truth.
- `backend/app/routers/mandi.py` (prefix `/mandi`, roles farmer/seller/broker via the new `require_roles` dependency in `core/deps.py`): `GET /prices` (crop contains-match on the English part, case-insensitive; optional district filter; pagination envelope `{data, page, pageSize, total}`, pageSize clamped to 50), `GET /list` (`{data: [...]}` from `mandis`).
- Tests (`tests/test_mandi.py`): 4 passed — all 4 in envelope, tomato filter → 3 with no Onion, transport activeProfile → 403 `FORBIDDEN_ROLE`, mandi list.

### Task A2 — /v1/mandi/vyapari-rates + compare + seller rate posting — DONE

- `GET /mandi/vyapari-rates?crops=`: Redis cache key `vyapari_rates:{crops|all}` TTL 7200 s; response `{data: [...], cachedAt}`; comma-separated crop filter.
- `GET /mandi/compare?crop=&quantityQuintals=&lat=&lng=`: transportCost = distanceKm × ₹12/km; netProfit = modalPrice × quantity − transportCost; sorted by netProfit desc; 422 `INVALID_QUANTITY` when quantity ≤ 0.
- `backend/app/routers/seller.py` (role seller): `POST /rates` → `vyapari_rates_pending` doc `{crop, ratePerKg, mandiName, sellerId, status: "pending", createdAt}`; `GET /rates/my` → this seller's pending+approved rates. Cache invalidation only on approval (out of scope — commented).
- Tests (`tests/test_vyapari.py`): shape (3 rates, valid changeDir), Redis cache counter (2 calls → 1 query, in-memory cache patch), compare ranking + transportCost check, invalid quantity 422, seller post pending + rates/my, farmer → 403.

### Task A3 — Produce lots CRUD (/v1/market/lots) — DONE

- `backend/app/models/lots.py`: `LotRequest` (crop, quantityQuintals > 0, expectedRate int ≥ 0, harvestDate, photos[], location) + `LotOut` (id, farmerId, status, createdAt).
- `backend/app/routers/lots.py` (role farmer): `POST /lots` → 201 with `status: "open"`; `GET /lots?status=&page=&pageSize=` → caller's own lots only, envelope; `PUT /lots/{id}` → owner-only (404 `LOT_NOT_FOUND`), sold → 409 `LOT_NOT_EDITABLE`; `DELETE /lots/{id}` → soft-withdraw (record kept; sold → 409); returns `{ok: true, status: "withdrawn"}`.
- Tests (`tests/test_lots.py`): 6 passed — create, own-only list, update, withdraw + status filters, other farmer's lot 404, sold lot PUT/DELETE 409.

### Task A4 — Rate sanity band on POST /v1/seller/rates — DONE

- Before storing: `ratePerKg × 100` compared against the reference `modalPrice` from `mandi_prices` (crop contains-match; mandiName loose-match preferred, else any doc for the crop). Outside ±25% → 422 `RATE_OUT_OF_BAND` with `fieldErrors: {"ratePerKg": "मंडी भाव ₹<modal> के ±25% सीमा से बाहर"}`. No reference for the crop → accepted (coverage gap handled by the admin moderation queue, Day 14 A6 — commented).
- Tests: 4 added — within band (₹2400/q vs ₹1950 modal) accepted, ₹4000/q and ₹1000/q rejected, unknown crop (Dragonfruit) accepted.

### Task A5 — GET /v1/mandi/prices/history + 90-day synthetic seed — DONE

- `build_history_rows()` in the seed script: 90 daily docs per mandi (360 total), deterministic `random.Random(42)` walk (±5%), anchored so day 90 equals the current `modalPrice`; one-line TODO for real Agmarknet backfill.
- `GET /mandi/prices/history?crop=&mandi=&months=`: crop/mandi matching as in `/prices` (substring on mandiName); missing crop or mandi → 422 `VALIDATION_ERROR` with fieldErrors; months clamped silently to 1–36; returns `{data: [{date, modalPrice}]}` ascending, last `months × 30` days.
- Tests (`tests/test_mandi_history.py`): 4 passed — 90 ascending points default, 30 for months=1, unknown crop → empty, missing params 422.

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
71 passed, 2 warnings in 5.85s
  app_config 4 | auth 5 | infra 3 | mpin 5 | users 6 | profiles 6 | referral 4
  role_profiles 5 | reference 6 | weather 3 | mandi 4 | vyapari 10 | lots 6 | history 4
```

### Blockers / notes

- **Seed script blocked on Firestore credentials** (same as Day 1) — `DefaultCredentialsError`; the script and its data are verified via the test suite, which imports the seed constants directly. Rerun `scripts/seed_mandi.py` once credentials exist.
- **`require_roles(*roles)` added to `core/deps.py`** (the conventions §9 pattern) — it loads the user and checks `activeProfile`, returning the user dict so routers have uid + profile in one dependency. Day 3's inline `require_role(user, *roles)` helper remains in users.py for its endpoints.
- Live smoke: health 200, all 9 new routes registered in OpenAPI, unauthed `/mandi/prices` and `POST /market/lots` → 401 envelope.
- `changePercent` stays a display string (`"+8.4%"`) per the day-file model — numeric parsing is a client concern for now.

## Day 4 — Reference data + weather (Tasks A1–A2)

**Status: implemented — 47/47 tests passing (9 new).**

### Task A1 — /v1/geo/reverse, /v1/regions/crops, /v1/languages — DONE

- `backend/app/services/geo.py`: `GeoAdapter` Protocol + `MockGeoAdapter` (bounding boxes for Nashik → West/`["mr","hi"]` and Ludhiana → North/`["pa","hi"]`; fallback Maharashtra/Unknown/`["hi","en"]`); module-level `adapter` for later swap-in.
- `backend/app/data/district_crops.py`: the 8-district kharif/rabi/suggested mapping exactly per the day file.
- `backend/app/data/languages.py`: 7 languages (hi/mr/gu/pa/te/ta/en) with vernacular names, regions, and per-language greeting `audioText`; `REGIONAL_MAPPING` for North/Central/West/East/NorthEast/South.
- `backend/app/routers/reference.py` (public): `GET /geo/reverse?lat=&lng=`, `GET /regions/crops?district=` (case-insensitive; unknown district → 200 with empty lists, not 404), `GET /languages` (`{languages, regionalMapping}`).
- Live curl verified: Nashik geo → `{"district":"Nashik","suggestedLanguages":["mr","hi"]}`; crops suggested `[Tomato, Onion, Grape]`; unknown district → empty lists; languages → 7 entries.
- Tests (`tests/test_reference.py`): 6 passed (day file asked for 5 — added Ludhiana box check).

### Task A2 — GET /v1/weather (Redis-cached proxy) — DONE

- `backend/app/services/weather.py`: `fetch_weather` — dev fixture when `weather_api_key` empty; otherwise OpenWeather `/data/2.5/weather` via `httpx.AsyncClient`, mapped to the same shape (`radarAvailable: false` for real API today, empty forecast — 5-day optional).
- `backend/app/routers/weather.py`: `GET /weather?lat=&lng=` (auth required via `current_user_id`); cache key `weather:{round(lat,1)}:{round(lng,1)}`, TTL 1800 s; hit → cached JSON, miss → fetch + `cache_set`.
- Tests (`tests/test_weather.py`): 3 passed — shape, cache counter (1 fetch for two same-coord calls, 2 after a different lat) with an in-memory `cache_get/cache_set` patch per the day-file instruction (never needs Redis), and 401 without auth.
- Live: `/weather` without auth → 401 envelope (authed path covered by tests; OpenWeather key absent → fixture shape).

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
47 passed, 2 warnings in 5.71s
  app_config 4 | auth 5 | infra 3 | mpin 5 | users 6 | profiles 6
  referral 4 | role_profiles 5 | reference 6 | weather 3
```

### Notes

- **Test-isolation fix:** `test_weather_shape` originally hit the real Redis client left over from the Day-1 infra test (event-loop-closed error in the full run). Per the day-file guidance, all weather tests now use the in-memory cache patch — the suite never needs Redis.
- `rainProbability` maps to OpenWeather's `clouds.all` (closest field on the current-weather endpoint) — flagged in case a forecast endpoint later provides a real precipitation probability.
- Language `regions` assignments beyond the day-file example (hi) are sensible defaults (mr/gu → West, pa → North, te/ta → South, en → none); adjust if the operator has a different mapping.

## Day 3 — Profile API (Tasks A1–A4)

**Status: implemented — 38/38 tests passing (21 new).**

### Task A1 — POST /v1/auth/register + GET/PUT /v1/users/me + farm boundary — DONE

- `backend/app/models/user.py`: `FarmBoundaryPoint`, `RegisterRequest` (with `idToken` per the day-file rule — register requires a verified Firebase token; optional `referralCode`, `roleProfiles` for A3/A4), `UserUpdateRequest` (all-optional), `FarmBoundaryRequest`, `VALID_PROFILES` set.
- `POST /auth/register` in `routers/auth.py`: verifies `idToken`, validates MPIN format, profile types (`422 INVALID_PROFILE_TYPE` for unknown types, empty profiles, or primary not in profiles), and phone-vs-token match (`400 PHONE_MISMATCH` — code not named in the day file, flagged in notes); requires a preceding `firebase-verify` (404 `NOT_FOUND` otherwise); updates the user doc with all wizard fields, `activeCrops`, `linkedProfiles`, `primaryProfile`, `activeProfile`, `mpinHash`; returns new tokens + full user (`mpinHash` stripped).
- `backend/app/routers/users.py`: `GET /me` (full user doc + additive `roleProfiles`), `PUT /me` (applies only non-None fields), `PUT /me/farm-boundary` (requires `farmer` in `linkedProfiles` → 403 `FORBIDDEN_ROLE`; stores points as `{lat,lng}`, `landAreaAcres`, `khasraNumber`). `require_role(user, *roles)` helper checks `activeProfile` per the day-file rule.
- `main.py`: users router mounted under `/v1`.
- Tests (`tests/test_users.py`): 6 passed — full-profile register, primary-not-in-profiles 422, GET /me keys, partial PUT, farm-boundary roundtrip, auth required.

### Task A2 — Profile link / unlink / activate / primary — DONE

- `backend/app/services/profile_routes.py`: `ACCESS_MAP` + `DEFAULT_HOME` ported from the persona×screen matrix (`docs/overview/04` §2) — `flutter-prototype/` is absent from this repo, so the matrix doc (which the day file says mirrors the prototype file) is the source used.
- `routers/users.py`: `POST /me/profiles` (409 `PROFILE_ALREADY_LINKED`), `DELETE /me/profiles/{type}` (404 `PROFILE_NOT_LINKED`; 409 `LAST_PROFILE` with message `कम से कम एक प्रोफाइल आवश्यक है`; promotes primary and falls back activeProfile), `POST /me/profiles/{type}/activate` (returns `activeProfile`, `defaultHomeRoute`, `user`), `PUT /me/profiles/{type}/primary`.
- Tests (`tests/test_profiles.py`): 6 passed — link, duplicate 409, last-profile 409, activate default home, unlink-active-promotes-primary, primary star.

### Task A3 — Referral code on register — DONE

- `referralCode: "ref_" + uid[:8]` generated for every user (new-user template + backfill on read of old docs, in `services/users.py`).
- `RegisterRequest.referralCode` optional; on register: lookup via `users` query on `referralCode` → 400 `INVALID_REFERRAL_CODE` for unknown code or self-referral; success writes `referral_attributions/{newUid}` with `status: "pending"` (coin award deferred to Day 13 — commented).
- Additive `referral: { "applied": bool }` on the register response (`RegisterResponse(AuthResponse)`).
- Tests (`tests/test_referral.py`): 4 passed — valid referral (attribution doc pending), invalid code 400, no referral (applied false, no doc), self-referral 400.

### Task A4 — Per-persona roleProfiles on register — DONE

- `backend/app/models/role_profiles.py`: `TransportRoleProfile`, `SellerRoleProfile`, `FarmLandlordRoleProfile`, `BrokerRoleProfile` + `ROLE_PROFILE_MODELS`.
- `RegisterRequest.roleProfiles: dict[str, dict] | None`; keys must be in `profiles` AND in `ROLE_PROFILE_MODELS`; failed variant parse → 422 `INVALID_ROLE_PROFILE` with `fieldErrors` keyed by profile type.
- Validated variants written to `users/{uid}/role_profiles/{profileType}` with `createdAt` (optionals omitted via `exclude_none`); `GET /me` returns them under additive `roleProfiles` ({} when none).
- Tests (`tests/test_role_profiles.py`): 5 passed — transport variant, seller optionals, missing-required 422, key-not-in-profiles 422, landlord+broker variants.

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
38 passed, 2 warnings in 5.68s
  test_app_config.py  4 | test_auth.py 5 | test_infra.py 3 | test_mpin.py 5
  test_users.py 6 | test_profiles.py 6 | test_referral.py 4 | test_role_profiles.py 5
```

### Blockers / notes

- **`flutter-prototype/` missing from this repo** — `profile_routes.dart` could not be ported file-to-file; `ACCESS_MAP` was built from `docs/overview/04-persona-screen-matrix.md` §2 (the doc that mirrors the prototype's map). If the prototype appears later, diff the two.
- **`PHONE_MISMATCH` (400)** and `INVALID_ROLE_PROFILE`/`INVALID_PROFILE_TYPE` (422) codes are not in the conventions §6 named list — used where the day file mandates the behavior but names no code. Flagging for operator review.
- **Register ordering:** validation order is idToken → MPIN format → phone match → profile/role-profile validity → user-exists → referral. Tests must call `firebase-verify` first (the day-file "preceding firebase-verify" rule).
- Firebase credentials still absent here, so live register cannot pass token verification (same as Day 2); mocked tests cover the full flow. Live smoke: health 200, `/users/me` without auth → 401 envelope, register body validation → 422.

## Day 2 — Auth backend (Tasks A1–A2)

**Status: implemented — 17/17 tests passing.**

### Task A1 — POST /v1/auth/firebase-verify + JWT issue/refresh — DONE

- `backend/app/models/auth.py`: `FirebaseVerifyRequest`, `TokenPair`, `AuthResponse`, `RefreshRequest` (+ `MpinSetRequest`, `MpinVerifyRequest`, `MpinResetRequest`, `OkResponse` for A2).
- `backend/app/services/tokens.py`: `create_access_token`, `create_refresh_token` (HS256 via python-jose, `sub`/`type`/`iat`/`exp` claims), `decode_token(token, expected_type)` → 401 `INVALID_TOKEN` on JWTError or type mismatch.
- `backend/app/services/users.py`: `upsert_user_from_firebase` creates the full `users/{uid}` doc per day-file template (createdAt = UTC ISO); `get_user`; `set_mpin_hash`.
- `backend/app/routers/auth.py` (prefix `/auth`): `POST /firebase-verify` verifies the Firebase ID token, normalizes phone to `+91...`, upserts the user, returns `AuthResponse` with `mpinHash` stripped (schema: never returned); 401 `INVALID_FIREBASE_TOKEN` on `InvalidIdTokenError`. `POST /refresh` rotates both tokens.
- `main.py`: auth router mounted; **error-envelope exception handler** — every `HTTPException` with a dict detail now renders as `{ "error": { "code", "message", "fieldErrors" } }` (conventions §6). Non-dict details are wrapped as `{"code": "ERROR"}`.
- Tests (`tests/test_auth.py`, fixtures in `tests/conftest.py` — mocked `firebase_admin.auth.verify_id_token` + in-memory user store patching `app.services.users.get_doc/set_doc`): new-user verify, invalid token → 401 envelope, existing-user verify (`isNewUser: False`), refresh roundtrip, access-token-to-refresh → 401 `INVALID_TOKEN`. 5 passed.

### Task A2 — MPIN set / verify / reset — DONE

- `backend/app/core/security.py`: passlib `CryptContext` bcrypt; `hash_mpin`, `verify_mpin`, `validate_mpin_format` (4 ASCII digits, else 422 `INVALID_MPIN_FORMAT`).
- `backend/app/core/deps.py`: `current_user_id` — parses `Bearer <token>`, decodes as access token; missing/malformed header → 401 `MISSING_TOKEN`.
- Endpoints on `routers/auth.py`: `POST /mpin/set` (auth, validates format, stores bcrypt hash), `POST /mpin/verify` (auth; 409 `MPIN_NOT_SET` if no hash; 401 `WRONG_MPIN` on mismatch), `POST /mpin/reset` (public, requires fresh Firebase ID token; 404 `NOT_FOUND` if user absent).
- Tests (`tests/test_mpin.py`): set+verify happy path, wrong MPIN → 401, verify-before-set → 409, bad format → 422, reset swaps hash (old fails, new verifies). 5 passed.

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
tests/test_app_config.py  4 passed
tests/test_auth.py        5 passed
tests/test_infra.py       3 passed
tests/test_mpin.py        5 passed
17 passed, 2 warnings in 2.37s
```

### Blockers / notes

- **Dependency deviation (reported per conventions §1.7):** `bcrypt` pinned to `<4.1` in `requirements.txt`. passlib 1.7.4 is incompatible with bcrypt ≥ 4.1 (its backend detection feeds bcrypt 5 a >72-byte "password" → `ValueError`). The day file lists `passlib[bcrypt]>=1.7.4` without a pin; the pin is the minimal fix. Alternative (replacing passlib with raw `bcrypt`) would deviate further from the day file.
- **Day-1 test updated:** `test_app_config_missing` now asserts the `{"error": {"code": "APP_CONFIG_MISSING"}}` envelope instead of FastAPI's default `{"detail": ...}` — the new envelope handler (a Day-2 deliverable) changed the response shape.
- **Firebase not initialized in this environment** (no service-account JSON): live `POST /v1/auth/firebase-verify` with a garbage token returns 500 because `verify_id_token` raises `ValueError` before token parsing. With credentials present it raises `InvalidIdTokenError` → 401 envelope, which the mocked tests verify. Live happy-path testing is blocked on credentials, same as Day 1 seeding.
- `MISSING_TOKEN`, envelope shapes verified live: mpin/verify without auth → 401 envelope; health still 200.

## Day 1 — Foundation (Tasks A1–A4)

**Status: implemented — 7/7 tests passing.**

### Task A1 — Backend skeleton + docker-compose + health endpoint — DONE

- FastAPI app at `backend/app/main.py` boots under uvicorn; `GET /v1/health` → `{"status":"ok"}`; `/docs` returns Swagger UI (HTTP 200).
- `backend/app/core/config.py`: pydantic-settings `Settings` with all day-file fields (+ `sentry_dsn` from A4); reads `.env`.
- `backend/.env.example` lists every field with dev defaults, no real secrets.
- `backend/requirements.txt` with the exact day-file packages + `sentry-sdk[fastapi]>=2.14` (A4).
- venv created at `backend/.venv`, all deps installed (Python 3.14, fastapi 0.141, firebase-admin 7.5, sentry-sdk 2.69).
- `infra/docker-compose.yml`: `api` (build `../backend`, port 8000, env_file) + `redis:7-alpine` (port 6379). Docker is not installed in this environment, so the api service was exercised via local uvicorn; Redis 8.0.5 was already running locally on 6379.
- Verified: `curl http://localhost:8000/v1/health` → 200 `{"status":"ok"}`, `/docs` → 200.

### Task A2 — Firebase init, Firestore helper, Redis cache helper — DONE

- `backend/app/core/firebase.py`: `init_firebase()` — skips with a warning if the service-account JSON is missing (dev mode boots clean), guards against double init.
- `backend/app/core/db.py`: Firestore approach is `google.cloud.firestore.AsyncClient(project=...)` (documented in-file; no Admin init needed for Firestore). Helpers: `get_doc`, `set_doc`, `query` (filters as `(field, op, value)` tuples).
- `backend/app/core/cache.py`: `redis.asyncio` client with `get_redis`, `cache_get`, `cache_set(ttl)`, `cache_delete`.
- `init_firebase()` called from the startup handler in `main.py`.
- `backend/pytest.ini`: `asyncio_mode = auto`, `pythonpath = .`; shared `client` fixture in `tests/conftest.py`.
- Tests (`tests/test_infra.py`): `test_settings_load`, `test_health`, `test_cache_roundtrip` — all 3 pass against the running local Redis (no skips).

### Task A3 — GET /v1/app-config (version gate / remote config) — DONE

- `backend/app/models/app_config.py`: `AppConfigOut` (minSupportedVersion, forceUpdate, featureFlags, maintenanceMode).
- `backend/app/routers/app_config.py`: public `GET /app-config?version=&platform=` (single object, no envelope); 404 `APP_CONFIG_MISSING` when the doc is absent; when `version` is given, `forceUpdate` is computed server-side from numeric version tuples, otherwise the stored value is echoed.
- `backend/scripts/seed_app_config.py`: seeds `app_config/current` via `set_doc`.
- Tests (`tests/test_app_config.py`): shape, force-update computation (0.9.0 → true, 1.2.0 → false), public access, plus a missing-doc 404 test — all pass with an in-memory patch of `get_doc`.
- Verified live: `curl "http://localhost:8000/v1/app-config?version=0.9.0&platform=android"` — logic verified by tests; live response 500s until Firestore credentials exist (see Blockers).

### Task A4 — Sentry SDK wiring — DONE

- `sentry-sdk[fastapi]>=2.14` added; `SENTRY_DSN=` in `.env.example` with a pointer to the Sentry project settings.
- `main.py` initializes Sentry with `FastApiIntegration`, `traces_sample_rate=0.2`, `environment=settings.env` — silently skipped when DSN is empty (all tests pass with no DSN).
- Dev-only probe `GET /v1/debug/sentry-test` raises `RuntimeError("sentry smoke test")` in `env=dev`, else 404. Verified: returns 500 with empty DSN; will be captured by Sentry once a real DSN is set (manual console check pending — no DSN available in this environment).

### Test run (final)

```
$ cd backend && .venv/bin/pytest -v
tests/test_app_config.py::test_app_config_shape PASSED
tests/test_app_config.py::test_force_update_computed PASSED
tests/test_app_config.py::test_app_config_public PASSED
tests/test_app_config.py::test_app_config_missing PASSED
tests/test_infra.py::test_settings_load PASSED
tests/test_infra.py::test_health PASSED
tests/test_infra.py::test_cache_roundtrip PASSED
7 passed, 2 warnings in 0.12s
```

Warnings are `on_event` deprecations from FastAPI (startup handler per day-file spec); can move to a lifespan handler later without behavior change.

### Blockers / notes

- **No Docker** in this environment — `infra/docker-compose.yml` was created but not exercised; `docker compose up -d redis` is the documented path where Docker exists (a local Redis was used for tests).
- **No GCP/Firestore credentials** — `scripts/seed_app_config.py` fails with `DefaultCredentialsError` and live `/v1/app-config` returns 500 until Application Default Credentials or `secrets/firebase-service-account.json` are provided. Route logic is fully verified via tests. Rerun the seed script once credentials exist.
- **No real Sentry DSN** — wiring verified structurally (empty DSN boots clean; probe returns 500); the Sentry-console event check is pending a dev DSN.
- **Repo has no `.gitignore` yet** — before committing, add `backend/.env`, `backend/.venv/`, `backend/secrets/`, `__pycache__/` per `docs/overview/02` §1.
- Version parsing treats non-numeric parts as 0 and pads to 3 segments, e.g. `"0.9" → (0, 9, 0)`.

## Done-when checklist (Day 1, backend items)

- [x] `curl -s http://localhost:8000/v1/health` → `{"status":"ok"}` (uvicorn from `backend/.venv`)
- [ ] `docker compose -f infra/docker-compose.yml up -d redis` — not verifiable here (no Docker); local Redis used instead, `redis-cli ping` → `PONG`
- [x] `cd backend && .venv/bin/pytest -v` → 7 passed (≥3)
- [x] `backend/app/core/{config,firebase,db,cache}.py` exist with the specified functions
- [x] `curl -s "http://localhost:8000/v1/app-config?version=0.9.0&platform=android"` — tests green (X12); live 200 pending Firestore credentials
- [ ] Sentry event visible in console (X14) — pending real DSN (manual check)
