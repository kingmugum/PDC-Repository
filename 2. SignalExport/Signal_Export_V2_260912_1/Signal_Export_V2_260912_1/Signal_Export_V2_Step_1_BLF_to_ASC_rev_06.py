# -*- coding: utf-8 -*-
"""
Signal_Export_V2_Step_1_BLF_to_ASC_rev_06.py

목적
- base_dir 및 (있으면) 로그파일류 폴더에서 .blf 파일을 .asc 파일로 변환
- 변환이 끝났거나, 변환할 .blf 가 없더라도 대상 폴더들의 .asc 파일명을 자동 정리
- 어떤 prefix(JG1_..., SP3_..., 임의문자열...)든 파일명 내의
  "{카테고리키워드}[_-]{번호...}(설명)" 블록을 찾아 맨 앞으로 이동
- 괄호가 바로 붙는 경우: "시트_35-2(설명)" 또는 "시트-35-2(설명)"
  -> "시트_35-2_(설명)" 로 보정
- 카테고리 뒤 구분자는 결과에서 항상 '_'로 통일 (예: 인포-11-2 -> 인포_11-2)
- [FIX] tail(desc) 파싱을 엄격하게 해서 파일명 깨짐 방지
- [NEW] 카테고리_번호에서 "번호 첫 토큰"을 2자리 zero-pad:
    시트_3      -> 시트_03
    시트_1-1    -> 시트_01-1
    시트_7-2-1  -> 시트_07-2-1
- [NEW] 파일명에 '_(_' 글리치가 있는 경우만 '_(' 로 보정:
    시트_94-2_(_JG1... -> 시트_94-2_(JG1...
    (정상 케이스: 시트_95-1_(2L...) 는 유지)

[ADD PATCH]
- [NEW] 카테고리_번호 뒤에 바로 글자(한글/영문)가 붙으면 '_' 삽입:
    시트_4-2다리받침대하강 -> 시트_04-2_다리받침대하강
    인포_11-2AVN...        -> 인포_11-2_AVN...
  (이미 '_'가 있거나 괄호로 시작하는 경우는 그대로)

[REV 03 변경점]
- 괄호 설명이 실제로 붙은 경우에만 카테고리_번호_(설명) 형식으로 보정
- 카테고리_번호로 끝나는 정상 파일명에 잘못된 "_("가 붙는 오류 수정
- (), [], {} 설명 블록과 파일명 뒤쪽 카테고리 블록 이동을 안정적으로 처리
- "_(_" 글리치를 "_("로 보정하여 여는 괄호를 보존
- ADAS 카테고리 키워드에 "보조"를 추가하여 Main/GUI와 동기화

[REV 04 변경점]
- BLUELINK_CCS 카테고리 파일명 키워드에 "블루", "링크" 추가
- 블루_... / 링크_... 형식의 ASC 파일명 정리와 BLF→ASC 후속 처리를 지원
- 짧은 별칭 "링크"가 하이퍼링크/다운로드링크 등 일반 문자열 내부에서 오인되지 않도록 카테고리 앞 독립 토큰 경계 적용
- 기존 블루링크/BLUELINK/CCS 및 다른 카테고리 파일명 정리 동작은 유지

[REV 05 변경점]
- 물리 CH 토큰을 CAN1~CAN4로 강제 변환하던 설정·helper·전용 실행 함수를 완전히 삭제
- ASC 파일명 정리는 카테고리/번호/괄호/순서 정규화만 수행하며 CH 토큰은 원문 그대로 유지
- Ch3가 CAN1인지 CAN3인지 프로그램이 추정하지 않으며 로그 CAN 매핑은 ASC/BLF 본문 번호와 파일명의 CANx_x-CAN 선언만 사용

[REV 06 변경점]
- 12. Connect UX 사양서 기반 TC 검토 초안(CONNECT) 카테고리 파일명 키워드 추가
- 커넥트 / UX / Connect / connect 카테고리_번호 블록의 ASC 파일명 정리 및 BLF→ASC 후속 처리를 지원
- 기존 1~11 카테고리 키워드 및 CH 토큰 보존 정책은 유지
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
import can


# =========================================================
# 대상 폴더 탐색 (base_dir + log_dir optional)
# =========================================================
def _normalize_folder_name(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", (s or "").strip().lower())


def find_log_dir_optional(base_dir: Path) -> Optional[Path]:
    targets = {
        _normalize_folder_name("log파일"),
        _normalize_folder_name("log file"),
        _normalize_folder_name("로그파일"),
        _normalize_folder_name("로그폴더"),
    }

    for p in base_dir.iterdir():
        if p.is_dir() and _normalize_folder_name(p.name) in targets:
            return p
    return None


def collect_target_dirs(base_dir: Path) -> list[Path]:
    dirs = [base_dir]
    log_dir = find_log_dir_optional(base_dir)
    if log_dir is not None:
        dirs.append(log_dir)
        print(f"[OK] Log directory detected: {log_dir}")
    else:
        print("[WARN] Log directory not found. Using base_dir only.")
    return dirs


# =========================================================
# BLF -> ASC
# =========================================================
def convert_blf_to_asc(input_blf: Path, output_asc: Optional[Path] = None) -> tuple[Path, int]:
    input_blf = Path(input_blf)

    if not input_blf.is_file():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없음: {input_blf}")

    if output_asc is None:
        output_asc = input_blf.with_suffix(".asc")
    else:
        output_asc = Path(output_asc)

    count = 0
    with can.BLFReader(str(input_blf)) as reader:
        with can.ASCWriter(str(output_asc)) as writer:
            for msg in reader:
                writer.on_message_received(msg)
                count += 1

    return output_asc, count


def find_blf_files_in_dirs(dirs: list[Path]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        out += list(Path(d).glob("*.blf"))
    return sorted(out, key=lambda p: (str(p.parent), p.name))


# =========================================================
# ASC Rename
# =========================================================
ASC_EXT = ".asc"
DEFAULT_EXCLUDE_KEYWORDS: list[str] = []

CATEGORIES = {
    "SEAT": {
        "prefix": "1. 시트 및 안전 장치",
        "keywords": ["시트"],
        "include_keywords": ["BDC", "PSS", "PSU", "HU", "H_U_MM_FD", "CTS", "ATS", "SAU", "SHVU"],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "CLUSTER": {
        "prefix": "2. 클러스터",
        "keywords": ["클러스터", "클러"],
        "include_keywords": [
            "ADP", "AMP", "ATCU", "DATC", "GW_BDC_FD", "BLTN_CAM",
            "CLU", "CLU_MM_FD", "EXT_AMP", "HU", "H_U_MM_FD", "HUD",
            "PDC", "PSS", "PSU", "SAU", "SBCM", "SHVU", "SWRC",
            "VPC", "ILCU", "MFSW",
        ],
        "include_message_name_keywords": ["DATC", "PSS", "SBCM", "SWRC", "VPC", "ILCU", "MFSW", "CLU"],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "CONVENIENCE": {
        "prefix": "3. 편의 장치",
        "keywords": ["편의", "편의장치"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "INFOTAINMENT": {
        "prefix": "4. 인포테인먼트",
        "keywords": ["인포", "인포테인먼트"],
        "include_keywords": [
            "ADP", "AMP", "ATCU", "DATC", "GW_BDC_FD", "BLTN_CAM",
            "CLU", "CLU_MM_FD", "EXT_AMP", "HU", "H_U_MM_FD", "HUD",
            "PDC", "PSS", "PSU", "SAU", "SBCM", "SHVU", "SWRC",
            "VPC", "ILCU", "MFSW",
        ],
        "include_message_name_keywords": ["DATC", "PSS", "SBCM", "SWRC", "VPC", "ILCU", "MFSW", "CLU"],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "DRIVE": {
        "prefix": "5. 시동 및 주행",
        "keywords": ["시동", "주행"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "ADAS": {
        "prefix": "6. 운전자 보조",
        "keywords": ["운전자", "운전자보조", "ADAS", "보조"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "BLUELINK_CCS": {
        "prefix": "7. 블루링크, CCS",
        "keywords": ["블루링크", "블루", "링크", "BLUELINK", "CCS"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "EV": {
        "prefix": "8. 환경차",
        "keywords": ["환경차", "EV"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "SCENARIO": {
        "prefix": "9. 시나리오 TC",
        "keywords": ["시나리오", "SCENARIO"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "AVP": {
        "prefix": "10. AVP_과거차문제",
        "keywords": ["AVP", "과거차문제"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "NEWSPEC": {
        "prefix": "11. 신사양 임시 적용 TC",
        "keywords": ["신사양", "임시"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
    "CONNECT": {
        "prefix": "12. Connect UX 사양서 기반 TC 검토 초안",
        "keywords": ["커넥트", "UX", "Connect", "connect"],
        "include_keywords": [],
        "include_message_name_keywords": [],
        "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS,
    },
}


def collect_category_keywords(categories: dict) -> list[str]:
    keywords: list[str] = []
    for category in categories.values():
        for kw in category.get("keywords", []):
            if kw and kw not in keywords:
                keywords.append(kw)
    keywords.sort(key=len, reverse=True)
    return keywords


CATEGORY_KEYWORDS = collect_category_keywords(CATEGORIES)
if not CATEGORY_KEYWORDS:
    raise ValueError("CATEGORIES 내 keywords가 비어 있습니다.")

CATEGORY_KEYWORD_UNION = "|".join(re.escape(k) for k in CATEGORY_KEYWORDS)


def normalize_category_number_anywhere(stem: str) -> str:
    """
    인포_71_1 -> 인포_71-1
    인포-71_1 -> 인포_71-1
    시트-12_2 -> 시트_12-2
    """
    pattern = re.compile(
        rf'(?<![A-Za-z0-9가-힣])(?P<category>{CATEGORY_KEYWORD_UNION})[_-]'
        r'(?P<num1>\d+(?:-\d+)*)_'
        r'(?P<num2>\d+(?:-\d+)*)',
        re.IGNORECASE
    )

    def repl(match: re.Match) -> str:
        category = match.group("category")
        num1 = match.group("num1")
        num2 = match.group("num2")
        return f"{category}_{num1}-{num2}"

    prev = None
    current = stem
    while prev != current:
        prev = current
        current = pattern.sub(repl, current)

    return current


def fix_category_num_paren_anywhere(stem: str) -> str:
    """
    카테고리_번호 바로 뒤에 괄호 설명이 붙은 경우에만 '_'를 삽입한다.

    예)
      시트_35-2(설명) -> 시트_35-2_(설명)
      시트-35-2[설명] -> 시트_35-2_[설명]
      클러-31{설명}   -> 클러_31_{설명}

    카테고리_번호로 끝나는 정상 파일명은 변경하지 않는다.
    """
    pattern = re.compile(
        rf'(?<![A-Za-z0-9가-힣])(?P<category>{CATEGORY_KEYWORD_UNION})[_-]'
        rf'(?P<num>\d+(?:-\d+)*)'
        rf'(?P<open>[\(\[\{{])',
        re.IGNORECASE,
    )

    def repl(m: re.Match) -> str:
        return f'{m.group("category")}_{m.group("num")}_{m.group("open")}'

    return pattern.sub(repl, stem)


# -------------------------
# [NEW] '_(_' 글리치 보정
# -------------------------
def fix_paren_underscore_glitch_anywhere(stem: str) -> str:
    """
    파일명에 '_(_' 글리치가 있는 경우 '_('로 보정하여 여는 괄호를 보존.

    예)
      시트_94-2_(_JG1... -> 시트_94-2_(JG1...
    정상 케이스:
      시트_95-1_(2L ...) -> 변경 없음
    """
    return stem.replace("_(_", "_(")


def reorder_last_category_block_to_front(filename: str) -> str | None:
    """
    파일명에서 마지막 카테고리_번호 블록을 찾아 맨 앞으로 이동한다.

    예)
      SP3_xxx_인포_67-1.asc
        -> 인포_67-1_SP3_xxx.asc
      SP3_xxx_인포_67-1_(설명).asc
        -> 인포_67-1_(설명)_SP3_xxx.asc

    번호 뒤 설명/차종 문자열은 카테고리 블록의 일부로 보존한다.
    이미 카테고리 블록이 선두에 있으면 변경하지 않는다.
    """
    p = Path(filename)
    if p.suffix.lower() != ASC_EXT:
        return None

    stem = p.stem
    pattern = re.compile(
        rf'(?<![A-Za-z0-9가-힣])(?P<category>{CATEGORY_KEYWORD_UNION})[_-]'
        rf'(?P<num>\d+(?:-\d+)*)',
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(stem))
    if not matches:
        return None

    m = matches[-1]
    head = stem[:m.start()].rstrip('_- ')
    category = m.group('category')
    num = m.group('num')
    tail = stem[m.end():]

    front = f'{category}_{num}{tail}'.strip('_')
    new_stem = f'{front}_{head}'.strip('_') if head else front
    new_name = new_stem + p.suffix
    return None if new_name == p.name else new_name


# -------------------------
# [NEW] 번호 첫 토큰 2자리 패딩
# -------------------------
def _pad_first_num_token(num: str) -> str:
    """
    "3" -> "03"
    "1-1" -> "01-1"
    "7-2-1" -> "07-2-1"
    "12-1" -> "12-1"
    """
    s = (num or "").strip()
    m = re.fullmatch(r"(\d+)(.*)", s)
    if not m:
        return s
    first = m.group(1)
    rest = m.group(2)
    return first.zfill(2) + rest


def pad_category_number_first_token_anywhere(stem: str) -> str:
    """
    stem 어디에 있든:
      시트_3 -> 시트_03
      시트-3 -> 시트_03
      시트_1-1 -> 시트_01-1
      인포-7-2-1 -> 인포_07-2-1

    - category 뒤 구분자 '_'/'-' 허용
    - 결과는 category_ 로 통일
    """
    pattern = re.compile(
        rf'(?<![A-Za-z0-9가-힣])(?P<category>{CATEGORY_KEYWORD_UNION})(?P<sep>[_-])(?P<num>\d+(?:-\d+)*)',
        re.IGNORECASE
    )

    def repl(m: re.Match) -> str:
        category = m.group("category")
        num = m.group("num")
        return f"{category}_{_pad_first_num_token(num)}"

    prev = None
    current = stem
    while prev != current:
        prev = current
        current = pattern.sub(repl, current)

    return current


# -------------------------
# [ADD PATCH] 번호 뒤에 바로 글자 붙는 경우 '_' 삽입
# -------------------------
def insert_underscore_after_category_number_when_stuck_anywhere(stem: str) -> str:
    """
    예)
      시트_04-2다리받침대하강 -> 시트_04-2_다리받침대하강
      인포_11-2AVN...        -> 인포_11-2_AVN...
    - 이미 언더스코어/하이픈/공백/괄호 등이 있으면 건드리지 않음
    - '글자'는 한글/영문으로 제한 (과도한 변경 방지)
    """
    pattern = re.compile(
        rf'(?<![A-Za-z0-9가-힣])(?P<category>{CATEGORY_KEYWORD_UNION})_(?P<num>\d+(?:-\d+)*)'
        rf'(?P<next>[A-Za-z가-힣])',
        re.IGNORECASE
    )

    def repl(m: re.Match) -> str:
        return f'{m.group("category")}_{m.group("num")}_{m.group("next")}'

    prev = None
    cur = stem
    while prev != cur:
        prev = cur
        cur = pattern.sub(repl, cur)

    return cur




def propose_new_name(filename: str) -> str | None:
    p = Path(filename)
    if p.suffix.lower() != ASC_EXT:
        return None

    original_stem = p.stem

    working_stem = original_stem

    # 0) 숫자부 통일(71_1 -> 71-1)
    working_stem = normalize_category_number_anywhere(working_stem)

    # 1) 괄호 앞 '_' 보정
    working_stem = fix_category_num_paren_anywhere(working_stem)

    # 1-1) '_(_' 글리치 보정
    working_stem = fix_paren_underscore_glitch_anywhere(working_stem)

    # 2) 번호 첫 토큰 2자리 패딩 + category 구분자 '_' 통일
    working_stem = pad_category_number_first_token_anywhere(working_stem)

    # 3) 번호 뒤 글자 붙음 방지: 4-2다리 -> 04-2_다리
    working_stem = insert_underscore_after_category_number_when_stuck_anywhere(working_stem)

    # 4) 마지막 카테고리 블록을 앞으로 이동
    reordered = reorder_last_category_block_to_front(working_stem + p.suffix)
    if reordered:
        working_stem2 = Path(reordered).stem
    else:
        working_stem2 = working_stem

    if working_stem2 == original_stem:
        return None

    return working_stem2 + p.suffix


def find_asc_files_in_dirs(dirs: list[Path]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        out += [p for p in Path(d).iterdir() if p.is_file() and p.suffix.lower() == ASC_EXT]
    return sorted(out, key=lambda p: (str(p.parent), p.name))


def rename_asc_files_in_dirs(dirs: list[Path]) -> tuple[int, int, int]:
    asc_files = find_asc_files_in_dirs(dirs)

    if not asc_files:
        print(f"[INFO] 처리할 .asc 파일이 없습니다: {[str(d) for d in dirs]}")
        return 0, 0, 0

    changes: list[tuple[Path, Path]] = []
    skipped_collision = 0
    unchanged = 0

    for old_path in asc_files:
        new_name = propose_new_name(old_path.name)
        if not new_name:
            unchanged += 1
            continue

        new_path = old_path.with_name(new_name)

        if new_path.exists() and new_path.resolve() != old_path.resolve():
            print(f"[SKIP: 충돌] {old_path} -> {new_path.name} (이미 존재)")
            skipped_collision += 1
            continue

        changes.append((old_path, new_path))

    if not changes and skipped_collision == 0:
        print("[INFO] 변경 대상 ASC 파일이 없습니다(이미 정리됨 / 패턴 불일치 / 파싱 실패).")
        return 0, 0, unchanged

    renamed_count = 0
    for old_path, new_path in changes:
        old_path.rename(new_path)
        print(f"[OK ] {old_path} -> {new_path}")
        renamed_count += 1

    return renamed_count, skipped_collision, unchanged




# =========================================================
# Combined Run
# =========================================================
def run(config) -> None:
    base_dir = Path(config.base_dir)
    target_dirs = collect_target_dirs(base_dir)

    # 1) BLF -> ASC
    blf_files = find_blf_files_in_dirs(target_dirs)

    total_files = 0
    total_msgs = 0
    failed_files: list[str] = []

    if not blf_files:
        print(f"[INFO] 변환할 .blf 파일이 없습니다: {[str(d) for d in target_dirs]}")
    else:
        print(f"[OK] Found {len(blf_files)} BLF files (merged targets)")

        for idx, input_blf in enumerate(blf_files, 1):
            print(f"\n[{idx}/{len(blf_files)}] Processing: {input_blf}")

            try:
                output_file, msg_count = convert_blf_to_asc(input_blf)
                print(f"[OK] 변환 완료: {output_file} (메시지 수: {msg_count})")
                total_files += 1
                total_msgs += msg_count
            except Exception as e:
                failed_files.append(str(input_blf))
                print(f"[FAIL] 오류 발생 ({input_blf}): {e}")

        print("\n" + "=" * 80)
        print("[STEP 1-1 SUMMARY: BLF -> ASC]")
        print(f"대상 BLF 파일 수   : {len(blf_files)}")
        print(f"변환 성공 파일 수 : {total_files}")
        print(f"총 메시지 수 합계 : {total_msgs}")
        print(f"변환 실패 파일 수 : {len(failed_files)}")

        if failed_files:
            print("[FAIL LIST]")
            for name in failed_files:
                print(f" - {name}")

        print("=" * 80)

        if blf_files and total_files == 0:
            raise RuntimeError("BLF -> ASC 변환이 전부 실패함")

    # 2) ASC Rename
    print("\n" + "=" * 80)
    print("[STEP 1-2 START: ASC FILE RENAME]")
    print("=" * 80)

    print("[INFO] ASC 파일명 정리는 카테고리/번호/괄호/순서만 보정하며 CH 토큰은 변경하지 않습니다.")
    renamed_count, skipped_collision, unchanged = rename_asc_files_in_dirs(target_dirs)

    print("\n" + "=" * 80)
    print("[STEP 1-2 SUMMARY: ASC RENAME]")
    print(f"변경 성공 파일 수 : {renamed_count}")
    print(f"충돌로 건너뜀    : {skipped_collision}")
    print(f"변경 불필요 파일 : {unchanged}")
    print("=" * 80)



def _load_latest_v2_main_module():
    """같은 폴더의 Signal_Export_V2_Main_rev_xx.py 중 가장 높은 rev를 로드한다."""
    import importlib.util
    import re as _re
    import sys as _sys
    code_dir = Path(__file__).resolve().parent
    base = "Signal_Export_V2_Main"
    rx = _re.compile(rf"^{_re.escape(base)}(?:[_\-.])rev(?:[_\-.])?(\d+)\.py$", _re.IGNORECASE)
    best = None
    for path in code_dir.glob(f"{base}*.py"):
        m = rx.match(path.name)
        if not m:
            continue
        rev = int(m.group(1))
        if best is None or rev > best[0]:
            best = (rev, path)
    selected = best[1] if best else code_dir / f"{base}.py"
    if not selected.is_file():
        raise FileNotFoundError(f"{base}_rev_xx.py를 찾지 못했습니다: {code_dir}")
    module_name = f"_dyn_{base}_{selected.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(selected))
    if spec is None or spec.loader is None:
        raise ImportError(f"Main 모듈 spec 생성 실패: {selected}")
    module = importlib.util.module_from_spec(spec)
    _sys.modules[module_name] = module
    spec.loader.exec_module(module)
    print(f"[INFO] Selected latest V2 Main: {selected.name}")
    return module


def main() -> None:
    main_module = _load_latest_v2_main_module()
    run(main_module.build_config())


if __name__ == "__main__":
    main()
