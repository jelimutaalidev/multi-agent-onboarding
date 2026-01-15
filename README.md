<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/LangChain-v1.2+-green?style=for-the-badge&logo=chainlink&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/Gemini-2.5_Flash-orange?style=for-the-badge&logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

# 🤖 Multi-Agent Customer Onboarding System

<p align="center">
  <b>An intelligent multi-agent system for automated customer onboarding validation using LangChain, RAG, and Vision AI</b>
</p>

---

## 🎯 Project Overview

This project demonstrates a **production-ready multi-agent architecture** for automating customer onboarding in financial services. The system combines **Computer Vision**, **RAG (Retrieval-Augmented Generation)**, and **Data Security** principles to create a seamless, secure, and compliant onboarding workflow.

### 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CUSTOMER ONBOARDING PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   AGENT 1    │    │   AGENT 2    │    │   AGENT 3    │              │
│  │  Document    │───▶│   Policy     │───▶│     PII      │───▶ Database │
│  │  Extractor   │    │  Validator   │    │   Guardian   │              │
│  │  (Vision)    │    │    (RAG)     │    │  (Security)  │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│   ┌──────────┐       ┌──────────┐       ┌──────────┐                   │
│   │  Gemini  │       │ Vector   │       │   PII    │                   │
│   │  Vision  │       │  Store   │       │ Masking  │                   │
│   └──────────┘       └──────────┘       └──────────┘                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

| Feature | Description | Technology |
|---------|-------------|------------|
| 🔍 **Document Extraction** | Auto-extract data from ID cards (KTP, Passport) using Vision AI | Gemini 2.5 Flash |
| 📋 **Policy Validation** | Validate customer eligibility against compliance policies using RAG | HuggingFace + LangChain |
| 🔒 **PII Protection** | Automatic masking of sensitive data before storage | Custom + LangChain Middleware |
| 📊 **Structured Output** | Type-safe responses using Pydantic schemas | Pydantic v2 |
| 🗄️ **Audit Trail** | Complete logging with data protection compliance | JSON-based simulation |

---

## 🚀 Agents

### Agent 1: Document Extractor (Vision Agent)

Extracts structured data from identity document photos using **Google Gemini Vision Model**.

**Capabilities:**
- Reads Indonesian ID cards (KTP), Passports, and Driver's Licenses (SIM)
- Extracts: Name, NIK (16-digit ID), Date of Birth, Address, Expiry Date
- Provides confidence score for extraction quality
- Handles various image formats (JPG, PNG, WebP)

**Tech Stack:** `LangChain create_agent()` · `Gemini 2.5 Flash` · `Pydantic`

---

### Agent 2: Policy Validator (RAG Agent)

Validates customer eligibility against company policies using **Retrieval-Augmented Generation**.

**Capabilities:**
- Age verification for different account types (Stocks: 18+, Futures: 21+, Crypto: 25+)
- Document validity checking
- Policy-based decision making with explanations
- Returns approval status with policy references

**Tech Stack:** `LangChain Tools` · `HuggingFace Embeddings` · `InMemoryVectorStore`

---

### Agent 3: PII Guardian (Security Agent)

Protects sensitive personal information before logging or storage.

**Capabilities:**
- Detects Indonesian PII: NIK, Phone, Email, Name, Address, Birth Date
- Multiple masking strategies: redact, mask, hash, tokenize
- Automatic masking before database storage
- Audit logging for compliance

**Tech Stack:** `LangChain PIIMiddleware` · `Regex Patterns` · `JSON Database`

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- Conda (recommended) or virtualenv
- Google API Key for Gemini

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/multi-agent-onboarding.git
cd multi-agent-onboarding

# 2. Create conda environment (recommended)
conda create -n onboarding python=3.10
conda activate onboarding

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API key
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Dependencies

```
langchain>=0.3.0
langchain-google-genai>=2.0.0
langgraph>=0.2.0
langchain-huggingface>=0.1.0
sentence-transformers>=2.0.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

---

## 🎮 Usage

### Full Pipeline (Recommended)

```bash
# Basic validation
python validate.py test_images/sample_ktp.png --account-type Futures

# With PII masking and database save
python validate.py test_images/sample_ktp.png -a Futures --save --show-pii-report
```

### Document Extraction Only

```bash
python main.py test_images/sample_ktp.png
```

### Python API

```python
from src.agent import extract_document_data
from src.policy_validator import validate_customer_from_document_data
from src.pii_guardian import process_and_save_customer

# Step 1: Extract document data
document_data = extract_document_data("path/to/ktp.jpg")

# Step 2: Validate against policies
validation = validate_customer_from_document_data(document_data, "Futures")

# Step 3: Save with PII protection
if validation["status"] == "APPROVED":
    record = process_and_save_customer(document_data, validation)
```

---

## 📊 Example Output

### Successful Onboarding (APPROVED)

```
======================================================================
[ONBOARDING] Customer Onboarding Validation System
======================================================================

[STEP 1] Document Extraction
   ✓ Name: BUDI SANTOSO
   ✓ NIK: 3201234567890001
   ✓ Age: 35 years
   ✓ Confidence: 98%

[STEP 2] Policy Validation
   ✓ Account Type: Futures (min age: 21)
   ✓ Status: APPROVED

[STEP 3] PII Protection
   ✓ Detected: 5 PII fields
   ✓ NIK Masked: xxxx-xxxx-xxxx-0001
   ✓ Name Masked: BUD***

[STEP 4] Database Save
   ✓ Customer ID: CUST-20260116061221
   ✓ PII Masked: True
```

### Failed Onboarding (REJECTED)

```
[STEP 2] Policy Validation
   ✗ Account Type: Futures (min age: 21)
   ✗ Customer Age: 20 years
   ✗ Status: REJECTED

   Reason: Customer age (20) is below minimum requirement (21) for Futures trading.
   
   Recommendations:
   - Apply again after reaching 21 years of age
   - Consider other account types suitable for current age
```

---

## 📁 Project Structure

```
multi-agent-onboarding/
├── 📄 README.md                 # This file
├── 📄 requirements.txt          # Python dependencies
├── 📄 .env.example              # Environment template
├── 📄 .gitignore                # Git ignore rules
│
├── 🐍 main.py                   # CLI - Document extraction only
├── 🐍 validate.py               # CLI - Full pipeline
│
├── 📂 src/
│   ├── 🐍 __init__.py
│   ├── 🐍 agent.py              # Document Extractor Agent
│   ├── 🐍 policy_validator.py   # Policy Validator Agent
│   ├── 🐍 pii_guardian.py       # PII Guardian Agent
│   ├── 🐍 rag_store.py          # Vector Store & Retrieval
│   └── 🐍 schemas.py            # Pydantic Schemas
│
├── 📂 data/
│   ├── 📂 policies/             # Compliance documents for RAG
│   │   └── 📄 exante_compliance_policy_2025.txt
│   └── 📂 db/                   # Simulated database
│       ├── 📄 customers.json
│       └── 📄 audit_log.json
│
└── 📂 test_images/              # Sample test images
    ├── 🖼️ sample_ktp.png        # Adult (35 years) - APPROVED
    └── 🖼️ sample_ktp_young.png  # Young (20 years) - REJECTED
```

---

## 🧪 Testing

### Test Cases

| Test Case | Input | Expected Result |
|-----------|-------|-----------------|
| Adult + Futures | KTP (35 years) + Futures | ✅ APPROVED |
| Underage + Futures | KTP (20 years) + Futures | ❌ REJECTED |
| Adult + Crypto | KTP (35 years) + Crypto | ✅ APPROVED |
| Young + Crypto | KTP (35 years < 25) + Crypto | ❌ REJECTED |

### Run Tests

```bash
# Test approval case
python validate.py test_images/sample_ktp.png -a Futures

# Test rejection case
python validate.py test_images/sample_ktp_young.png -a Futures
```

---

## 🔧 Configuration

### Model Configuration

Edit `src/agent.py` to change the Vision model:

```python
agent = create_agent(
    model="google_genai:gemini-2.5-flash",      # Default - Fast
    # model="google_genai:gemini-2.5-pro",      # More accurate
)
```

### PII Masking Strategies

Available in `src/pii_guardian.py`:

| Strategy | Example | Use Case |
|----------|---------|----------|
| `mask` | `1234xxxx5678xxxx` | Partial visibility |
| `redact` | `[REDACTED_NIK]` | Complete removal |
| `hash` | `[HASH:a8f5f167...]` | Reversible mapping |
| `tokenize` | `[TOKEN:nik_0001]` | Unique identifiers |

---

## 🔐 Security Considerations

- ✅ PII is automatically masked before logging
- ✅ Sensitive data never stored in plain text
- ✅ Audit trail for all operations
- ✅ Environment variables for API keys
- ⚠️ This is a demo - use proper encryption for production

---

## 🛣️ Roadmap

- [ ] Add FastAPI REST endpoint
- [ ] Integrate with real database (PostgreSQL)
- [ ] Add OCR fallback for low-quality images
- [ ] Implement webhook notifications
- [ ] Add multi-language support
- [ ] Create Docker deployment

---

## 📚 Technologies Used

| Category | Technology |
|----------|------------|
| **LLM Framework** | LangChain v1.2+, LangGraph |
| **Vision Model** | Google Gemini 2.5 Flash |
| **Embeddings** | HuggingFace sentence-transformers |
| **Vector Store** | LangChain InMemoryVectorStore |
| **Data Validation** | Pydantic v2 |
| **Language** | Python 3.10+ |

---

## 👨‍💻 Author

**Your Name**
- GitHub: [@yourusername](https://github.com/jelimutaalidev)
- LinkedIn: [Your LinkedIn](https://linkedin.com/in/moh-jeli-almutaali-5b09772b9)
- Email: jelimutaalidev@gmail.com

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>⭐ Star this repo if you find it useful! ⭐</b>
</p>
