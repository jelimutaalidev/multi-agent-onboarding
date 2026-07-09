import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest

os.environ["GOOGLE_API_KEY"] = "test-mock-key"
os.environ["HUGGINGFACEHUB_API_TOKEN"] = "test-mock-hf-token"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark test as requiring external API (HF Embeddings / Gemini)",
    )


SAMPLE_DOCUMENT = {
    "nama": "BUDI SANTOSO",
    "nik": "3201234567890001",
    "tanggal_lahir": "15-08-1990",
    "tempat_lahir": "JAKARTA",
    "jenis_kelamin": "LAKI-LAKI",
    "alamat": "JL. MERDEKA NO. 123, RT 001/RW 002, KEL. SUKAMAJU",
    "tanggal_kadaluarsa": "SEUMUR HIDUP",
    "jenis_dokumen": "KTP",
    "confidence": 0.95,
    "catatan": None,
}

SAMPLE_VALIDATION_RESULT = {
    "status": "APPROVED",
    "customer_name": "BUDI SANTOSO",
    "account_type": "Futures",
    "customer_age": 35,
    "minimum_age_required": 21,
    "reasons": ["Usia 35 memenuhi syarat minimum 21 tahun untuk akun Futures"],
    "policy_references": ["Kebijakan EXANTE: Minimum 21 tahun untuk Futures trading"],
    "recommendations": None,
}


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    from sqlalchemy import create_engine
    try:
        engine = create_engine(f"sqlite:///{path}")
        engine.dispose()
    except Exception:
        pass
    import gc
    gc.collect()
    for _ in range(3):
        try:
            if path.exists():
                path.unlink()
            break
        except PermissionError:
            import time
            time.sleep(0.1)


@pytest.fixture
def temp_policy_dir(tmp_path: Path) -> Path:
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    policy_file = policy_dir / "test_policy.txt"
    policy_file.write_text(
        "EXANTE Compliance Policy\n"
        "Minimum age for Futures trading: 21 years\n"
        "Minimum age for Crypto trading: 25 years\n"
        "Minimum age for Stocks trading: 18 years\n"
        "All customers must provide valid government-issued ID\n"
        "Margin trading requires minimum 21 years with additional approval\n",
        encoding="utf-8",
    )
    return tmp_path
