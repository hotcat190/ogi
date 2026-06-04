"""``ogi dev`` sub-commands for the CLI."""
from __future__ import annotations

import asyncio
import random
import uuid
import time
import os
from datetime import datetime, timezone
from typing import List, Set, Tuple
import typer
from sqlmodel import select

from ogi.db import database as db
from ogi.models import Project, Entity, Edge, EntityType
from ogi.models.project import ProjectCreate
from ogi.store.project_store import ProjectStore
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore
from ogi.engine.graph_engine import GraphEngine
from ogi.engine import analysis

app = typer.Typer(help="Developer utilities for graph generation and performance testing.")

ENTITY_TYPES = [
    EntityType.DOMAIN,
    EntityType.IP_ADDRESS,
    EntityType.EMAIL_ADDRESS,
    EntityType.PERSON,
    EntityType.ORGANIZATION,
    EntityType.URL,
]

def _run(coro) -> None:
    asyncio.run(coro)

async def _seed_graph(name: str, nodes_count: int, edges_count: int, topology: str) -> None:
    await db.init_db()
    
    anon_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    
    async with db.async_session_maker() as session:
        project_store = ProjectStore(session)
        
        # Check if project exists, delete first to refresh
        stmt = select(Project).where(Project.name == name)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            typer.echo(f"Deleting existing project '{name}'...")
            await project_store.delete(existing.id)
            
        project = await project_store.create(
            ProjectCreate(name=name, description=f"Auto-generated {topology} graph", is_public=True),
            owner_id=anon_id
        )
        project_id = project.id
        
        typer.echo(f"Created project '{name}' with ID: {project_id}")
        
        # Generate Entities
        entities: List[Entity] = []
        for i in range(nodes_count):
            etype = ENTITY_TYPES[i % len(ENTITY_TYPES)]
            if etype == EntityType.DOMAIN:
                val = f"domain-{i}.com"
            elif etype == EntityType.IP_ADDRESS:
                val = f"192.168.{1 + (i // 254) % 254}.{1 + i % 254}"
            elif etype == EntityType.EMAIL_ADDRESS:
                val = f"user-{i}@mail.com"
            elif etype == EntityType.PERSON:
                val = f"Person {i}"
            elif etype == EntityType.ORGANIZATION:
                val = f"Org {i}"
            else:
                val = f"https://site-{i}.com/page"
                
            entities.append(Entity(
                id=uuid.uuid4(),
                type=etype,
                value=val,
                project_id=project_id,
                source="generator",
                origin_source="generator",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            
        # Bulk insert entities
        for ent in entities:
            session.add(ent)
        await session.flush()
        
        # Generate Edges
        edges: List[Edge] = []
        edge_pairs: Set[Tuple[int, int]] = set()
        
        def add_edge_pair(src_idx: int, tgt_idx: int) -> bool:
            if src_idx == tgt_idx:
                return False
            pair = (min(src_idx, tgt_idx), max(src_idx, tgt_idx))
            if pair in edge_pairs:
                return False
            edge_pairs.add(pair)
            
            edges.append(Edge(
                id=uuid.uuid4(),
                source_id=entities[src_idx].id,
                target_id=entities[tgt_idx].id,
                label="connected_to",
                project_id=project_id,
                created_at=datetime.now(timezone.utc)
            ))
            return True
            
        if topology == "scale-free":
            # Albert-Barabasi Preferential Attachment
            m0 = min(3, nodes_count)
            for i in range(m0):
                for j in range(i + 1, m0):
                    add_edge_pair(i, j)
                    
            degrees = [0] * nodes_count
            for u, v in edge_pairs:
                degrees[u] += 1
                degrees[v] += 1
                
            m = max(1, min(3, int(edges_count / nodes_count)))
            for i in range(m0, nodes_count):
                total_deg = sum(degrees[:i])
                if total_deg == 0:
                    targets = random.sample(range(i), min(m, i))
                else:
                    targets = []
                    available = list(range(i))
                    while len(targets) < min(m, i):
                        w = [degrees[x] for x in available]
                        if sum(w) == 0:
                            chosen = random.choice(available)
                        else:
                            chosen = random.choices(available, weights=w, k=1)[0]
                        targets.append(chosen)
                        available.remove(chosen)
                        
                for t in targets:
                    if add_edge_pair(i, t):
                        degrees[i] += 1
                        degrees[t] += 1
                        
            # Fill remaining edges randomly to hit exact edge count
            attempts = 0
            while len(edges) < edges_count and attempts < edges_count * 10:
                attempts += 1
                u = random.randint(0, nodes_count - 1)
                v = random.randint(0, nodes_count - 1)
                add_edge_pair(u, v)
                
        elif topology == "clustered":
            K = 5
            cluster_size = max(1, nodes_count // K)
            node_clusters = [i // cluster_size for i in range(nodes_count)]
            
            intra_target = int(edges_count * 0.9)
            
            # Intra-cluster edges
            attempts = 0
            while len(edges) < intra_target and attempts < edges_count * 10:
                attempts += 1
                cluster = random.randint(0, K - 1)
                start_idx = cluster * cluster_size
                end_idx = min(nodes_count - 1, start_idx + cluster_size - 1)
                if end_idx - start_idx < 1:
                    continue
                u = random.randint(start_idx, end_idx)
                v = random.randint(start_idx, end_idx)
                add_edge_pair(u, v)
                
            # Inter-cluster edges
            attempts = 0
            while len(edges) < edges_count and attempts < edges_count * 10:
                attempts += 1
                u = random.randint(0, nodes_count - 1)
                v = random.randint(0, nodes_count - 1)
                if node_clusters[u] != node_clusters[v]:
                    add_edge_pair(u, v)
                    
        else:
            # Random Erdős-Rényi
            attempts = 0
            while len(edges) < edges_count and attempts < edges_count * 10:
                attempts += 1
                u = random.randint(0, nodes_count - 1)
                v = random.randint(0, nodes_count - 1)
                add_edge_pair(u, v)
                
        # Bulk insert edges
        for edg in edges:
            session.add(edg)
            
        await session.commit()
        typer.echo(f"Seeded {len(entities)} entities and {len(edges)} edges successfully.")
        
    await db.close_db()

async def _benchmark_graph(project_name: str) -> None:
    await db.init_db()
    
    async with db.async_session_maker() as session:
        stmt = select(Project).where(Project.name == project_name)
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            typer.echo(f"Project '{project_name}' not found.")
            await db.close_db()
            raise typer.Exit(1)
            
        project_id = project.id
        
        entity_store = EntityStore(session)
        edge_store = EdgeStore(session)
        
        entities = await entity_store.list_by_project(project_id)
        edges = await edge_store.list_by_project(project_id)
        
        engine = GraphEngine()
        for ent in entities:
            engine.add_entity(ent)
        for edg in edges:
            try:
                engine.add_edge(edg)
            except ValueError:
                pass
                
        n = len(entities)
        m = len(edges)
        
        results = []
        
        def run_algo(name: str, fn):
            t0 = time.perf_counter()
            fn()
            t1 = time.perf_counter()
            duration = (t1 - t0) * 1000
            results.append((name, duration))
            typer.echo(f"  {name:<25}: {duration:8.2f} ms")
            
        typer.echo(f"\nBenchmarking Project: {project_name} (Nodes: {n}, Edges: {m})")
        typer.echo("=" * 45)
        
        run_algo("Degree Centrality", lambda: analysis.degree_centrality(engine))
        run_algo("Connected Components", lambda: analysis.connected_components(engine))
        run_algo("PageRank (10 iters)", lambda: analysis.pagerank(engine, iterations=10))
        
        if n <= 3000:
            run_algo("Closeness Centrality", lambda: analysis.closeness_centrality(engine))
            run_algo("Betweenness Centrality", lambda: analysis.betweenness_centrality(engine))
        else:
            typer.echo("  Closeness Centrality     : Skipped (nodes > 3000)")
            typer.echo("  Betweenness Centrality   : Skipped (nodes > 3000)")
            results.append(("Closeness Centrality", -1))
            results.append(("Betweenness Centrality", -1))
            
        # Write to log file
        os.makedirs("logs", exist_ok=True)
        log_path = "logs/benchmark.log"
        
        with open(log_path, "a") as f:
            f.write(f"\n[{datetime.now().isoformat()}] Project: {project_name} | Nodes: {n} | Edges: {m}\n")
            for name, dur in results:
                dur_str = f"{dur:.2f} ms" if dur >= 0 else "Skipped"
                f.write(f"  {name:<25}: {dur_str}\n")
                
        typer.echo(f"\nResults appended to {log_path}\n")
        
    await db.close_db()

@app.command()
def seed(
    name: str = typer.Option(..., "--name", "-n", help="Name of project to seed"),
    nodes: int = typer.Option(500, "--nodes", help="Number of nodes to seed"),
    edges: int = typer.Option(1500, "--edges", help="Number of edges to seed"),
    topology: str = typer.Option("scale-free", "--topology", help="Graph topology: scale-free, clustered, random"),
) -> None:
    """Seed project with generated graph."""
    if topology not in ("scale-free", "clustered", "random"):
        typer.echo(f"Error: Unknown topology '{topology}'")
        raise typer.Exit(1)
        
    _run(_seed_graph(name, nodes, edges, topology))

@app.command()
def benchmark(
    project_name: str = typer.Option(..., "--project-name", "-p", help="Name of project to benchmark"),
) -> None:
    """Benchmark backend centrality and clustering on project graph."""
    _run(_benchmark_graph(project_name))
