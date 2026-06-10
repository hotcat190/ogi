import { beforeEach, describe, expect, it } from "vitest";
import Graph from "graphology";
import { EntityType, type Entity } from "../types/entity";
import { useGraphStore } from "./graphStore";
import type { Edge } from "../types/edge";

function makeEntity(id: string, overrides: Partial<Entity> = {}): Entity {
  return {
    id,
    type: EntityType.Domain,
    value: `${id}.example.org`,
    properties: {},
    icon: "globe",
    weight: 1,
    notes: "",
    tags: [],
    source: "manual",
    origin_source: "manual",
    project_id: "p-1",
    created_at: "2026-03-03T10:00:00Z",
    updated_at: "2026-03-03T10:00:00Z",
    ...overrides,
  };
}

function makeEdge(id: string, sourceId: string, targetId: string): Edge {
  return {
    id,
    source_id: sourceId,
    target_id: targetId,
    label: "related",
    weight: 1,
    properties: {},
    bidirectional: false,
    source_transform: "manual",
    project_id: "p-1",
    created_at: "2026-03-03T10:00:00Z",
  };
}

function makeGraph(entities: Entity[], edges: Edge[] = []) {
  const graph = new Graph({ multi: true, type: "directed" });
  for (const entity of entities) {
    graph.addNode(entity.id, { x: 0, y: 0, size: 8, color: "#6366f1", label: entity.value });
  }
  for (const edge of edges) {
    graph.addEdgeWithKey(edge.id, edge.source_id, edge.target_id, { label: edge.label });
  }
  return graph;
}

describe("Shortest Path Finder", () => {
  beforeEach(() => {
    useGraphStore.getState().clearGraph();
    useGraphStore.getState().clearShortestPath();
  });

  it("finds a simple shortest path between two nodes", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b");
    const c = makeEntity("e-c");
    const ab = makeEdge("edge-ab", a.id, b.id);
    const bc = makeEdge("edge-bc", b.id, c.id);

    const graph = makeGraph([a, b, c], [ab, bc]);

    useGraphStore.setState({
      graph,
      entities: new Map([
        [a.id, a],
        [b.id, b],
        [c.id, c],
      ]),
      edges: new Map([
        [ab.id, ab],
        [bc.id, bc],
      ]),
    });

    useGraphStore.getState().setShortestPathStartId(a.id);
    useGraphStore.getState().setShortestPathEndId(c.id);

    const state = useGraphStore.getState();
    expect(state.shortestPaths).toEqual([[a.id, b.id, c.id]]);
    expect(state.currentPathIndex).toBe(0);

    const overlay = state.nodeOverlay;
    expect(overlay).not.toBeNull();
    if (overlay?.type === "shortest-path") {
      expect(overlay.pathNodeIds).toEqual(new Set([a.id, b.id, c.id]));
      expect(overlay.pathEdgeIds).toEqual(new Set([ab.id, bc.id]));
      expect(overlay.startNodeId).toBe(a.id);
      expect(overlay.endNodeId).toBe(c.id);
    }
  });

  it("finds multiple shortest paths of minimal length", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b");
    const c = makeEntity("e-c");
    const d = makeEntity("e-d");
    const ab = makeEdge("edge-ab", a.id, b.id);
    const bd = makeEdge("edge-bd", b.id, d.id);
    const ac = makeEdge("edge-ac", a.id, c.id);
    const cd = makeEdge("edge-cd", c.id, d.id);

    // Paths from A to D: A->B->D (length 2) and A->C->D (length 2)
    const graph = makeGraph([a, b, c, d], [ab, bd, ac, cd]);

    useGraphStore.setState({
      graph,
      entities: new Map([
        [a.id, a],
        [b.id, b],
        [c.id, c],
        [d.id, d],
      ]),
      edges: new Map([
        [ab.id, ab],
        [bd.id, bd],
        [ac.id, ac],
        [cd.id, cd],
      ]),
    });

    useGraphStore.getState().setShortestPathStartId(a.id);
    useGraphStore.getState().setShortestPathEndId(d.id);

    const state = useGraphStore.getState();
    expect(state.shortestPaths.length).toBe(2);
    // Expect both paths to be found: A->B->D and A->C->D
    expect(state.shortestPaths).toContainEqual([a.id, b.id, d.id]);
    expect(state.shortestPaths).toContainEqual([a.id, c.id, d.id]);
  });

  it("respects visibility toggle (ignores hidden nodes when visible-only is true)", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b"); // will be hidden
    const c = makeEntity("e-c");
    const d = makeEntity("e-d");
    
    const ab = makeEdge("edge-ab", a.id, b.id);
    const bc = makeEdge("edge-bc", b.id, c.id);
    const ad = makeEdge("edge-ad", a.id, d.id);
    const dc = makeEdge("edge-dc", d.id, c.id);

    const graph = makeGraph([a, b, c, d], [ab, bc, ad, dc]);

    useGraphStore.setState({
      graph,
      entities: new Map([
        [a.id, a],
        [b.id, b],
        [c.id, c],
        [d.id, d],
      ]),
      edges: new Map([
        [ab.id, ab],
        [bc.id, bc],
        [ad.id, ad],
        [dc.id, dc],
      ]),
      hiddenNodeIds: new Set([b.id]), // B is hidden
    });

    // When visible-only is true, it cannot use B, so it should find A->D->C
    useGraphStore.getState().setShortestPathVisibleOnly(true);
    useGraphStore.getState().setShortestPathStartId(a.id);
    useGraphStore.getState().setShortestPathEndId(c.id);

    let state = useGraphStore.getState();
    expect(state.shortestPaths).toEqual([[a.id, d.id, c.id]]);

    // When visible-only is false, it can use the full graph and should find both A->B->C and A->D->C
    useGraphStore.getState().setShortestPathVisibleOnly(false);
    state = useGraphStore.getState();
    expect(state.shortestPaths.length).toBe(2);
    expect(state.shortestPaths).toContainEqual([a.id, b.id, c.id]);
    expect(state.shortestPaths).toContainEqual([a.id, d.id, c.id]);
  });

  it("handles case where no path exists", () => {
    const a = makeEntity("e-a");
    const b = makeEntity("e-b");
    const graph = makeGraph([a, b], []);

    useGraphStore.setState({
      graph,
      entities: new Map([
        [a.id, a],
        [b.id, b],
      ]),
    });

    useGraphStore.getState().setShortestPathStartId(a.id);
    useGraphStore.getState().setShortestPathEndId(b.id);

    const state = useGraphStore.getState();
    expect(state.shortestPaths).toEqual([]);
    expect(state.nodeOverlay).toBeNull();
  });

  it("handles case where start node equals end node", () => {
    const a = makeEntity("e-a");
    const graph = makeGraph([a]);

    useGraphStore.setState({
      graph,
      entities: new Map([[a.id, a]]),
    });

    useGraphStore.getState().setShortestPathStartId(a.id);
    useGraphStore.getState().setShortestPathEndId(a.id);

    const state = useGraphStore.getState();
    expect(state.shortestPaths).toEqual([[a.id]]);
    expect(state.nodeOverlay).not.toBeNull();
  });
});
