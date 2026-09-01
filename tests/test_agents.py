from google.adk.agents import SequentialAgent

from watchtower.agents import AgentPipeline
from watchtower.config import Settings
from watchtower.mcp_client import StaticQueryExecutor
from watchtower.models import Anomaly, AnomalyKind


def test_adk_pipeline_has_four_specialized_agents() -> None:
    pipeline = AgentPipeline(
        Settings(watchtower_env="test", _env_file=None), StaticQueryExecutor([])
    )
    root = pipeline._build_pipeline(
        Anomaly(
            kind=AnomalyKind.BUFFER_SPIKE,
            title_id="aurora-drift",
            title_name="Aurora Drift",
            region="MENA",
            observed=0.2,
            baseline=0.02,
            deviation_percent=900,
            confidence=0.9,
        )
    )
    assert isinstance(root, SequentialAgent)
    assert [agent.name for agent in root.sub_agents] == [
        "detector_agent",
        "root_cause_agent",
        "impact_estimator_agent",
        "action_drafter_agent",
    ]
    assert len(root.sub_agents[0].tools) == 1
    assert len(root.sub_agents[1].tools) == 1
    assert root.sub_agents[-1].tools == []
