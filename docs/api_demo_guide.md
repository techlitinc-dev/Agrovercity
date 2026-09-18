# AGROVERCITY Backend — Beginner API Testing Guide (Swagger Demo)

Every endpoint (236) with a ready-to-paste request body.
All payloads are generated from the backend's OpenAPI schema (`/openapi.json`), so they pass Pydantic validation as-is.

> **Convention:** values in `<ANGLE_BRACKETS>` are placeholders — replace them with real IDs copied from the GET list APIs (see §3). Everything else can be pasted directly.

---

## 1. Start the server

**Linux / Ubuntu**
```bash
cd backend
.venv/bin/uvicorn app.main:app --port 8080
```

**Windows CMD**
```cmd
cd C:\ShuBhanGi\Agrovercity\backend
.venv\Scripts\activate
python -m uvicorn app.main:app --port 8080
```

Then open:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## 2. Generate a token and authorize

Open a **second** terminal (keep the server running).

**Linux**
```bash
cd backend
.venv/bin/python -c "from app.services.tokens import create_access_token; print(create_access_token('<UID>'))"
```

**Windows CMD**
```cmd
cd C:\ShuBhanGi\Agrovercity\backend
.venv\Scripts\python.exe -c "from app.services.tokens import create_access_token; print(create_access_token('YOUR_FIRESTORE_USER_ID'))"
```

`<UID>` = a real document ID from your Firestore `users` collection.

In Swagger:
1. Click **Authorize** 🔒 (top right)
2. Paste **only the token** — do **not** add `Bearer `
3. Click **Authorize**, then **Close**

For admin APIs: use a Firebase ID token instead (admin endpoints below are marked).

## 3. Golden rules for the demo

1. **Public first:** `/v1/health`, `/v1/app-config`, `/v1/weather`, `/v1/mandi/prices` need no token.
2. **Never invent IDs.** Every `<...>` placeholder comes from a GET call, e.g.:
   - `GET /v1/gamification/rewards` → copy `id` → `POST /v1/gamification/redeem`
   - `POST /v1/transport/bookings` → copy `id` → `PATCH /v1/transport/bookings/{id}`
   - `GET /v1/products` → copy `id` → `POST /v1/orders`
3. **Role gates:** some APIs need the user's *active profile* to match (e.g. `farmer`, `seller`, `transporter`). Activate with `POST /v1/users/me/profiles` then `POST /v1/users/me/profiles/{type}/activate`. Wrong role → `403 FORBIDDEN_ROLE`.
4. Check **status code + body + headers** on every call.

## 4. Error cases to demo

| Case | Expected |
|---|---|
| No token on protected API | `401 MISSING_TOKEN` |
| Wrong active profile | `403 FORBIDDEN_ROLE` |
| Invalid body / missing field | `422` with `fieldErrors` |
| Wrong file type / too large | `415` / `413` |
| >~100 requests/min | `429 RATE_LIMITED` + `Retry-After` header (restart clears dev counters) |

All errors follow the same envelope:
```json
{ "error": { "code": "ERROR_CODE", "message": "...", "fieldErrors": {} } }
```

## 5. File-upload endpoints

Attach a real `.jpg`/`.png` via **Try it out → Choose File → Execute**:

- `POST /v1/advisory/disease-scan` — 1 crop-leaf photo
- `POST /v1/post-harvest/grade` — **1–3** produce photos
- `POST /v1/vault/documents` — 1 document (PDF/photo)
- `POST /v1/insurance/claims` — 1–3 `damagePhotos` + JSON body fields

## 6. Finish with the automated suite

```bash
cd backend
.venv/bin/python -m pytest        # Linux
.venv\Scripts\python.exe -m pytest  # Windows
```
Expected: **396 passed**.

---

# Endpoint Reference — 236 endpoints with sample payloads

Generated from the app's OpenAPI schema. Groups are ordered alphabetically by Swagger tag; use your editor's search (Ctrl+F) or Swagger's tag filter to find an endpoint.

### addresses

#### `GET /v1/addresses`
List Addresses
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/addresses`
Create Address
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "label": "Home",
  "line1": "House 12, near panchayat bhawan",
  "village": "Rampur",
  "district": "Lucknow",
  "state": "Uttar Pradesh",
  "pincode": "226001",
  "lat": 26.85,
  "lng": 80.95,
  "isDefault": true
}
```

#### `DELETE /v1/addresses/{address_id}`
Delete Address
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: address_id=`abc123`

#### `PUT /v1/addresses/{address_id}`
Update Address
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: address_id=`abc123`
- Request body:
```json
{
  "label": "Home",
  "line1": "House 12, near panchayat bhawan",
  "village": "Rampur",
  "district": "Lucknow",
  "state": "Uttar Pradesh",
  "pincode": "226001",
  "lat": 26.85,
  "lng": 80.95,
  "isDefault": true
}
```


### admin

#### `GET /v1/admin/analytics/summary`
Analytics Summary
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)

#### `POST /v1/admin/broadcast`
Broadcast
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Request body:
```json
{
  "segment": {
    "role": "farmer",
    "district": "Lucknow"
  },
  "title": "Mandi closed tomorrow",
  "body": "Lucknow mandi closed for maintenance",
  "dryRun": true
}
```

#### `GET /v1/admin/claims`
List Claims
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Optional params: status, page, pageSize

#### `PUT /v1/admin/claims/{user_id}/{claim_id}`
Advance Claim
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: user_id=`abc123`, claim_id=`abc123`
- Request body:
```json
{
  "newStatus": "disbursed",
  "approvedAmount": 15000,
  "dbtTransactionId": "DBT123456789",
  "note": "Amount credited"
}
```

#### `POST /v1/admin/content/{collection}`
Create Content
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: collection=`news`
- Request body:
```json
{
  "title": "PM-Kisan 20th installment update",
  "summary": "New beneficiary list released"
}
```

#### `DELETE /v1/admin/content/{collection}/{doc_id}`
Delete Content
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: collection=`news`, doc_id=`abc123`

#### `PUT /v1/admin/content/{collection}/{doc_id}`
Update Content
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: collection=`news`, doc_id=`abc123`
- Request body:
```json
{
  "title": "PM-Kisan 20th installment update (edited)"
}
```

#### `GET /v1/admin/kyc/pending`
Kyc Pending
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Optional params: page, pageSize

#### `POST /v1/admin/kyc/{entity_id}/reject`
Kyc Reject
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: entity_id=`abc123`
- Request body:
```json
{
  "reason": "Aadhaar photo unreadable"
}
```

#### `POST /v1/admin/kyc/{entity_id}/verify`
Kyc Verify
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: entity_id=`abc123`

#### `POST /v1/admin/login`
Login
- Token: **not required** (public)

#### `GET /v1/admin/rates/pending`
Pending Rates
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Optional params: page, pageSize

#### `POST /v1/admin/rates/{rate_id}/approve`
Approve Rate
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: rate_id=`abc123`

#### `POST /v1/admin/rates/{rate_id}/reject`
Reject Rate
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: rate_id=`abc123`
- Request body:
```json
{
  "reason": "Price does not match Agmarknet"
}
```

#### `GET /v1/admin/reports`
Admin Reports
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Optional params: status, page, pageSize

#### `POST /v1/admin/reports/{report_id}/resolve`
Resolve Report
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: report_id=`abc123`
- Request body:
```json
{
  "action": "dismiss",
  "note": "Checked — no violation"
}
```

#### `GET /v1/admin/settlements`
Admin Settlements
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Optional params: status, page, pageSize

#### `POST /v1/admin/settlements/{settlement_id}/settle`
Settle
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: settlement_id=`abc123`
- Request body:
```json
{
  "action": "approve"
}
```

#### `GET /v1/admin/users`
List Users
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Optional params: persona, page, pageSize

#### `PUT /v1/admin/users/{user_id}/status`
Set User Status
- Token: **required — Admin token** (`POST /v1/admin/login`, then use returned token)
- Required query/path params: user_id=`abc123`
- Request body:
```json
{
  "status": "active"
}
```


### advisory

#### `POST /v1/advisory/disease-scan`
Disease Scan
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- **Multipart upload** — file field(s): file (attach one `.jpg`/`.png` (or PDF for vault docs))

#### `POST /v1/advisory/npk`
Npk
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "n": 1,
  "p": 1,
  "k": 1,
  "crop": "wheat",
  "soilType": "loamy"
}
```

#### `GET /v1/advisory/pest-radar`
Pest Radar
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: lat, lng, radiusKm

#### `POST /v1/advisory/saturation`
Saturation
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "crop": "wheat",
  "district": "Lucknow",
  "lat": 26.85,
  "lng": 80.95,
  "radiusKm": 25,
  "shareSowingIntent": true
}
```

#### `POST /v1/advisory/sowing-intent`
Sowing Intent
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "crop": "wheat",
  "plannedDate": "2026-09-20",
  "plotId": "abc123"
}
```


### app-config

#### `GET /v1/app-config`
Get App Config
- Token: **not required** (public)
- Optional params: version, platform


### auth

#### `POST /v1/auth/firebase-verify`
Firebase Verify
- Token: **not required** (public)
- Request body:
```json
{
  "idToken": "<Firebase ID token>"
}
```

#### `POST /v1/auth/mpin/reset`
Mpin Reset
- Token: **not required** (public)
- Request body:
```json
{
  "idToken": "<Firebase ID token>",
  "newMpin": "1234"
}
```

#### `POST /v1/auth/mpin/set`
Mpin Set
- Token: **not required** (public)
- Request body:
```json
{
  "mpin": "1234"
}
```

#### `POST /v1/auth/mpin/verify`
Mpin Verify
- Token: **not required** (public)
- Request body:
```json
{
  "mpin": "1234"
}
```

#### `POST /v1/auth/refresh`
Refresh
- Token: **not required** (public)
- Request body:
```json
{
  "refreshToken": "eyJhbGciOiJIUzI1NiJ9.<refresh-token-from-login>"
}
```

#### `POST /v1/auth/register`
Register
- Token: **not required** (public)
- Request body:
```json
{
  "idToken": "<Firebase ID token>",
  "name": "Ramesh Kumar",
  "phone": "+919812345678",
  "state": "Uttar Pradesh",
  "district": "Lucknow",
  "tehsil": "Mohanlalganj",
  "village": "Rampur",
  "landAreaAcres": 1,
  "soilType": "loamy",
  "irrigationType": "canal",
  "crops": [
    "wheat"
  ],
  "mpin": "1234",
  "profiles": [
    "profiles"
  ],
  "primaryProfile": "farmer",
  "referralCode": "AGRO-1234",
  "roleProfiles": {}
}
```


### bank-accounts

#### `GET /v1/bank-accounts`
List Accounts
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/bank-accounts`
Create Account
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "accountHolder": "Ramesh Kumar",
  "accountNumber": "1234567890",
  "ifsc": "SBIN0001234",
  "bankName": "SBI"
}
```

#### `DELETE /v1/bank-accounts/{account_id}`
Delete Account
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: account_id=`abc123`

#### `POST /v1/bank-accounts/{account_id}/set-primary`
Set Primary
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: account_id=`abc123`

#### `POST /v1/bank-accounts/{account_id}/verify`
Verify Account
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: account_id=`abc123`


### chatbot

#### `POST /v1/chatbot/handoff`
Handoff
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "sessionId": "session-001",
  "reason": "Need expert advice"
}
```

#### `GET /v1/chatbot/history`
History
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: sessionId=`session-001`
- Optional params: page, pageSize

#### `POST /v1/chatbot/messages`
Send Message
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "sessionId": "session-001",
  "text": "मेरी फसल पर पीले धब्बे हैं",
  "audioUrl": "https://example.com/audio.mp3",
  "language": "hi"
}
```


### climate

#### `GET /v1/climate/carbon-potential`
Carbon Potential
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: lat, lng

#### `GET /v1/climate/resilient-varieties`
Resilient Varieties
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: crop, district


### content

#### `GET /v1/channels`
List Channels
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `GET /v1/channels/{channel_id}/chat`
Get Chat
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: channel_id=`abc123`

#### `POST /v1/channels/{channel_id}/chat`
Post Chat
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: channel_id=`abc123`
- Optional params: joined, left
- Request body:
```json
{
  "text": "मेरी फसल पर पीले धब्बे हैं"
}
```

#### `GET /v1/news`
List News
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: category, page, pageSize


### contracts

#### `GET /v1/contracts`
List Contracts
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: status, page, pageSize

#### `GET /v1/contracts/{contract_id}`
Get Contract
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: contract_id=`abc123`

#### `POST /v1/contracts/{contract_id}/accept`
Accept Contract
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: contract_id=`abc123`
- Request body:
```json
{
  "signatureData": "signed-by-ramesh",
  "consentTimestamp": "2026-09-20T10:00:00Z",
  "mpin": "1234"
}
```


### devices

#### `POST /v1/devices`
Register Device Top
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "fcmToken": "device-token-123",
  "platform": "android",
  "locale": "hi-IN"
}
```

#### `DELETE /v1/devices/{token_hash}`
Delete Device Top
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: token_hash=`token hash`


### diary

#### `GET /v1/diary/entries`
List Entries
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: type, category, from, to, page, pageSize

#### `POST /v1/diary/entries`
Create Entry
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "title": "North field",
  "category": "seeds",
  "type": "expense",
  "date": "2026-09-20",
  "amount": 1,
  "cropName": "wheat",
  "notes": "Sown on 10 July, urea applied twice"
}
```

#### `DELETE /v1/diary/entries/{entry_id}`
Delete Entry
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: entry_id=`abc123`

#### `GET /v1/diary/report`
Diary Report
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: from, to


### equipment

#### `GET /v1/equipment`
List Equipment
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: type, lat, lng

#### `DELETE /v1/equipment/bookings/{booking_id}`
Cancel Booking
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: booking_id=`abc123`

#### `POST /v1/equipment/slots/{slot_id}/book`
Book Slot
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: slot_id=`abc123`
- Request body:
```json
{
  "farmerName": "Ramesh Kumar"
}
```

#### `POST /v1/equipment/slots/{slot_id}/waitlist`
Join Waitlist
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: slot_id=`abc123`

#### `GET /v1/equipment/{equipment_id}/slots`
Get Slots
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: equipment_id=`abc123`
- Optional params: date


### equipment-owner

#### `POST /v1/equipment`
Create Equipment
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "name": "Ramesh Kumar",
  "type": "farmer",
  "hourlyRate": 1,
  "ownerType": "farmer",
  "perAcreRate": 1,
  "slotTemplate": [
    {}
  ],
  "rcDocUrl": "https://example.com/audio.mp3",
  "insuranceDocUrl": "https://example.com/audio.mp3"
}
```

#### `GET /v1/equipment/bookings/pending`
Pending Bookings
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/equipment/bookings/{booking_id}/approve`
Approve Booking
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: booking_id=`abc123`

#### `POST /v1/equipment/bookings/{booking_id}/reject`
Reject Booking
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: booking_id=`abc123`
- Request body:
```json
{
  "reason": "Need expert advice"
}
```

#### `GET /v1/equipment/owner/fleet`
Owner Fleet
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `PUT /v1/equipment/{equipment_id}`
Update Equipment
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: equipment_id=`abc123`
- Request body:
```json
{
  "name": "Ramesh Kumar",
  "type": "farmer",
  "hourlyRate": 1,
  "ownerType": "farmer",
  "perAcreRate": 1,
  "slotTemplate": [
    {}
  ],
  "rcDocUrl": "https://example.com/audio.mp3",
  "insuranceDocUrl": "https://example.com/audio.mp3"
}
```


### finance

#### `GET /v1/finance/credit-score`
Credit Score
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `GET /v1/finance/kcc`
Kcc
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/finance/loan-calculator`
Loan Calculator
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "amount": 5000.0,
  "tenureMonths": 3.0,
  "interestRate": 1
}
```

#### `GET /v1/finance/loans`
List Loans
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/finance/loans/apply`
Apply Loan
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "amount": 1,
  "tenureMonths": 3.0,
  "purpose": "seeds"
}
```


### fpo

#### `GET /v1/fpo/machinery`
Machinery
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: week

#### `GET /v1/fpo/me`
Fpo Me
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `GET /v1/fpo/pools`
List Pools
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/fpo/pools/{pool_id}/join`
Join Pool
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: pool_id=`abc123`
- Request body:
```json
{
  "units": 1
}
```


### gamification

#### `GET /v1/gamification/ledger`
Ledger
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/gamification/redeem`
Redeem
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "rewardId": "<REWARD_ID — copy from GET /v1/gamification/rewards>"
}
```

#### `GET /v1/gamification/rewards`
Rewards
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `GET /v1/gamification/status`
Status
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)


### gyan

#### `GET /v1/blogs`
List Blogs
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: category, page, pageSize

#### `POST /v1/blogs/{blog_id}/bookmark`
Toggle Bookmark
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: blog_id=`abc123`

#### `POST /v1/blogs/{blog_id}/like`
Like Blog
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: blog_id=`abc123`

#### `GET /v1/expert-talks`
List Talks
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/expert-talks/{talk_id}/questions`
Ask Question
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: talk_id=`abc123`
- Request body:
```json
{
  "question": "abc123"
}
```

#### `POST /v1/expert-talks/{talk_id}/register`
Register Talk
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: talk_id=`abc123`

#### `GET /v1/videos`
List Videos
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: category, page, pageSize

#### `GET /v1/workshops`
List Workshops
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/workshops/{workshop_id}/enroll`
Enroll Workshop
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: workshop_id=`abc123`
- Request body:
```json
{
  "useCoins": true,
  "coinsToRedeem": 1
}
```


### insurance

#### `GET /v1/insurance/claims`
List Claims
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/insurance/claims`
Submit Claim
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- **Multipart upload** — file field(s): damagePhotos (attach the file here)
- Other form fields:
```json
{
  "policyId": "abc123",
  "cropName": "wheat",
  "calamityType": "drought",
  "dateOfDamage": "2026-09-10",
  "cropStage": "flowering",
  "estimatedLossPercent": 1,
  "gpsCoordinates": "26.85, 80.95",
  "village": "Rampur"
}
```

#### `GET /v1/insurance/claims/{claim_id}`
Get Claim
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: claim_id=`abc123`

#### `POST /v1/insurance/claims/{claim_id}/appeal`
Appeal Claim
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: claim_id=`abc123`
- Request body:
```json
{
  "reason": "Need expert advice",
  "photos": [
    "photos"
  ]
}
```

#### `GET /v1/insurance/policies`
List Policies
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/insurance/policies/apply`
Apply Policy
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "cropName": "wheat",
  "season": "kharif",
  "landAreaAcres": 5
}
```

#### `GET /v1/insurance/policies/{policy_id}/certificate`
Policy Certificate
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: policy_id=`abc123`

#### `GET /v1/insurance/rates`
List Rates
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: season, crop, page, pageSize


### jobs

#### `POST /v1/jobs/rent-reminders/run`
Run Rent Reminders Job
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: x-cron-secret

#### `POST /v1/jobs/settlements/run`
Run Settlements Job
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: x-cron-secret
- Request body:
```json
{
  "periodStart": "2026-07-01",
  "periodEnd": "2026-09-30"
}
```


### land

#### `GET /v1/land/leases`
List Leases
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: status, page, pageSize

#### `POST /v1/land/leases`
Create Lease
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "plotId": "abc123",
  "tenantName": "Ramesh Kumar",
  "tenantPhone": "+919812345678",
  "monthlyRentRupees": 1,
  "startDate": "2026-09-20",
  "endDate": "2026-09-20"
}
```

#### `DELETE /v1/land/leases/{lease_id}`
Delete Lease
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: lease_id=`abc123`

#### `PUT /v1/land/leases/{lease_id}`
Update Lease
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: lease_id=`abc123`
- Request body:
```json
{
  "monthlyRentRupees": 1,
  "endDate": "2026-09-20",
  "status": "active",
  "verified": true
}
```

#### `GET /v1/land/leases/{lease_id}/payments`
List Payments
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: lease_id=`abc123`
- Optional params: page, pageSize

#### `POST /v1/land/leases/{lease_id}/payments`
Add Payment
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: lease_id=`abc123`
- Request body:
```json
{
  "amountRupees": 1,
  "month": "September 2026",
  "method": "cash",
  "paidAt": "abc123"
}
```

#### `GET /v1/land/plots`
List Plots
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/land/plots`
Create Plot
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "name": "Ramesh Kumar",
  "village": "Rampur",
  "district": "Lucknow",
  "areaAcres": 1,
  "gatNumber": "abc123",
  "soilType": "loamy"
}
```

#### `DELETE /v1/land/plots/{plot_id}`
Delete Plot
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: plot_id=`abc123`

#### `PUT /v1/land/plots/{plot_id}`
Update Plot
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: plot_id=`abc123`
- Request body:
```json
{
  "name": "Ramesh Kumar",
  "village": "Rampur",
  "district": "Lucknow",
  "areaAcres": 1,
  "gatNumber": "abc123",
  "soilType": "loamy"
}
```


### land-market

#### `GET /v1/land/lease-requests`
List Lease Requests
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: status, page, pageSize

#### `POST /v1/land/lease-requests`
Create Lease Request
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "listingId": "abc123",
  "durationMonths": 1.0,
  "message": "Mandi rates updated daily at 6 AM"
}
```

#### `POST /v1/land/lease-requests/{request_id}/accept`
Accept Lease Request
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: request_id=`abc123`

#### `POST /v1/land/lease-requests/{request_id}/reject`
Reject Lease Request
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: request_id=`abc123`
- Request body:
```json
{
  "reason": "Need expert advice"
}
```

#### `GET /v1/land/leases/{lease_id}/agreement-pdf`
Lease Agreement Pdf
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: lease_id=`abc123`

#### `GET /v1/land/listings`
Browse Listings
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: near, acres, page, pageSize

#### `POST /v1/land/listings`
Create Listing
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "village": "Rampur",
  "district": "Lucknow",
  "lat": 26.85,
  "lng": 80.95,
  "areaAcres": 1,
  "expectedRentRupees": 1,
  "soilType": "loamy",
  "waterSource": "canal",
  "plotId": "abc123"
}
```

#### `GET /v1/land/listings/mine`
My Listings
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `DELETE /v1/land/listings/{listing_id}`
Delete Listing
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: listing_id=`abc123`

#### `PUT /v1/land/listings/{listing_id}`
Update Listing
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: listing_id=`abc123`
- Request body:
```json
{
  "village": "Rampur",
  "district": "Lucknow",
  "lat": 26.85,
  "lng": 80.95,
  "areaAcres": 1,
  "expectedRentRupees": 1,
  "soilType": "loamy",
  "waterSource": "canal",
  "plotId": "abc123"
}
```


### land-records

#### `GET /v1/land-records/search`
Search
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: gatNumber, village, district, type

#### `POST /v1/land-records/{record_id}/import`
Import Record
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: record_id=`abc123`

#### `GET /v1/land-records/{record_id}/pdf`
Record Pdf
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: record_id=`abc123`


### livestock

#### `GET /v1/dairy-products`
List Dairy
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: category, page, pageSize

#### `POST /v1/dairy-products/{product_id}/order`
Order Dairy
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: product_id=`abc123`
- Request body:
```json
{
  "quantity": 1.0
}
```

#### `GET /v1/gaushalas`
List Gaushalas
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: district, lat, lng, page, pageSize

#### `POST /v1/gaushalas/{gaushala_id}/manure-order`
Manure Order
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: gaushala_id=`abc123`
- Request body:
```json
{
  "product": "cow-dung manure",
  "quantity": "2"
}
```

#### `GET /v1/nurseries`
List Nurseries
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: lat, lng, page, pageSize

#### `GET /v1/vets`
List Vets
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: lat, lng, emergency, page, pageSize

#### `POST /v1/vets/bookings/{booking_id}/complete`
Complete Vet Booking
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: booking_id=`abc123`

#### `POST /v1/vets/{vet_id}/book`
Book Vet
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: vet_id=`abc123`
- Request body:
```json
{
  "visitType": "farm",
  "slot": "2026-09-20 06:00-10:00",
  "animalType": "cow"
}
```


### lots

#### `GET /v1/market/lots`
List Lots
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: status, page, pageSize

#### `POST /v1/market/lots`
Create Lot
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "crop": "wheat",
  "quantityQuintals": 1,
  "expectedRate": 1,
  "harvestDate": "2026-09-20",
  "location": {},
  "photos": [
    "photos"
  ]
}
```

#### `DELETE /v1/market/lots/{lot_id}`
Withdraw Lot
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: lot_id=`abc123`

#### `PUT /v1/market/lots/{lot_id}`
Update Lot
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: lot_id=`abc123`
- Request body:
```json
{
  "crop": "wheat",
  "quantityQuintals": 1,
  "expectedRate": 1,
  "harvestDate": "2026-09-20",
  "location": {},
  "photos": [
    "photos"
  ]
}
```


### mandi

#### `GET /v1/mandi/compare`
Compare
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: crop=`wheat`, quantityQuintals=`1`
- Optional params: lat, lng

#### `GET /v1/mandi/list`
List Mandis
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `GET /v1/mandi/prices`
Get Prices
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: crop, district, lat, lng, page, pageSize

#### `GET /v1/mandi/prices/history`
Price History
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: crop, mandi, months

#### `GET /v1/mandi/vyapari-rates`
Vyapari Rates
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: crops


### marketplace

#### `GET /v1/cart`
Get Cart
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/cart/items`
Add Cart Item
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "productId": "abc123",
  "quantity": 1
}
```

#### `DELETE /v1/cart/items/{product_id}`
Remove Cart Item
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: product_id=`abc123`

#### `PUT /v1/cart/items/{product_id}`
Update Cart Item
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: product_id=`abc123`
- Request body:
```json
{
  "quantity": 1
}
```

#### `GET /v1/products`
List Products
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: category, query, lat, lng, page, pageSize

#### `GET /v1/products/{product_id}`
Get Product
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: product_id=`abc123`

#### `GET /v1/products/{product_id}/certificate`
Get Certificate
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: product_id=`abc123`

#### `GET /v1/products/{product_id}/reviews`
List Reviews
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: product_id=`abc123`
- Optional params: page, pageSize

#### `POST /v1/products/{product_id}/reviews`
Post Review
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: product_id=`abc123`
- Request body:
```json
{
  "rating": 5,
  "comment": "On time service"
}
```


### notifications

#### `GET /v1/notifications`
List Notifications
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/notifications/read`
Mark Read
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "notificationIds": [
    "<NOTIFICATION_ID — copy from GET /v1/notifications>"
  ]
}
```


### orders

#### `GET /v1/orders`
List Orders
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/orders`
Place Order
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "items": [
    {
      "productId": "abc123",
      "quantity": 1
    }
  ],
  "paymentMethod": "upi",
  "idempotencyKey": "abc123",
  "deliveryAddress": "Rampur, Lucknow",
  "addressId": "abc123"
}
```

#### `GET /v1/orders/{order_id}`
Get Order
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: order_id=`abc123`

#### `POST /v1/orders/{order_id}/cancel`
Cancel Order
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: order_id=`abc123`

#### `POST /v1/payments/razorpay/order`
Create Razorpay Order
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "orderId": "abc123"
}
```

#### `POST /v1/payments/razorpay/refund`
Refund Payment
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "orderId": "abc123"
}
```

#### `POST /v1/payments/razorpay/verify`
Verify Razorpay Payment
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "orderId": "abc123",
  "razorpayOrderId": "abc123",
  "razorpayPaymentId": "abc123",
  "razorpaySignature": "razorpay-signature-123"
}
```


### other

#### `GET /v1/debug/sentry-test`
Sentry Test
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `GET /v1/health`
Health
- Token: **not required** (public)


### pnl

#### `POST /v1/pnl/break-even`
Break Even
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "totalCost": 1,
  "expectedYieldQuintals": 1
}
```

#### `GET /v1/pnl/crops`
List Crops
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/pnl/crops/{crop_id}/expenses`
Add Expense
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: crop_id=`abc123`
- Request body:
```json
{
  "category": "seeds",
  "amount": 1
}
```

#### `GET /v1/pnl/summary`
Summary
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)


### post-harvest

#### `GET /v1/post-harvest/cold-storage`
Cold Storage
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: lat, lng, page, pageSize

#### `POST /v1/post-harvest/cold-storage/{facility_id}/book`
Book Cold Storage
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: facility_id=`abc123`
- Request body:
```json
{
  "quantityQuintals": 1,
  "fromDate": "2026-09-20",
  "months": 1.0
}
```

#### `POST /v1/post-harvest/grade`
Grade
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- **Multipart upload** — file field(s): images (attach **1–3** `.jpg`/`.png` produce photos)


### ratings

#### `POST /v1/ratings`
Submit Rating
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "bookingKind": "transport",
  "bookingId": "abc123",
  "stars": 5,
  "comment": "On time service"
}
```

#### `GET /v1/ratings/providers/{provider_id}`
Provider Rating
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: provider_id=`abc123`


### reference

#### `GET /v1/geo/reverse`
Reverse Geocode
- Token: **not required** (public)
- Required query/path params: lat=`26.85`, lng=`80.95`

#### `GET /v1/languages`
Languages
- Token: **not required** (public)

#### `GET /v1/regions/crops`
Region Crops
- Token: **not required** (public)
- Required query/path params: district=`Lucknow`


### referrals

#### `GET /v1/referrals`
Get Referrals
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/referrals/invite`
Invite
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "farmerName": "Suresh Yadav",
  "phone": "+919812345678"
}
```


### schemes

#### `GET /v1/schemes`
List Schemes
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: category, eligibleOnly, page, pageSize

#### `GET /v1/schemes/portals`
Portals
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/schemes/{scheme_id}/apply`
Apply Scheme
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: scheme_id=`abc123`
- Request body:
```json
{
  "documentIds": [
    "abc123"
  ]
}
```


### seller

#### `POST /v1/seller/rates`
Post Rate
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "crop": "wheat",
  "ratePerKg": 1,
  "mandiName": "Ramesh Kumar"
}
```

#### `GET /v1/seller/rates/my`
My Rates
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)


### settlements

#### `GET /v1/broker/settlements`
Broker Settlements
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `GET /v1/equipment/settlements`
Equipment Settlements
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `GET /v1/transport/settlements`
Transport Settlements
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize


### soil-tests

#### `GET /v1/soil-tests`
List Bookings
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/soil-tests/book`
Book
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "address": "Rampur, Lucknow",
  "slot": "2026-09-20 06:00-10:00",
  "plotId": "abc123"
}
```


### speech

#### `POST /v1/speech/stt`
Stt
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- **Multipart upload** — file field(s): file (attach one `.jpg`/`.png` (or PDF for vault docs))
- Other form fields:
```json
{
  "languageHint": null
}
```

#### `POST /v1/speech/tts`
Tts
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "text": "मेरी फसल पर पीले धब्बे हैं",
  "language": "hi"
}
```


### support

#### `GET /v1/support/threads`
List Threads
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `GET /v1/support/threads/{thread_id}/messages`
List Messages
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: thread_id=`abc123`
- Optional params: page, pageSize

#### `POST /v1/support/threads/{thread_id}/messages`
Post Message
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: thread_id=`abc123`
- Request body:
```json
{
  "text": "मेरी फसल पर पीले धब्बे हैं"
}
```


### sync

#### `POST /v1/sync`
Sync
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "operations": [
    {}
  ]
}
```


### transport

#### `GET /v1/transport/bookings`
List Bookings
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: status, page, pageSize

#### `POST /v1/transport/bookings`
Create Booking
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "vehicleType": "tractor-trolley",
  "distanceKm": 1,
  "pickup": "Rampur mandi",
  "drop": "Lucknow",
  "date": "2026-09-20",
  "lotId": "abc123"
}
```

#### `PATCH /v1/transport/bookings/{booking_id}`
Update Booking
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: booking_id=`abc123`
- Request body:
```json
{
  "status": "active",
  "vehicleId": "abc123",
  "vehicleNo": "UP32AB1234",
  "podPhotos": [
    "podPhotos"
  ],
  "receiverName": "Ramesh Kumar"
}
```

#### `POST /v1/transport/bookings/{booking_id}/accept`
Accept Booking
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: booking_id=`abc123`
- Request body:
```json
{
  "vehicleId": "abc123",
  "vehicleNo": "UP32AB1234"
}
```

#### `POST /v1/transport/bookings/{booking_id}/reject`
Reject Booking
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: booking_id=`abc123`
- Request body:
```json
{
  "reason": "Need expert advice"
}
```

#### `POST /v1/transport/fare-estimate`
Fare Estimate
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "vehicleType": "tractor-trolley",
  "distanceKm": 1
}
```

#### `GET /v1/transport/vehicles`
List Vehicle Types
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/transport/vehicles`
Create Vehicle
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "vehicleType": "tractor-trolley",
  "registrationNo": "UP32AB1234",
  "capacityTonnes": 1,
  "rcDocUrl": "https://example.com/audio.mp3",
  "insuranceDocUrl": "https://example.com/audio.mp3"
}
```

#### `GET /v1/transport/vehicles/my`
My Vehicles
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: verifiedOnly

#### `DELETE /v1/transport/vehicles/{vehicle_id}`
Delete Vehicle
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: vehicle_id=`abc123`

#### `PUT /v1/transport/vehicles/{vehicle_id}`
Update Vehicle
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: vehicle_id=`abc123`
- Request body:
```json
{
  "vehicleType": "tractor-trolley",
  "registrationNo": "UP32AB1234",
  "capacityTonnes": 1,
  "rcDocUrl": "https://example.com/audio.mp3",
  "insuranceDocUrl": "https://example.com/audio.mp3"
}
```

#### `PUT /v1/transport/vehicles/{vehicle_id}/availability`
Set Availability
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: vehicle_id=`abc123`
- Request body:
```json
{
  "availableDates": [
    "availableDates"
  ]
}
```

#### `GET /v1/transport/vehicles/{vehicle_id}/calendar`
Vehicle Calendar
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: vehicle_id=`abc123`


### tree

#### `GET /v1/tree/articles`
List Articles
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: category, page, pageSize

#### `GET /v1/tree/biofuel`
List Biofuel
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `GET /v1/tree/care-guides`
List Care Guides
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `GET /v1/tree/ngos`
List Ngos
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/tree/ngos/{ngo_id}/sapling-request`
Request Saplings
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: ngo_id=`abc123`
- Request body:
```json
{
  "treeType": "timber",
  "count": 1.0
}
```


### users

#### `DELETE /v1/users/me`
Delete Me
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "mpin": "1234"
}
```

#### `GET /v1/users/me`
Get Me
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `PUT /v1/users/me`
Update Me
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "name": "Ramesh Kumar",
  "vernacularName": "Ramesh Kumar",
  "village": "Rampur",
  "tehsil": "Mohanlalganj",
  "district": "Lucknow",
  "state": "Uttar Pradesh",
  "landAreaAcres": 1,
  "soilType": "loamy",
  "irrigationType": "canal",
  "activeCrops": [
    "wheat"
  ],
  "bankName": "SBI",
  "kccLimit": 1
}
```

#### `GET /v1/users/me/blocks`
List Blocks
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/users/me/blocks`
Block User
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "userId": "abc123"
}
```

#### `DELETE /v1/users/me/blocks/{block_user_id}`
Unblock User
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: block_user_id=`abc123`

#### `GET /v1/users/me/bookings`
My Bookings
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: status

#### `GET /v1/users/me/consents`
Get Consents
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `PUT /v1/users/me/consents`
Put Consents
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "dataSharing": true,
  "location": true,
  "marketing": true
}
```

#### `PUT /v1/users/me/farm-boundary`
Save Farm Boundary
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "farmBoundaryPoints": [
    {
      "lat": 26.85,
      "lng": 80.95
    }
  ],
  "landAreaAcres": 1,
  "khasraNumber": "abc123"
}
```

#### `POST /v1/users/me/profiles`
Link Profile
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "profileType": "farmer"
}
```

#### `DELETE /v1/users/me/profiles/{profile_type}`
Unlink Profile
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: profile_type=`farmer`

#### `POST /v1/users/me/profiles/{profile_type}/activate`
Activate Profile
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: profile_type=`farmer`

#### `PUT /v1/users/me/profiles/{profile_type}/primary`
Set Primary Profile
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: profile_type=`farmer`

#### `POST /v1/users/{user_id}/report`
Report User
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: user_id=`abc123`
- Request body:
```json
{
  "reason": "Need expert advice"
}
```


### vault

#### `GET /v1/vault/documents`
List Documents
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: page, pageSize

#### `POST /v1/vault/documents`
Upload Document
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- **Multipart upload** — file field(s): file (attach one `.jpg`/`.png` (or PDF for vault docs))
- Other form fields:
```json
{
  "docType": "farmer"
}
```

#### `DELETE /v1/vault/documents/{document_id}`
Delete Document
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: document_id=`abc123`


### water

#### `GET /v1/water/canal-rotation`
Canal Rotation
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: canal

#### `GET /v1/water/groundwater`
Groundwater
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Optional params: district

#### `POST /v1/water/pmksy-calculator`
Pmksy Calculator
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "acres": 1
}
```

#### `GET /v1/water/schedule`
Schedule
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)


### weather

#### `GET /v1/weather`
Get Weather
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Required query/path params: lat=`26.85`, lng=`80.95`


### women

#### `GET /v1/women/home-enterprise`
Home Enterprise
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `GET /v1/women/shg`
Get Shg
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)

#### `POST /v1/women/shg/deposit`
Deposit
- Token: **required** (paste in Authorize 🔒, no `Bearer ` prefix)
- Request body:
```json
{
  "amount": 1,
  "month": "September 2026"
}
```
