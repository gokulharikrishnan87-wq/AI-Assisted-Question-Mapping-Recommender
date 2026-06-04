from mapper_copilot.core.suggester import Suggester
from mapper_copilot.providers.embeddings import HashingEmbedder
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore
from mapper_copilot import ui


class _SidebarProxy:
    def __init__(self, parent):
        self._parent = parent

    def __getattr__(self, name):
        return getattr(self._parent, name)


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.calls = []
        self.sidebar = _SidebarProxy(self)

    def set_page_config(self, **kwargs):
        self.calls.append(("set_page_config", kwargs))

    def title(self, text):
        self.calls.append(("title", text))

    def caption(self, text):
        self.calls.append(("caption", text))

    def header(self, text):
        self.calls.append(("header", text))

    def subheader(self, text):
        self.calls.append(("subheader", text))

    def write(self, value):
        self.calls.append(("write", value))

    def info(self, value):
        self.calls.append(("info", value))

    def success(self, value):
        self.calls.append(("success", value))

    def warning(self, value):
        self.calls.append(("warning", value))

    def error(self, value):
        self.calls.append(("error", value))

    def metric(self, label, value, **kwargs):
        self.calls.append(("metric", label, value, kwargs))

    def progress(self, value):
        self.calls.append(("progress", value))

    def text_input(self, label, value="", **kwargs):
        self.calls.append(("text_input", label, value, kwargs))
        return value

    def button(self, label, **kwargs):
        self.calls.append(("button", label, kwargs))
        return False

    def slider(self, label, min_value, max_value, value, **kwargs):
        self.calls.append(("slider", label, min_value, max_value, value, kwargs))
        return value

    def file_uploader(self, label, **kwargs):
        self.calls.append(("file_uploader", label, kwargs))
        return None

    def dataframe(self, data, **kwargs):
        self.calls.append(("dataframe", data, kwargs))

    def download_button(self, label, **kwargs):
        self.calls.append(("download_button", label, kwargs))

    def columns(self, spec):
        self.calls.append(("columns", spec))
        count = spec if isinstance(spec, int) else len(spec)
        return [self for _ in range(count)]

    def cache_resource(self, func=None, **kwargs):
        self.calls.append(("cache_resource", kwargs))
        if func is None:
            return lambda wrapped: wrapped
        return func


def test_streamlit_page_config() -> None:
    fake_streamlit = FakeStreamlit()

    ui.render_app(fake_streamlit)

    assert (
        "set_page_config",
        {"page_title": "Mapper Copilot", "layout": "wide"},
    ) in fake_streamlit.calls


def test_suggester_initialized() -> None:
    fake_streamlit = FakeStreamlit()

    ui.render_app(fake_streamlit)

    assert "suggester" in fake_streamlit.session_state
    assert isinstance(fake_streamlit.session_state["suggester"], Suggester)


def test_ui_has_title() -> None:
    fake_streamlit = FakeStreamlit()

    ui.render_app(fake_streamlit)

    assert (
        "title",
        "Mapper Copilot - RSC to SLCP Question Mapper",
    ) in fake_streamlit.calls


def test_ui_input_field_exists() -> None:
    fake_streamlit = FakeStreamlit()

    ui.render_app(fake_streamlit)

    assert any(
        call[0] == "text_input" and call[1] == "Enter RSC Question" for call in fake_streamlit.calls
    )


def test_streamlit_imports() -> None:
    assert ui.st is not None
    assert Suggester is not None
    assert HashingEmbedder is not None
    assert MockLLM is not None
    assert NumpyVectorStore is not None
