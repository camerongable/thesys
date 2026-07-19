package thesys.memory_write

default decision = {"allow": false, "requires_approval": true, "reason": "Memory write is denied by policy.", "allowed_scopes": [], "max_records": 0}

decision = {"allow": true, "requires_approval": true, "reason": "Durable memory requires review by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "agent"
    input.principal.role != "viewer"
}

decision = {"allow": true, "requires_approval": false, "reason": "Confirmed user memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "user"
    input.principal.role != "viewer"
}

decision = {"allow": true, "requires_approval": false, "reason": "Trusted derived memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "system"
    input.memory.trusted_projection == true
}

decision = {"allow": true, "requires_approval": false, "reason": "Versioned procedural memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "system"
    input.memory.memory_type == "procedural"
    input.memory.write_policy == "derived_read_only"
    input.memory.source_entity_type == "code"
}

decision = {"allow": true, "requires_approval": false, "reason": "Versioned procedural memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "system"
    input.memory.memory_type == "procedural"
    input.memory.write_policy == "derived_read_only"
    input.memory.source_entity_type == "config"
}
}
