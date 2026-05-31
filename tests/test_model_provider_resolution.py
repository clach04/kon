from kon.llm.models import get_model


def test_get_model_prefers_provider_when_specified():
    copilot = get_model("gpt-5.5", "github-copilot")
    openai = get_model("gpt-5.5", "openai-codex")

    assert copilot is not None
    assert openai is not None
    assert copilot.provider == "github-copilot"
    assert openai.provider == "openai-codex"
    assert copilot.api != openai.api


def test_get_model_falls_back_to_id_lookup():
    model = get_model("glm-5.1")

    assert model is not None
    assert model.provider == "zhipu"


def test_get_model_prefers_provider_for_gpt_5_5():
    copilot = get_model("gpt-5.5", "github-copilot")
    openai = get_model("gpt-5.5", "openai-codex")

    assert copilot is not None
    assert openai is not None
    assert copilot.provider == "github-copilot"
    assert openai.provider == "openai-codex"
    assert copilot.api != openai.api


def test_get_model_resolves_deepseek_models():
    model = get_model("deepseek-v4-flash", "deepseek")

    assert model is not None
    assert model.provider == "deepseek"
