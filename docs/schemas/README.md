# MemoryChain Schema Docs

These documents define the canonical V1 object model for MemoryChain.

They exist before code on purpose. The product idea is easy to make fuzzy. The schema is where ambiguity has to die.

Reading order:

1. `SCHEMA_RULES.md`
2. `AUTHORED_OBJECTS.md`
3. `DERIVED_OBJECTS.md`
4. `INGESTION_EXAMPLES.md`

Goals of this schema layer:

- preserve raw source truth
- define clear authored versus derived boundaries
- make extraction and validation explicit
- keep V1 scope narrow enough to ship

Out of scope for these docs:

- UI wireframes
- storage engine specifics
- vector retrieval details
- multi-agent runtime design
