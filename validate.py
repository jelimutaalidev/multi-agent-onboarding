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

sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    print("[ERROR] GOOGLE_API_KEY tidak ditemukan!")
    print("   Silakan set GOOGLE_API_KEY di file .env")
    sys.exit(1)

from src.langfuse_tracing import init_tracing, flush_traces, pipeline_span
from src.graph import run_pipeline
from src.schemas import RoutingDecision

init_tracing()


def main():
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

    if not Path(args.image_path).exists():
        print(f"[ERROR] File tidak ditemukan: {args.image_path}")
        sys.exit(1)

    print("=" * 70)
    print("[ONBOARDING] Customer Onboarding Validation System")
    print("=" * 70)

    with pipeline_span("onboarding-pipeline", account_type=args.account_type) as handler:
        try:
            report = run_pipeline(args.image_path, args.account_type, callbacks=[handler])
        except Exception as e:
            print(f"\n   [ERROR] Pipeline gagal: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    extraction = report.get("extraction") or {}
    validation = report.get("validation") or {}
    pii = report.get("pii_report") or {}
    saved = report.get("saved_record")
    pipeline_error = report.get("error")

    if pipeline_error:
        print(f"\n[REJECTED] {pipeline_error}")
        sys.exit(1)

    print(f"\n[STEP 1] Ekstraksi Data Dokumen")
    print("-" * 70)
    print(f"   File: {args.image_path}")
    print("\n   [OK] Data berhasil diekstrak:")
    print(f"   - Nama          : {extraction.get('nama', 'N/A')}")
    print(f"   - NIK           : {extraction.get('nik', 'N/A')}")
    print(f"   - Tanggal Lahir : {extraction.get('tanggal_lahir', 'N/A')}")
    print(f"   - Jenis Dokumen : {extraction.get('jenis_dokumen', 'N/A')}")
    print(f"   - Kadaluarsa    : {extraction.get('tanggal_kadaluarsa', 'N/A')}")
    print(f"   - Confidence    : {extraction.get('confidence', 0) * 100:.1f}%")

    routing_decision = RoutingDecision.PROCEED
    if args.account_type:
        from src.schemas import make_routing_decision
        routing_decision = make_routing_decision(extraction.get("confidence", 0.0))

    if routing_decision == RoutingDecision.PENDING_REVIEW:
        print(f"\n   [REVIEW] Kualitas dokumen perlu diperiksa (confidence: {extraction.get('confidence', 0):.1%})")
        print("   Data akan diverifikasi manual oleh tim operasional.")

    print(f"\n[STEP 2] Validasi Kebijakan")
    print("-" * 70)
    print(f"   Jenis Akun: {args.account_type}")

    status = validation.get('status', 'UNKNOWN')
    status_icon = {
        "APPROVED": "[APPROVED]",
        "REJECTED": "[REJECTED]",
        "PENDING_REVIEW": "[PENDING]",
    }.get(status, "[UNKNOWN]")

    print(f"\n[STEP 3] Hasil Validasi")
    print("=" * 70)

    if status == "APPROVED":
        print(f"\n   {status_icon} APLIKASI DISETUJUI")
    elif status == "REJECTED":
        print(f"\n   {status_icon} APLIKASI DITOLAK")
    else:
        print(f"\n   {status_icon} MEMERLUKAN REVIEW MANUAL")

    print(f"\n   Nama Nasabah    : {validation.get('customer_name', 'N/A')}")
    print(f"   Jenis Akun      : {validation.get('account_type', 'N/A')}")
    print(f"   Usia Nasabah    : {validation.get('customer_age', 'N/A')} tahun")
    print(f"   Usia Minimum    : {validation.get('minimum_age_required', 'N/A')} tahun")

    reasons = validation.get('reasons', [])
    if reasons:
        print(f"\n   Alasan Keputusan:")
        for reason in reasons:
            print(f"   - {reason}")

    policy_refs = validation.get('policy_references', [])
    if policy_refs:
        print(f"\n   Referensi Kebijakan:")
        for ref in policy_refs:
            ref_display = ref[:100] + "..." if len(ref) > 100 else ref
            print(f"   - {ref_display}")

    recommendations = validation.get('recommendations')
    if recommendations:
        print(f"\n   Rekomendasi:")
        for rec in recommendations:
            print(f"   - {rec}")

    print(f"\n[STEP 4] PII Guardian - Proteksi Data")
    print("-" * 70)

    print(f"   [SCAN] Terdeteksi {pii.get('total_pii_found', 0)} data sensitif:")
    for pii_type in pii.get('pii_types', []):
        print(f"   - {pii_type.upper()}")

    masked_data = pii.get('masked_data', {})
    print(f"\n   [MASK] Data setelah masking:")
    print(f"   - Nama (masked) : {masked_data.get('nama', 'N/A')}")
    print(f"   - NIK (masked)  : {masked_data.get('nik', 'N/A')}")

    if args.show_pii_report:
        print("\n" + "-" * 70)
        print("[PII REPORT] Laporan Lengkap:")
        print("-" * 70)
        print(json.dumps(pii, indent=2, ensure_ascii=False, default=str))

    if args.save:
        print(f"\n[STEP 5] Menyimpan ke Database")
        print("-" * 70)
        if saved:
            print(f"   [OK] Data tersimpan!")
            print(f"   - Customer ID  : {saved.get('customer_id', 'N/A')}")
            print(f"   - PII Masked   : {saved.get('pii_masked', False)}")
            print(f"   - Fields Masked: {saved.get('pii_fields_count', 0)}")
        else:
            print(f"   [ERROR] Gagal simpan: tidak ada data record")

    print("\n" + "=" * 70)
    print("[JSON] Validation Result:")
    print("=" * 70)
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    print("=" * 70)


if __name__ == "__main__":
    main()
    flush_traces()
