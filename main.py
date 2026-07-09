"""
Document Extractor Vision Agent - Main Entry Point

Contoh penggunaan:
    python main.py path/to/ktp_photo.jpg
    python main.py test_images/sample_ktp.png
"""

import os
import sys
import json
from pathlib import Path

# Fix encoding untuk Windows
sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Validate API key
if not os.getenv("GOOGLE_API_KEY"):
    print("[ERROR] GOOGLE_API_KEY tidak ditemukan!")
    print("   Silakan set GOOGLE_API_KEY di file .env")
    print("   Contoh: GOOGLE_API_KEY=your-api-key-here")
    sys.exit(1)

from src.langfuse_tracing import init_tracing, get_handler, flush_traces

init_tracing()
handler = get_handler()

from src.agent import extract_document_data


def main():
    """Main function untuk menjalankan Document Extractor."""
    
    # Check command line arguments
    if len(sys.argv) < 2:
        print("=" * 60)
        print("[DOC] Document Extractor Vision Agent")
        print("=" * 60)
        print("\nPenggunaan:")
        print("  python main.py <path_to_image>")
        print("\nContoh:")
        print("  python main.py ktp_photo.jpg")
        print("  python main.py test_images/sample_ktp.png")
        print("\nFormat gambar yang didukung:")
        print("  JPG, JPEG, PNG, WebP, GIF, BMP")
        print("=" * 60)
        return
    
    image_path = sys.argv[1]
    
    # Validate file exists
    if not Path(image_path).exists():
        print(f"[ERROR] File tidak ditemukan: {image_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("[DOC] Document Extractor Vision Agent")
    print("=" * 60)
    print(f"\n[SCAN] Menganalisis: {image_path}")
    print("   Mohon tunggu...\n")
    
    try:
        # Extract document data
        result = extract_document_data(image_path, callbacks=[handler])
        
        # Display results
        print("[OK] Ekstraksi berhasil!\n")
        print("-" * 60)
        print("[RESULT] HASIL EKSTRAKSI:")
        print("-" * 60)
        
        # Pretty print key information
        print(f"\n  [TYPE] Jenis Dokumen : {result['jenis_dokumen']}")
        print(f"  [NAME] Nama          : {result['nama']}")
        print(f"  [NIK]  NIK           : {result['nik']}")
        print(f"  [DOB]  Tanggal Lahir : {result['tanggal_lahir']}")
        
        if result.get('tempat_lahir'):
            print(f"  [POB]  Tempat Lahir  : {result['tempat_lahir']}")
        
        if result.get('jenis_kelamin'):
            print(f"  [SEX]  Jenis Kelamin : {result['jenis_kelamin']}")
        
        if result.get('alamat'):
            print(f"  [ADDR] Alamat        : {result['alamat']}")
        
        print(f"  [EXP]  Kadaluarsa    : {result['tanggal_kadaluarsa']}")
        print(f"  [CONF] Confidence    : {result['confidence'] * 100:.1f}%")
        
        if result.get('catatan'):
            print(f"\n  [NOTE] Catatan: {result['catatan']}")
        
        # Print full JSON
        print("\n" + "-" * 60)
        print("[JSON] OUTPUT:")
        print("-" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 60)
        
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error tidak terduga: {e}")
        print("\nPastikan:")
        print("  1. GOOGLE_API_KEY sudah benar di file .env")
        print("  2. Gambar adalah dokumen identitas yang valid")
        print("  3. Koneksi internet stabil")
        sys.exit(1)


if __name__ == "__main__":
    main()
    flush_traces()
