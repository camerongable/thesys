package thesys.tool_access

default decision = {"allow": false, "requires_approval": true, "reason": "Tool access is denied by policy.", "allowed_scopes": [], "max_records": 0}

decision = {"allow": true, "requires_approval": approval_required, "reason": "Tool access is allowed by policy.", "allowed_scopes": ["project"], "max_records": 100} {
    input.principal.role == "owner"
    approval_required := input.tool.access_mode != "read"
}

decision = {"allow": true, "requires_approval": approval_required, "reason": "Tool access is allowed by policy.", "allowed_scopes": ["project"], "max_records": 100} {
    input.principal.role == "admin"
    approval_required := input.tool.access_mode != "read"
}

decision = {"allow": true, "requires_approval": approval_required, "reason": "Tool access is allowed by policy.", "allowed_scopes": ["project"], "max_records": 100} {
    input.principal.role == "editor"
    approval_required := input.tool.access_mode != "read"
}

decision = {"allow": true, "requires_approval": false, "reason": "Read-only tool access is allowed by policy.", "allowed_scopes": ["project"], "max_records": 100} {
    input.principal.role == "viewer"
    input.tool.access_mode == "read"
}
