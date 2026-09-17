from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core import db
from app.core.deps import current_user_id
from app.models.land import LandListingIn, LeaseRequestIn, RejectLeaseRequestIn
from app.services import land as land_service
from app.services import reports as reports_service

router = APIRouter(prefix="/land", tags=["land-market"])

ROLES = ("farmer", "farmLandlord")


def _envelope(data: list[dict], page: int, page_size: int) -> dict:
    total = len(data)
    start = (max(1, page) - 1) * page_size
    return {"data": data[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


def _page_size(pageSize: int) -> int:
    return max(1, min(pageSize, 50))


@router.post("/listings", status_code=201)
async def create_listing(body: LandListingIn, uid: str = Depends(current_user_id)):
    user = await land_service.user_or_403(uid, "farmLandlord")
    if body.plotId:
        plot = await db.get_subdoc_at(land_service.plots_path(uid), body.plotId)
        if plot is None:
            raise HTTPException(status_code=404, detail={"code": "PLOT_NOT_FOUND", "message": "Plot not found", "fieldErrors": {}})
    listing_id = f"lst_{uuid4().hex[:10]}"
    doc = {
        "id": listing_id,
        **body.model_dump(),
        "landlordId": uid,
        "landlordName": user.get("name") or "Landlord",
        "status": "open",
        "createdAt": datetime.utcnow().isoformat(),
    }
    await db.set_doc("land_listings", listing_id, doc)
    return doc


@router.get("/listings")
async def browse_listings(near: str | None = None, acres: float | None = None, page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, *ROLES)
    listings = await db.query("land_listings", [], limit=1000)
    listings = [l for l in listings if l.get("status") == "open"]
    if near:
        try:
            lat, lng = (float(x) for x in near.split(","))
        except ValueError:
            raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "near must be lat,lng", "fieldErrors": {"near": "must be lat,lng"}})
        listings = [l for l in listings if land_service.haversine_km(lat, lng, l.get("lat", 0), l.get("lng", 0)) <= 25]
    if acres is not None:
        listings = [l for l in listings if l.get("areaAcres", 0) >= acres]
    return _envelope(listings, page, _page_size(pageSize))


@router.get("/listings/mine")
async def my_listings(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, "farmLandlord")
    listings = await db.query("land_listings", [("landlordId", "==", uid)], limit=1000)
    return _envelope(listings, page, _page_size(pageSize))


@router.put("/listings/{listing_id}")
async def update_listing(listing_id: str, body: LandListingIn, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, "farmLandlord")
    listing = await db.get_doc("land_listings", listing_id)
    if listing is None or listing.get("landlordId") != uid:
        raise HTTPException(status_code=403, detail={"code": "NOT_LISTING_OWNER", "message": "Listing does not belong to this landlord", "fieldErrors": {}})
    listing.update(body.model_dump())
    await db.set_doc("land_listings", listing_id, listing)
    return listing


@router.delete("/listings/{listing_id}", status_code=204)
async def delete_listing(listing_id: str, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, "farmLandlord")
    listing = await db.get_doc("land_listings", listing_id)
    if listing is None or listing.get("landlordId") != uid:
        raise HTTPException(status_code=403, detail={"code": "NOT_LISTING_OWNER", "message": "Listing does not belong to this landlord", "fieldErrors": {}})
    if listing.get("status") == "leased":
        raise HTTPException(status_code=409, detail={"code": "LISTING_HAS_ACTIVE_LEASE", "message": "Listing has an active lease", "fieldErrors": {}})
    await db.delete_doc("land_listings", listing_id)
    return Response(status_code=204)


@router.post("/lease-requests", status_code=201)
async def create_lease_request(body: LeaseRequestIn, uid: str = Depends(current_user_id)):
    user = await land_service.user_or_403(uid, "farmer")
    listing = await db.get_doc("land_listings", body.listingId)
    if listing is None:
        raise HTTPException(status_code=404, detail={"code": "LISTING_NOT_FOUND", "message": "Listing not found", "fieldErrors": {}})
    if listing.get("status") != "open":
        raise HTTPException(status_code=409, detail={"code": "LISTING_NOT_OPEN", "message": "Listing is no longer open", "fieldErrors": {}})
    existing = await db.query("lease_requests", [("listingId", "==", body.listingId)], limit=1000)
    if any(r.get("farmerId") == uid and r.get("status") == "pending" for r in existing):
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_LEASE_REQUEST", "message": "A pending request already exists", "fieldErrors": {}})
    request_id = f"lreq_{uuid4().hex[:10]}"
    doc = {
        "id": request_id,
        **body.model_dump(),
        "farmerId": uid,
        "farmerName": user.get("name") or "Farmer",
        "farmerPhone": user.get("phone", ""),
        "landlordId": listing["landlordId"],
        "status": "pending",
        "createdAt": datetime.utcnow().isoformat(),
    }
    await db.set_doc("lease_requests", request_id, doc)
    return doc


@router.get("/lease-requests")
async def list_lease_requests(status: str | None = None, page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, "farmLandlord")
    requests = await db.query("lease_requests", [("landlordId", "==", uid)], limit=1000)
    if status:
        requests = [r for r in requests if r.get("status") == status]
    return _envelope(requests, page, _page_size(pageSize))


def _add_months(day, months: int):
    y = day.year + (day.month - 1 + months) // 12
    m = (day.month - 1 + months) % 12 + 1
    return day.replace(year=y, month=m)


@router.post("/lease-requests/{request_id}/accept")
async def accept_lease_request(request_id: str, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, "farmLandlord")
    request = await db.get_doc("lease_requests", request_id)
    if request is None or request.get("landlordId") != uid:
        raise HTTPException(status_code=403, detail={"code": "NOT_LISTING_OWNER", "message": "Listing does not belong to this landlord", "fieldErrors": {}})
    if request.get("status") != "pending":
        raise HTTPException(status_code=409, detail={"code": "REQUEST_ALREADY_RESOLVED", "message": "Request already resolved", "fieldErrors": {}})
    listing = await db.get_doc("land_listings", request["listingId"])

    farmer = await db.get_doc("users", request["farmerId"])
    start = datetime.utcnow().date()
    end = _add_months(start, request["durationMonths"])
    lease_id = f"lease_{uuid4().hex[:10]}"
    lease = {
        "id": lease_id,
        "plotId": (listing or {}).get("plotId") or "",
        "tenantName": (farmer or {}).get("name") or request.get("farmerName", ""),
        "tenantPhone": (farmer or {}).get("phone") or request.get("farmerPhone", ""),
        "monthlyRentRupees": (listing or {}).get("expectedRentRupees", 0),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "status": "active",
        "verified": False,
        "createdAt": datetime.utcnow().isoformat(),
    }
    await db.set_subdoc_at(land_service.leases_path(uid), lease_id, lease)
    # top-level index so the tenant can resolve the lease without knowing the landlord uid
    await db.set_doc("land_leases_index", lease_id, {"landlordUid": uid, "tenantPhone": lease["tenantPhone"]})
    if listing is not None:
        listing["status"] = "leased"
        await db.set_doc("land_listings", listing["id"], listing)
    requests = await db.query("lease_requests", [("listingId", "==", request["listingId"])], limit=1000)
    for r in requests:
        if r["id"] != request_id and r.get("status") == "pending":
            r["status"] = "rejected"
            r["rejectionReason"] = "Listed plot leased to another farmer"
            await db.set_doc("lease_requests", r["id"], r)
    request["status"] = "accepted"
    await db.set_doc("lease_requests", request_id, request)
    return {"leaseId": lease_id}


@router.post("/lease-requests/{request_id}/reject")
async def reject_lease_request(request_id: str, body: RejectLeaseRequestIn, uid: str = Depends(current_user_id)):
    await land_service.user_or_403(uid, "farmLandlord")
    request = await db.get_doc("lease_requests", request_id)
    if request is None or request.get("landlordId") != uid:
        raise HTTPException(status_code=403, detail={"code": "NOT_LISTING_OWNER", "message": "Listing does not belong to this landlord", "fieldErrors": {}})
    request["status"] = "rejected"
    request["rejectionReason"] = body.reason
    await db.set_doc("lease_requests", request_id, request)
    return {"status": "rejected"}


@router.get("/leases/{lease_id}/agreement-pdf")
async def lease_agreement_pdf(lease_id: str, uid: str = Depends(current_user_id)):
    user = await land_service.user_or_403(uid, *ROLES)
    lease = await db.get_subdoc_at(land_service.leases_path(uid), lease_id)
    landlord_uid = uid
    if lease is None:
        index = await db.get_doc("land_leases_index", lease_id)
        if index is None:
            raise HTTPException(status_code=404, detail={"code": "LEASE_NOT_FOUND", "message": "Lease not found", "fieldErrors": {}})
        landlord_uid = index["landlordUid"]
        lease = await db.get_subdoc_at(land_service.leases_path(landlord_uid), lease_id)
        if lease is None or lease.get("tenantPhone") != user.get("phone", ""):
            raise HTTPException(status_code=404, detail={"code": "LEASE_NOT_FOUND", "message": "Lease not found", "fieldErrors": {}})
    landlord = await db.get_doc("users", landlord_uid) or {"name": "Landlord", "village": ""}
    path = reports_service.build_lease_agreement_pdf(lease, landlord, user)
    url = reports_service.upload_to_storage(path, f"agreements/{landlord_uid}/{lease_id}.pdf")
    return {"agreementUrl": url}
