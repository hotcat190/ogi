import json
import re
from typing import Any, Dict, List, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from ogi.models import Edge, Entity, EntityType, Project


def parse_indicator_pattern(pattern: str) -> List[Tuple[EntityType, str]]:
    """
    Parses a STIX 2.1 pattern string and returns a list of (EntityType, value) tuples.
    Example: "[ipv4-addr:value = '219.76.208.163']" -> [(EntityType.IP_ADDRESS, '219.76.208.163')]
    """
    # Find all matches of form stix_type:field = 'value'
    matches = re.findall(r"([\w\-]+):([\w\-\.]+)\s*=\s*['\"]([^'\"]+)['\"]", pattern)
    entities = []
    for stix_type, field, val in matches:
        val = val.strip()
        if stix_type in ("ipv4-addr", "ipv6-addr"):
            entities.append((EntityType.IP_ADDRESS, val))
        elif stix_type == "domain-name":
            entities.append((EntityType.DOMAIN, val))
        elif stix_type == "url":
            entities.append((EntityType.URL, val))
        elif stix_type == "email-addr":
            entities.append((EntityType.EMAIL_ADDRESS, val))
        elif stix_type == "file":
            if "hashes" in field:
                entities.append((EntityType.HASH, val))
            else:
                entities.append((EntityType.DOCUMENT, val))
        elif stix_type == "x509-certificate":
            entities.append((EntityType.SSL_CERTIFICATE, val))
            
    # Try alternate forms, like OR/AND compounds or file:name
    if not entities:
        # Fallback to general regex for any values in single/double quotes
        values = re.findall(r"=\s*['\"]([^'\"]+)['\"]", pattern)
        for val in values:
            val = val.strip()
            # Try to guess type based on value shape
            if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", val):
                entities.append((EntityType.IP_ADDRESS, val))
            elif re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", val):
                entities.append((EntityType.DOMAIN, val))
            elif len(val) in (32, 40, 64) and re.match(r"^[a-fA-F0-9]+$", val):
                entities.append((EntityType.HASH, val))
            else:
                entities.append((EntityType.DOCUMENT, val))
                
    return entities


def parse_stix_bundle(
    bundle_data: Dict[str, Any]
) -> Tuple[List[Tuple[str, EntityType, str, Dict[str, Any]]], List[Tuple[str, str, str, Dict[str, Any]]]]:
    """
    Parses a STIX 2.1 JSON bundle and returns (entity_specs, edge_specs).
    entity_specs is a list of tuples: (stix_id, ogi_entity_type, value, properties)
    edge_specs is a list of tuples: (source_stix_id, target_stix_id, label, properties)
    """
    objects = bundle_data.get("objects", [])
    entity_specs = []
    edge_specs = []
    
    # First pass: parse all SDOs
    for obj in objects:
        obj_type = obj.get("type")
        obj_id = obj.get("id")
        if not obj_type or not obj_id:
            continue
            
        if obj_type == "relationship":
            source_ref = obj.get("source_ref")
            target_ref = obj.get("target_ref")
            rel_type = obj.get("relationship_type", "associated-with")
            if source_ref and target_ref:
                edge_specs.append((source_ref, target_ref, rel_type, obj))
            continue
            
        # Standard SDO mapping
        ogi_type = None
        val = None
        
        if obj_type in ("threat-actor", "intrusion-set"):
            ogi_type = EntityType.ORGANIZATION
            val = obj.get("name")
        elif obj_type == "identity":
            identity_class = obj.get("identity_class")
            if identity_class == "individual":
                ogi_type = EntityType.PERSON
            else:
                ogi_type = EntityType.ORGANIZATION
            val = obj.get("name")
        elif obj_type in ("malware", "tool", "attack-pattern"):
            ogi_type = EntityType.VULNERABILITY
            val = obj.get("name")
        elif obj_type == "vulnerability":
            ogi_type = EntityType.VULNERABILITY
            val = obj.get("name")
        elif obj_type == "indicator":
            pattern = obj.get("pattern", "")
            parsed_entities = parse_indicator_pattern(pattern)
            if parsed_entities:
                # An indicator can represent multiple entities; we add them all
                for etype, evalue in parsed_entities:
                    entity_specs.append((obj_id, etype, evalue, obj))
                continue
            else:
                # Fallback
                ogi_type = EntityType.DOCUMENT
                val = obj.get("name") or obj.get("id")
                
        if ogi_type and val:
            entity_specs.append((obj_id, ogi_type, val, obj))
            
    return entity_specs, edge_specs


async def seed_dataset_to_project(
    session: AsyncSession,
    dataset_path: str,
    project_id: UUID,
) -> Tuple[List[Entity], List[Edge]]:
    """
    Loads a STIX 2.1 dataset from dataset_path and inserts parsed entities/edges
    into the database under project_id.
    """
    with open(dataset_path, "r", encoding="utf-8") as f:
        bundle_data = json.load(f)
        
    entity_specs, edge_specs = parse_stix_bundle(bundle_data)
    
    # Map from STIX ID to created OGI Entity objects
    sdo_to_entities: Dict[str, List[Entity]] = {}
    
    created_entities = []
    for stix_id, etype, val, props in entity_specs:
        entity = Entity(
            id=uuid4(),
            project_id=project_id,
            type=etype,
            value=val,
            properties=props,
            source="seeder",
            origin_source="stix_dataset",
        )
        session.add(entity)
        created_entities.append(entity)
        
        if stix_id not in sdo_to_entities:
            sdo_to_entities[stix_id] = []
        sdo_to_entities[stix_id].append(entity)
        
    # Flush entities first so they exist in the DB (for foreign keys)
    await session.flush()
    
    created_edges = []
    for src_ref, tgt_ref, label, props in edge_specs:
        sources = sdo_to_entities.get(src_ref, [])
        targets = sdo_to_entities.get(tgt_ref, [])
        
        for src in sources:
            for tgt in targets:
                edge = Edge(
                    id=uuid4(),
                    project_id=project_id,
                    source_id=src.id,
                    target_id=tgt.id,
                    label=label,
                    properties=props,
                )
                session.add(edge)
                created_edges.append(edge)
                
    await session.commit()
    return created_entities, created_edges
