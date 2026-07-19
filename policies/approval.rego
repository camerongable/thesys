package thesys.approval

default decision = {"allow": false, "requires_approval": true, "reason": "Approval is denied by policy.", "allowed_scopes": [], "max_records": 0}

decision = {"allow": true, "requires_approval": false, "reason": "Approval action is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.principal.role == "owner"
}

decision = {"allow": true, "requires_approval": false, "reason": "Approval action is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.principal.role == "admin"
}
