# ALIRA Vision Probe (Detachable)

이 폴더는 Requirement Studio 본체와 **완전히 분리된 진단 모듈**입니다.
본체는 이 폴더를 import하지 않습니다. 필요 없으면 `diagnostics/ALIRA_Vision_Probe` 폴더를 통째로 삭제해도 Requirement Studio 실행에 영향이 없습니다.

## 가장 빠른 확인 방법
Windows에서 이 폴더의 **`RUN_ALIRA_VISION_PROBE.cmd`** 를 실행합니다.

이 Quick Test는 다음을 한 번에 수행합니다.

1. ALIRA/Qwen 설정 및 `alira.exe --help` 확인
2. 이미지에만 답이 존재하는 `probe_fixture.png` 생성
3. 현재 `config/provider_config.json`의 ALIRA `api_base` / `model`을 사용하여 **이미지를 내부 API에 직접 전달**
4. 응답을 화면에 출력

내부 API가 API Key를 요구한다면 실행 전 CMD에서 다음처럼 환경변수만 설정합니다.

```bat
set ALIRA_VISION_PROBE_API_KEY=실제_KEY
RUN_ALIRA_VISION_PROBE.cmd
```

Key는 파일/config에 저장하지 않습니다.

## PASS 판정
Fixture의 정답은 다음과 같습니다.

- code = `R7K-42`
- arrow_color = `green`
- arrow_direction = `STATE_A -> STATE_B`
- Timeout = `3.7 s`
- star_position = `STATE_B` 오른쪽
- Mode = `VISION_ONLY`

`[DIRECT API RESPONSE]`가 위 정보를 이미지로부터 정확히 읽으면 **ALIRA/Qwen API 수준에서 Native Vision 가능성이 확인**됩니다.

- Direct API 실패 → 현재 Model 또는 API가 image payload를 받지 못할 가능성이 큼
- Direct API 성공 → Model/API Vision은 가능. 다음은 ALIRA CLI 전달 계층 확인

> 이 Quick Test는 Requirement Studio 본체의 H-Chat Vision fallback과 무관합니다. 즉 `Main=ALIRA / Vision=H-Chat GPT (Fallback)` 로그를 시험하는 것이 아니라 ALIRA/Qwen API 자체에 이미지를 직접 보내는 테스트입니다.

## 단계별 수동 실행

환경/CLI와 Fixture만 확인:

```bat
python alira_vision_probe.py --inspect --make-fixture
```

Direct API Vision 시험:

```bat
python alira_vision_probe.py --api-image
```

CLI 이미지 인자가 실제 `alira.exe --help` 또는 담당부서 문서로 확인된 후에만:

```bat
python alira_vision_probe.py --cli-image --cli-image-arg=--image
```

`--image`는 예시입니다. 확인되지 않은 인자를 임의로 사용하지 마세요.

## 본체 Capability 전환
Probe 결과를 사람이 확인한 뒤 명시적으로 실행합니다.

```bat
python alira_vision_probe.py --set-capability=true
```

롤백:

```bat
python alira_vision_probe.py --set-capability=false
```

V0.40 본체의 ALIRA Native Vision은 이 Direct API Probe 경로를 사용하지 않습니다. 별도 ALIRA Vision Verifier V0.3에서 실제 통과한 CLI/general_agent + Image Tool 경로를 사용하며 기본값은 `supports_images=true`입니다. 문제가 있으면 `false`로 즉시 롤백할 수 있습니다.


## V0.40 note
Requirement Studio V0.40 production Native Vision no longer depends on this Probe's Direct API image route. The validated production path is ALIRA CLI/general_agent + Image Tool, confirmed separately with ALIRA Vision Verifier V0.3. This diagnostics folder remains detachable and may still be used for gateway/CLI exploration.
