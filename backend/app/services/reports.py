import logging
import uuid
from datetime import datetime, timezone

import firebase_admin
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)


def build_diary_pdf(uid: str, entries: list[dict], from_date: str, to_date: str) -> str:
    path = f"/tmp/diary_{uid}_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Farm Diary Report", styles["Title"]), Spacer(1, 6 * mm),
                Paragraph(f"Period: {from_date} to {to_date}", styles["Normal"]), Spacer(1, 4 * mm)]

    rows = [["Date", "Title", "Category", "Type", "Amount (₹)"]]
    for e in entries:
        rows.append([e.get("date", ""), e.get("title", ""), e.get("category", ""), e.get("type", ""), f"{e.get('amount', 0):.0f}"])
    total_income = sum(e.get("amount", 0) for e in entries if e.get("type") == "income")
    total_expense = sum(e.get("amount", 0) for e in entries if e.get("type") == "expense")
    rows.append(["", "", "", "Total income", f"{total_income:.0f}"])
    rows.append(["", "", "", "Total expense", f"{total_expense:.0f}"])
    rows.append(["", "", "", "Net", f"{total_income - total_expense:.0f}"])

    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#43A047")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(table)
    doc.build(elements)
    return path


def build_lease_agreement_pdf(lease: dict, landlord: dict, tenant: dict) -> str:
    path = f"/tmp/lease_{lease.get('id', uuid.uuid4().hex[:8])}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    generated = datetime.now(timezone.utc).date().isoformat()
    elements = [
        Paragraph("कृषि भूमि पट्टा अनुबंध", styles["Title"]),
        Paragraph("Agricultural Land Lease Agreement", styles["Normal"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Landlord (मालिक): {landlord.get('name') or landlord.get('id', '')} — {landlord.get('village', '')}", styles["Normal"]),
        Paragraph(f"Plot (प्लॉट): {lease.get('plotId', '')}", styles["Normal"]),
        Paragraph(f"Tenant (किरायेदार): {lease.get('tenantName', '')} — {lease.get('tenantPhone', '')}", styles["Normal"]),
        Paragraph(f"Monthly rent (मासिक किराया): ₹{lease.get('monthlyRentRupees', 0):.0f}", styles["Normal"]),
        Paragraph(f"Term (अवधि): {lease.get('startDate', '')} to {lease.get('endDate', '')}", styles["Normal"]),
        Spacer(1, 4 * mm),
        Paragraph(f"Generated on: {generated}", styles["Normal"]),
    ]
    doc.build(elements)
    return path


def build_policy_certificate_pdf(policy: dict) -> str:
    path = f"/tmp/policy_{policy.get('policyNumber', uuid.uuid4().hex[:8])}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Crop Insurance Policy Certificate", styles["Title"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Policy number: {policy.get('policyNumber', '')}", styles["Normal"]),
        Paragraph(f"Scheme: {policy.get('schemeName', '')}", styles["Normal"]),
        Paragraph(f"Crop: {policy.get('cropName', '')} ({policy.get('season', '')} {policy.get('year', '')})", styles["Normal"]),
        Paragraph(f"Sum insured: ₹{policy.get('sumInsured', 0):.0f}", styles["Normal"]),
        Paragraph(f"Validity: {policy.get('coverageStartDate', '')} to {policy.get('coverageEndDate', '')}", styles["Normal"]),
        Paragraph(f"Insurer: {policy.get('insuranceCompany', '')}", styles["Normal"]),
    ]
    doc.build(elements)
    return path


def upload_to_storage(local_path: str, dest_path: str) -> str:
    if not firebase_admin._apps:
        logger.warning("Firebase not initialised — returning local file:// URL for %s", dest_path)
        return f"file://{local_path}"
    bucket = firebase_admin.storage.bucket()
    blob = bucket.blob(dest_path)
    blob.upload_from_filename(local_path)
    blob.make_public()
    return blob.public_url
