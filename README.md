# 📄 Document Extractor Vision Agent

Agent AI untuk mengekstrak data dari foto dokumen identitas Indonesia (KTP, Paspor, SIM) menggunakan **LangChain** dan **Google Gemini Vision Model**.

## ✨ Fitur

- 🔍 **Vision AI** - Menggunakan Gemini 2.5 Flash untuk membaca dokumen
- 📋 **Structured Output** - Hasil ekstraksi dalam format JSON terstruktur
- 🎯 **Multi-Document** - Mendukung KTP, Paspor, dan SIM
- 📊 **Confidence Score** - Indikator kualitas ekstraksi
- 🔒 **Validasi** - Validasi format NIK dan tanggal

## 📦 Instalasi

### 1. Clone atau masuk ke folder project

```bash
cd multi-agent-onboarding
```

### 2. Buat Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup API Key

1. Dapatkan API Key dari [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Copy `.env.example` ke `.env`:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` dan masukkan API key:
   ```
   GOOGLE_API_KEY=your-actual-api-key-here
   ```

## 🚀 Penggunaan

### Command Line

```bash
python main.py path/to/document_photo.jpg
```

### Contoh Output

```
============================================================
📄 Document Extractor Vision Agent
============================================================

🔍 Menganalisis: sample_ktp.jpg
   Mohon tunggu...

✅ Ekstraksi berhasil!

------------------------------------------------------------
📋 HASIL EKSTRAKSI:
------------------------------------------------------------

  📌 Jenis Dokumen : KTP
  👤 Nama          : BUDI SANTOSO
  🆔 NIK           : 3201234567890001
  📅 Tanggal Lahir : 15-08-1990
  📍 Tempat Lahir  : JAKARTA
  ⚧ Jenis Kelamin : LAKI-LAKI
  🏠 Alamat        : JL. MERDEKA NO. 123
  ⏰ Kadaluarsa    : SEUMUR HIDUP
  📊 Confidence    : 95.0%

------------------------------------------------------------
📄 JSON OUTPUT:
------------------------------------------------------------
{
  "nama": "BUDI SANTOSO",
  "nik": "3201234567890001",
  "tanggal_lahir": "15-08-1990",
  "tempat_lahir": "JAKARTA",
  "jenis_kelamin": "LAKI-LAKI",
  "alamat": "JL. MERDEKA NO. 123",
  "tanggal_kadaluarsa": "SEUMUR HIDUP",
  "jenis_dokumen": "KTP",
  "confidence": 0.95,
  "catatan": null
}
```

### Sebagai Module Python

```python
from src.agent import extract_document_data

# Dari file gambar
result = extract_document_data("path/to/ktp.jpg")
print(result)

# Dari base64 (untuk integrasi API)
from src.agent import extract_document_data_from_base64
import base64

with open("ktp.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

result = extract_document_data_from_base64(image_b64, "image/jpeg")
print(result)
```

## 📁 Struktur Project

```
multi-agent-onboarding/
├── .env                    # API keys (jangan commit!)
├── .env.example            # Template environment variables
├── .gitignore              # Git ignore rules
├── requirements.txt        # Python dependencies
├── README.md               # Dokumentasi ini
├── main.py                 # CLI entry point
└── src/
    ├── __init__.py
    ├── agent.py            # Core agent implementation
    └── schemas.py          # Pydantic schemas
```

## 🔧 Konfigurasi Model

Secara default, agent menggunakan `gemini-2.5-flash`. Anda bisa mengubah model di `src/agent.py`:

```python
# Opsi model yang tersedia:
agent = create_agent(
    model="google_genai:gemini-2.5-flash",      # Default - Fast
    # model="google_genai:gemini-2.5-pro",      # More accurate
    # model="google_genai:gemini-2.0-flash",    # Alternative
    ...
)
```

## 📄 Format Gambar yang Didukung

- JPG / JPEG
- PNG
- WebP
- GIF
- BMP

## ⚠️ Catatan Penting

1. **Kualitas Gambar**: Pastikan foto dokumen jelas dan tidak buram
2. **Pencahayaan**: Hindari foto dengan bayangan atau silau
3. **Orientasi**: Dokumen harus dalam posisi tegak (tidak miring)
4. **Privasi**: Jangan gunakan data KTP asli untuk testing - gunakan data simulasi

## 📝 License

MIT License
