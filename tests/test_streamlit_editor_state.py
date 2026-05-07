from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
SAMPLE_CHAT_BYTES = (Path(__file__).resolve().parent / "fixtures" / "sample_chat.txt").read_bytes()


def _run_with_uploaded_sample(at: AppTest) -> AppTest:
    at.run()
    at.file_uploader[0].upload("sample_chat.txt", SAMPLE_CHAT_BYTES, "text/plain").run()
    return at


def test_render_app_tolerates_none_chat_editor_state():
    at = AppTest.from_file(str(APP_PATH))
    at.session_state["chat_editor"] = None

    _run_with_uploaded_sample(at)

    assert len(at.exception) == 0
    assert at.title[0].value == "💬 카카오톡 나와의 채팅 정리기"



def test_render_app_tolerates_non_mapping_chat_editor_state():
    at = AppTest.from_file(str(APP_PATH))
    at.session_state["chat_editor"] = "stale-editor-state"

    _run_with_uploaded_sample(at)

    assert len(at.exception) == 0
    assert at.title[0].value == "💬 카카오톡 나와의 채팅 정리기"
