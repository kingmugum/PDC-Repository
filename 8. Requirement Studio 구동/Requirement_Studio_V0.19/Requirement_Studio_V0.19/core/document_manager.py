from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xlsm",
}


@dataclass
class DocumentLookupResult:
    document: Optional[Path] = None
    error: Optional[str] = None


class DocumentManager:
    def __init__(self, input_dir: Path):
        self.input_dir = Path(input_dir).resolve()
        self.ensure_input_dir()

    def ensure_input_dir(self):
        self.input_dir.mkdir(parents=True, exist_ok=True)

    def list_documents(self):
        return sorted(
            [
                path
                for path in self.input_dir.iterdir()
                if path.is_file()
                and not path.name.startswith(".")
                and not path.name.startswith("~$")
                and path.suffix.lower() in SUPPORTED_EXTENSIONS
            ],
            key=lambda p: p.name.lower(),
        )

    def get_single_document(self) -> DocumentLookupResult:
        documents = self.list_documents()

        if len(documents) == 0:
            return DocumentLookupResult(
                error="지원 문서가 0개입니다. sample_inputs에서 샘플 1개를 input 폴더로 복사해주세요."
            )

        if len(documents) > 1:
            return DocumentLookupResult(
                error=f"지원 문서가 {len(documents)}개입니다. 현재는 input 폴더의 문서 1개만 분석할 수 있습니다."
            )

        return DocumentLookupResult(document=documents[0])

    @staticmethod
    def format_size(size_bytes: int) -> str:
        size = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size_bytes} B"
