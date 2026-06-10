import { useState, useEffect, useMemo } from "react";
import { BarChart3, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import { api } from "../api/client";
import { getSigmaRef } from "../stores/sigmaRef";
import { type Entity } from "../types/entity";

interface AlgorithmOption {
  value: string;
  label: string;
  description: string;
  type: "scores" | "communities";
}

const ALGORITHMS: AlgorithmOption[] = [
  { value: "degree_centrality", label: "Degree Centrality", description: "Nodes with most connections", type: "scores" },
  { value: "betweenness_centrality", label: "Betweenness Centrality", description: "Nodes bridging communities", type: "scores" },
  { value: "closeness_centrality", label: "Closeness Centrality", description: "Nodes closest to all others", type: "scores" },
  { value: "pagerank", label: "PageRank", description: "Most important nodes", type: "scores" },
  { value: "connected_components", label: "Connected Components", description: "Find isolated clusters", type: "communities" },
  { value: "shortest_path", label: "Shortest Path Finder", description: "Find path between two nodes", type: "scores" },
];

const COMMUNITY_COLORS = [
  "#6366f1", "#22d3ee", "#f59e0b", "#10b981", "#f472b6",
  "#a78bfa", "#fb923c", "#34d399", "#60a5fa", "#94a3b8",
];

interface NodeAutocompleteProps {
  placeholder: string;
  selectedId: string | null;
  onSelect: (nodeId: string | null) => void;
  entities: Map<string, Entity>;
}

function NodeAutocomplete({ placeholder, selectedId, onSelect, entities }: NodeAutocompleteProps) {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);

  const selectedEntity = selectedId ? entities.get(selectedId) : null;

  const suggestions = useMemo(() => {
    if (!query.trim()) {
      return Array.from(entities.entries()).slice(0, 10);
    }
    const cleanQuery = query.toLowerCase();
    const matches: [string, Entity][] = [];
    for (const [id, entity] of entities.entries()) {
      if (
        entity.value.toLowerCase().includes(cleanQuery) ||
        entity.type.toLowerCase().includes(cleanQuery)
      ) {
        matches.push([id, entity]);
        if (matches.length >= 10) break;
      }
    }
    return matches;
  }, [query, entities]);

  return (
    <div className="relative">
      {selectedEntity ? (
        <div className="flex items-center justify-between px-2 py-1.5 bg-surface border border-accent/30 rounded text-xs font-sans">
          <div className="min-w-0 flex-1">
            <p className="font-medium text-text truncate">{selectedEntity.value}</p>
            <p className="text-[9px] text-text-muted uppercase font-mono">{selectedEntity.type}</p>
          </div>
          <button
            onClick={() => {
              onSelect(null);
              setQuery("");
            }}
            className="p-1 hover:bg-surface-hover rounded text-text-muted hover:text-text shrink-0"
          >
            <X size={12} />
          </button>
        </div>
      ) : (
        <>
          <input
            type="text"
            placeholder={placeholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setTimeout(() => setFocused(false), 200)}
            className="w-full px-2 py-1.5 text-xs bg-surface border border-border rounded text-text focus:outline-none focus:border-accent font-medium placeholder:text-text-muted/50 font-sans"
          />
          {focused && suggestions.length > 0 && (
            <div className="absolute z-50 left-0 right-0 mt-1 bg-surface border border-border rounded shadow-lg max-h-48 overflow-y-auto font-sans">
              {suggestions.map(([id, entity]) => (
                <button
                  key={id}
                  onMouseDown={() => {
                    onSelect(id);
                    setQuery("");
                  }}
                  className="w-full text-left px-2 py-1.5 hover:bg-surface-hover text-xs flex flex-col transition-colors border-b border-border/50 last:border-0"
                >
                  <span className="font-medium text-text truncate">{entity.value}</span>
                  <span className="text-[9px] text-text-muted uppercase font-mono">{entity.type}</span>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function AnalysisPanel() {
  const [selected, setSelected] = useState(ALGORITHMS[0].value);
  const [running, setRunning] = useState(false);

  const { currentProject } = useProjectStore();
  const {
    entities,
    setNodeOverlay,
    analysisResults: results,
    setAnalysisResults: setResults,
    selectedNodeIds,
    shortestPathStartId,
    shortestPathEndId,
    shortestPaths,
    currentPathIndex,
    shortestPathVisibleOnly,
    setShortestPathStartId,
    setShortestPathEndId,
    setShortestPathVisibleOnly,
    setCurrentPathIndex,
    clearShortestPath,
    selectNode,
    graph,
  } = useGraphStore();

  useEffect(() => {
    if (selected === "shortest_path") {
      const selectedArr = Array.from(selectedNodeIds);
      if (selectedArr.length === 1) {
        if (shortestPathStartId !== selectedArr[0]) {
          setShortestPathStartId(selectedArr[0]);
        }
      } else if (selectedArr.length === 2) {
        if (shortestPathStartId !== selectedArr[0] || shortestPathEndId !== selectedArr[1]) {
          setShortestPathStartId(selectedArr[0]);
          setShortestPathEndId(selectedArr[1]);
        }
      }
    }
  }, [selectedNodeIds, selected, shortestPathStartId, shortestPathEndId, setShortestPathStartId, setShortestPathEndId]);

  const handleRun = async () => {
    if (!currentProject) return;
    if (selected === "shortest_path") return;
    setRunning(true);
    try {
      const result = await api.graph.analyze(currentProject.id, selected);
      const algo = ALGORITHMS.find((a) => a.value === selected);
      setResults({ type: algo?.type ?? "scores", ...result });

      if (result.scores) {
        const maxScore = Math.max(...Object.values(result.scores), 0.001);
        setNodeOverlay({ type: "analysis-scores", scores: result.scores, maxScore });
        toast.success(`${algo?.label}: analysis complete`);
      } else if (result.communities) {
        const nodeToColor: Record<string, string> = {};
        result.communities.forEach((community, i) => {
          const color = COMMUNITY_COLORS[i % COMMUNITY_COLORS.length];
          for (const nodeId of community) {
            nodeToColor[nodeId] = color;
          }
        });
        setNodeOverlay({ type: "analysis-communities", colors: nodeToColor });
        toast.success(`Found ${result.communities.length} connected components`);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Analysis failed: ${msg}`);
    } finally {
      setRunning(false);
    }
  };

  const handleReset = () => {
    setResults(null);
    setNodeOverlay(null);
  };

  const handleSelectAlgo = (val: string) => {
    setSelected(val);
    handleReset();
    clearShortestPath();
  };

  // Sorted top entities for score results
  const topEntities = results?.scores
    ? Object.entries(results.scores)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 10)
        .map(([id, score]) => ({
          id,
          value: entities.get(id)?.value ?? id.slice(0, 8),
          type: entities.get(id)?.type ?? "unknown",
          score: score.toFixed(4),
        }))
    : [];

  return (
    <div className="flex h-full font-sans">
      {/* Algorithm selector */}
      <div className="w-56 border-r border-border overflow-y-auto">
        <div className="p-2 border-b border-border">
          <p className="text-xs font-semibold text-text-muted">Graph Analysis</p>
        </div>
        <div className="p-1">
          {ALGORITHMS.map((algo) => (
            <button
              key={algo.value}
              onClick={() => handleSelectAlgo(algo.value)}
              className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
                selected === algo.value
                  ? "bg-surface-hover text-text"
                  : "text-text-muted hover:bg-surface-hover"
              }`}
            >
              <p className="font-medium text-left">{algo.label}</p>
              <p className="text-[10px] text-text-muted text-left">{algo.description}</p>
            </button>
          ))}
        </div>
        <div className="p-2 border-t border-border flex gap-1">
          {selected !== "shortest_path" ? (
            <>
              <button
                onClick={handleRun}
                disabled={running}
                className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50 transition-colors"
              >
                {running ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <BarChart3 size={12} />
                )}
                Run
              </button>
              {results && (
                <button
                  onClick={handleReset}
                  className="px-2 py-1.5 text-xs text-text-muted border border-border rounded hover:bg-surface-hover transition-colors"
                >
                  Reset
                </button>
              )}
            </>
          ) : (
            <button
              onClick={clearShortestPath}
              className="flex-1 px-2 py-1.5 text-xs text-text-muted border border-border rounded hover:bg-surface-hover transition-colors"
            >
              Clear Pathfinder
            </button>
          )}
        </div>
      </div>

      {/* Results / Pathfinder Config */}
      <div className="flex-1 overflow-y-auto p-3">
        {selected === "shortest_path" ? (
          <div className="space-y-4 max-w-lg">
            <div>
              <h3 className="text-sm font-semibold text-text mb-1">Shortest Path Finder</h3>
              <p className="text-xs text-text-muted">
                Compute the shortest path of minimal hops between two nodes. Select nodes below or click/right-click nodes on the canvas.
              </p>
            </div>

            {/* Inputs */}
            <div className="grid grid-cols-2 gap-4">
              <div className="relative">
                <label className="block text-[10px] uppercase font-semibold text-text-muted mb-1">Start Node</label>
                <NodeAutocomplete
                  placeholder="Select start node..."
                  selectedId={shortestPathStartId}
                  onSelect={setShortestPathStartId}
                  entities={entities}
                />
              </div>

              <div className="relative">
                <label className="block text-[10px] uppercase font-semibold text-text-muted mb-1">End Node</label>
                <NodeAutocomplete
                  placeholder="Select end node..."
                  selectedId={shortestPathEndId}
                  onSelect={setShortestPathEndId}
                  entities={entities}
                />
              </div>
            </div>

            {/* Toggle */}
            <div className="flex items-center gap-2 py-1">
              <input
                id="visible-only-toggle"
                type="checkbox"
                checked={shortestPathVisibleOnly}
                onChange={(e) => setShortestPathVisibleOnly(e.target.checked)}
                className="rounded border-border bg-surface-hover text-accent focus:ring-accent"
              />
              <label htmlFor="visible-only-toggle" className="text-xs text-text cursor-pointer select-none">
                Only search visible elements
              </label>
            </div>

            {/* Results */}
            <div className="border-t border-border pt-4">
              {!shortestPathStartId || !shortestPathEndId ? (
                <p className="text-xs text-text-muted italic">
                  Select start and end nodes to compute shortest path.
                </p>
              ) : shortestPaths.length === 0 ? (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
                  No path found between the selected nodes.
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Pager */}
                  <div className="flex items-center justify-between bg-surface-hover p-2 rounded border border-border">
                    <span className="text-xs font-medium text-text">
                      Found {shortestPaths.length} shortest path{shortestPaths.length > 1 ? "s" : ""}
                    </span>
                    {shortestPaths.length > 1 && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setCurrentPathIndex((currentPathIndex - 1 + shortestPaths.length) % shortestPaths.length)}
                          className="px-2 py-1 hover:bg-surface border border-border rounded text-text text-xs transition-colors"
                        >
                          &larr;
                        </button>
                        <span className="text-xs text-text font-medium">
                          Path {currentPathIndex + 1} of {shortestPaths.length}
                        </span>
                        <button
                          onClick={() => setCurrentPathIndex((currentPathIndex + 1) % shortestPaths.length)}
                          className="px-2 py-1 hover:bg-surface border border-border rounded text-text text-xs transition-colors"
                        >
                          &rarr;
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Path steps */}
                  <div>
                    <h4 className="text-[10px] uppercase font-semibold text-text-muted mb-2 font-sans">
                      Path Steps (Click node to zoom)
                    </h4>
                    <div className="space-y-1">
                      {shortestPaths[currentPathIndex]?.map((nodeId, idx) => {
                        const entity = entities.get(nodeId);
                        const isStart = nodeId === shortestPathStartId;
                        const isEnd = nodeId === shortestPathEndId;
                        return (
                          <div key={nodeId} className="flex flex-col font-sans">
                            {idx > 0 && (
                              <div className="text-[10px] text-text-muted px-4 py-0.5 border-l border-dashed border-border ml-1.5 my-0.5">
                                &darr;
                              </div>
                            )}
                            <button
                              onClick={() => {
                                selectNode(nodeId);
                                const sigma = getSigmaRef();
                                if (sigma) {
                                  const displayData = sigma.getNodeDisplayData(nodeId);
                                  const target = displayData
                                    ? { x: displayData.x, y: displayData.y }
                                    : graph.hasNode(nodeId)
                                      ? (() => {
                                          const attrs = graph.getNodeAttributes(nodeId);
                                          return { x: Number(attrs.x) || 0, y: Number(attrs.y) || 0 };
                                        })()
                                      : null;
                                  if (target) {
                                    const camera = sigma.getCamera();
                                    const current = camera.getState();
                                    camera.animate(
                                      {
                                        x: target.x,
                                        y: target.y,
                                        ratio: Math.min(current.ratio, 0.8),
                                      },
                                      { duration: 300 }
                                    );
                                  }
                                }
                              }}
                              className={`flex items-center gap-2 w-full text-left px-3 py-2 rounded border transition-colors ${
                                isStart
                                  ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-400 hover:bg-yellow-500/20"
                                  : isEnd
                                    ? "bg-green-500/10 border-green-500/20 text-green-400 hover:bg-green-500/20"
                                    : "bg-surface border-border text-text hover:bg-surface-hover"
                              }`}
                            >
                              <div
                                className={`w-4 h-4 rounded-full shrink-0 flex items-center justify-center text-[9px] font-bold text-white ${
                                  isStart
                                    ? "bg-yellow-500"
                                    : isEnd
                                      ? "bg-green-500"
                                      : "bg-text-muted"
                                }`}
                              >
                                {idx + 1}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-xs font-semibold truncate">
                                  {entity?.value ?? nodeId}
                                </p>
                                <p className="text-[10px] text-text-muted uppercase font-mono">
                                  {entity?.type ?? "unknown"}
                                </p>
                              </div>
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : !results ? (
          <div className="flex flex-col items-center justify-center h-full gap-1">
            <BarChart3 size={20} className="text-text-muted" />
            <p className="text-xs text-text-muted">Select an algorithm and click Run</p>
          </div>
        ) : results.type === "scores" && topEntities.length > 0 ? (
          <div>
            <h4 className="text-[10px] uppercase text-text-muted mb-2">
              Top Entities by Score
            </h4>
            <div className="space-y-1">
              {topEntities.map((item, i) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-text-muted w-4">{i + 1}.</span>
                    <span className="text-text">{item.value}</span>
                    <span className="text-[10px] text-text-muted">({item.type})</span>
                  </div>
                  <span className="text-accent font-mono text-[10px]">{item.score}</span>
                </div>
              ))}
            </div>
          </div>
        ) : results.type === "communities" && results.communities ? (
          <div>
            <h4 className="text-[10px] uppercase text-text-muted mb-2">
              Communities ({results.communities.length})
            </h4>
            <div className="space-y-2">
              {results.communities.map((community, i) => (
                <div key={i} className="p-2 border border-border rounded">
                  <div className="flex items-center gap-2 mb-1">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COMMUNITY_COLORS[i % COMMUNITY_COLORS.length] }}
                    />
                    <span className="text-xs font-medium text-text">
                      Group {i + 1} ({community.length} entities)
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {community.slice(0, 8).map((id) => (
                      <span key={id} className="text-[10px] text-text-muted">
                        {entities.get(id)?.value ?? id.slice(0, 8)}
                      </span>
                    ))}
                    {community.length > 8 && (
                      <span className="text-[10px] text-text-muted">
                        +{community.length - 8} more
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
