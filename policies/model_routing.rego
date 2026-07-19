package thesys.model_routing

default decision = {"allow": false, "requires_approval": false, "reason": "Model routing is denied by policy.", "allowed_scopes": [], "max_records": 0}

decision = {"allow": true, "requires_approval": false, "reason": "Approved provider routing is allowed by policy.", "allowed_scopes": ["provider"], "max_records": 1} {
    input.request.provider_approved == true
}
