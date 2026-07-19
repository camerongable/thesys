package thesys.memory_write

default decision = {"allow": false, "requires_approval": true, "reason": "Memory write is denied by policy.", "allowed_scopes": [], "max_records": 0}

decision = {"allow": true, "requires_approval": true, "reason": "Durable memory requires review by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "agent"
}

decision = {"allow": true, "requires_approval": false, "reason": "Confirmed user memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "user"
}
