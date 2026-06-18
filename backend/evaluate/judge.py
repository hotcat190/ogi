import json
import logging
import os
from typing import Any, Dict, Optional, Tuple
import httpx

from ogi.config import settings

logger = logging.getLogger("ogi.evaluate.judge")


async def grade_summary(
    question: str,
    final_summary: str,
    ground_truth_entities: list[str],
    ground_truth_text: Optional[str] = None,
) -> Tuple[float, str]:
    """
    Grades the investigator's final summary against the ground truth entities and description
    using Gemini API. Returns a tuple of (score_out_of_5, reasoning).
    """
    api_key = os.environ.get("GEMINI_API_KEY") or settings.llm_api_key
    if not api_key:
        logger.warning("No Gemini API key available for evaluation grading. Skipping judge.")
        return 0.0, "Skipped: GEMINI_API_KEY not configured"

    # We use a default gemini model for grading
    model = "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    gt_text_str = f"Expected Ground Truth Text:\n{ground_truth_text}" if ground_truth_text else ""
    prompt = f"""You are an expert cybersecurity analyst grading an automated investigation report.
Evaluate how accurately and completely the investigator answered the question.

Question:
{question}

Investigator's Final Summary:
{final_summary}

Expected Target Entities (Ground Truth):
{", ".join(ground_truth_entities)}

{gt_text_str}

Assign a score from 1 to 5 based on these criteria:
- 5 (Excellent): Fully answered the question, identified all relevant target entities, and provided a highly accurate explanation.
- 4 (Good): Answered the question well and identified most target entities, with minor omissions or details missing.
- 3 (Satisfactory): Identified some target entities but missed major components of the question.
- 2 (Poor): Missed almost all target entities, gave a vague or irrelevant summary.
- 1 (Fail): Incorrect summary or completely failed to address the question.

Return ONLY a JSON object with two fields:
"score": <float from 1 to 5>
"reasoning": "<explanation for the score>"
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            if response.is_error:
                return 0.0, f"Gemini API returned error: {response.text}"
            
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            
            score = float(parsed.get("score", 0.0))
            reasoning = str(parsed.get("reasoning", ""))
            return score, reasoning
    except Exception as e:
        logger.exception("Failed to grade summary using Gemini")
        return 0.0, f"Error during grading: {str(e)}"
