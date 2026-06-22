' 대시보드 서버를 창 없이 백그라운드로 실행하는 런처.
' 이 파일의 복사본이 Windows 시작프로그램 폴더에 있어 로그인 시 자동 실행된다.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\user\OneDrive\GoogleAD\adsense-daily-report"
sh.Run """C:\Users\user\OneDrive\GoogleAD\adsense-daily-report\.venv\Scripts\pythonw.exe"" ""C:\Users\user\OneDrive\GoogleAD\adsense-daily-report\serve.py""", 0, False
