# Current Project Understanding - OpenGraph Intel (OGI)

OpenGraph Intel (OGI) is an open-source visual link analysis and OSINT framework built to explore and analyze entity relationship graphs.

---

## Core Architecture

### 1. Database, Auth & Local Mode
- **ORM & Models**: SQLModel (SQLAlchemy wrapper) with Pydantic for validation and serialization.
- **Engines**: Supports PostgreSQL for team/cloud modes and SQLite for local zero-config mode.
- **Constraints**: SQLite foreign key constraints are explicitly enabled at connection time via a SQLAlchemy listener (`PRAGMA foreign_keys = ON;`).
- **Auth**: In local mode (where Supabase auth is not configured), a default anonymous profile (`00000000-0000-0000-0000-000000000000`) is seeded and resolved transparently as the current user.

### 2. Backend Graph Engine & Analysis
- **GraphEngine**: In-memory adjacency-list based graph representation (`_adjacency` and `_neighbors`) used to speed up traversal, search, and neighborhood queries.
- **Analysis Algorithms**: Located in `backend/ogi/engine/analysis.py`.
  - **Centrality**: Degree Centrality ($O(N)$), Closeness Centrality ($O(N \cdot M)$), Betweenness Centrality (Brandes' algorithm, $O(N \cdot M)$), PageRank (power iteration, 100 iterations).
  - **Community Detection**: Connected components via BFS ($O(N + M)$).
- **Execution Model**: Computed on-demand inside FastAPI request handlers, which is synchronous and can block workers for large graphs.

### 3. Frontend Visualization & Layout
- **Rendering**: React 19 and **Sigma.js** powered by **WebGL** (underlying library is **graphology**). Handles high node counts efficiently.
- **Node Hover Customization**: Renders custom tooltip labels using 2D canvas drawing (`drawHighlightedNodeHover`) with shadow blur, contrast icon colors, and rounded background boxes.
- **Interaction and Event Handling**:
  - **Drag State Tracking**: Avoids React re-renders during active drag actions by storing coordinate states, initial positions, and dragging flags in a `dragStateRef` mutable reference object.
  - **Drag vs Click Threshold**: Introduces a minimum movement threshold of 3 pixels (`Math.sqrt(dx*dx + dy*dy) > 3`) to differentiate between clicks and drags. Prevents click selection events from firing if the node was dragged.
  - **Smooth Camera Handling**: Disables camera panning and rotation controls while dragging nodes, and utilizes Sigma's mouse captor (`mousemovebody` and `mouseup` events) to keep dragging active even when the pointer moves outside the canvas element.
  - **Unified Reducers**: GraphCanvas serves as the single source of truth for `nodeReducer` and `edgeReducer` configurations, managing node size scaling, type-specific styling, community coloring, and connection visual cues dynamically.
  - **Window-bound Box Selection**: Captures modifier keys (`Shift`/`Ctrl`/`Meta`) on wrapper `onMouseDownCapture`. Registers mouse-move and mouse-up listeners directly on the `window` object to draw a dashed selection box and compute node selection in real-time, even across browser boundaries.
- **Layout Presets**: Defined in `frontend/src/lib/graphLayouts.ts`. Includes Force-directed (ForceAtlas2), CoSE, circular, spiral, concentric, components, Sugiyama, and grid layouts.
- **Shortest Path Integration**:
  - Computed entirely on the client-side (frontend) using an undirected Breadth-First Search (BFS) on the in-memory `graphology` instance.
  - Highlights path nodes and edges using `nodeReducer` and `edgeReducer` via a custom overlay (`nodeOverlay` of type `shortest-path`).
  - Colors the start node gold (#eab308) and the end node green (#22c55e), colors path edges bright blue (#3b82f6) and scales up thickness. Fades non-path nodes/edges (opacity `0.1` or hides entirely) to preserve overall graph context.
  - Supports a visible-only filter toggle (defaults to true). If disabled, traverses the full graph and temporarily reveals hidden/filtered nodes/edges on the path.
  - Supports multiple minimal hop shortest paths with a pager control ("Path 1 of N") to cycle through and highlight them individually.
  - Integrates manual searchable autocomplete inputs (Start/End) in the bottom Analysis tab, direct canvas click/selection updates, and right-click context menu options.
- **Performance & Execution**:
  - ForceAtlas2 layouts are executed synchronously on the main thread: `forceAtlas2.assign(graph, { ... })`. For large graphs, this blocks the user interface.
  - Kamada-Kawai layout scales poorly ($O(N^2)$ to $O(N^3)$) and automatically falls back to ForceAtlas2 if node count exceeds 140.
  - Layout positions, canvas pin states, and active filters are saved only in the browser's `localStorage` (scoped per project), not synced to the PostgreSQL backend.

### 4. Collaboration, Sync, and Audit Trails
- **Real-Time Sync**: Synchronizes node and edge creations/deletions in real-time via Supabase Postgres replication listener (`useRealtimeSync`). However, dragging nodes or camera panning does not sync across sessions, and presence cursors are absent.
- **Audit Logging**: Logs transform execution runs and agent activities in `audit_logs` / `system_audit_logs` tables. Note: Previously, the `audit_logs` table (and other tables like `geocode_cache`, `global_transform_settings`, `user_plugin_preferences`, and `user_transform_settings`) were missing from Alembic migrations, causing first-time setups in PostgreSQL/Docker Compose environments to fail when writing audit logs. This has been resolved by adding Alembic migration `74be48ab662a` to create these tables. Manual creation, deletion, or modification of nodes/edges by users on the canvas bypasses the audit log.
- **Event Timeline**: A timeline slider query (`get_graph_window`) slices the graph based on PostgreSQL `created_at` timestamp metadata, rather than real-world observation timestamps (`observed_at`, `valid_from`) stored in the entity properties JSON payload.

### 5. AI Investigator / Agent Runtime
- **LLM Integration**: Supports OpenAI, Gemini (via native REST API `generateContent`), and Anthropic. Consolidates multiple context system messages and schemas into a single system instruction to ensure robust JSON outputs and avoid model/compatibility layer confusion.
- **Robust Decision Normalization**: Employs Pydantic's `@model_validator` before validation to adapt raw model tool calls (translating keys like `name`, `arguments`, `parameters`) into the structured `LlmDecision` schema transparently.
- **Concurrency & Locking**: Runs on a background daemon (`run_worker.py` / `poll_orchestrator`) that claims runnable steps (`pending` or `approved`) using PostgreSQL/SQLite transaction row-level locks (`WITH FOR UPDATE SKIP LOCKED`).
- **Worker Ownership & Recovery**: Workers register unique identifiers (`hostname:pid:uuid`) to trace ownership. Stuck workers are recovered by a stale state resolver (`recover_stale_state`) which resets orphaned steps to `pending` and fails runs without active paths.
- **Budget Boundaries**: Enforces hard budget limits (`max_steps`, `max_transforms`, `max_runtime_sec`) on every processing step, raising a `BudgetExceededError` and failing the run if crossed.
- **Execution States**:
  - `THINK`: Assembles prompt contexts, invokes the LLM, normalizes structured JSON choices, and evaluates action safety.
  - `TOOL_CALL`: Executes handlers, captures outputs, and triggers self-correction replanning.
  - `APPROVAL_REQUEST` / `APPROVAL_RESPONSE`: Coordinates human-in-the-loop approvals for high-risk actions (`run_transform`, `create_entity`), pausing runs and notifying clients.
  - `SUMMARY` / `ERROR`: Concludes the active run, logging concluding reports or trace errors.
- **Action Policies & Self-Correction**:
  - **Loop Prevention**: Blocks repeated identical tool calls and lateral exploration of low-yield transforms.
  - **Transform Yield Scoring**: Evaluates transform productivity. If a transform family is low-yield (generates zero/minimal new elements) in 2 of the last 3 runs, it is registered in `exhausted_transform_families` and blocked.
  - **Validation Replanning**: Catches FastAPI validation HTTP 400/404 tool execution errors, logging a warning feedback block, setting the tool result to failed, and triggering a new `THINK` step to let the LLM self-correct.
- **Context Builder (`AgentContextBuilder`)**:
  - **System Instruction Consolidation**: Consolidates schemas and system constraints into a single system instruction.
  - **History Compression**: Summarizes older steps into single-line lists, keeping only the last 8 steps in full detail to preserve token limits.
  - **Platform Goal Focus**: Scans user prompts for keywords (e.g. `twitter`, `youtube`) and appends specific focus directives to prevent lateral drift.
- **Project Memory (`AgentProjectMemory`)**:
  - Synchronizes cumulative knowledge after each step, merging findings, known facts, and exhausted paths across runs.
  - Compiles a paragraph summary that gets injected as historical reference in future runs on the same project.
- **Frontend & Sync Syncing**:
  - The UI uses Zustand (`useInvestigatorStore`) to drive controls. Renders steps dynamically based on type (e.g., custom rendering for thinking reasoning, approvals, summaries, and errors).
  - Real-time updates are driven by Redis Pub/Sub events (`agent_thinking`, `agent_approval_requested`, etc.) streamed via WebSockets, triggering automatic client refreshes to display live progress.

---

## Transform Feature Pipeline

A **Transform** is a plugin or built-in script that accepts an input entity and executes an enrichment task to produce new entities and edges.

### 1. Registry & Loading
- **Base Class**: `BaseTransform` in `ogi.transforms.base`.
- **Built-in Transforms**: Located in `ogi/transforms/` and registered during start-up using `TransformEngine.auto_discover()`.
- **Plugins**: Located in `plugins/` (e.g., `plugins/example-plugin`). Discovered via `plugin.yaml` manifests and dynamically imported from the `transforms/` sub-package.

### 2. Execution Service (`TransformExecutionService`)
- **Validation & Preparation**:
  - Verifies user permissions (requires `owner` or `editor` role on the project).
  - Resolves settings by merging default, global, user, and runtime settings.
  - Validates and sanitizes types, min/max values, and regex patterns.
  - Injects stored API keys for required settings ending with `_api_key` if allowed by global allowlists/blocklists and plugin verification tiers.
  - Enforces run policies and enqueues tasks onto the Redis-backed RQ queue.
- **Direct Execution**: For synchronous execution, it runs them directly and merges output entities/edges into the database.

### 3. Worker & Background Processing (`transform_job.py`)
- **Background Worker**:
  - Bootstraps its own database connection and caches local `TransformEngine`/`PluginEngine` instances.
  - Invokes `await transform.run(entity, config)` under an event loop.
  - Deduplicates and persists generated entities/edges to the database, mapping temporary entity IDs to final persisted DB UUIDs.
  - Updates the `TransformRun` record in the database.
  - Publishes progress events (`job_started`, `job_completed`, `job_failed`) to Redis Pub/Sub.

### 4. WebSocket Broadcasting & Canvas Update (`websocket.py`)
- **Broadcaster**:
  - A singleton background task listens to the Redis Pub/Sub channels `ogi:transform_events:*`.
  - Forwards all transform events verbatim to connected WebSocket clients for that project.
- **Frontend Hook (`useTransformWebSocket`)**:
  - Merges new entities/edges received on `job_completed` events directly into the Sigma.js/Graphology canvas.

---

## Tools & Environments
- **Package Managers**: `uv` for backend, `pnpm` for frontend.
- **CLI Wrapper**: Entrypoint `ogi` implemented with Typer in `backend/ogi/cli/main.py`.
- **Tests**: Pytest for backend, Vitest/ESLint for frontend.
