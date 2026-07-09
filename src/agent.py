"""
Document Extractor Vision Agent menggunakan LangChain dan Gemini.

Agent ini menggunakan Vision Model untuk membaca dan mengekstrak
data dari foto dokumen identitas (KTP, Paspor, SIM).
"""

import base64
from pathlib import Path
from typing import Union

from typing import Any

from langchain.agents import create_agent
from langchain.messages import HumanMessage

from .schemas import DocumentData


# System prompt untuk agent
SYSTEM_PROMPT = """Kamu adalah Document Extractor AI yang ahli dalam membaca dan mengekstrak data dari dokumen identitas Indonesia (KTP, Paspor, dan SIM).

TUGAS UTAMA:
1. Analisis gambar dokumen yang diberikan dengan teliti
2. Identifikasi jenis dokumen (KTP, Paspor, atau SIM)
3. Ekstrak semua informasi yang tersedia:
   - Nama lengkap
   - NIK (Nomor Induk Kependudukan) - 16 digit untuk KTP
   - Tempat dan tanggal lahir
   - Jenis kelamin
   - Alamat (jika ada)
   - Tanggal kadaluarsa dokumen
4. Berikan confidence score berdasarkan kualitas gambar dan kejelasan teks

ATURAN EKSTRAKSI:
- Jika ada data yang tidak terbaca jelas, isi dengan "TIDAK TERBACA"
- Format tanggal HARUS dalam format DD-MM-YYYY
- NIK harus tepat 16 digit. Jika kurang/lebih, tetap tulis apa adanya tapi beri catatan
- Untuk KTP dengan masa berlaku seumur hidup, isi tanggal_kadaluarsa dengan "SEUMUR HIDUP"
- Confidence score:
  - 0.9 - 1.0: Gambar sangat jelas, semua data terbaca sempurna
  - 0.7 - 0.9: Gambar jelas, sebagian besar data terbaca
  - 0.5 - 0.7: Gambar kurang jelas, beberapa data sulit dibaca
  - 0.0 - 0.5: Gambar buram/rusak, banyak data tidak terbaca

CATATAN PENTING:
- Selalu periksa apakah gambar benar-benar dokumen identitas
- Jika gambar bukan dokumen identitas, set jenis_dokumen ke "UNKNOWN" dan confidence ke 0.0
- Berikan catatan jika ada masalah dengan kualitas gambar atau format dokumen"""


def load_image_as_base64(image_path: Union[str, Path]) -> str:
    """
    Load image file dan convert ke base64 string.
    
    Args:
        image_path: Path ke file gambar
        
    Returns:
        str: Base64 encoded string dari gambar
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {image_path}")
    
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path: Union[str, Path]) -> str:
    """
    Dapatkan MIME type dari file gambar berdasarkan ekstensi.
    
    Args:
        image_path: Path ke file gambar
        
    Returns:
        str: MIME type (e.g., "image/jpeg")
    """
    suffix = Path(image_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    return mime_types.get(suffix, "image/jpeg")


def create_document_extractor_agent() -> Any:
    """
    Buat Document Extractor Agent dengan Vision capability.
    
    Agent ini menggunakan Gemini Vision Model untuk membaca
    dokumen identitas dan mengekstrak data ke format terstruktur.
    
    Returns:
        Agent: LangChain agent dengan structured output
    """
    agent = create_agent(
        model="google_genai:gemini-2.5-flash-lite",  # Vision-capable model
        tools=[],  # No tools needed - direct extraction
        system_prompt=SYSTEM_PROMPT,
        response_format=DocumentData,  # Structured output using Pydantic
    )
    
    return agent


def extract_document_data(image_path: Union[str, Path]) -> dict:
    """
    Ekstrak data dari foto dokumen identitas (KTP/Paspor/SIM).
    
    Fungsi ini menerima path ke file gambar, menggunakan Vision Model
    untuk membaca dokumen, dan mengembalikan data terstruktur dalam
    format JSON/dict.
    
    Args:
        image_path: Path ke file gambar (jpg, png, webp)
        
    Returns:
        dict: Data terstruktur hasil ekstraksi dengan format:
            {
                "nama": str,
                "nik": str,
                "tanggal_lahir": str,
                "tempat_lahir": str | None,
                "jenis_kelamin": str | None,
                "alamat": str | None,
                "tanggal_kadaluarsa": str,
                "jenis_dokumen": str,
                "confidence": float,
                "catatan": str | None
            }
    
    Raises:
        FileNotFoundError: Jika file gambar tidak ditemukan
        ValueError: Jika format file tidak didukung
    """
    # Validate file exists
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {image_path}")
    
    # Validate file extension
    valid_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    if path.suffix.lower() not in valid_extensions:
        raise ValueError(
            f"Format file tidak didukung: {path.suffix}. "
            f"Format yang didukung: {', '.join(valid_extensions)}"
        )
    
    # Load and encode image
    image_base64 = load_image_as_base64(path)
    mime_type = get_image_mime_type(path)
    
    # Create agent
    agent = create_document_extractor_agent()
    
    # Create message with image content (using image_url format for Google Genai)
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": "Tolong analisis dan ekstrak semua data dari dokumen identitas pada gambar ini. Berikan hasil dalam format yang terstruktur."
            },
            {
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{image_base64}",
            },
        ]
    )
    
    # Invoke agent
    result = agent.invoke({"messages": [message]})
    
    # Extract structured response
    structured_data: DocumentData = result["structured_response"]
    
    # Convert to dict
    return structured_data.model_dump()


def extract_document_data_from_base64(
    image_base64: str,
    mime_type: str = "image/jpeg"
) -> dict:
    """
    Ekstrak data dari gambar yang sudah di-encode base64.
    
    Berguna untuk integrasi dengan API yang menerima upload
    gambar dalam format base64.
    
    Args:
        image_base64: Base64 encoded string dari gambar
        mime_type: MIME type gambar (default: "image/jpeg")
        
    Returns:
        dict: Data terstruktur hasil ekstraksi
    """
    # Create agent
    agent = create_document_extractor_agent()
    
    # Create message with image content (using image_url format for Google Genai)
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": "Tolong analisis dan ekstrak semua data dari dokumen identitas pada gambar ini. Berikan hasil dalam format yang terstruktur."
            },
            {
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{image_base64}",
            },
        ]
    )
    
    # Invoke agent
    result = agent.invoke({"messages": [message]})
    
    # Extract structured response
    structured_data: DocumentData = result["structured_response"]
    
    return structured_data.model_dump()
