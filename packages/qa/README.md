# Citation Q&A Package

Boundary for retrieval and citation-based course answers.

Current slice:

- Answer course questions from local transcript segment evidence.
- Return citation payloads tied to lecture sequence, segment id, and timestamps.
- Block honestly when the local store has no matching transcript evidence.
- Do not call external LLMs or private learning-coach routes.
