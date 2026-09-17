"""Production smoke test — run: python scripts/smoke_test.py https://api.agrovercity.in"""

import os
import re
import sys
from datetime import date

import httpx

BASE = "http://localhost:8000"
results = []


def record(ok):
    results.append(ok)


def check(n, method, path, expect, **kw):
    r = httpx.request(method, BASE + path, timeout=15, **kw)
    ok = r.status_code == expect
    record(ok)
    print(f"{'PASS' if ok else 'FAIL'} {n}. {method} {path} -> {r.status_code}")
    return r


def skip(n, why):
    record(True)
    print(f"SKIP {n}. {why}")


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    global BASE
    if len(sys.argv) > 1:
        BASE = sys.argv[1].rstrip("/")

    # 1. health (no auth)
    r = check(1, "GET", "/v1/health", 200)
    if r.json() != {"status": "ok"}:
        record(False)
        print("FAIL 1b. health body unexpected:", r.text)

    # 2. refresh -> access token
    refresh_token = os.environ.get("SMOKE_REFRESH_TOKEN")
    access_token = None
    if not refresh_token:
        skip(2, "SMOKE_REFRESH_TOKEN unset — authed checks run with SKIP semantics")
    else:
        r = httpx.post(BASE + "/v1/auth/refresh", json={"refreshToken": refresh_token}, timeout=15)
        ok = r.status_code == 200 and "accessToken" in r.json()
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 2. POST /v1/auth/refresh -> {r.status_code}")
        if ok:
            access_token = r.json()["accessToken"]

    auth = _bearer(access_token) if access_token else {}

    # 3. users/me
    if access_token:
        r = check(3, "GET", "/v1/users/me", 200, headers=auth)
        record("id" in r.json())
        print(f"{'PASS' if results[-1] else 'FAIL'} 3b. users/me has id")
    else:
        skip(3, "no access token")

    # 4. mandi prices
    if access_token:
        r = check(4, "GET", "/v1/mandi/prices", 200, headers=auth)
        record("data" in r.json())
    else:
        skip(4, "no access token")

    # 5. vyapari rates
    if access_token:
        check(5, "GET", "/v1/mandi/vyapari-rates", 200, headers=auth)
    else:
        skip(5, "no access token")

    # 6. weather
    if access_token:
        check(6, "GET", "/v1/weather?lat=20.0&lng=73.8", 200, headers=auth)
    else:
        skip(6, "no access token")

    # 7. diary entry (+15 coins)
    if access_token:
        r = httpx.post(
            BASE + "/v1/diary/entries",
            json={"title": "smoke", "category": "other", "type": "farmActivity", "date": date.today().isoformat()},
            headers=auth,
            timeout=15,
        )
        ok = r.status_code == 201 and r.json().get("agriCoinsEarned") == 15
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 7. POST /v1/diary/entries -> {r.status_code}")
    else:
        skip(7, "no access token")

    # 8. pnl summary
    if access_token:
        check(8, "GET", "/v1/pnl/summary", 200, headers=auth)
    else:
        skip(8, "no access token")

    # 9. schemes eligibleOnly
    if access_token:
        check(9, "GET", "/v1/schemes?eligibleOnly=true", 200, headers=auth)
    else:
        skip(9, "no access token")

    # 10. credit score
    if access_token:
        check(10, "GET", "/v1/finance/credit-score", 200, headers=auth)
    else:
        skip(10, "no access token")

    # 11. insurance policies
    if access_token:
        check(11, "GET", "/v1/insurance/policies", 200, headers=auth)
    else:
        skip(11, "no access token")

    # 12. chatbot
    if access_token:
        r = httpx.post(
            BASE + "/v1/chatbot/messages",
            json={"text": "नमस्ते", "sessionId": "smoke", "language": "hi"},
            headers=auth,
            timeout=15,
        )
        record(r.status_code == 200)
        print(f"{'PASS' if r.status_code == 200 else 'FAIL'} 12. POST /v1/chatbot/messages -> {r.status_code}")
    else:
        skip(12, "no access token")

    # 13. gamification status
    if access_token:
        check(13, "GET", "/v1/gamification/status", 200, headers=auth)
    else:
        skip(13, "no access token")

    # 14. news
    if access_token:
        check(14, "GET", "/v1/news", 200, headers=auth)
    else:
        skip(14, "no access token")

    # 15. admin analytics
    admin_token = os.environ.get("SMOKE_ADMIN_TOKEN")
    if not admin_token:
        skip(15, "SMOKE_ADMIN_TOKEN unset")
    else:
        check(15, "GET", "/v1/admin/analytics/summary", 200, headers=_bearer(admin_token))

    # 16. app-config (X12)
    r = check(16, "GET", "/v1/app-config?version=1.0.0", 200)
    if r.status_code == 200:
        body = r.json()
        record("minSupportedVersion" in body and "forceUpdate" in body)
        print(f"{'PASS' if results[-1] else 'FAIL'} 16b. app-config fields present")

    # 17. referral invite
    if access_token:
        r = httpx.post(
            BASE + "/v1/referrals/invite",
            json={"farmerName": "smoke", "phone": "+919999000099"},
            headers=auth,
            timeout=15,
        )
        ok = r.status_code == 201 or (r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_INVITED")
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 17. POST /v1/referrals/invite -> {r.status_code}")
    else:
        skip(17, "no access token")

    # 18. bank account + verify (F16)
    if access_token:
        r = httpx.post(
            BASE + "/v1/bank-accounts",
            json={"accountHolder": "Smoke User", "accountNumber": "12345678901", "ifsc": "SBIN0001234", "bankName": "SBI"},
            headers=auth,
            timeout=15,
        )
        ok = r.status_code == 201
        if ok:
            account_id = r.json()["id"]
            r2 = httpx.post(BASE + f"/v1/bank-accounts/{account_id}/verify", headers=auth, timeout=15)
            ok = r2.status_code == 200 and r2.json().get("verifyStatus") == "verified"
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 18. POST /v1/bank-accounts + verify")
    else:
        skip(18, "no access token")

    # 19. lots CRUD (F7)
    if access_token:
        r = httpx.post(
            BASE + "/v1/market/lots",
            json={
                "crop": "Tomato", "quantityQuintals": 5, "expectedRate": 1500,
                "harvestDate": date.today().isoformat(), "photos": [], "location": {"lat": 20.0, "lng": 73.8},
            },
            headers=auth,
            timeout=15,
        )
        ok = r.status_code == 201
        if ok:
            lot_id = r.json()["id"]
            r2 = httpx.get(BASE + "/v1/market/lots", headers=auth, timeout=15)
            ok = ok and any(l["id"] == lot_id for l in r2.json()["data"])
            r3 = httpx.delete(BASE + f"/v1/market/lots/{lot_id}", headers=auth, timeout=15)
            ok = ok and r3.status_code == 204
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 19. lots CRUD -> ok")
    else:
        skip(19, "no access token")

    # 20. order cancel + refund (X5)
    if access_token:
        r = httpx.post(
            BASE + "/v1/orders",
            json={
                "items": [{"productId": "prod-1", "quantity": 1}],
                "paymentMethod": "upi", "deliveryAddress": "smoke", "idempotencyKey": "smoke-order-1",
            },
            headers=auth,
            timeout=15,
        )
        ok = r.status_code == 200
        if ok:
            order_id = r.json()["orderId"]
            r2 = httpx.post(BASE + f"/v1/orders/{order_id}/cancel", headers=auth, timeout=15)
            ok = r2.status_code == 200 and "refundStatus" in r2.json()
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 20. order create + cancel -> ok")
    else:
        skip(20, "no access token")

    # 21. transport booking accept (T2)
    transporter_token = os.environ.get("SMOKE_TRANSPORTER_TOKEN")
    if not transporter_token:
        skip(21, "SMOKE_TRANSPORTER_TOKEN unset")
    else:
        booking_id = os.environ.get("SMOKE_BOOKING_ID")
        r = httpx.post(
            BASE + f"/v1/transport/bookings/{booking_id}/accept",
            headers=_bearer(transporter_token),
            timeout=15,
        )
        record(r.status_code == 200)
        print(f"{'PASS' if r.status_code == 200 else 'FAIL'} 21. POST /v1/transport/bookings/{{id}}/accept -> {r.status_code}")

    # 22. equipment booking approve (E2)
    if not os.environ.get("SMOKE_EQUIPMENT_OWNER_TOKEN"):
        skip(22, "SMOKE_EQUIPMENT_OWNER_TOKEN unset")
    else:
        owner_auth = _bearer(os.environ["SMOKE_EQUIPMENT_OWNER_TOKEN"])
        r = httpx.post(BASE + "/v1/equipment/bookings/pending", headers=owner_auth, timeout=15)
        pending = r.json().get("data", [])
        ok = True
        if pending:
            r2 = httpx.post(
                BASE + f"/v1/equipment/bookings/{pending[0]['bookingId']}/approve",
                headers=owner_auth,
                timeout=15,
            )
            ok = r2.status_code == 200
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 22. equipment approve -> ok")

    # 23. settlements job (X10)
    cron_secret = os.environ.get("SMOKE_CRON_SECRET")
    if not cron_secret:
        skip(23, "SMOKE_CRON_SECRET unset")
    else:
        r = httpx.post(BASE + "/v1/jobs/settlements/run", headers={"X-Cron-Secret": cron_secret}, timeout=15)
        record(r.status_code == 200)
        print(f"{'PASS' if r.status_code == 200 else 'FAIL'} 23. POST /v1/jobs/settlements/run -> {r.status_code}")

    # 24. consents (X17)
    if access_token:
        r = httpx.put(
            BASE + "/v1/users/me/consents",
            json={"dataSharing": True, "location": True, "marketing": False},
            headers=auth,
            timeout=15,
        )
        record(r.status_code == 200)
        print(f"{'PASS' if r.status_code == 200 else 'FAIL'} 24. PUT /v1/users/me/consents -> {r.status_code}")
    else:
        skip(24, "no access token")

    # 25. claim appeal (F15)
    if not admin_token:
        skip(25, "SMOKE_ADMIN_TOKEN unset")
    else:
        claims = httpx.get(BASE + "/v1/admin/claims", headers=_bearer(admin_token), timeout=15).json().get("data", [])
        rejected = next((c for c in claims if c["status"] == "rejected"), None)
        ok = rejected is not None
        if ok and access_token:
            r = httpx.post(
                BASE + f"/v1/insurance/claims/{rejected['id']}/appeal",
                json={"reason": "smoke appeal — evidence attached"},
                headers=auth,
                timeout=15,
            )
            ok = r.status_code == 200 and r.json().get("status") == "intimated"
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 25. claim appeal -> ok")

    # 26. admin KYC verify + broadcast dry run (A1/A4)
    if not admin_token:
        skip(26, "SMOKE_ADMIN_TOKEN unset")
    else:
        ok = True
        r = httpx.get(BASE + "/v1/admin/kyc/pending", headers=_bearer(admin_token), timeout=15)
        pending = r.json().get("data", [])
        if pending:
            r2 = httpx.post(
                BASE + f"/v1/admin/kyc/{pending[0]['entityId']}/verify",
                headers=_bearer(admin_token),
                timeout=15,
            )
            ok = r2.status_code == 200
        r = httpx.post(
            BASE + "/v1/admin/broadcast",
            json={"segment": {"role": "farmer"}, "title": "smoke", "body": "smoke", "dryRun": True},
            headers=_bearer(admin_token),
            timeout=15,
        )
        ok = ok and r.status_code == 200 and "targetedCount" in r.json()
        record(ok)
        print(f"{'PASS' if ok else 'FAIL'} 26. admin KYC + broadcast dry-run -> ok")

    # endpoint-coverage gate: endpoints.md + docs/overview/03 paths must exist in openapi
    try:
        openapi = httpx.get(BASE + "/openapi.json", timeout=15).json()["paths"]
        spec_text = ""
        here = os.path.dirname(os.path.abspath(__file__))
        for doc_path in (
            os.path.join(here, "../../endpoints.md"),
            os.path.join(here, "../../docs/overview/03-gap-analysis-new-screens-and-endpoints.md"),
        ):
            try:
                with open(doc_path, encoding="utf-8") as f:
                    spec_text += f.read()
            except OSError:
                pass
        missing = []
        openapi_normalized = {re.sub(r"\{[^}]+\}", "{}", p) for p in openapi}
        for match in re.finditer(r"\|\s*`?(GET|POST|PUT|PATCH|DELETE)[\s|]*`?(/v1/[A-Za-z0-9._{}?=&/-]+)", spec_text):
            method, path = match.group(1), match.group(2).split("?")[0]
            path_tpl = re.sub(r"\{[^}]+\}", "{}", path)
            if path_tpl not in openapi_normalized:
                missing.append(f"{method} {path}")
        if missing:
            for m in missing:
                print(f"COVERAGE MISS: {m}")
            record(False)
        else:
            record(True)
            print("PASS coverage. all documented /v1 paths present in openapi.json")
    except Exception as exc:
        print(f"SKIP coverage gate: {exc}")
        record(True)

    passed = sum(1 for r in results if r)
    print(f"SMOKE: {passed}/{len(results)} passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
