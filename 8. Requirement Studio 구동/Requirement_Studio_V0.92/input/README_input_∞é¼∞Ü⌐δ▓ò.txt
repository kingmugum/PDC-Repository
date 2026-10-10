Requirement Studio input 폴더

- PDF / DOCX / PPTX / XLSX / XLSM 문서를 1개 이상 넣을 수 있습니다.
- 여러 문서가 있으면 각 문서를 독립적인 Batch 작업으로 순차 처리합니다.
- 각 문서는 자체 Document IR / AI 요청 / Canonical Requirement 결과를 생성하므로,
  여러 문서를 하나의 거대한 Prompt로 합치지 않습니다.
- 따라서 문서 수가 늘어나면 처리 시간과 AI 호출량은 문서 수/분량에 비례해 증가합니다.
- 서로 다른 문서를 하나의 통합 Spec으로 Cross-reference 하는 Bundle 모드는 현재 버전에 포함하지 않습니다.
- 원본 문서는 수정하지 않습니다.
