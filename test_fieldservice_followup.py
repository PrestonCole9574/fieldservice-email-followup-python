from fieldservice_followup import follow_up_state


def test_open_event_routes_a_dispatched_work_order_to_technician_follow_up():
    events = [{"event": "delivered"}, {"event": "opened"}]

    assert follow_up_state(events) == "technician_follow_up"


def test_bounce_takes_priority_over_open_for_contact_replacement():
    assert follow_up_state([{"type": "opened"}, {"type": "bounced"}]) == "replace_contact"
