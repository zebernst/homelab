from unifi_pdu import merge_outlet_overrides


def test_merge_updates_existing_index():
    existing = [
        {"index": 1, "relay_state": True, "name": "modem"},
        {"index": 2, "relay_state": True, "name": "switch"},
    ]
    result = merge_outlet_overrides(existing, 1, False)
    assert result[0]["relay_state"] is False
    assert result[0]["name"] == "modem"
    assert result[1]["relay_state"] is True
    # Original list not mutated
    assert existing[0]["relay_state"] is True


def test_merge_appends_missing_index():
    existing = [{"index": 2, "relay_state": True}]
    result = merge_outlet_overrides(existing, 7, False)
    assert {"index": 7, "relay_state": False} in result
    assert len(result) == 2
