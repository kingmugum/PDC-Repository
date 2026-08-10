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
            "keyring 패키지가 설치되지 않았습니다. "
            "setup_first_run.bat을 먼저 실행하세요."
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
