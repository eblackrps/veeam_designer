from veeam_designer.models import AgentInput
from veeam_designer.agent import size_agent


def test_agent_basic():
    ain = AgentInput(machine_count=50, avg_size_gb=200.0)
    r = size_agent(ain)
    assert r.total_repo_tb > 0
    assert r.coordinator_cores >= 2


def test_more_machines_more_repo():
    small = size_agent(AgentInput(machine_count=10, avg_size_gb=200.0))
    large = size_agent(AgentInput(machine_count=100, avg_size_gb=200.0))
    assert large.total_repo_tb > small.total_repo_tb
