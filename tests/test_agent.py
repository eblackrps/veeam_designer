from veeam_designer.agent import size_agent
from veeam_designer.models import AgentInput


def test_agent_repo_uses_v13_n_plus_one_retention():
    result = size_agent(
        AgentInput(
            machine_count=1,
            avg_size_gb=1024.0,
            daily_change_pct=10.0,
            retention_days=7,
            concurrent_tasks=1,
        )
    )

    # 1 TB full + seven 0.1 TB increments = 1.7 TB, plus 25% reserve.
    assert result.total_repo_tb == 2.1


def test_agent_minimum_three_restore_points_is_enforced():
    result = size_agent(
        AgentInput(
            machine_count=1,
            avg_size_gb=1024.0,
            daily_change_pct=10.0,
            retention_days=1,
            concurrent_tasks=1,
        )
    )

    assert result.total_repo_tb == 1.5


def test_agent_general_proxy_minimum_scales_with_concurrent_tasks():
    one_task = size_agent(
        AgentInput(
            machine_count=50,
            avg_size_gb=200.0,
            concurrent_tasks=1,
        )
    )
    four_tasks = size_agent(
        AgentInput(
            machine_count=50,
            avg_size_gb=200.0,
            concurrent_tasks=4,
        )
    )

    assert one_task.coordinator_cores == 2
    assert one_task.coordinator_ram_gb == 3
    assert four_tasks.coordinator_cores == 8
    assert four_tasks.coordinator_ram_gb == 6


def test_agent_default_case_has_deterministic_capacity():
    result = size_agent(AgentInput(machine_count=50, avg_size_gb=200.0))

    assert result.total_repo_tb == 20.8
    assert result.coordinator_cores == 8
    assert result.coordinator_ram_gb == 6


def test_more_machines_require_more_repo_capacity():
    small = size_agent(AgentInput(machine_count=10, avg_size_gb=200.0))
    large = size_agent(AgentInput(machine_count=100, avg_size_gb=200.0))

    assert large.total_repo_tb > small.total_repo_tb
