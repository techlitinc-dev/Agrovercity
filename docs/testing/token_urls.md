# Agrovercity Backend — Getting Tokens with cURL

**Project:** Agrovercity
**Project ID:** `agrovercity-2c6fc`
**Purpose:** Generate Firebase ID tokens and Agrovercity backend access tokens using cURL (verified working, including from Windows CMD).

All commands in this document were verified against the live Firebase project and the backend code.

---

## 1. Test Credentials (verified)

| Item | Value |
|---|---|
| Firebase Web API key | `AIzaSyAZVEjM0mQ5wuMJk2YxzGOyBJhxTmgfEX0` |
| Test phone number | `+919405888020` |
| Verification code | `123456` |

> **Important:** `+919405888020` is the phone number registered as a **test
> number** in Firebase Console → Authentication → Sign-in method → Phone.
> Do **not** use other numbers (e.g. `+919999999999`) — they are not
> registered, and Firebase rejects them with `BILLING_NOT_ENABLED` because it
> would try to send a real SMS. Test numbers never send SMS and always accept
> their fixed code.

The Web API key is used in the `?key=` parameter of Firebase's REST API. It is
not a secret-grade credential, but it should be **restricted in Google Cloud
Console** (Identity Toolkit only, plus app/referrer restrictions as
applicable).

---

## 2. FIRESTORE_USER_ID

`FIRESTORE_USER_ID` is not a config value — it is the document ID of a user in
the Firestore `users` collection. Document IDs equal the Firebase UID of the
account that created them.

Verified in project `agrovercity-2c6fc`:

```text
FIRESTORE_USER_ID = aWoKf3ILhtMNvHno3hKC4GU7bNy1
```

This user exists and already has an active profile:

```json
{
  "activeProfile": "farmer",
  "linkedProfiles": ["farmer"]
}
```

So role-gated APIs **will work** for this user (no 403 `FORBIDDEN_ROLE`).
If you create a fresh user instead, you must activate a profile first via:

```text
POST /v1/users/me/profiles/{type}/activate
```

---

## 3. Option A — Backend Access Token (no Firebase needed)

If you only need a backend access token for the Firestore user above:

```bash
cd backend
.venv/bin/python -c "from app.services.tokens import create_access_token; print(create_access_token('aWoKf3ILhtMNvHno3hKC4GU7bNy1'))"
```

Paste the printed token into Swagger's **Authorize 🔒** (without the `Bearer `
prefix).

This is the fastest path for testing regular (non-admin) APIs.

---

## 4. Option B — Firebase ID Token via cURL (REST API)

### Step 1 — Get `sessionInfo`

Linux / macOS / Git Bash:

```bash
curl -s -X POST "https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key=AIzaSyAZVEjM0mQ5wuMJk2YxzGOyBJhxTmgfEX0" \
  -H "Content-Type: application/json" \
  -d '{"phoneNumber":"+919405888020","recaptchaToken":"NO_RECAPTCHA"}'
```

**Windows CMD** (CMD does not treat single quotes as quotes — use double
quotes and escape the inner ones):

```bat
curl -s -X POST "https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key=AIzaSyAZVEjM0mQ5wuMJk2YxzGOyBJhxTmgfEX0" -H "Content-Type: application/json" -d "{\"phoneNumber\":\"+919405888020\",\"recaptchaToken\":\"NO_RECAPTCHA\"}"
```

Successful response:

```json
{
  "sessionInfo": "AD8T5It1fBR0dj7..."
}
```

Copy the complete `sessionInfo` value.

### Step 2 — Exchange the OTP for a Firebase `idToken`

Replace `PASTE_SESSION_INFO_HERE` with the value from Step 1.

Linux / macOS / Git Bash:

```bash
curl -s -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber?key=AIzaSyAZVEjM0mQ5wuMJk2YxzGOyBJhxTmgfEX0" \
  -H "Content-Type: application/json" \
  -d '{"phoneNumber":"+919405888020","code":"123456","sessionInfo":"PASTE_SESSION_INFO_HERE"}'
```

**Windows CMD:**

```bat
curl -s -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber?key=AIzaSyAZVEjM0mQ5wuMJk2YxzGOyBJhxTmgfEX0" -H "Content-Type: application/json" -d "{\"phoneNumber\":\"+919405888020\",\"code\":\"123456\",\"sessionInfo\":\"PASTE_SESSION_INFO_HERE\"}"
```

Successful response:

```json
{
  "idToken": "eyJ...",
  "refreshToken": "AMf-...",
  "localId": "PoSq6G9rkIS5p29r4cHoT8rKnmg2",
  "expiresIn": "3600"
}
```

Copy the `idToken`. It is valid for **1 hour** (`expiresIn: 3600`).

> A `sessionInfo` value is single-use and short-lived. If Step 2 fails, go
> back to Step 1 and get a fresh one.

### Step 3 — Get your Agrovercity backend tokens

Replace `PASTE_FIREBASE_ID_TOKEN_HERE` with the `idToken` from Step 2
(backend must be running on `localhost:8080`).

```bash
curl -s -X POST "http://localhost:8080/v1/auth/firebase-verify" \
  -H "Content-Type: application/json" \
  -d '{"idToken":"PASTE_FIREBASE_ID_TOKEN_HERE"}'
```

**Windows CMD:**

```bat
curl -s -X POST "http://localhost:8080/v1/auth/firebase-verify" -H "Content-Type: application/json" -d "{\"idToken\":\"PASTE_FIREBASE_ID_TOKEN_HERE\"}"
```

The backend returns:

```json
{
  "accessToken": "...",
  "refreshToken": "...",
  "isNewUser": true,
  "user": { "...": "full user profile (mpinHash removed)" }
}
```

Use `accessToken` for regular backend APIs. The Firebase `idToken` from
Step 2 is only used for `/v1/auth/*` endpoints and `/v1/admin/*` (admin users
need the `admin: true` custom claim — see
[admin-token-setup.md](./admin-token-setup.md)).

---

## 5. Troubleshooting

### Step 1 returns `BILLING_NOT_ENABLED`

The phone number is **not registered as a test number** in Firebase Console.
Use `+919405888020`, or register your number under
Authentication → Sign-in method → Phone → *Phone numbers for testing*.

### Step 2 returns `INVALID_SESSION_INFO` / `CODE_EXPIRED`

The `sessionInfo` is single-use and expires quickly. Run Step 1 again and
retry immediately with the fresh value.

### Step 2 returns `INVALID_CODE`

The code must exactly match the one registered for the test number
(`123456`).

### Step 3 returns `401`

The Firebase `idToken` has expired (1 hour) or belongs to a different project.
Generate a fresh one from Step 1.

### reCAPTCHA concerns

Firebase's normal phone flow uses an ApplicationVerifier (reCAPTCHA) on the
client. The REST API flow above works **only because the phone number is a
registered test number** — test numbers bypass the verifier. For real phone
numbers you must go through the client SDK.

---

## 6. Security Guidelines

- ✅ Restrict the Firebase Web API key in Google Cloud Console.
- ✅ Treat generated `idToken` / `accessToken` values as credentials — never
  commit or share them.
- ✅ Prefer the test phone number for all development testing.
- ❌ Don't register real personal numbers as test numbers in shared projects.
- ❌ Don't paste tokens into chat, issues, or documentation.
