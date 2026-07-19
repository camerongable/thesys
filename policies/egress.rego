package thesys.egress

default decision = {"allow": false, "requires_approval": false, "reason": "Egress destination is denied by policy.", "allowed_scopes": [], "max_records": 0}

decision = {"allow": true, "requires_approval": false, "reason": "Egress destination is allowed by policy.", "allowed_scopes": ["network"], "max_records": 1} {
    input.request.destination_allowed == true
}
