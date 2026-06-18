# OGI AI Investigator Benchmarking Report (Static Mode)

Generated at: 2026-06-18T12:08:22.895218+00:00 UTC

## Summary Metrics

| Task ID | Success | Steps | Duration (s) | Tokens | Precision | Recall | F1 Score | Judge Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `threat-actor-bravo` | ✅ | 14 | 8.7s | 11484 | 1.00 | 1.00 | 1.00 | 5.0/5.0 |
| `poisonivy-cnc` | ✅ | 15 | 10.8s | 20193 | 0.05 | 1.00 | 0.10 | 1.0/5.0 |

## Detailed Task Reports

### Task: `threat-actor-bravo`

**Final Summary:**
Adversary Bravo is a threat actor known for utilizing phishing attacks as a primary attack pattern. They are associated with the deployment of remote access malware, specifically identified in the project scope as 'Poison Ivy Variant d1c6'.

**Judge Reasoning (5.0/5):**
> The investigator's summary accurately and completely answers the question. It correctly identifies 'Poison Ivy Variant d1c6' as the malware and 'phishing attacks' as the attack pattern used by 'Adversary Bravo'. All expected target entities are present and correctly described, providing a highly accurate explanation.

---

### Task: `poisonivy-cnc`

**Final Summary:**
The investigation into the Poison Ivy Variant (8010cae3e8431bb11ed6dc9acabb93b7,) identified that the entity's metadata description references 'Two CnC domain names from the admin@338 sample 8010cae3e843'. However, these specific domains and their associated IP addresses are not currently indexed as standalone entities within the project scope, and no available transforms were able to extract or link these indicators to the graph.

**Judge Reasoning (1.0/5):**
> The investigator's summary explicitly states that the specific CnC domains and their associated IP addresses were 'not currently indexed as standalone entities' and 'no available transforms were able to extract or link these indicators'. This means the investigation failed to identify any of the expected target entities (www.webserver.dynssl.com, www.webserver.freetcp.com, www.webserver.fartit.com, 219.76.208.163) that were requested in the question. While the summary explains *why* they weren't found, the core task of identification was not met.
