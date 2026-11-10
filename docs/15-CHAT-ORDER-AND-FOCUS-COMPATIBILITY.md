# Chat chronology and FOCUS use-case compatibility

Implemented 2026-10-21.

## Chat

Tool activity persists `after_message_id`, anchored to the assistant's visible text (or the human message before any assistant text). The timeline renders each activity block at that anchor. Consecutive tools without intervening prose remain grouped. Live work stays at the end, followed by the next streamed response. Anchors survive reloads. Existing unanchored history retains its legacy placement; historical order is not guessed.

The previous eight-model-round cap was independent of HTTP retry policy. It is now forty rounds per turn for both parent and delegated graphs, with a shared 125-node recursion budget. Admission controls, tool permissions, per-request transport timeouts and provider rate limits remain enforced. Source adapter instructs agents to reuse snapshots and avoid repeating failed SQL.

## Data

The synthetic generator now emits additional billing/provider/region/SKU/pricing/commitment fields needed by imported use cases. FOCUS names are retained; ServiceProviderName and other catalog-version compatibility fields coexist. Unused commitment consumption is null, optional missing source fields remain null rather than fabricated zero. Original source prompts/SQL remain intact.

Existing DuckDB databases gain columns without dropping data. Inserts name columns explicitly to support schema upgrades. The two synthetic clients were republished under `focus/v2/`; original S3 objects remain intact. The active source prefix points at v2. Row-key upserts preserve costs and counts: lab-fintech 456 rows/76 published days; lab-commerce 450 rows/75 days. The known acme-demo CSV was also enriched and reingested without adding rows. No customer-authored source files were rewritten.

The deterministic SQL adapter repairs imported encoding, JSON tag access, MySQL JSON extraction, invalid GROUP BY aliases, unsigned casts and an invalid aggregate ordering. Snapshot dimension filters with unspecified values are broadened to the immutable client/date/currency scope and listed explicitly in `omitted_dimension_filters`; direct execution still requires parameters. This is not a claim of full FOCUS certification.

On generated data, 56 of 60 catalog cases execute successfully (including genuinely empty results). Case 16 requires a tag selector/dialect adaptation; cases 38/47/52 require contract JSON/contract data support beyond these billing CSVs. These remain unavailable with reasons, never reported as zero findings. Source SQL and executed SQL are retained for audit.

## Verification

174 backend tests passed. A deterministic model double completed eleven rounds, verifying ten tool results anchored to their preceding assistant messages. Both generated clients run the reference catalog without missing-column errors. Ingestion is idempotent, snapshots survive JSON round trips, and tenant/SQL safety tests pass. Frontend production build, Ruff and mypy pass. Local S3 synchronization confirmed no duplicated costs. Visual verification uses an isolated UI fixture, clearly labeled synthetic, without any NVIDIA call.
