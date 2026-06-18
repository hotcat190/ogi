import os
import pytest
from uuid import uuid4

# Set up in-memory database configuration for testing
os.environ["OGI_DB_PATH"] = ":memory:"
os.environ["OGI_USE_SQLITE"] = "true"
os.environ["OGI_SUPABASE_URL"] = ""
os.environ["OGI_SUPABASE_ANON_KEY"] = ""

from ogi.db import database as db_module
from ogi.models import Entity, Edge, EntityType, Project
from evaluate.dataset import parse_indicator_pattern, parse_stix_bundle, seed_dataset_to_project
from evaluate.runner import mock_run_transform_static
from ogi.agent.tools import ToolContext, ScopeConfig


def test_parse_indicator_pattern():
    # Test IPv4 pattern
    p1 = "[ipv4-addr:value = '192.168.1.1']"
    res1 = parse_indicator_pattern(p1)
    assert res1 == [(EntityType.IP_ADDRESS, "192.168.1.1")]

    # Test Domain pattern
    p2 = "[domain-name:value = 'evil.com']"
    res2 = parse_indicator_pattern(p2)
    assert res2 == [(EntityType.DOMAIN, "evil.com")]

    # Test compound OR pattern
    p3 = "[domain-name:value = 'evil.com' OR ipv4-addr:value = '8.8.8.8']"
    res3 = parse_indicator_pattern(p3)
    assert (EntityType.DOMAIN, "evil.com") in res3
    assert (EntityType.IP_ADDRESS, "8.8.8.8") in res3

    # Test fallback
    p4 = "something-weird"
    res4 = parse_indicator_pattern(p4)
    assert len(res4) == 0


def test_parse_stix_bundle():
    bundle = {
        "type": "bundle",
        "id": "bundle--1",
        "objects": [
            {
                "type": "threat-actor",
                "id": "threat-actor--1",
                "name": "APT-X"
            },
            {
                "type": "malware",
                "id": "malware--1",
                "name": "SuperTrojan"
            },
            {
                "type": "relationship",
                "id": "relationship--1",
                "source_ref": "threat-actor--1",
                "target_ref": "malware--1",
                "relationship_type": "uses"
            }
        ]
    }
    entities, edges = parse_stix_bundle(bundle)
    assert len(entities) == 2
    assert len(edges) == 1
    
    # Verify mappings
    assert entities[0][1] == EntityType.ORGANIZATION  # threat-actor -> Organization
    assert entities[0][2] == "APT-X"
    assert entities[1][1] == EntityType.VULNERABILITY  # malware -> Vulnerability
    assert entities[1][2] == "SuperTrojan"
    
    assert edges[0][0] == "threat-actor--1"
    assert edges[0][1] == "malware--1"
    assert edges[0][2] == "uses"


@pytest.mark.asyncio
async def test_seeding_and_mock_transform():
    # Initialize the database in memory
    await db_module.init_db()
    assert db_module.async_session_maker is not None
    
    try:
        async with db_module.async_session_maker() as session:
            # Create a mock project
            project = Project(
                id=uuid4(),
                name="TestProject",
                description="Testing evaluation seeding",
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)
            
            # Write a temporary stix bundle to parse and seed
            import tempfile
            import json
            
            bundle = {
                "type": "bundle",
                "id": "bundle--test",
                "objects": [
                    {
                        "type": "threat-actor",
                        "id": "threat-actor--test",
                        "name": "Test Actor"
                    },
                    {
                        "type": "malware",
                        "id": "malware--test",
                        "name": "Test Trojan"
                    },
                    {
                        "type": "relationship",
                        "id": "relationship--test",
                        "source_ref": "threat-actor--test",
                        "target_ref": "malware--test",
                        "relationship_type": "uses"
                    }
                ]
            }
            
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
                json.dump(bundle, tmp)
                tmp_path = tmp.name
                
            try:
                # Seed the project
                entities, edges = await seed_dataset_to_project(session, tmp_path, project.id)
                assert len(entities) == 2
                assert len(edges) == 1
                
                # Find the threat actor entity
                actor_ent = [e for e in entities if e.value == "Test Actor"][0]
                
                # Call mock_run_transform_static on the threat actor
                ctx = ToolContext(
                    project_id=project.id,
                    user_id=uuid4(),
                    run_id=uuid4(),
                    scope=ScopeConfig(mode="all", entity_ids=[]),
                    session=session,
                )
                
                result = await mock_run_transform_static(
                    {"entity_id": str(actor_ent.id), "transform_name": "get_relations"},
                    ctx
                )
                
                assert result.data["transform_run"]["status"] == "completed"
                res_entities = result.data["result"]["entities"]
                res_edges = result.data["result"]["edges"]
                
                assert len(res_entities) == 1
                assert res_entities[0]["value"] == "Test Trojan"
                assert len(res_edges) == 1
                assert res_edges[0]["label"] == "uses"
                
            finally:
                os.remove(tmp_path)
    finally:
        await db_module.close_db()
