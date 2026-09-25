from veeam_designer.agent import size_agent
from veeam_designer.models import AgentInput


def test_agent_repo_uses_v13_n_plus_one_and_separate_headroom():
    result = size_agent(
        AgentInput(
            machine_count=1,
            avg_size_gb=1024.0,
            daily_change_pct=10.0,
            retention_days=7,
            concurrent_tasks=1,
        )
    )

    assert result.short_term_data_tb == 1.7
    assert result.operational_headroom_tb == 1.2
    assert result.total_repo_tb == 3.0


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

    assert result.short_term_data_tb == 1.2
    assert result.total_repo_tb == 2.5


def test_agent_general_proxy_minimum_scales_with_concurrent_tasks():
    one_task = size_agent(
        AgentInput(machine_count=50, avg_size_gb=200.0, concurrent_tasks=1)
    )
    four_tasks = size_agent(
        AgentInput(machine_count=50, avg_size_gb=200.0, concurrent_tasks=4)
    )

    assert one_task.coordinator_cores == 2
    assert one_task.coordinator_ram_gb == 3
    assert four_tasks.coordinator_cores == 8
    assert four_tasks.coordinator_ram_gb == 6


def test_agent_known_network_requirement():
    result = size_agent(
        AgentInput(
            machine_count=1,
            avg_size_gb=1024.0,
            daily_change_pct=10.0,
            backup_window_hours=8.0,
            concurrent_tasks=1,
        )
    )

    assert result.required_mbps == 29.1


def test_more_machines_require_more_repo_capacity():
    small = size_agent(AgentInput(machine_count=10, avg_size_gb=200.0))
    large = size_agent(AgentInput(machine_count=100, avg_size_gb=200.0))

    assert large.total_repo_tb > small.total_repo_tb
