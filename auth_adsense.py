"""AdSense OAuth 최초 1회 인증.

브라우저로 본인 Google 계정 동의 → refresh token 을 token_adsense.json 에 저장.
이후 collect_adsense.py 가 이 토큰으로 무인 갱신/실행한다.

실행:  python auth_adsense.py
(처음 1회만. 토큰이 만료/폐기되면 다시 실행.)
"""
from google_auth_oauthlib.flow import InstalledAppFlow

import common


def main():
    client_id = common.env("ADSENSE_CLIENT_ID", required=True)
    client_secret = common.env("ADSENSE_CLIENT_SECRET", required=True)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, common.ADSENSE_SCOPES)
    # 로컬 브라우저를 띄워 동의를 받는다. 헤드리스 PC면 run_console() 로 바꿀 것.
    creds = flow.run_local_server(port=0, prompt="consent")

    common.TOKEN_ADSENSE.write_text(creds.to_json(), encoding="utf-8")
    print(f"[완료] refresh token 저장: {common.TOKEN_ADSENSE}")
    if not creds.refresh_token:
        print("[경고] refresh_token 이 비어있습니다. OAuth 동의화면을 다시(consent) 거쳐야 합니다.")


if __name__ == "__main__":
    main()
