# Current Project Understanding - OpenGraph Intel (OGI)

OpenGraph Intel (OGI) is an open-source visual link analysis and OSINT framework built to explore and analyze entity relationship graphs.

## Core Architecture

### 1. Database & Local Mode
- **ORM**: SQLModel (SQLAlchemy wrapper) with Pydantic for validation.
- **Engines**: Supports PostgreSQL for team/cloud modes and SQLite for local zero-config mode.
- **Constraints**: SQLite foreign key constraints are explicitly enabled at connection time via a SQLAlchemy listener (`PRAGMA foreign_keys = ON;`).
- **Auth**: In local mode (where Supabase auth is not configured), a default anonymous profile (`00000000-0000-0000-0000-000000000000`) is seeded and resolved transparently as the current user.

### 2. Backend Graph Engine & Analysis
- **GraphEngine**: In-memory adjacency-list based graph representation (`_adjacency` and `_neighbors`) used to speed up traversal, search, and neighborhood queries.
- **Analysis Algorithms**: Located in `backend/ogi/engine/analysis.py`.
  - **Centrality**: Degree Centrality ($O(N)$), Closeness Centrality ($O(N \cdot M)$), Betweenness Centrality (Brandes' algorithm, $O(N \cdot M)$), PageRank (power iteration, 100 iterations).
  - **Community detection**: Connected components via BFS ($O(N + M)$).
- **Execution Model**: Computed on-demand inside FastAPI request handlers, which is synchronous and can block workers for large graphs.

### 3. Frontend Visualization & Layout
- **Rendering**: React 19 and **Sigma.js** powered by **WebGL** (underlying library is **graphology**). Handles high node counts efficiently.
- **Layout presets**: Defined in `frontend/src/lib/graphLayouts.ts`. Includes Force-directed (ForceAtlas2), CoSE, circular, spiral, concentric, components, Sugiyama, and grid layouts.
- **Performance & Execution**:
  - ForceAtlas2 layouts are executed synchronously on the main thread: `forceAtlas2.assign(graph, { ... })`. For large graphs, this blocks the user interface.
  - Kamada-Kawai layout scales poorly ($O(N^2)$ to $O(N^3)$) and automatically falls back to ForceAtlas2 if node count exceeds 140.
  - Layout positions, canvas pin states, and active filters are saved only in the browser's `localStorage` (scoped per project), not synced to the PostgreSQL backend.

### 4. Collaboration, Sync, and Audit Trails
- **Real-Time Sync**: Synchronizes node and edge creations/deletions in real-time via Supabase Postgres replication listener (`useRealtimeSync`). However, dragging nodes or camera panning does not sync across sessions, and presence cursors are absent.
- **Audit Logging**: Logs transform execution runs and agent activities in `audit_logs` / `system_audit_logs` tables. Manual creation, deletion, or modification of nodes/edges by users on the canvas bypasses the audit log.
- **Event Timeline**: A timeline slider query (`get_graph_window`) slices the graph based on PostgreSQL `created_at` timestamp metadata, rather than real-world observation timestamps (`observed_at`, `valid_from`) stored in the entity properties JSON payload.

## Tools & Environments
- **Package Managers**: `uv` (backend), `pnpm` (frontend).
- **CLI Wrapper**: `ogi` (implemented with Typer in `backend/ogi/cli/main.py`).
- **Tests**: Pytest for backend, Vitest/ESLint for frontend.

