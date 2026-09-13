# -*- coding: utf-8 -*-
"""
Signal Export V2 - TestCase Excel compatibility helper rev03

목적
- TestCase_모음 입력을 XLS / XLSX / XLSM에서 공통 처리한다.
- 파일 확장자만 믿지 않고 실제 파일 signature를 우선 판별한다.
- 확장자와 실제 형식이 다르면 WARN을 남기되 읽을 수 있으면 계속 진행한다.
- OLE2 컨테이너는 우선 xlrd로 실제 XLS 여부를 확인하고, Workbook 스트림이 없으면 Office 권한/보호 문서 가능성을 명확히 안내한다.
- 일반 XLSX/XLSM 계열은 openpyxl을 사용한다.
- pandas object dtype ffill FutureWarning을 피하기 위해 TC 번호/분류 forward-fill을 공통 helper로 처리한다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Optional

OLE_SIGNATURE = bytes.fromhex("D0 CF 11 E0 A1 B1 1A E1")
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def detect_excel_format(path: Path) -> str:
    """Return actual container family: 'ole', 'xlsx', or 'unknown'.

    주의: OLE2 signature 자체는 구형 XLS 전용 signature가 아니다.
    실제 XLS와 Office 권한/보호 문서 등이 모두 OLE2 컨테이너일 수 있다.
    """
    path = Path(path)
    try:
        with path.open("rb") as f:
            head = f.read(8)
    except Exception:
        return "unknown"

    if head.startswith(OLE_SIGNATURE):
        return "ole"
    if any(head.startswith(sig) for sig in ZIP_SIGNATURES):
        return "xlsx"
    return "unknown"


def _extension_family(path: Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".xls":
        return "xls"
    if suffix in {".xlsx", ".xlsm"}:
        return "xlsx"
    return "unknown"


def _require_package(import_name: str, install_name: str, purpose: str) -> None:
    if importlib.util.find_spec(import_name) is None:
        raise ImportError(
            f"{purpose}을(를) 읽으려면 '{install_name}' 패키지가 필요합니다. "
            f"GUI의 '필요 패키지 설치'를 실행하거나 '{install_name}'을 설치하세요."
        )


def resolve_excel_engine(path: Path, *, log: bool = True) -> tuple[str, str]:
    """Return (engine, actual_container). Actual signature wins over suffix."""
    path = Path(path)
    actual = detect_excel_format(path)
    ext_family = _extension_family(path)

    if actual == "xlsx":
        _require_package("openpyxl", "openpyxl", "XLSX/XLSM 형식")
        engine = "openpyxl"
        if log and ext_family == "xls":
            print(
                f"[WARN] TestCase Excel 확장자와 실제 형식이 다릅니다: {path.name} "
                f"| 확장자={path.suffix.lower()} | 실제=XLSX | 실제 형식을 우선 사용합니다."
            )
        if log:
            print(f"[INFO] TestCase Excel reader: {path.name} | format=XLSX | engine={engine}")
        return engine, actual

    if actual == "ole":
        _require_package("xlrd", "xlrd>=2.0.1", "OLE2/XLS 후보 형식")
        engine = "xlrd"
        if log:
            if ext_family == "xlsx":
                print(
                    f"[WARN] TestCase Excel은 .xlsx/.xlsm 확장자이지만 실제 컨테이너가 OLE2입니다: {path.name} "
                    "| 구형 XLS 또는 Office 권한/보호 문서일 수 있어 xlrd로 실제 XLS 여부를 확인합니다."
                )
            print(f"[INFO] TestCase Excel reader: {path.name} | container=OLE2 | engine={engine} (XLS 여부 확인)")
        return engine, actual

    # signature를 모르면 확장자 기반 마지막 fallback
    if ext_family == "xlsx":
        _require_package("openpyxl", "openpyxl", "XLSX/XLSM 형식")
        if log:
            print(f"[WARN] Excel signature를 판별하지 못해 확장자 기준으로 openpyxl을 사용합니다: {path.name}")
        return "openpyxl", "unknown"
    if ext_family == "xls":
        _require_package("xlrd", "xlrd>=2.0.1", "구형 XLS 형식")
        if log:
            print(f"[WARN] Excel signature를 판별하지 못해 확장자 기준으로 xlrd를 사용합니다: {path.name}")
        return "xlrd", "unknown"

    raise ValueError(
        f"지원하지 않거나 판별할 수 없는 Excel 형식입니다: {path.name} "
        f"(확장자={path.suffix or '(없음)'}, signature=unknown)"
    )


def _raise_security_friendly_error(path: Path, exc: Exception) -> None:
    msg = str(exc)
    if "Can't find workbook in OLE2 compound document" not in msg:
        raise exc

    warning = (
        "TestCase Excel이 OLE2 컨테이너이지만 구형 XLS Workbook을 찾지 못했습니다. "
        "Excel 보안/권한 설정 때문에 발생한 문제인지 확인해주세요. "
        "Excel에서 파일 → 정보 → 통합 문서 보호를 확인하고, '사내한(Restricted)'으로 되어 있다면 "
        "해당 문서가 보호 대상이 아닌 경우에만 'Any user' 등 허용된 권한으로 변경한 뒤 저장해 주세요."
    )
    # GUI가 popup을 띄울 수 있도록 고유 marker를 남긴다.
    print(f"[TESTCASE_EXCEL_SECURITY_WARNING] {warning} | 파일={Path(path).name}")
    raise RuntimeError(warning) from exc


def read_excel_compat(path: Path, **kwargs):
    import pandas as pd

    path = Path(path)
    engine, actual = resolve_excel_engine(path, log=True)
    try:
        return pd.read_excel(path, engine=engine, **kwargs)
    except Exception as exc:
        if actual == "ole":
            _raise_security_friendly_error(path, exc)
        raise



def ffill_dataframe_columns_compat(df, start_idx: int, column_indices) -> None:
    """Forward-fill selected DataFrame columns without pandas silent-downcast warnings.

    pandas의 object dtype Series.ffill() 결과를 다시 대입할 때 발생할 수 있는
    FutureWarning을 피하면서 기존 값/빈칸 의미를 그대로 유지한다.
    TC Excel은 수백~수천 행 규모이므로 scalar 순회 비용은 무시 가능한 수준이다.
    """
    import pandas as pd

    start = max(0, int(start_idx or 0))
    ncols = len(df.columns)
    for col_idx in column_indices:
        try:
            col = int(col_idx)
        except Exception:
            continue
        if col < 0 or col >= ncols:
            continue

        has_last = False
        last_value = None
        for row_idx in range(start, len(df)):
            value = df.iat[row_idx, col]
            try:
                is_missing = bool(pd.isna(value))
            except Exception:
                is_missing = value is None

            if is_missing:
                if has_last:
                    df.iat[row_idx, col] = last_value
            else:
                last_value = value
                has_last = True

def excel_file_compat(path: Path, **kwargs):
    import pandas as pd

    path = Path(path)
    engine, actual = resolve_excel_engine(path, log=True)
    try:
        return pd.ExcelFile(path, engine=engine, **kwargs)
    except Exception as exc:
        if actual == "ole":
            _raise_security_friendly_error(path, exc)
        raise


def find_excel_file_compat(base_dir: Path, excel_glob: str, *, required: bool = True) -> Optional[Path]:
    """
    Find the newest TestCase Excel. New config uses *.xls*; old *.xlsx config also
    falls back to .xls/.xlsm so older saved settings do not block compatibility.
    """
    base_dir = Path(base_dir)
    patterns = [str(excel_glob or "TestCase_모음*.xls*")]
    if patterns[0].lower().endswith("*.xlsx") or patterns[0].lower() == "testcase_모음*.xlsx":
        patterns.extend(["TestCase_모음*.xls", "TestCase_모음*.xlsm"])

    found: dict[str, Path] = {}
    for pattern in patterns:
        for p in base_dir.glob(pattern):
            if p.is_file() and p.suffix.lower() in {".xls", ".xlsx", ".xlsm"}:
                found[str(p.resolve()).lower()] = p

    candidates = list(found.values())
    if not candidates:
        if required:
            raise FileNotFoundError(
                f"TestCase Excel을 찾지 못함: {base_dir} / "
                f"지원 형식=.xls,.xlsx,.xlsm / 검색={excel_glob}"
            )
        return None

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if len(candidates) > 1:
        print("[WARN] TestCase Excel이 여러 개 발견되어 최신 수정 파일을 사용합니다:")
        for p in candidates:
            print(f"  - {p.name}")
        print(f"[OK] 선택됨: {candidates[0].name}")
    return candidates[0]
