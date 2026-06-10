# 1. Client-Side Shortest Path Calculation

## Status
Proposed

## Context
The user needs to select two entities (nodes) on the graph canvas and visualize the shortest path between them. 

The application architecture loads the complete project graph (entities and edges) into the client-side browser memory (using `graphology`) when a project is opened. Centrality algorithms and community detection are computed on the server on-demand, which can block backend workers and requires API requests. 

We need to decide whether to compute the shortest path on the server-side via a new API endpoint or on the client-side.

## Decision
Compute the shortest path entirely on the client-side (frontend) using a Breadth-First Search (BFS) algorithm operating directly on the `graphology` graph instance.

## Alternatives Considered
1. **Server-side shortest path computation**:
   * *Pros*: Reuses the existing `find_paths` BFS logic in python `GraphEngine`.
   * *Cons*: Requires a network round-trip. Cannot easily respect client-side filtering (e.g. hidden nodes/edges or temporary search filters) without transmitting the entire client-side filter state to the server.

## Consequences
* **Performance**: Calculation is instantaneous (typically < 1ms for graphs of several thousand nodes) with zero network overhead.
* **Filter Awareness**: The client-side path finder can easily query the current hidden/filtered node state to find paths that are currently visible, or fall back to the complete graph if requested.
* **State Management**: The path calculation is handled via Zustand actions in `graphStore.ts` and set as a temporary `nodeOverlay` visual layer, making it easy to reset or clear.
* **CPU usage**: Traversal is performed on the user's CPU, which is highly efficient for graphs within Sigma.js rendering limits (under 10,000 nodes).
