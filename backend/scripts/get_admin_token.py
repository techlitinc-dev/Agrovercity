"""Get an admin token (Firebase ID token) via the Firebase Auth REST API.

Prerequisites (one-time):
  1. Test phone number + code added in Firebase Console -> Authentication -> Sign-in method -> Phone.
  2. Admin claim set:  .venv/bin/python scripts/make_admin.py <uid>

Usage:
  .venv/bin/python scripts/get_admin_token.py
  .venv/bin/python scripts/get_admin_token.py --phone +919405888020 --code 123456 --print
"""
import argparse
import json
import sys
import urllib.request

API_KEY = "AIzaSyAZVEjM0mQ5wuMJk2YxzGOyBJhxTmgfEX0"
DEFAULT_PHONE = "+919405888020"
DEFAULT_CODE = "123456"

IDENTITY_URL = "https://identitytoolkit.googleapis.com/v1/accounts:{action}?key=" + API_KEY


def _post(action: str, payload: dict) -> dict:
    req = urllib.request.Request(
        IDENTITY_URL.format(action=action),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR: Firebase returned {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def get_admin_token(phone: str = DEFAULT_PHONE, code: str = DEFAULT_CODE) -> str:
    sent = _post("sendVerificationCode", {"phoneNumber": phone, "recaptchaToken": "NO_RECAPTCHA"})
    session = sent.get("sessionInfo")
    if not session:
        print("ERROR: no sessionInfo in sendVerificationCode response", file=sys.stderr)
        sys.exit(1)
    signed = _post("signInWithPhoneNumber", {"phoneNumber": phone, "code": code, "sessionInfo": session})
    token = signed.get("idToken")
    if not token:
        print("ERROR: no idToken in signInWithPhoneNumber response", file=sys.stderr)
        sys.exit(1)
    return token


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get admin token (Firebase ID token)")
    parser.add_argument("--phone", default=DEFAULT_PHONE)
    parser.add_argument("--code", default=DEFAULT_CODE)
    parser.add_argument("--print", action="store_true", help="print only the token (for $(...) use)")
    args = parser.parse_args()

    token = get_admin_token(args.phone, args.code)
    if args.print:
        print(token)
    else:
        print(f"admin token:\n\n{token}\n\nuse as:  curl -H 'Authorization: Bearer {token}' ...")
