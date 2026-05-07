# 카카오톡 나와의 채팅 정리기

카카오톡에서 `대화 내용 내보내기`로 받은 TXT 파일을 업로드해서 한눈에 검토하고, 불필요한 메시지는 제외하고, URL은 메타데이터와 스크린샷 형태로 미리 본 뒤, 수정된 TXT 파일로 다시 다운로드할 수 있는 Python 프로그램입니다.

## 주요 기능

- 카카오톡 TXT 파일 업로드
- 전체 메시지 목록 확인
- 채팅 목록에서 `삭제` 체크로 메시지 제외
- 메시지 내용 직접 수정
- `중복 메시지` 버튼으로 중복 메시지만 빠르게 보기
- `중복 URL` 버튼으로 URL 메시지만 빠르게 보기
- URL 메타데이터(제목, 설명, 사이트명, 대표 이미지) 미리보기
- URL 10개씩 페이지 이동하며 보기
- 열린 페이지 스크린샷형 URL 미리보기
- 수정된 TXT 파일 다운로드

## 기술 스택

- Python 3.10+
- Streamlit
- pandas
- requests
- BeautifulSoup4

## 폴더 구조

```text
kakao_chat_manager/
├─ app.py
├─ pyproject.toml
├─ requirements.txt
├─ README.md
├─ .gitignore
├─ src/
│  └─ kakao_chat_manager/
│     ├─ __init__.py
│     ├─ parser.py
│     ├─ cleaning.py
│     ├─ exporter.py
│     └─ url_preview.py
└─ tests/
   ├─ conftest.py
   ├─ test_parser.py
   ├─ test_cleaning_and_export.py
   ├─ test_url_preview.py
   └─ fixtures/
      └─ sample_chat.txt
```

## 실행 방법

### 1) 저장소 클론

```bash
git clone <YOUR_GITHUB_REPO_URL>
cd kakao_chat_manager
```

### 2) 가상환경 생성 및 활성화

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) 의존성 설치

```bash
pip install -r requirements.txt
pip install -e .
```

### 4) 앱 실행

```bash
streamlit run app.py
```

실행 후 브라우저에서 표시되는 로컬 주소로 접속하면 됩니다.

## 사용 방법

1. 카카오톡에서 `나와의 채팅` 또는 원하는 채팅방으로 들어갑니다.
2. `대화 내용 내보내기`로 TXT 파일을 저장합니다.
3. 앱에서 TXT 파일을 업로드합니다.
4. 목록에서 `삭제` 체크를 하면 그 메시지는 다운로드 파일에서 제거됩니다.
5. `text` 칸은 직접 수정할 수 있습니다.
6. 왼쪽 사이드바의 `중복 메시지`, `중복 URL` 버튼으로 원하는 메시지 유형만 빠르게 볼 수 있습니다.
7. URL 미리보기는 10개씩 페이지를 넘기며 확인할 수 있고, 스크린샷 형태로 열린 페이지를 바로 볼 수 있습니다.
8. `현재 페이지 메타데이터 불러오기`를 누르면 링크 제목/설명/대표 이미지를 함께 확인할 수 있습니다.
9. 마지막으로 `수정된 TXT 다운로드` 버튼을 누르면 정리된 파일을 받을 수 있습니다.

## 테스트 방법

```bash
pytest
```

## GitHub 업로드 팁

```bash
git init
git add .
git commit -m "feat: initial kakao chat manager"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## 주의 사항

- URL 미리보기는 각 웹사이트의 메타데이터 제공 여부에 따라 일부 정보가 비어 있을 수 있습니다.
- 페이지 스크린샷 미리보기는 외부 스크린샷 서비스 또는 사이트 임베드 정책에 따라 일부 URL에서 제한될 수 있습니다.
- 아주 특이한 형식의 카카오톡 TXT 파일은 추가 파서 보정이 필요할 수 있습니다.
- 기본적으로 원본 TXT는 수정하지 않고, 정리된 새 TXT 파일만 다운로드합니다.
