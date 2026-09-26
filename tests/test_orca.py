import pytest

from veeam_designer.orca import size_orca


def test_object_first_requires_explicit_node_capacity():
    with pytest.raises(ValueError, match="must be supplied explicitly"):
        size_orca(100.0, usable_tb_per_node=0.0)


def test_object_first_helper_does_not_invent_immutability_overhead():
    result = size_orca(100.0, usable_tb_per_node=72.0)

    assert result.node_count == 2
    assert result.usable_tb_per_node == 72.0
    assert result.total_usable_tb == 144.0
    assert result.concurrent_stream_capacity == 0
    assert any("explicitly supplied usable capacity" in note for note in result.notes)


def test_object_first_helper_warns_when_selected_node_model_exceeds_cluster_limit():
    result = size_orca(400.0, usable_tb_per_node=72.0, max_nodes_per_cluster=4)

    assert result.node_count == 6
    assert any("exceeds the supplied 4-node cluster limit" in note for note in result.notes)
