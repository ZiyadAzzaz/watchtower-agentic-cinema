from pathlib import Path


def test_shipped_runtime_has_no_non_google_ai_sdks() -> None:
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in Path("watchtower").rglob("*.py")
    )
    forbidden_imports = (
        "import openai",
        "from openai",
        "import anthropic",
        "from anthropic",
        "import boto3",
        "from langchain",
        "from llama_index",
    )
    assert all(value not in runtime_text for value in forbidden_imports)


def test_required_google_and_clickhouse_integrations_are_real_imports() -> None:
    agents = Path("watchtower/agents.py").read_text(encoding="utf-8")
    mcp_client = Path("watchtower/mcp_client.py").read_text(encoding="utf-8")
    assert "from google.adk.agents import LlmAgent, SequentialAgent" in agents
    assert "from mcp import ClientSession, StdioServerParameters" in mcp_client
    assert 'args=["-m", "mcp_clickhouse.main"]' in mcp_client
