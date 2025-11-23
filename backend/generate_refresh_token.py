import os
from dotenv import load_dotenv
load_dotenv()

from config import Config
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

def main():
    client_id = Config.YOUTUBE_CLIENT_ID
    client_secret = Config.YOUTUBE_CLIENT_SECRET

    print("Loaded CLIENT ID:", client_id)
    print("Loaded CLIENT SECRET:", client_secret)

    if not client_id or not client_secret:
        raise Exception("Missing YOUTUBE_CLIENT_ID or YOUTUBE_CLIENT_SECRET in environment variables.")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8080, prompt="consent")

    print("\nREFRESH TOKEN:")
    print(creds.refresh_token)

if __name__ == "__main__":
    main()
