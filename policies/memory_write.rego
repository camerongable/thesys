package thesys.memory_write

default decision = {"allow": false, "requires_approval": true, "reason": "Memory write is denied by policy.", "allowed_scopes": [], "max_records": 0}

decision = {"allow": true, "requires_approval": true, "reason": "Durable memory requires review by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "agent"
    input.principal.role != "viewer"
    input.memory.operation == "content_write"
}

decision = {"allow": true, "requires_approval": false, "reason": "Confirmed user memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "user"
    input.principal.role != "viewer"
    input.memory.operation == "content_write"
}

decision = {"allow": true, "requires_approval": false, "reason": "Authorized memory lifecycle change is allowed by policy.", "allowed_scopes": ["project"], "max_records": 100} {
    input.request.source == "user"
    input.principal.role != "viewer"
    lifecycle_operation
}

decision = {"allow": true, "requires_approval": false, "reason": "Trusted derived memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "system"
    input.memory.trusted_projection == true
    input.memory.operation == "content_write"
}

decision = {"allow": true, "requires_approval": false, "reason": "Versioned procedural memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "system"
    input.memory.memory_type == "procedural"
    input.memory.write_policy == "derived_read_only"
    input.memory.source_entity_type == "code"
    input.memory.operation == "content_write"
}

decision = {"allow": true, "requires_approval": false, "reason": "Versioned procedural memory is allowed by policy.", "allowed_scopes": ["project"], "max_records": 1} {
    input.request.source == "system"
    input.memory.memory_type == "procedural"
    input.memory.write_policy == "derived_read_only"
    input.memory.source_entity_type == "config"
    input.memory.operation == "content_write"
}

lifecycle_operation {
    input.memory.operation == "approve"
}

lifecycle_operation {
    input.memory.operation == "reject"
}

lifecycle_operation {
    input.memory.operation == "mark_stale"
}

lifecycle_operation {
    input.memory.operation == "archive"
}

lifecycle_operation {
    input.memory.operation == "merge_duplicates"
}

lifecycle_operation {
    input.memory.operation == "resolve_conflict"
}
}
