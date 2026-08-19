from __future__ import annotations

SERVICE_NAME = "BoardRepo_Groupware"


class CredentialStoreError(RuntimeError):
    pass


def _keyring():
    try:
        import keyring
        return keyring
    except ImportError as exc:
        raise CredentialStoreError(
            "keyring 패키지가 준비되지 않았습니다. "
            "BoardRepo의 [필수 모듈 설치/복구] 또는 [회사용 오프라인 준비] 절차를 확인하세요."
        ) from exc


def save_credentials(username: str, password: str) -> None:
    username = username.strip()
    if not username or not password:
        raise CredentialStoreError("ID와 비밀번호를 모두 입력해야 합니다.")

    kr = _keyring()
    # fixed account stores the username; username account stores password
    kr.set_password(SERVICE_NAME, "__username__", username)
    kr.set_password(SERVICE_NAME, username, password)


def load_credentials():
    kr = _keyring()
    username = kr.get_password(SERVICE_NAME, "__username__")
    if not username:
        return None
    password = kr.get_password(SERVICE_NAME, username)
    if not password:
        return None
    return username, password
