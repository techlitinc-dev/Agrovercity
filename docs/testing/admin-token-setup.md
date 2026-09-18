# Agrovercity Backend — Firebase Admin Token Setup & Swagger Authentication

**Project:** Agrovercity
**Backend:** FastAPI
**Authentication:** Firebase Authentication
**Authorization:** Firebase Custom Claims
**Admin Claim:** `admin: true`
**Purpose:** Authenticate and test protected `/v1/admin/*` APIs through Swagger and cURL.

---

## 1. Overview

Agrovercity backend uses Firebase Authentication for user authentication.

Admin APIs require an authenticated Firebase user with the following custom claim:

```json
{
  "admin": true
}
```

Firebase supports custom claims for role-based access control. Custom claims must be assigned from a trusted server environment using the Firebase Admin SDK. ([Firebase: Custom Claims][1])

The authentication flow is:

```text
Firebase User
      ↓
Firebase UID
      ↓
Set custom claim
admin: true
      ↓
Generate fresh Firebase ID token
      ↓
Swagger / cURL
      ↓
Authorization: Bearer <ID_TOKEN>
      ↓
FastAPI backend
      ↓
Verify Firebase ID token
      ↓
Check admin claim
      ↓
Allow /v1/admin/* API
```

---

## 2. Prerequisites

The following must already be configured:

* Agrovercity backend
* Python virtual environment
* Firebase project
* Firebase Authentication (Phone sign-in enabled)
* **A test phone number registered in Firebase Console** (see Section 2.1)
* Firebase service-account JSON
* Firebase Admin SDK
* Admin helper scripts

Current backend structure:

```text
backend/
├── scripts/
│   ├── get_admin_token.py
│   └── make_admin.py
│
├── secrets/
│   └── firebase-service-account.json
│
└── .venv/
```

### Important security rule

The following file contains a private service-account key:

```text
backend/secrets/firebase-service-account.json
```

**Never share it with developers through chat, commit it to GitHub, or paste its contents into documentation.** Firebase specifically recommends keeping service-account private keys confidential and out of public version control. ([Firebase: Create Custom Tokens][2])

### 2.1 Required: Firebase test phone number

`scripts/get_admin_token.py` signs in through the Firebase Auth REST API using a
fixed test phone number and verification code (hardcoded as defaults in the
script). This only works if that phone number is registered as a **test phone
number** in Firebase:

1. Open **Firebase Console → Authentication → Sign-in method → Phone**.
2. Under **Phone numbers for testing**, add the test phone number (for example
   `+91XXXXXXXXXX`) together with its fixed verification code.
3. Save.

Without this step, token generation in Section 6 will fail with an error from
the Firebase Auth REST API.

> **Note:** the script also contains the Firebase **Web API key** in plaintext.
> A Web API key is not a secret-grade credential, but it should be restricted
> in Google Cloud Console (API restrictions → Identity Toolkit only, plus HTTP
> referrer / app restrictions as applicable). Do not replace it with the
> service-account private key.

---

## 3. Firebase Project Configuration

Current Agrovercity Firebase project ID:

```text
agrovercity-2c6fc
```

### Where the project ID actually comes from

* The **running backend** reads the project ID from `backend/.env`:

```text
FIREBASE_PROJECT_ID=agrovercity-2c6fc
```

You do **not** need any shell exports for the server itself.

* The **standalone helper scripts** (`make_admin.py`) run outside the app and
  do not read `backend/.env`. They rely on:

  * `GOOGLE_APPLICATION_CREDENTIALS` pointing at the service-account JSON, and
  * `GOOGLE_CLOUD_PROJECT` as the project ID (used when the credential file
    does not carry one).

Set both in the shell where you run the scripts:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/secrets/firebase-service-account.json"
export GOOGLE_CLOUD_PROJECT="agrovercity-2c6fc"
```

Verify:

```bash
echo "$GOOGLE_APPLICATION_CREDENTIALS"
```

Expected:

```text
/root/Agrovercity_project/Agrovercity/backend/secrets/firebase-service-account.json
```

Verify project:

```bash
echo "$GOOGLE_CLOUD_PROJECT"
```

Expected:

```text
agrovercity-2c6fc
```

---

## 4. Identify the Firebase User UID

An admin role is assigned to a **Firebase UID**, not directly to a phone number.

Example:

```text
PoSq6G9rkIS5p29r4cHoT8rKnmg2
```

For this project, the current admin user UID is:

```text
PoSq6G9rkIS5p29r4cHoT8rKnmg2
```

Developers should replace this with the Firebase UID of the intended admin
account when setting up another environment.

---

## 5. Assign Admin Permission

From the backend directory:

```bash
cd ~/Agrovercity_project/Agrovercity/backend
```

Set the Firebase credentials (needed by the standalone script):

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/secrets/firebase-service-account.json"
export GOOGLE_CLOUD_PROJECT="agrovercity-2c6fc"
```

Run:

```bash
.venv/bin/python scripts/make_admin.py PoSq6G9rkIS5p29r4cHoT8rKnmg2
```

Expected output:

```text
admin claim set for PoSq6G9rkIS5p29r4cHoT8rKnmg2
```

This means Firebase now has:

```json
{
  "admin": true
}
```

for that user.

The Firebase Admin SDK supports setting custom claims such as `admin: true`
using `set_custom_user_claims`. ([Firebase: Custom Claims][1])

---

## 6. Generate the Admin Firebase ID Token

After assigning the admin claim, generate a **new ID token**.

> **Reminder:** this step requires the Firebase test phone number from
> Section 2.1 to be configured first.

Run:

```bash
TOKEN=$(.venv/bin/python scripts/get_admin_token.py --print)
```

For easier use with cURL:

```bash
export TOKEN=$(.venv/bin/python scripts/get_admin_token.py --print)
```

Check that the token exists:

```bash
echo "${TOKEN:0:50}..."
```

Expected format:

```text
eyJhbGciOiJSUzI1NiIs...
```

> The script uses the default test phone and code hardcoded in it. If your
> team uses a different test number, override it:
>
> ```bash
> export TOKEN=$(.venv/bin/python scripts/get_admin_token.py \
>   --phone +91XXXXXXXXXX --code XXXXXX --print)
> ```

### Do not share the complete token in documentation

The actual token should be treated as a credential.

Do not put this in Git:

```text
admin-token.txt
```

Do not put the actual token in:

* GitHub
* GitLab
* Jira
* Slack
* Teams
* documentation
* source code

---

## 7. Verify the Admin Claim

The generated token should contain:

```json
"admin": true
```

Run (this requires the `export TOKEN=...` from Section 6, because the command
reads the token from the `TOKEN` environment variable):

```bash
python3 -c 'import os,base64,json; t=os.environ["TOKEN"]; p=t.split(".")[1]; p += "="*(-len(p)%4); print(json.dumps(json.loads(base64.urlsafe_b64decode(p)), indent=2))'
```

Expected portion:

```json
{
  "user_id": "PoSq6G9rkIS5p29r4cHoT8rKnmg2",
  "admin": true
}
```

If `"admin": true` is missing, generate a fresh token after running
`make_admin.py`.

Firebase notes that newly assigned custom claims propagate to a user's ID
token when a new token is issued, when the session refreshes, or when the
client explicitly forces a token refresh. ([Firebase: Custom Claims][1])

---

## 8. Start Agrovercity Backend

From the backend directory:

```bash
cd ~/Agrovercity_project/Agrovercity/backend
```

Start FastAPI (the server reads its Firebase configuration from
`backend/.env` — no shell exports required):

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Swagger should then be available at:

```text
http://SERVER_IP:8080/docs
```

For local testing:

```text
http://localhost:8080/docs
```

---

## 9. Authenticate in Swagger

Open:

```text
http://SERVER_IP:8080/docs
```

Click:

```text
Authorize 🔒
```

Swagger should display the HTTP Bearer authentication field.

Paste the **full Firebase ID token**:

```text
eyJhbGciOiJSUzI1NiIs...
```

### Important

If Swagger's authentication scheme is configured as `HTTPBearer`, paste:

```text
eyJhbGciOi...
```

not:

```text
Bearer eyJhbGciOi...
```

Swagger will handle the Bearer scheme.

Then click:

```text
Authorize
```

and:

```text
Close
```

---

## 10. Test Admin Analytics API

Open:

```text
GET /v1/admin/analytics/summary
```

Click:

```text
Try it out
```

Then:

```text
Execute
```

Successful response example:

```json
{
  "totalUsers": 2,
  "usersByPersona": {
    "farmer": 2,
    "farmLandlord": 0,
    "transport": 0,
    "seller": 0,
    "equipmentRental": 0,
    "broker": 0
  },
  "bookings": {
    "equipment": 0,
    "vet": 0,
    "transport": 0
  },
  "orders": {
    "count": 0,
    "gmv": 0
  },
  "claimsByStatus": {},
  "pendingRates": 0
}
```

This confirms:

```text
Firebase Authentication       ✅
Firebase Admin claim          ✅
Firebase ID token             ✅
HTTP Bearer authentication    ✅
FastAPI authentication       ✅
Admin authorization           ✅
Admin analytics endpoint      ✅
```

---

## 11. Test Using cURL

After generating the token:

```bash
export TOKEN=$(.venv/bin/python scripts/get_admin_token.py --print)
```

Run:

```bash
curl -s http://localhost:8080/v1/admin/analytics/summary \
  -H "Authorization: Bearer $TOKEN"
```

Expected:

```json
{
  "totalUsers": 2,
  "usersByPersona": {
    "farmer": 2,
    "farmLandlord": 0,
    "transport": 0,
    "seller": 0,
    "equipmentRental": 0,
    "broker": 0
  }
}
```

---

## 12. Complete Setup — Copy/Paste Version

For a new developer who already has the repository, the service-account file,
**and the Firebase test phone number configured (Section 2.1)**:

```bash
cd ~/Agrovercity_project/Agrovercity/backend

# Needed only for the helper scripts, not for the running server
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/secrets/firebase-service-account.json"
export GOOGLE_CLOUD_PROJECT="agrovercity-2c6fc"

.venv/bin/python scripts/make_admin.py <FIREBASE_UID>

export TOKEN=$(.venv/bin/python scripts/get_admin_token.py --print)
echo "${TOKEN:0:50}..."

curl -s http://localhost:8080/v1/admin/analytics/summary \
  -H "Authorization: Bearer $TOKEN"
```

Replace:

```text
<FIREBASE_UID>
```

with the Firebase UID of the approved admin user.

---

## 13. Troubleshooting

### Error: `A project ID is required`

Example:

```text
ValueError: A project ID is required to access the auth service.
```

This comes from the standalone scripts (`make_admin.py`), which need the
project ID from the environment.

Fix:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/secrets/firebase-service-account.json"
export GOOGLE_CLOUD_PROJECT="agrovercity-2c6fc"
```

Then retry:

```bash
.venv/bin/python scripts/make_admin.py <FIREBASE_UID>
```

### Error: `TOKEN` not found

Example:

```text
KeyError: 'TOKEN'
```

Fix:

```bash
export TOKEN=$(.venv/bin/python scripts/get_admin_token.py --print)
```

Then:

```bash
echo "${TOKEN:0:50}..."
```

### Error during token generation (Firebase Auth REST API)

`get_admin_token.py` prints `ERROR: Firebase returned <code>: <body>` when the
sign-in fails. Common causes:

1. The test phone number is **not registered** in Firebase Console
   (see Section 2.1).
2. The verification code does not match the one registered for the test number.
3. A different phone/code is being passed than the one configured — pass it
   explicitly with `--phone` and `--code`.

### Error: `ADMIN_REQUIRED`

Example:

```json
{
  "error": {
    "code": "ADMIN_REQUIRED",
    "message": "यह खाता एडमिन नहीं है",
    "fieldErrors": {}
  }
}
```

Check that the admin claim was assigned:

```bash
.venv/bin/python scripts/make_admin.py <FIREBASE_UID>
```

Then **generate a fresh token**:

```bash
export TOKEN=$(.venv/bin/python scripts/get_admin_token.py --print)
```

Do not continue using the old token.

### Error: `401 Unauthorized`

Check:

1. Token is valid.
2. Token hasn't expired.
3. Token belongs to the correct Firebase project.
4. Swagger has been authorized with the new token.
5. Backend is using the same Firebase project (see `backend/.env`).

Generate a fresh token:

```bash
export TOKEN=$(.venv/bin/python scripts/get_admin_token.py --print)
```

Then re-authorize Swagger.

### Error: `403` / admin permission failure

Verify the token contains:

```json
"admin": true
```

Run the token verification command from Section 7.

Firebase recommends that the backend verify the Firebase ID token and then
check the custom `admin` claim before allowing access to protected admin
resources. ([Firebase: Custom Claims][1])

---

## 14. Security Guidelines for the Development Team

### DO

✅ Store the service-account JSON securely.
✅ Use environment variables for the helper scripts:

```bash
GOOGLE_APPLICATION_CREDENTIALS
GOOGLE_CLOUD_PROJECT
```

✅ Keep the server's own Firebase configuration in `backend/.env`.
✅ Generate a fresh ID token when required.
✅ Use Swagger's `Authorize` button for testing.
✅ Use `Authorization: Bearer <token>` for cURL/API clients.
✅ Keep admin access limited to approved users.
✅ Restrict the Firebase Web API key in Google Cloud Console.

### DON'T

❌ Don't commit:

```text
firebase-service-account.json
```

❌ Don't commit Firebase ID tokens.
❌ Don't put tokens in source code.
❌ Don't put tokens in GitHub issues.
❌ Don't send service-account private keys to developers through chat.
❌ Don't use a production admin token as a shared team credential.

The Firebase documentation specifically warns that service-account JSON files
contain private keys and should not be exposed publicly. ([Firebase: Create Custom Tokens][2])

---

## 15. Recommended Team Workflow

For the **manager**, the important point is:

```text
Admin user
    ↓
Firebase UID
    ↓
Backend make_admin.py
    ↓
admin: true custom claim
    ↓
Fresh Firebase ID token
    ↓
Swagger Authorize
    ↓
Admin API testing
```

For **developers**, each developer should ideally use their own approved
Firebase test account rather than sharing one admin token.

This provides better traceability and reduces the risk associated with sharing
credentials.

---

## 16. Current Agrovercity Verification

The implementation has been successfully verified in the current environment.

Admin claim assignment returned:

```text
admin claim set for PoSq6G9rkIS5p29r4cHoT8rKnmg2
```

The admin analytics endpoint then successfully returned:

```json
{
  "totalUsers": 2,
  "usersByPersona": {
    "farmer": 2,
    "farmLandlord": 0,
    "transport": 0,
    "seller": 0,
    "equipmentRental": 0,
    "broker": 0
  },
  "bookings": {
    "equipment": 0,
    "vet": 0,
    "transport": 0
  },
  "orders": {
    "count": 0,
    "gmv": 0
  },
  "claimsByStatus": {},
  "pendingRates": 0
}
```

Therefore the complete chain has been verified:

**Firebase admin claim → fresh ID token → Bearer authentication → FastAPI admin authorization → admin analytics API.**

### Official references

* [Firebase: Control Access with Custom Claims and Security Rules][1]
* [Firebase: Admin Authentication](https://firebase.google.com/docs/auth/admin)
* [Firebase: Admin SDK Setup](https://firebase.google.com/docs/admin/setup)
* [Firebase: Create Custom Tokens][2]

[1]: https://firebase.google.com/docs/auth/admin/custom-claims "Control Access with Custom Claims and Security Rules | Firebase Authentication"
[2]: https://firebase.google.com/docs/auth/admin/create-custom-tokens "Create Custom Tokens | Firebase Authentication"
