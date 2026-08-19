BoardRepo 회사 PC용 오프라인 패키지 폴더
=======================================

이 폴더는 기본 배포본에서는 제3자 wheel 바이너리를 포함하지 않습니다.
인터넷이 가능한 Windows 64-bit PC에서 BoardRepo 탭의
[회사용 오프라인 준비] 버튼을 한 번 실행하면 자동으로 채워집니다.

준비 결과
---------
1) windows_x64/
   - CPython 3.10~3.14용 Windows x64 wheel 파일
   - 회사 PC에서는 pip가 가능할 경우 --no-index / --find-links로만 설치

2) vendor/
   - 준비를 실행한 PC의 현재 Python 버전/64-bit와 동일한 회사 PC에서
     pip 없이도 사용할 수 있는 Portable Vendor Runtime
   - vendor_manifest.json으로 Python 버전/비트수 호환성을 확인

중요
----
- `playwright install chromium`은 회사 안전 모드에서 자동 실행하지 않습니다.
- 기존 Playwright Chromium이 이미 있으면 계속 1순위로 사용합니다.
- Chromium이 없거나 실행 실패하면 설치된 Microsoft Edge로 자동 전환합니다.
- 회사 보안정책이 Edge 자동 제어 자체를 차단하면 우회하지 않고 오류를 표시합니다.
