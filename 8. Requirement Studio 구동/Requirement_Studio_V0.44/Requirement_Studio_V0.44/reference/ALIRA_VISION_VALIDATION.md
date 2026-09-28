# ALIRA Vision Validation — V0.41 Current Status

Date: 2026-09-27

## Scope

This note records the runtime evidence used to promote ALIRA image capability from an unverified capability flag to the V0.40 native Vision path.

## User runtime evidence

The independent `ALIRA Vision Verifier V0.3` was executed in the user's corporate Windows/ALIRA environment.

Observed outcome:

- Control without image: randomized fixture answers were not recovered (`UNKNOWN`).
- ALIRA CLI / `general_agent` Image Tool path: randomized image-only facts matched **6/6**.
- The previously attempted Direct API diagnostic returned HTTP 404 for the assumed `/chat/completions` route.
- The earlier V0.2 permission failure was resolved by allowing headless Image Tool execution for the isolated verifier run.

Interpretation:

- The validated image path is **ALIRA CLI / general_agent + EncodeImage or equivalent Image Tool**.
- The result is evidence for ALIRA's image-reading capability and for the CLI Image Tool transport.
- It is not evidence that the guessed Qwen Direct API route is supported.

## V0.40 product decision

Requirement Studio V0.40 therefore uses:

- `alira.supports_images = true`
- `alira.vision_transport = "cli_image_tool"`
- per-request image staging under `work/alira_vision_runtime/<run>`
- isolated `--cwd` pointing to that staging folder
- `--no-permission-enabled` only for the native Vision subprocess call
- normal per-image failure isolation in `AIJobRunner`

The product path does **not** use the guessed Direct API image endpoint.

## Verification boundary

Still requires user-environment End-to-End verification:

1. Select ALIRA in Requirement Studio V0.40.
2. Run a document containing embedded images.
3. Confirm STEP 3 logs show `Vision=ALIRA ... (Native)`.
4. Confirm `Visual Evidence N개 준비` where N > 0.
5. Review `work/normalized/.../visual_evidence.json` and final SWE.1/SWE.6 outputs for image-derived facts.

## Product End-to-End evidence (user V0.40 run)

The user executed Requirement Studio V0.40 with `sample_vcu_lite_visual_diagram.docx` and supplied the generated Analysis, SWE.1 Word, SWE.1 Excel and SWE.6 Excel outputs.

Observed propagation:

- Analysis recognized image structure and image-only facts such as state-info storage, Wake-up/Normal restore, communication reactivation detection and state-info resend.
- SWE.1 Traceability contains `VISUAL IMG-001` evidence.
- Image-derived requirements became SRS_003 and SRS_004.
- The corresponding SWE.6 cases TC_003 and TC_004 were generated.

Interpretation: ALIRA Native Vision is now verified not only at Verifier capability level but also through the Requirement Studio product pipeline from Visual Evidence to final SRS/TC outputs.

Remaining V0.41 verification boundary: only the new AI Action Stack position requires final Windows visual confirmation.
