import json
import traceback
from typing import Any

from app.services.llm_service import llm_service


# ============================================================
# Configuration
# ============================================================

GROUNDING_THRESHOLD = 0.70


# ============================================================
# JSON extraction
# ============================================================

def extract_json(text: str) -> dict[str, Any] | None:
    """
    Extract and validate the JSON returned by the judge LLM.
    """

    if not text:
        return None

    text = text.strip()

    # Remove markdown code fences if the LLM adds them
    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)

    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    if "grounded" not in data:
        return None

    if "score" not in data:
        return None

    grounded = data["grounded"]
    score = data["score"]

    # grounded MUST be a real boolean
    if not isinstance(grounded, bool):
        return None

    # score MUST be numeric
    if isinstance(score, bool):
        return None

    try:
        score = float(score)
    except (TypeError, ValueError):
        return None

    # Score must be between 0 and 1
    if not 0 <= score <= 1:
        return None

    return {
        "grounded": grounded,
        "score": score
    }


# ============================================================
# Groundedness evaluation
# ============================================================

async def evaluate_groundedness(
    question: str,
    documents: list,
    answer: str
) -> dict[str, Any]:

    # --------------------------------------------------------
    # Build context
    # --------------------------------------------------------

    context_parts = []

    for doc in documents[:3]:

        content = doc.get("content", "")

        if content:
            context_parts.append(content[:1500])

    context = "\n\n--- DOCUMENT ---\n\n".join(context_parts)

    # --------------------------------------------------------
    # Judge prompt
    # --------------------------------------------------------

    messages = [

        {
            "role": "system",
            "content": """
You are a RAG evaluation classifier.

Your ONLY task is to determine whether the answer is
supported by the provided context.

Return ONLY valid JSON.

Required format:

{
  "grounded": true,
  "score": 0.95
}

Rules:

- grounded = true ONLY if the answer is supported by the context.
- grounded = false if the answer contains unsupported information.
- score must be between 0 and 1.
- 1.0 = completely supported.
- 0.0 = completely unsupported.
- Do not explain your decision.
- Do not add extra keys.
- Do not use markdown.
"""
        },

        {
            "role": "user",
            "content": f"""
Question:
{question}

Context:
{context}

Answer:
{answer}

Return JSON only.
"""
        }

    ]

    # --------------------------------------------------------
    # First judge call
    # --------------------------------------------------------

    try:

        response = await llm_service.generate_judge(
            messages=messages,
            temperature=0,
            max_tokens=100
        )

        print("\n========== RAW JUDGE ==========")
        print(response)
        print("================================")

        evaluation = extract_json(response)

        # ----------------------------------------------------
        # Retry if invalid JSON
        # ----------------------------------------------------

        if evaluation is None:

            print("Invalid judge response. Retrying...")

            retry_messages = [

                {
                    "role": "system",
                    "content": """
Return ONLY valid JSON.

Format:

{
  "grounded": false,
  "score": 0.0
}

No markdown.
No explanation.
No extra keys.
"""
                },

                {
                    "role": "user",
                    "content": f"""
Convert the following evaluation into valid JSON:

{response}
"""
                }

            ]

            retry = await llm_service.generate_judge(
                messages=retry_messages,
                temperature=0,
                max_tokens=50
            )

            print("\n========== RETRY JUDGE ==========")
            print(retry)
            print("=================================")

            evaluation = extract_json(retry)

        # ----------------------------------------------------
        # If still invalid
        # ----------------------------------------------------

        if evaluation is None:
            raise ValueError("Invalid judge JSON response")

        # ----------------------------------------------------
        # Read score
        # ----------------------------------------------------

        score = float(evaluation["score"])

        # Safety clamp
        score = max(0.0, min(score, 1.0))

        # ----------------------------------------------------
        # IMPORTANT:
        # Grounded status is derived from score threshold
        # ----------------------------------------------------

        grounded = score >= GROUNDING_THRESHOLD

        # ----------------------------------------------------
        # Result
        # ----------------------------------------------------

        result = {
            "grounded": grounded,
            "score": round(score, 4)
        }

        print("\n========== PARSED EVALUATION ==========")
        print(result)
        print("=======================================")

        return result

    # --------------------------------------------------------
    # Error handling
    # --------------------------------------------------------

    except Exception as e:

        print("\n========== EVALUATION ERROR ==========")
        traceback.print_exc()
        print("======================================")

        return {
            "grounded": False,
            "score": 0.0,
            "error": str(e)
        }
