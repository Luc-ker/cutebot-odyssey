import edge


def test_edge_blocks_forward_allows_reverse():
    assert edge.edge_gate(80, 10, edge.EDGE_VALUE, 0) == (0, 10)
    assert edge.edge_gate(80, 0, 0, edge.EDGE_VALUE) == (0, 0)
    assert edge.edge_gate(-80, 0, edge.EDGE_VALUE, edge.EDGE_VALUE) == (-80, 0)


def test_no_edge_passes_through():
    other = 1 - edge.EDGE_VALUE
    assert edge.edge_gate(80, 5, other, other) == (80, 5)
