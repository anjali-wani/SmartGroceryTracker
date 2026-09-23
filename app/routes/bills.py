import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PurchaseLog, Inventory, InventoryStatus, ReceiptUpload
from app.schemas import CSVUploadSummary, PurchaseLogOut, ReceiptUploadOut, BillItemOut
from app.services.ingestion import process_receipt_csv

logger = logging.getLogger("grocery_bills")

router = APIRouter(prefix="/bills", tags=["Bills & Ingestion"])


@router.post("/upload-csv", response_model=CSVUploadSummary, status_code=status.HTTP_201_CREATED)
async def upload_csv_receipt(
    file: UploadFile = File(..., description="Grocery receipt / invoice CSV file"),
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Upload raw grocery bill CSV, extract units, resolve items via RapidFuzz / LLM,
    record purchase transactions, and automatically populate active inventory.
    """
    if not file.filename.lower().endswith(('.csv', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a .csv file."
        )

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )
        summary = process_receipt_csv(file_bytes=file_bytes, db=db, household_id=household_id, filename=file.filename)
        return summary
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except Exception as e:
        logger.exception(f"Error processing CSV bill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CSV bill: {str(e)}"
        )


@router.get("/purchases", response_model=List[PurchaseLogOut])
def get_purchase_history(
    household_id: int = Query(1, description="Household ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    item_id: Optional[int] = Query(None, description="Filter by canonical item ID"),
    db: Session = Depends(get_db)
):
    """Retrieve historical transaction logs parsed from grocery receipts for a specific household."""
    query = db.query(PurchaseLog).filter(PurchaseLog.household_id == household_id)
    if item_id:
        query = query.filter(PurchaseLog.canonical_item_id == item_id)
    logs = query.order_by(PurchaseLog.purchase_date.desc(), PurchaseLog.id.desc()).offset(offset).limit(limit).all()
    return logs


@router.delete("/purchases/{purchase_id}", status_code=status.HTTP_200_OK)
def delete_purchase_log_item(
    purchase_id: int,
    db: Session = Depends(get_db)
):
    """Delete a mistaken, duplicate, or refunded purchase line item and rollback active inventory."""
    log = db.query(PurchaseLog).filter(PurchaseLog.id == purchase_id).first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase log entry not found.")

    # Rollback corresponding inventory for this household if active
    if log.canonical_item_id:
        inv = (
            db.query(Inventory)
            .filter(
                Inventory.household_id == log.household_id,
                Inventory.canonical_item_id == log.canonical_item_id,
                Inventory.purchase_date == log.purchase_date,
                Inventory.status == InventoryStatus.ACTIVE
            )
            .first()
        )
        if inv:
            if inv.current_quantity <= log.quantity:
                inv.current_quantity = 0.0
                inv.status = InventoryStatus.CONSUMED
            else:
                inv.current_quantity -= log.quantity

    item_name = log.item.canonical_name if log.item else log.raw_text
    db.delete(log)
    db.commit()

    return {"message": f"Deleted purchase transaction for '{item_name}' and updated inventory."}


@router.get("", response_model=List[ReceiptUploadOut])
def list_uploaded_bills(
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """List all uploaded grocery receipts / bills for a household."""
    bills = (
        db.query(ReceiptUpload)
        .filter(ReceiptUpload.household_id == household_id)
        .order_by(ReceiptUpload.uploaded_at.desc(), ReceiptUpload.id.desc())
        .all()
    )
    return bills


@router.get("/{bill_id}/items", response_model=List[BillItemOut])
def get_bill_line_items(
    bill_id: int,
    db: Session = Depends(get_db)
):
    """List all purchased line items from a specific bill."""
    bill = db.query(ReceiptUpload).filter(ReceiptUpload.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")

    purchases = (
        db.query(PurchaseLog)
        .filter(PurchaseLog.bill_id == bill_id)
        .order_by(PurchaseLog.id.asc())
        .all()
    )

    out = []
    for p in purchases:
        item_name = p.item.canonical_name if p.item else p.raw_text
        category = p.item.category if p.item else "General"
        out.append(BillItemOut(
            id=p.id,
            raw_text=p.raw_text,
            canonical_item_id=p.canonical_item_id,
            item_name=item_name,
            category=category,
            quantity=p.quantity,
            unit=p.unit,
            price=p.price,
            matched_via=p.matched_via,
            confidence=p.confidence,
            purchase_date=p.purchase_date,
            store_name=p.store_name
        ))
    return out


@router.delete("/{bill_id}", status_code=status.HTTP_200_OK)
def delete_entire_bill(
    bill_id: int,
    db: Session = Depends(get_db)
):
    """Delete an entire uploaded bill, all its purchase logs, and rollback corresponding active inventory."""
    bill = db.query(ReceiptUpload).filter(ReceiptUpload.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")

    purchases = db.query(PurchaseLog).filter(PurchaseLog.bill_id == bill_id).all()
    count = len(purchases)

    for p in purchases:
        # Rollback inventory
        inv = db.query(Inventory).filter(Inventory.purchase_log_id == p.id).first()
        if not inv and p.canonical_item_id:
            inv = (
                db.query(Inventory)
                .filter(
                    Inventory.household_id == p.household_id,
                    Inventory.canonical_item_id == p.canonical_item_id,
                    Inventory.purchase_date == p.purchase_date,
                    Inventory.status == InventoryStatus.ACTIVE
                )
                .first()
            )
        if inv:
            if inv.current_quantity <= p.quantity:
                inv.current_quantity = 0.0
                inv.status = InventoryStatus.CONSUMED
            else:
                inv.current_quantity -= p.quantity

    db.delete(bill)  # cascade deletes PurchaseLog
    db.commit()
    return {
        "success": True,
        "message": f"Bill '{bill.filename}' ({count} items) deleted successfully and active inventory rolled back."
    }
