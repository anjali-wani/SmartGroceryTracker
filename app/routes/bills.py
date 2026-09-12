from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PurchaseLog, Inventory, InventoryStatus
from app.schemas import CSVUploadSummary, PurchaseLogOut
from app.services.ingestion import process_receipt_csv

router = APIRouter(prefix="/bills", tags=["Bills & Ingestion"])


@router.post("/upload-csv", response_model=CSVUploadSummary, status_code=status.HTTP_201_CREATED)
async def upload_csv_receipt(
    file: UploadFile = File(..., description="Grocery receipt / invoice CSV file"),
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Upload raw grocery bill CSV, extract units, resolve items via RapidFuzz,
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
        summary = process_receipt_csv(file_bytes=file_bytes, db=db, household_id=household_id)
        return summary
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CSV bill: {str(e)}"
        )


@router.get("/purchases", response_model=List[PurchaseLogOut])
def get_purchase_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    item_id: Optional[int] = Query(None, description="Filter by canonical item ID"),
    db: Session = Depends(get_db)
):
    """Retrieve historical transaction logs parsed from grocery receipts."""
    query = db.query(PurchaseLog)
    if item_id:
        query = query.filter(PurchaseLog.canonical_item_id == item_id)
    logs = query.order_by(PurchaseLog.purchase_date.desc()).offset(offset).limit(limit).all()
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

    # Rollback corresponding inventory if active
    if log.canonical_item_id:
        inv = (
            db.query(Inventory)
            .filter(
                Inventory.canonical_item_id == log.canonical_item_id,
                Inventory.purchase_date == log.purchase_date,
                Inventory.status == InventoryStatus.ACTIVE
            )
            .first()
        )
        if inv:
            # Deduct quantity or remove
            if inv.current_quantity <= log.quantity:
                db.delete(inv)
            else:
                inv.current_quantity -= log.quantity

    item_name = log.item.canonical_name if log.item else log.raw_text
    db.delete(log)
    db.commit()

    return {"message": f"Deleted purchase transaction for '{item_name}' and updated inventory."}
