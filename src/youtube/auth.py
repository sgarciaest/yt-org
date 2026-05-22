from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/youtube"]


def get_credentials(
    client_secrets_file: str = "client_secrets.json",
    token_file: str = ".token.json",
) -> Credentials:
    secrets_path = Path(client_secrets_file)
    if not secrets_path.exists():
        raise FileNotFoundError(
            f"OAuth client secrets not found: {client_secrets_file}\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials"
        )

    token_path = Path(token_file)
    credentials: Credentials | None = None

    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            try:
                credentials = flow.run_local_server(port=0)
            except Exception:
                # Fallback for headless environments
                credentials = flow.run_console()

        token_path.write_text(credentials.to_json())

    return credentials
