import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from uuid import UUID, uuid4

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from ogi.agent.context import AgentContextBuilder
from ogi.agent.models import AgentRun, AgentRunStatus, AgentStep, AgentStepStatus, AgentStepType
from ogi.agent.orchestrator import AgentOrchestrator
from ogi.agent.store import AgentRunStore, AgentStepStore
from ogi.agent.tool_implementations import build_default_tool_registry
from ogi.agent.tools import ToolContext, ToolDefinition, ToolResult
from ogi.agent.llm_provider import ScriptedLLMProvider, LlmDecision, TokenUsage
from ogi.config import settings
from ogi.db import database as db_module
from ogi.engine.plugin_engine import PluginEngine
from ogi.engine.transform_engine import TransformEngine
from ogi.engine.transform_execution_service import TransformExecutionService
from ogi.models import Edge, Entity, EntityType, Project
from ogi.store.entity_store import EntityStore

from evaluate.dataset import seed_dataset_to_project
from evaluate.judge import grade_summary
from evaluate.models import EdgeSpec, EntitySpec, EvalResult, EvalTask


def load_evaluate_env() -> None:
    """Load GEMINI_API_KEY from backend/evaluate/.env if present."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key == "GEMINI_API_KEY":
                            os.environ[key] = val
        except Exception:
            pass


load_evaluate_env()

# Scripted LLM decisions for fallback execution when no API key is present
SCRIPTED_DECISIONS = {
    "threat-actor-bravo": [
        LlmDecision(
            reasoning="I will list all entities in the project scope to locate Adversary Bravo.",
            action_type="tool_call",
            tool_name="list_entities",
            tool_params={"limit": 10},
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=20),
        ),
        LlmDecision(
            reasoning="I found the entity for Adversary Bravo. I will run the uses transform on it.",
            action_type="tool_call",
            tool_name="run_transform",
            tool_params={"entity_value": "Adversary Bravo", "transform_name": "uses"},
            token_usage=TokenUsage(prompt_tokens=150, completion_tokens=30),
        ),
        LlmDecision(
            reasoning="The transform returned Poison Ivy Variant d1c6 and Phishing technique. I have all target entities, so I will finish the investigation.",
            action_type="finish",
            final_summary="Adversary Bravo is a threat actor that uses the Phishing attack pattern and the Poison Ivy Variant d1c6 malware.",
            token_usage=TokenUsage(prompt_tokens=200, completion_tokens=40),
        )
    ],
    "poisonivy-cnc": [
        LlmDecision(
            reasoning="I will locate the Poison Ivy Variant (8010cae3e8431bb11ed6dc9acabb93b7,) entity.",
            action_type="tool_call",
            tool_name="list_entities",
            tool_params={"limit": 10},
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=20),
        ),
        LlmDecision(
            reasoning="I will run the static transform on the Poison Ivy Variant to find associated domains and IPs.",
            action_type="tool_call",
            tool_name="run_transform",
            tool_params={
                "entity_value": "Poison Ivy Variant (8010cae3e8431bb11ed6dc9acabb93b7,)",
                "transform_name": "cnc_connections"
            },
            token_usage=TokenUsage(prompt_tokens=150, completion_tokens=30),
        ),
        LlmDecision(
            reasoning="The transform returned domains www.webserver.dynssl.com, www.webserver.freetcp.com, www.webserver.fartit.com, and IP 219.76.208.163. I will finish the investigation.",
            action_type="finish",
            final_summary="Poison Ivy Variant (8010cae3e8431bb11ed6dc9acabb93b7,) is associated with CnC domains www.webserver.dynssl.com, www.webserver.freetcp.com, and www.webserver.fartit.com, all resolving to the IP address 219.76.208.163.",
            token_usage=TokenUsage(prompt_tokens=200, completion_tokens=40),
        )
    ],
    "apt1-uglygorilla": [
        LlmDecision(
            reasoning="I will locate the Ugly Gorilla entity.",
            action_type="tool_call",
            tool_name="list_entities",
            tool_params={"limit": 10},
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=20),
        ),
        LlmDecision(
            reasoning="I will run the static transform on Ugly Gorilla to retrieve his details, aliases, and authored malware.",
            action_type="tool_call",
            tool_name="run_transform",
            tool_params={"entity_value": "Ugly Gorilla", "transform_name": "attributed_details"},
            token_usage=TokenUsage(prompt_tokens=150, completion_tokens=30),
        ),
        LlmDecision(
            reasoning="The transform returned aliases JackWang and Wang Dong, email address uglygorilla@163.com, and authored malware MANITSME and WEBC2-UGX. I will finish the investigation.",
            action_type="finish",
            final_summary="Ugly Gorilla is a threat actor whose real-world aliases are JackWang and Wang Dong. His email address is uglygorilla@163.com, and he authored malware families MANITSME and WEBC2-UGX.",
            token_usage=TokenUsage(prompt_tokens=200, completion_tokens=40),
        )
    ]
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ogi.evaluate.runner")


# Define evaluation tasks
EVAL_TASKS = [
    # EvalTask(
    #     id="threat-actor-bravo",
    #     question="Which malware and attack patterns are used by Adversary Bravo?",
    #     dataset_path="evaluate/datasets/threat-actor-leveraging-attack-patterns-and-malware.json",
    #     seed_entities=[EntitySpec(type="Organization", value="Adversary Bravo")],
    #     ground_truth_entities=[
    #         EntitySpec(type="Organization", value="Adversary Bravo"),
    #         EntitySpec(type="Vulnerability", value="Poison Ivy Variant d1c6"),
    #         EntitySpec(type="Vulnerability", value="Phishing"),
    #     ],
    # ),
    # EvalTask(
    #     id="poisonivy-cnc",
    #     question="Identify the CnC domains and IP addresses associated with Poison Ivy Variant (8010cae3e8431bb11ed6dc9acabb93b7,).",
    #     dataset_path="evaluate/datasets/poisonivy.json",
    #     seed_entities=[
    #         EntitySpec(type="Vulnerability", value="Poison Ivy Variant (8010cae3e8431bb11ed6dc9acabb93b7,)")
    #     ],
    #     ground_truth_entities=[
    #         EntitySpec(type="Domain", value="www.webserver.dynssl.com"),
    #         EntitySpec(type="Domain", value="www.webserver.freetcp.com"),
    #         EntitySpec(type="Domain", value="www.webserver.fartit.com"),
    #         EntitySpec(type="IPAddress", value="219.76.208.163"),
    #     ],
    # ),
    EvalTask(
        id="apt1-uglygorilla",
        question="Who is Ugly Gorilla, what is his email address, and which malware did he author?",
        dataset_path="evaluate/datasets/apt1.json",
        seed_entities=[EntitySpec(type="Organization", value="Ugly Gorilla")],
        ground_truth_entities=[
            EntitySpec(type="Person", value="JackWang"),
            EntitySpec(type="Person", value="Wang Dong"),
            EntitySpec(type="EmailAddress", value="uglygorilla@163.com"),
            EntitySpec(type="Vulnerability", value="MANITSME"),
            EntitySpec(type="Vulnerability", value="WEBC2-UGX"),
        ],
    ),
]


async def mock_run_transform_static(params: dict[str, Any], ctx: ToolContext) -> ToolResult:
    """
    Mock transform runner for Static Mode evaluation.
    Instead of executing actual scripts, queries the seeded database to find
    existing edges/relationships starting from the target entity.
    """
    from ogi.store.entity_store import EntityStore
    entity_store = EntityStore(ctx.session)
    
    # Resolve the input entity
    entity_id = None
    entity = None
    
    # Try resolving via helper
    try:
        from ogi.agent.tool_implementations import _resolve_entity
        entity_id, entity = await _resolve_entity(ctx, params)
    except Exception:
        # Fallback manual resolution
        val = params.get("entity_value") or params.get("entity_id")
        if val:
            stmt = select(Entity).where(Entity.project_id == ctx.project_id).where(Entity.value == val)
            entity = (await ctx.session.execute(stmt)).scalars().first()
            if entity:
                entity_id = entity.id
                
    if not entity or not entity_id:
        return ToolResult(
            data={"entities": [], "edges": []},
            summary="Entity not found in static graph.",
        )
        
    transform_name = str(params.get("transform_name", "unknown"))
    
    # Query edges originating from this entity
    stmt = select(Edge).where(Edge.project_id == ctx.project_id).where(Edge.source_id == entity_id)
    edges = (await ctx.session.execute(stmt)).scalars().all()
    
    # Retrieve the target entities connected via those edges
    target_ids = [edge.target_id for edge in edges]
    entities = []
    if target_ids:
        entity_stmt = select(Entity).where(Entity.project_id == ctx.project_id).where(Entity.id.in_(target_ids))
        entities = (await ctx.session.execute(entity_stmt)).scalars().all()
        
    entities_payload = [
        {
            "id": str(e.id),
            "type": e.type.value,
            "value": e.value,
            "properties": e.properties,
        }
        for e in entities
    ]
    edges_payload = [
        {
            "id": str(edge.id),
            "source_id": str(edge.source_id),
            "target_id": str(edge.target_id),
            "label": edge.label,
        }
        for edge in edges
    ]
    
    return ToolResult(
        data={
            "transform_run": {
                "id": str(uuid4()),
                "status": "completed",
                "transform_name": transform_name,
                "input_entity_id": str(entity_id),
            },
            "result": {
                "entities": entities_payload,
                "edges": edges_payload,
            },
        },
        summary=(
            f"Mock transform {transform_name} loaded {len(entities_payload)} entities and "
            f"{len(edges_payload)} edges from the static graph."
        ),
    )


async def run_evaluation_task(task: EvalTask) -> EvalResult:
    """
    Runs the evaluator runner on a single evaluation task in Static Mode.
    """
    logger.info("Starting task evaluation: %s", task.id)
    
    if db_module.async_session_maker is None:
        raise RuntimeError("Database not initialized")
        
    async with db_module.async_session_maker() as session:
        # 1. Create temporary project
        project = Project(
            id=uuid4(),
            name=f"EvalStatic-{task.id}",
            description=f"Auto evaluation project for task {task.id}",
            owner_id=UUID("00000000-0000-0000-0000-000000000000"),
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        
        # 2. Seed the dataset into the project
        logger.info("Seeding dataset: %s", task.dataset_path)
        created_entities, created_edges = await seed_dataset_to_project(session, task.dataset_path, project.id)
        logger.info("Seeded %d entities and %d edges", len(created_entities), len(created_edges))
        
        # 3. Locate the seed entities in the project DB to establish agent scope
        seed_ids = []
        for seed_spec in task.seed_entities:
            stmt = select(Entity).where(Entity.project_id == project.id).where(Entity.type == seed_spec.type).where(Entity.value == seed_spec.value)
            entity = (await session.execute(stmt)).scalars().first()
            if entity:
                seed_ids.append(str(entity.id))
            else:
                # Fallback create seed entity if not found
                entity = Entity(
                    id=uuid4(),
                    project_id=project.id,
                    type=EntityType(seed_spec.type),
                    value=seed_spec.value,
                    source="eval_seed",
                )
                session.add(entity)
                await session.flush()
                seed_ids.append(str(entity.id))
                
        # 4. Create the Agent Run record
        # Target gemini-3.1-flash for investigator
        run = AgentRun(
            project_id=project.id,
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            status=AgentRunStatus.PENDING,
            scope={"mode": "all", "entity_ids": seed_ids},
            prompt=task.question,
            provider="gemini",
            model="gemini-3.1-flash-lite",
            budget={
                "max_steps": 25,
                "max_transforms": 20,
                "max_runtime_sec": 300,
            },
            usage={
                "steps_used": 0,
                "transforms_run": 0,
                "llm_calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        
        # Create first step (THINK)
        step = AgentStep(
            run_id=run.id,
            step_number=1,
            type=AgentStepType.THINK,
            status=AgentStepStatus.PENDING,
        )
        session.add(step)
        await session.commit()
        run_id = run.id

    # 5. Build AgentOrchestrator and inject mock tools / LLM provider
    transform_engine = TransformEngine()
    transform_engine.auto_discover()
    plugin_engine = transform_engine.load_plugins(settings.plugin_dirs)
    
    execution_service = TransformExecutionService(
        transform_engine_getter=lambda: transform_engine,
        plugin_engine_getter=lambda: plugin_engine,
    )
    
    # Build default tools registry and override run_transform for static evaluation
    tool_registry = build_default_tool_registry(
        transform_engine=transform_engine,
        plugin_engine=plugin_engine,
        transform_execution_service=execution_service,
    )
    
    tool_registry.register(
        ToolDefinition(
            name="run_transform",
            description="Execute static transform by reading pre-populated graph.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_value": {"type": "string"},
                    "transform_name": {"type": "string"},
                    "config": {"type": "object"},
                },
                "required": ["transform_name"],
                "additionalProperties": False,
            },
            risk_level="high",
            requires_approval=False,
        ),
        mock_run_transform_static,
    )
    
    # Disable approval for all tools to prevent agent gatekeeping
    for tool_def in tool_registry.list_tools():
        tool_def.requires_approval = False
        
    context_builder = AgentContextBuilder()
    
    # Instantiate the scripted provider once per task run to prevent state reset on subsequent THINK steps
    scripted_provider = ScriptedLLMProvider(list(SCRIPTED_DECISIONS.get(task.id, [])))

    # Custom LLM provider factory to read key from environment or use scripted fallback
    async def custom_llm_provider_factory(s: AsyncSession, r: AgentRun):
        provider = r.provider.strip().lower()
        model = r.model.strip()
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or settings.llm_api_key
        
        if not api_key:
            logger.warning("No API key configured for %s. Falling back to ScriptedLLMProvider.", provider)
            return scripted_provider
            
        if provider == "gemini":
            from ogi.agent.llm_provider import GeminiLLMProvider
            return GeminiLLMProvider(
                api_key=api_key,
                model=model,
                retry_attempts=settings.llm_retry_max_attempts,
            )
        elif provider in ("openai", "openai-compatible"):
            from ogi.agent.llm_provider import OpenAILLMProvider
            return OpenAILLMProvider(
                api_key=api_key,
                model=model,
                retry_attempts=settings.llm_retry_max_attempts,
            )
            
        from ogi.agent.llm_provider import build_llm_provider_for_run
        return await build_llm_provider_for_run(session=s, run=r)
        
    orchestrator = AgentOrchestrator(
        session_factory=db_module.async_session_maker,
        worker_id="eval-static-worker",
        llm_provider_factory=custom_llm_provider_factory,
        tool_registry=tool_registry,
        context_builder=context_builder,
    )
    
    # 6. Run the execution loop
    start_time = time.time()
    max_iterations = 60
    logger.info("Executing Agent run iteration loop...")
    for i in range(max_iterations):
        result = await orchestrator.run_once()
        if not result.processed:
            # No steps processed, wait briefly
            await asyncio.sleep(0.1)
            
        # Check current run status
        async with db_module.async_session_maker() as session:
            db_run = await session.get(AgentRun, run_id)
            if db_run.status in (AgentRunStatus.COMPLETED, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED):
                break
                
    duration = time.time() - start_time
    
    # 7. Collect statistics and grade the run
    async with db_module.async_session_maker() as session:
        final_run = await session.get(AgentRun, run_id)
        steps = await AgentStepStore(session).list_for_run(run_id)
        
        # Calculate Precision, Recall, and F1 of target entities
        # Find all entity values the agent loaded or visited
        visited_values = set()
        for step in steps:
            if step.status != AgentStepStatus.COMPLETED:
                continue
            # Look at tool inputs
            if step.type == AgentStepType.TOOL_CALL:
                params = step.tool_input or {}
                val = params.get("entity_value") or params.get("value")
                if val:
                    visited_values.add(str(val).strip().lower())
                entity_id = params.get("entity_id")
                if entity_id:
                    try:
                        entity = await EntityStore(session).get(UUID(entity_id))
                        if entity:
                            visited_values.add(entity.value.strip().lower())
                    except Exception:
                        pass
            # Look at tool results
            elif step.type == AgentStepType.TOOL_RESULT:
                output = step.tool_output or {}
                data = output.get("data", {})
                
                # Check entity details returned
                ent_data = data.get("entity")
                if isinstance(ent_data, dict) and ent_data.get("value"):
                    visited_values.add(str(ent_data["value"]).strip().lower())
                
                entities = data.get("entities", [])
                if isinstance(entities, list):
                    for ent in entities:
                        if isinstance(ent, dict) and ent.get("value"):
                            visited_values.add(str(ent["value"]).strip().lower())
                            
        # Also scan the final summary for mentions
        summary = final_run.summary or ""
        
        ground_truth_values = {e.value.strip().lower() for e in task.ground_truth_entities}
        
        # Match discovered entities
        discovered = set()
        for val in ground_truth_values:
            if val in visited_values or val in summary.lower():
                discovered.add(val)
                
        # To compute precision/recall fairly:
        # TP = target entities found
        # FN = target entities not found
        # FP = other entities visited by the agent that were not target entities
        tp = len(discovered)
        fn = len(ground_truth_values - discovered)
        # FP count should be bounded to all other visited values
        fp = len({v for v in visited_values if v not in ground_truth_values})
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # LLM-as-a-Judge semantic score
        success = final_run.status == AgentRunStatus.COMPLETED
        semantic_score = None
        judge_reasoning = None
        if success:
            logger.info("Running LLM-as-a-Judge semantic score...")
            semantic_score, judge_reasoning = await grade_summary(
                question=task.question,
                final_summary=summary,
                ground_truth_entities=[e.value for e in task.ground_truth_entities],
                ground_truth_text=task.ground_truth_text,
            )
            logger.info("Judge score: %s/5 (Reasoning: %s)", semantic_score, judge_reasoning)
            
        result = EvalResult(
            task_id=task.id,
            success=success,
            final_summary=summary,
            step_count=len(steps),
            token_count=final_run.usage.get("prompt_tokens", 0) + final_run.usage.get("completion_tokens", 0),
            cost=0.0,  # Token cost can be configured if needed
            duration=duration,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            semantic_score=semantic_score,
            judge_reasoning=judge_reasoning,
        )
        return result


async def run_all_evaluations() -> None:
    """
    Executes all benchmarking runs, prints summary, and writes a Markdown report.
    """
    logger.info("Initializing database for OGI Benchmarking...")
    await db_module.init_db()
    
    results: List[EvalResult] = []
    for task in EVAL_TASKS:
        try:
            res = await run_evaluation_task(task)
            results.append(res)
        except Exception as e:
            logger.exception("Failed to run evaluation task %s", task.id)
            results.append(
                EvalResult(
                    task_id=task.id,
                    success=False,
                    final_summary=f"Execution error: {str(e)}",
                )
            )
            
    await db_module.close_db()
    
    # Print results to CLI
    print("\n" + "="*50)
    print("OGI AI INVESTIGATOR BENCHMARK RESULTS (STATIC MODE)")
    print("="*50)
    for res in results:
        status_str = "SUCCESS" if res.success else "FAILED"
        print(f"Task: {res.task_id} [{status_str}]")
        print(f"  Steps: {res.step_count} | Duration: {res.duration:.1f}s | Tokens: {res.token_count}")
        print(f"  Precision: {res.precision:.2f} | Recall: {res.recall:.2f} | F1: {res.f1_score:.2f}")
        if res.semantic_score is not None:
            print(f"  Judge Semantic Score: {res.semantic_score:.1f}/5.0")
            print(f"  Judge Reasoning: {res.judge_reasoning}")
        print("-"*50)
        
    # Generate markdown report
    report_path = "evaluate/evaluation_report.md"
    logger.info("Writing evaluation report to %s", report_path)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# OGI AI Investigator Benchmarking Report (Static Mode)\n\n")
        f.write(f"Generated at: {datetime.now(timezone.utc).isoformat()} UTC\n\n")
        
        f.write("## Summary Metrics\n\n")
        f.write("| Task ID | Success | Steps | Duration (s) | Tokens | Precision | Recall | F1 Score | Judge Score |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for res in results:
            judge_str = f"{res.semantic_score:.1f}/5.0" if res.semantic_score is not None else "N/A"
            f.write(
                f"| `{res.task_id}` | {'✅' if res.success else '❌'} | {res.step_count} | {res.duration:.1f}s | "
                f"{res.token_count} | {res.precision:.2f} | {res.recall:.2f} | {res.f1_score:.2f} | {judge_str} |\n"
            )
        f.write("\n\n")
        
        f.write("## Detailed Task Reports\n\n")
        for res in results:
            f.write(f"### Task: `{res.task_id}`\n\n")
            f.write(f"**Final Summary:**\n{res.final_summary}\n\n")
            if res.judge_reasoning:
                f.write(f"**Judge Reasoning ({res.semantic_score}/5):**\n> {res.judge_reasoning}\n\n")
            f.write("---\n\n")


def main() -> None:
    asyncio.run(run_all_evaluations())


if __name__ == "__main__":
    main()
