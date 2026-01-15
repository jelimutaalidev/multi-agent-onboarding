"""
Validate - CLI untuk validasi nasabah end-to-end.

Menggabungkan Document Extractor + Policy Validator + PII Guardian untuk
workflow validasi nasabah lengkap dengan proteksi data.

Contoh penggunaan:
    python validate.py test_images/sample_ktp.png --account-type Futures
    python validate.py test_images/sample_ktp.png --account-type Stocks --save
"""

import os
import sys
import json
import argparse
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
    sys.exit(1)

from src.agent import extract_document_data
from src.policy_validator import validate_customer_from_document_data
from src.pii_guardian import (
    mask_dict, 
    get_pii_report, 
    process_and_save_customer,
    MaskingStrategy
)


def main():
    """Main function untuk validasi nasabah."""
    
    parser = argparse.ArgumentParser(
        description="Validasi nasabah untuk pembukaan akun trading"
    )
    parser.add_argument(
        "image_path",
        help="Path ke foto dokumen identitas (KTP/Paspor)"
    )
    parser.add_argument(
        "--account-type", "-a",
        required=True,
        choices=["Stocks", "ETF", "Futures", "Options", "Margin", "Forex", "Crypto"],
        help="Jenis akun yang ingin dibuka"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="Simpan data ke database simulasi (dengan PII masking)"
    )
    parser.add_argument(
        "--show-pii-report",
        action="store_true",
        help="Tampilkan laporan PII yang terdeteksi"
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    if not Path(args.image_path).exists():
        print(f"[ERROR] File tidak ditemukan: {args.image_path}")
        sys.exit(1)
    
    print("=" * 70)
    print("[ONBOARDING] Customer Onboarding Validation System")
    print("=" * 70)
    
    # Step 1: Extract document data
    print(f"\n[STEP 1] Ekstraksi Data Dokumen")
    print("-" * 70)
    print(f"   File: {args.image_path}")
    print("   Menganalisis dokumen dengan Vision AI...")
    
    try:
        document_data = extract_document_data(args.image_path)
        
        print("\n   [OK] Data berhasil diekstrak:")
        print(f"   - Nama          : {document_data['nama']}")
        print(f"   - NIK           : {document_data['nik']}")
        print(f"   - Tanggal Lahir : {document_data['tanggal_lahir']}")
        print(f"   - Jenis Dokumen : {document_data['jenis_dokumen']}")
        print(f"   - Kadaluarsa    : {document_data['tanggal_kadaluarsa']}")
        print(f"   - Confidence    : {document_data['confidence'] * 100:.1f}%")
        
    except Exception as e:
        print(f"\n   [ERROR] Gagal ekstrak dokumen: {e}")
        sys.exit(1)
    
    # Step 2: Validate against policy
    print(f"\n[STEP 2] Validasi Kebijakan")
    print("-" * 70)
    print(f"   Jenis Akun: {args.account_type}")
    print("   Memeriksa kebijakan perusahaan dengan RAG...")
    
    try:
        validation_result = validate_customer_from_document_data(
            document_data, 
            args.account_type
        )
        
        # Display validation result
        status = validation_result['status']
        status_icon = {
            "APPROVED": "[APPROVED]",
            "REJECTED": "[REJECTED]", 
            "PENDING_REVIEW": "[PENDING]"
        }.get(status, "[UNKNOWN]")
        
        print(f"\n[STEP 3] Hasil Validasi")
        print("=" * 70)
        
        # Status with color indication
        if status == "APPROVED":
            print(f"\n   {status_icon} APLIKASI DISETUJUI")
        elif status == "REJECTED":
            print(f"\n   {status_icon} APLIKASI DITOLAK")
        else:
            print(f"\n   {status_icon} MEMERLUKAN REVIEW MANUAL")
        
        print(f"\n   Nama Nasabah    : {validation_result['customer_name']}")
        print(f"   Jenis Akun      : {validation_result['account_type']}")
        print(f"   Usia Nasabah    : {validation_result['customer_age']} tahun")
        print(f"   Usia Minimum    : {validation_result['minimum_age_required']} tahun")
        
        # Reasons
        print(f"\n   Alasan Keputusan:")
        for reason in validation_result['reasons']:
            print(f"   - {reason}")
        
        # Policy references
        if validation_result['policy_references']:
            print(f"\n   Referensi Kebijakan:")
            for ref in validation_result['policy_references']:
                # Truncate long references
                ref_display = ref[:100] + "..." if len(ref) > 100 else ref
                print(f"   - {ref_display}")
        
        # Recommendations (if rejected)
        if validation_result.get('recommendations'):
            print(f"\n   Rekomendasi:")
            for rec in validation_result['recommendations']:
                print(f"   - {rec}")
        
    except Exception as e:
        print(f"\n   [ERROR] Gagal validasi: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 4: PII Guardian - Data Protection
    print(f"\n[STEP 4] PII Guardian - Proteksi Data")
    print("-" * 70)
    
    # Get PII report
    pii_report = get_pii_report(document_data)
    print(f"   [SCAN] Terdeteksi {pii_report['total_pii_found']} data sensitif:")
    for pii_type in pii_report['pii_types']:
        print(f"   - {pii_type.upper()}")
    
    # Show masked preview
    print(f"\n   [MASK] Data setelah masking:")
    masked_data = pii_report['masked_data']
    print(f"   - Nama (masked) : {masked_data.get('nama', 'N/A')}")
    print(f"   - NIK (masked)  : {masked_data.get('nik', 'N/A')}")
    
    # Show full PII report if requested
    if args.show_pii_report:
        print("\n" + "-" * 70)
        print("[PII REPORT] Laporan Lengkap:")
        print("-" * 70)
        print(json.dumps(pii_report, indent=2, ensure_ascii=False, default=str))
    
    # Step 5: Save to database (optional)
    if args.save:
        print(f"\n[STEP 5] Menyimpan ke Database")
        print("-" * 70)
        print("   [DB] Menyimpan dengan PII masking...")
        
        try:
            record = process_and_save_customer(document_data, validation_result)
            print(f"   [OK] Data tersimpan!")
            print(f"   - Customer ID  : {record['customer_id']}")
            print(f"   - PII Masked   : {record['pii_masked']}")
            print(f"   - Fields Masked: {record['pii_fields_count']}")
        except Exception as e:
            print(f"   [ERROR] Gagal simpan: {e}")
    
    # Full JSON output
    print("\n" + "=" * 70)
    print("[JSON] Validation Result:")
    print("=" * 70)
    print(json.dumps(validation_result, indent=2, ensure_ascii=False))
    print("=" * 70)


if __name__ == "__main__":
    main()
