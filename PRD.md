# PRD — Multi-Agent Customer Onboarding System
## Product Requirements Document: Peningkatan v1.0 → v2.0

**Author:** Moh. Jeli Almutaali  
**Repo:** `jelimutaalidev/multi-agent-onboarding`  
**Status:** Draft  
**Last Updated:** 2026-03-16

---

## 1. Latar Belakang

Sistem onboarding saat ini telah berhasil membuktikan konsep arsitektur multi-agent (Vision + RAG + PII Guardian). Namun terdapat beberapa kelemahan fundamental yang membuat sistem ini belum layak diklaim sebagai *production-ready*:

- Vector store berbasis in-memory (hilang saat restart)
- Database berbasis JSON flat-file (tidak concurrent-safe)
- Tidak ada test suite yang terstruktur
- Tidak ada interface API yang bisa dikonsumsi sistem lain
- Tidak ada benchmark performa yang terdokumentasi

PRD ini mendefinisikan scope perbaikan yang diprioritaskan berdasarkan dampak terhadap kualitas sistem dan nilai pada CV/portofolio.

---

## 2. Tujuan

| Tujuan | Metrik Sukses |
|--------|--------------|
| Sistem bisa restart tanpa kehilangan data vector/policy | ChromaDB persist di disk, load otomatis saat startup |
| Data customer tersimpan aman dan concurrent-safe | Migrasi ke SQLite/PostgreSQL, zero data loss pada concurrent request |
| Kualitas kode terverifikasi | Test coverage ≥ 80%, semua agent punya unit test |
| Sistem bisa dikonsumsi via API | FastAPI endpoint `/onboard` berjalan dan terdokumentasi |
| Performa terukur dan terdokumentasi | Benchmark table tersedia di README |

---

## 3. Scope Perbaikan

### P0 — Harus Selesai (Critical)

---

#### [P0-1] Migrasi Vector Store: InMemory → ChromaDB

**Masalah:**  
`InMemoryVectorStore` tidak persistent. Setiap kali aplikasi restart, semua embedding policy harus di-generate ulang dari awal. Ini memakan waktu dan biaya API.

**Solusi:**  
Ganti ke `ChromaDB` dengan persistent storage di direktori lokal.

**Implementasi:**

```python
# src/rag_store.py — SEBELUM
from langchain.vectorstores import InMemoryVectorStore
vectorstore = InMemoryVectorStore(embedding=embeddings)

# SESUDAH
import chromadb
from langchain_chroma import Chroma

CHROMA_PATH = "./data/chroma_db"

def get_vectorstore(embeddings):
    return Chroma(
        collection_name="compliance_policies",
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH,
    )
```

**Kriteria selesai:**
- [ ] ChromaDB terinstall dan ada di `requirements.txt`
- [ ] Data policy di-load sekali, tersimpan di `data/chroma_db/`
- [ ] Saat restart, system load dari disk (tidak re-embed)
- [ ] Tambahkan script `scripts/init_vectorstore.py` untuk inisialisasi pertama kali

**Estimasi:** 2–3 jam

---

#### [P0-2] Migrasi Database: JSON File → SQLite

**Masalah:**  
`customers.json` dan `audit_log.json` tidak aman untuk concurrent write, tidak bisa di-query dengan filter, dan tidak scalable.

**Solusi:**  
Migrasi ke SQLite menggunakan `SQLAlchemy` ORM. SQLite tidak butuh server eksternal, cocok untuk tahap ini.

**Schema Database:**

```sql
-- Tabel customers
CREATE TABLE customers (
    id          TEXT PRIMARY KEY,          -- CUST-20260116061221
    full_name   TEXT NOT NULL,
    nik_masked  TEXT NOT NULL,
    dob         DATE,
    account_type TEXT,
    status      TEXT CHECK(status IN ('APPROVED', 'REJECTED', 'PENDING')),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabel audit_log
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT REFERENCES customers(id),
    action      TEXT NOT NULL,             -- EXTRACTED, VALIDATED, MASKED, SAVED
    agent       TEXT NOT NULL,             -- VISION_AGENT, POLICY_AGENT, PII_GUARDIAN
    detail      TEXT,
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Implementasi:**

```python
# src/database.py — baru
from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.orm import declarative_base, Session
from datetime import datetime

Base = declarative_base()
engine = create_engine("sqlite:///data/db/onboarding.db")

class Customer(Base):
    __tablename__ = "customers"
    id           = Column(String, primary_key=True)
    full_name    = Column(String)
    nik_masked   = Column(String)
    account_type = Column(String)
    status       = Column(String)
    created_at   = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    customer_id  = Column(String)
    action       = Column(String)
    agent        = Column(String)
    detail       = Column(Text)
    timestamp    = Column(DateTime, default=datetime.utcnow)
```

**Kriteria selesai:**
- [ ] `SQLAlchemy` ada di `requirements.txt`
- [ ] File `src/database.py` dibuat dengan model `Customer` dan `AuditLog`
- [ ] `pii_guardian.py` diupdate untuk write ke SQLite, bukan JSON
- [ ] Migration script tersedia di `scripts/init_db.py`
- [ ] File JSON lama dipindah ke `data/legacy/` sebagai backup

**Estimasi:** 3–4 jam

---

#### [P0-3] Test Suite dengan Pytest

**Masalah:**  
Tidak ada automated test. Tidak bisa membuktikan sistem berjalan benar kecuali run manual.

**Solusi:**  
Implementasi pytest dengan coverage minimal 80% untuk 3 agent utama.

**Struktur Test:**

```
tests/
├── conftest.py              # Fixtures (mock API, sample data)
├── unit/
│   ├── test_pii_guardian.py # Test masking logic (no API needed)
│   ├── test_schemas.py      # Test Pydantic validation
│   └── test_rag_store.py    # Test retrieval logic
├── integration/
│   ├── test_policy_validator.py  # Test dengan mock vector store
│   └── test_full_pipeline.py     # Test end-to-end dengan mock Vision
└── fixtures/
    ├── sample_document_data.json
    └── sample_policy_response.json
```

**Test Case Wajib:**

```python
# tests/unit/test_pii_guardian.py
def test_nik_masking():
    result = mask_pii("NIK: 3201234567890001", strategy="mask")
    assert "3201234567890001" not in result
    assert "xxxx" in result.lower() or "[" in result

def test_phone_masking():
    result = mask_pii("Phone: 081234567890", strategy="redact")
    assert "081234567890" not in result

def test_no_false_positive():
    text = "Order ID: 123456"
    result = mask_pii(text, strategy="mask")
    assert result == text  # bukan PII, tidak boleh dimasking

# tests/unit/test_schemas.py  
def test_document_schema_valid():
    data = {"name": "Budi", "nik": "3201234567890001", "age": 35}
    doc = DocumentData(**data)
    assert doc.age == 35

def test_document_schema_invalid_nik():
    with pytest.raises(ValidationError):
        DocumentData(name="Budi", nik="123", age=35)  # NIK harus 16 digit

# tests/integration/test_policy_validator.py
def test_futures_approved(mock_vectorstore):
    result = validate_policy(age=25, account_type="Futures", 
                             vectorstore=mock_vectorstore)
    assert result["status"] == "APPROVED"

def test_futures_rejected_underage(mock_vectorstore):
    result = validate_policy(age=19, account_type="Futures",
                             vectorstore=mock_vectorstore)
    assert result["status"] == "REJECTED"
    assert "21" in result["reason"]
```

**Kriteria selesai:**
- [ ] `pytest` dan `pytest-cov` ada di `requirements.txt`
- [ ] Minimal 15 test case total
- [ ] Coverage ≥ 80% untuk `pii_guardian.py` dan `schemas.py`
- [ ] Semua test bisa jalan **tanpa** API key (gunakan mock/fixture)
- [ ] Tambahkan `pytest.ini` atau `pyproject.toml` untuk konfigurasi
- [ ] `README.md` diupdate dengan cara run test

**Estimasi:** 4–5 jam

---

### P1 — Tinggi (Sangat Disarankan)

---

#### [P1-1] FastAPI REST Endpoint

**Masalah:**  
Sistem hanya bisa diakses via CLI. Tidak bisa diintegrasikan dengan frontend atau sistem lain.

**Solusi:**  
Tambahkan FastAPI layer di atas pipeline yang sudah ada.

**Endpoint yang Dibutuhkan:**

```
POST   /api/v1/onboard          # Submit dokumen + account type → hasil validasi
GET    /api/v1/customers/{id}   # Get customer record (masked)
GET    /api/v1/audit/{id}       # Get audit trail customer
GET    /api/v1/health           # Health check + status komponen
```

**Request/Response:**

```python
# POST /api/v1/onboard
# Request: multipart/form-data
# - file: image (JPG/PNG/WebP)
# - account_type: str ("Stocks" | "Futures" | "Crypto")

# Response 200 APPROVED:
{
  "customer_id": "CUST-20260116061221",
  "status": "APPROVED",
  "account_type": "Futures",
  "processing_time_ms": 4320,
  "agents": {
    "extraction": { "status": "success", "confidence": 0.98 },
    "validation": { "status": "approved", "policy": "age >= 21" },
    "pii_guardian": { "status": "masked", "fields_masked": 5 }
  }
}

# Response 200 REJECTED:
{
  "status": "REJECTED",
  "reason": "Customer age (20) below minimum requirement (21) for Futures",
  "recommendations": ["Apply after age 21", "Consider Stocks account (min 18)"]
}
```

**Struktur File:**

```
api/
├── main.py          # FastAPI app entry point
├── routes/
│   ├── onboard.py   # POST /onboard endpoint
│   └── customers.py # GET endpoints
└── middleware/
    └── timing.py    # Request timing middleware
```

**Kriteria selesai:**
- [ ] `fastapi` dan `uvicorn` ada di `requirements.txt`
- [ ] Semua 4 endpoint berjalan
- [ ] Response menyertakan `processing_time_ms`
- [ ] Swagger UI tersedia di `/docs`
- [ ] Error handling: file bukan gambar → 400, agent gagal → 500
- [ ] README diupdate dengan cara run API: `uvicorn api.main:app --reload`

**Estimasi:** 5–6 jam

---

#### [P1-2] Benchmark & Performance Documentation

**Masalah:**  
Tidak ada data performa yang terdokumentasi. Recruiter dan user tidak tahu seberapa cepat sistem ini.

**Solusi:**  
Buat script benchmark dan dokumentasikan hasilnya di README.

**Script:**

```python
# scripts/benchmark.py
import time, statistics

def benchmark_pipeline(n_runs=10):
    results = {"extraction": [], "validation": [], "pii": [], "total": []}
    
    for _ in range(n_runs):
        t0 = time.perf_counter()
        doc = extract_document_data("test_images/sample_ktp.png")
        results["extraction"].append(time.perf_counter() - t0)
        
        t1 = time.perf_counter()
        val = validate_customer_from_document_data(doc, "Futures")
        results["validation"].append(time.perf_counter() - t1)
        
        # ... dst
    
    print("=== BENCHMARK RESULTS ===")
    for k, v in results.items():
        print(f"{k:12} avg={statistics.mean(v)*1000:.0f}ms  "
              f"p95={sorted(v)[int(n_runs*0.95)]*1000:.0f}ms")
```

**Target Tabel untuk README:**

```
| Operation           | Avg    | P95    | Notes                    |
|---------------------|--------|--------|--------------------------|
| Document Extraction | ~3.2s  | ~4.1s  | Gemini API latency       |
| Policy Validation   | ~1.1s  | ~1.5s  | RAG retrieval + LLM      |
| PII Masking         | ~18ms  | ~25ms  | Pure regex, no API call  |
| Full Pipeline       | ~4.5s  | ~5.8s  | End-to-end               |
```

**Kriteria selesai:**
- [ ] `scripts/benchmark.py` tersedia dan bisa dijalankan
- [ ] Tabel benchmark ada di README dengan data hasil run nyata
- [ ] Catat environment (CPU, RAM, region API) untuk reproducibility

**Estimasi:** 2 jam

---

### P2 — Sedang (Opsional tapi Impresif)

---

#### [P2-1] Docker & Docker Compose

**Tujuan:** Siapapun bisa menjalankan sistem dengan 1 command tanpa setup manual.

```dockerfile
# Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data    # persist ChromaDB + SQLite
    env_file: .env
```

**Kriteria selesai:**
- [ ] `docker compose up` langsung berjalan
- [ ] Data persist di volume (tidak hilang saat container restart)
- [ ] README punya section "Quick Start with Docker"

**Estimasi:** 2–3 jam

---

#### [P2-2] Tambah Test Image & Edge Cases

**Tujuan:** Membuktikan sistem robust, bukan hanya happy path.

**Test cases yang perlu ditambah:**

| File | Skenario | Expected |
|------|----------|----------|
| `expired_ktp.png` | Dokumen kedaluwarsa | REJECTED + reason expired |
| `blurry_ktp.png` | Foto buram | confidence < 70%, warning |
| `passport_wni.png` | Paspor Indonesia | APPROVED jika eligible |
| `ktp_young.png` | Usia 17 tahun | REJECTED semua account type |
| `ktp_crypto_eligible.png` | Usia 26 tahun | APPROVED Crypto |

**Estimasi:** 2 jam

---

## 4. Urutan Pengerjaan yang Disarankan

```
Week 1
├── Hari 1–2  : [P0-1] ChromaDB migration
├── Hari 2–3  : [P0-2] SQLite migration  
└── Hari 4–5  : [P0-3] Pytest test suite

Week 2
├── Hari 1–3  : [P1-1] FastAPI endpoint
├── Hari 4    : [P1-2] Benchmark script + README update
└── Hari 5    : [P2-1] Docker (jika waktu cukup)
```

---

## 5. Update README Setelah Semua P0+P1 Selesai

Bagian yang harus ditambahkan/diupdate:

- [ ] **Architecture diagram** diupdate (tambahkan FastAPI layer + ChromaDB + SQLite)
- [ ] **Quick Start** diupdate dengan 2 opsi: CLI dan Docker
- [ ] **Benchmark table** ditambahkan
- [ ] **Test section** diupdate dengan `pytest --cov` instructions
- [ ] **API docs** link ke `/docs` endpoint

---

## 6. Dampak ke CV Setelah Implementasi

Setelah P0 + P1 selesai, bullet CV bisa diupgrade menjadi:

**Sebelum:**
> *"Engineered a Vision AI Agent utilizing Google Gemini 3.0 Flash to extract structured identity data"*

**Sesudah:**
> *"Engineered a production-ready multi-agent onboarding pipeline with FastAPI REST interface, achieving **98% extraction confidence** on KTP/Passport documents, **~4.5s** end-to-end processing, and **80%+ test coverage** across 3 specialized agents (Vision, RAG Policy, PII Guardian)"*

---

*PRD ini bersifat living document — update setiap kali ada perubahan scope atau prioritas.*
