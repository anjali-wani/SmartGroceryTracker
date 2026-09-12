# Smart Grocery Tracker & Nutrition Engine

**Technical Architecture & Implementation — Phase 1: Foundation Layer**

---

## Overview

The Smart Grocery Tracker is a multi-tier data pipeline that processes raw receipt bills, tracks inventory velocity, models consumption behavior, and runs nutritional gap analysis.

### Phase 1 Deliverables (Completed):
1. **Relational Database Schema (SQLAlchemy)**:
   - `items`: Canonical grocery items with category, standard units, and default shelf life.
   - `item_aliases`: Store-specific receipt text mapped to canonical items.
   - `household`: Household demographic profiles for consumption baseline.
   - `purchase_logs`: Transaction line items recorded from bills.
   - `inventory`: Current active stock with expiration dates and statuses.
   - `guest_events`: Historical/planned guest events.
2. **Text Normalization & Unit Extraction Engine (`app/normalizer.py`)**:
   - Cleans store barcodes, SKUs, and transaction noise.
   - Regex extraction of quantities and units (e.g. `1 Gal`, `128oz`, `2.5 lbs`, `24 ct`, `500g`).
3. **Multi-Tier Entity Resolution Engine (`app/resolution.py`)**:
   - **Tier 1**: Exact canonical and alias dictionary lookup.
   - **Tier 2**: RapidFuzz string similarity (`token_set_ratio`) matching against canonical catalog.
   - **Tier 3**: Heuristic token-subset fallback.
4. **Receipt CSV Ingestion (`POST /bills/upload-csv`)**:
   - Ingests CSV receipts, parses line items, normalizes units, matches items via RapidFuzz, records transactions, and populates active inventory.
5. **Initial Seed Dataset (`app/seed.py`)**:
   - Pre-seeds 30+ canonical items and store aliases across Dairy, Produce, Meat, Bakery, Pantry, and Beverages.

---

## Quickstart

### 1. Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Database & Start API Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Open Swagger UI docs at: `http://localhost:8000/docs`
- Root health check: `http://localhost:8000/`

### 3. Run Automated Tests
```bash
pytest tests/test_phase1.py -v
```

### 4. Upload a Sample Receipt CSV
```bash
curl -X POST "http://localhost:8000/bills/upload-csv" \
  -F "file=@data/sample_receipt.csv"
```
