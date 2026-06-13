from scripts.gmail_auth_setup import GMAIL_READONLY_SCOPE


def test_gmail_auth_scope_is_read_only() -> None:
    assert GMAIL_READONLY_SCOPE == (
        "https://www.googleapis.com/auth/gmail.readonly"
    )
