---
name: finops-build-atomic-memory
description: Build and extend the Dual HippoRAG Knowledge Graph (canonical FinOps KB + episodic client memory) and the atomic Ticket/Context Unit-of-Work manager. Use whenever working on HippoRAG indexing, client context files, or ticket creation and status updates.
---

# FinOps Atomic Memory & Dual HippoRAG Skill

## Capabilities Covered
- `@finops_capabilities_md/capabilities/automation-tools-services.md` (https://www.finops.org/framework/capabilities/automation-tools-services/)
- `@finops_capabilities_md/capabilities/anomaly-management.md` (https://www.finops.org/framework/capabilities/anomaly-management/)

## Core Blueprint: 3-Step Atomic Unit of Work for Tickets & Context

To prevent drift between Markdown files, DuckDB `tickets_ledger`, and HippoRAG's `client_memory_graph`, all ticket and context mutations must execute through `AtomicTicketMemoryManager`:

### 1. Deterministic Fingerprint
Every ticket/finding computes a deterministic 16-char SHA-256 fingerprint:
```python
fingerprint = make_fingerprint(client_id, capability_slug, sub_account_id, service_name, period_bucket)
```
- If `fingerprint` already exists in `tickets_ledger` with status `IN ('PROPOSED', 'APPROVED', 'FALSE_POSITIVE', 'SNOOZED')`, **skip creation** (idempotent deduplication).

### 2. Atomic File Write + Ledger Upsert + HippoRAG Node Upsert
```python
class AtomicTicketMemoryManager:
    def upsert_ticket(self, ticket: FinOpsTicket) -> FinOpsTicket:
        md_path = self.workspace_dir / ticket.client_id / "tickets" / f"{ticket.ticket_id}.md"
        # Step 1: Atomic POSIX file replacement (.tmp -> os.replace)
        atomic_write_text(md_path, ticket.to_markdown_with_frontmatter())

        # Step 2: Atomic DuckDB ledger upsert
        with self.db.atomic_tx() as tx:
            tx.execute(
                """
                INSERT OR REPLACE INTO tickets_ledger
                (fingerprint, ticket_id, client_id, capability, maturity_tier, status,
                 sub_account_id, service_name, impact_usd, currency, updated_at_utc)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                ticket.to_ledger_tuple(),
            )

        # Step 3: Idempotent HippoRAG episodic graph upsert (keyed by fingerprint)
        self.hipporag.upsert_document(
            graph_id=f"client_{ticket.client_id}",
            doc_id=ticket.fingerprint,
            text=ticket.to_graph_passage(),
        )
        return ticket
```

### 3. Dual HippoRAG Graph Separation
1. **`finops_kb_graph` (Read-Only Shared Singleton)**:
   - Indexed once from `finops_capabilities_md/capabilities/*.md`.
   - Queried by `capability_slug` + specific topic (`Showback vs Chargeback`, `Commitment Discount Waste`, `Holdback`).
2. **`client_<id>_graph` (Read-Write Episodic Per Client)**:
   - Indexes `client_profile.yaml`, `context_notes/*.md`, and all `tickets/FIN-*.md` (including human resolution comments).
   - Enables multi-hop associative recall: `SubAccountId` -> `Ticket FIN-004` -> `Approved GPU training until Oct 30` -> `Suppress false positive anomaly & exclude from 1-yr CUD baseload`.
