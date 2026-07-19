package thesys.data_access

default decision = {"allow": false, "requires_approval": false, "reason": "Data access is denied by policy.", "allowed_scopes": [], "max_records": 0}

decision = {"allow": true, "requires_approval": false, "reason": "Project-scoped data access is allowed by policy.", "allowed_scopes": ["project"], "max_records": 100} {
    input.principal.workspace_id == input.project.workspace_id
}
