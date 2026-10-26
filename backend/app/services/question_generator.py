"""Question Generation Service.

Responsible for generating exactly two technical interview questions tailored to
the candidate's selected skills. Supports:
1. Server-side LLM generation when configured with valid API credentials.
2. High-quality deterministic fallback question bank when no LLM is configured
   or when LLM invocation fails.
3. Strict validation: exactly two questions, question length/format, relevance
   to selected skills, and unique question IDs.
"""

from abc import ABC, abstractmethod
import json
import logging
from typing import Dict, List, Optional, Tuple
import uuid
import httpx

from app.config import settings
from app.schemas.assessment import QuestionModel, QuestionGenerationMode
from app.services.question_bank import PREDEFINED_QUESTIONS

logger = logging.getLogger("question_generator")


class QuestionGenerationError(Exception):
    """Raised when question generation fails and fallback is unavailable."""
    pass


# Curated question bank with single-skill and cross-skill scenarios
FALLBACK_BANK: List[Dict[str, object]] = [
    # Cross-skill combinations (preferred when candidate selects multiple skills)
    {
        "id_prefix": "comb_py_sql",
        "skills": ["Python", "SQL"],
        "text": (
            "When building a high-throughput Python API using an ORM like SQLAlchemy, "
            "how do you diagnose and prevent N+1 query bottlenecks, and what database "
            "connection pooling configurations would you tune to sustain heavy concurrency?"
        )
    },
    {
        "id_prefix": "comb_py_ml",
        "skills": ["Python", "Machine Learning"],
        "text": (
            "How would you structure an asynchronous Python inference service for an ML model "
            "to support dynamic batching, ensure thread safety, and prevent out-of-memory errors "
            "under spike traffic?"
        )
    },
    {
        "id_prefix": "comb_java_sql",
        "skills": ["Java", "SQL"],
        "text": (
            "In an enterprise Java service using Spring Data JPA, how do you handle optimistic locking "
            "exceptions during concurrent updates, and how do you optimize batch operations to minimize "
            "database round-trips?"
        )
    },
    {
        "id_prefix": "comb_java_ml",
        "skills": ["Java", "Machine Learning"],
        "text": (
            "How would you integrate a trained Machine Learning model into a low-latency Java microservice "
            "architecture (e.g. using ONNX Runtime or gRPC), and how do you ensure thread isolation "
            "during concurrent scoring requests?"
        )
    },
    {
        "id_prefix": "comb_sql_ml",
        "skills": ["SQL", "Machine Learning"],
        "text": (
            "How do you design a point-in-time correct feature extraction pipeline in SQL to prevent "
            "data leakage between training and real-time inference tables?"
        )
    },
    # Python specific
    {
        "id_prefix": "py_streaming",
        "skills": ["Python"],
        "text": (
            "How would you design a Python stream-processing pipeline using generators to parse gigabyte-scale "
            "log files without loading them entirely into memory, and how do you handle cleanup and exceptions?"
        )
    },
    {
        "id_prefix": "py_concurrency",
        "skills": ["Python"],
        "text": (
            "Explain how Python's Global Interpreter Lock (GIL) affects CPU-bound versus I/O-bound workloads, "
            "and describe how you would architect a concurrent service using asyncio versus multiprocessing."
        )
    },
    # SQL specific
    {
        "id_prefix": "sql_optimization",
        "skills": ["SQL"],
        "text": (
            "Given a slow-running SQL query joining multiple multi-million row tables with complex filtering, "
            "what specific metrics do you inspect in EXPLAIN ANALYZE, and how do composite indexes help?"
        )
    },
    {
        "id_prefix": "sql_transactions",
        "skills": ["SQL"],
        "text": (
            "How do transaction isolation levels (Read Committed vs. Repeatable Read vs. Serializable) prevent "
            "anomalies such as non-repeatable reads and phantom reads in a concurrent financial ledger?"
        )
    },
    # Java specific
    {
        "id_prefix": "java_concurrency",
        "skills": ["Java"],
        "text": (
            "How do you implement a thread-safe, bounded in-memory cache in Java without introducing high lock "
            "contention, and which java.util.concurrent primitives would you employ?"
        )
    },
    {
        "id_prefix": "java_performance",
        "skills": ["Java"],
        "text": (
            "How do you profile and diagnose an application experiencing high Garbage Collection pause times "
            "and out-of-memory errors in a containerized Java environment?"
        )
    },
    # Machine Learning specific
    {
        "id_prefix": "ml_drift",
        "skills": ["Machine Learning"],
        "text": (
            "In a production recommendation system, how do you continuously detect covariate shift and concept drift, "
            "and what strategies do you use for safe, automated model canary rollouts?"
        )
    },
    {
        "id_prefix": "ml_imbalance",
        "skills": ["Machine Learning"],
        "text": (
            "When training a classifier on heavily imbalanced fraud detection data (99.9% negative), how do you structure "
            "sampling techniques, loss functions, and evaluation metrics beyond accuracy?"
        )
    }
]


def validate_question_list(
    questions: List[QuestionModel],
    selected_skills: List[str]
) -> None:
    """Validate that generated questions strictly meet all requirements."""
    if len(questions) != 2:
        raise QuestionGenerationError(
            f"Expected exactly 2 questions, but got {len(questions)}."
        )

    question_ids = set()
    question_texts = set()
    selected_set = set(selected_skills)

    for idx, q in enumerate(questions, start=1):
        if not q.question_id or not q.question_id.strip():
            raise QuestionGenerationError(f"Question #{idx} is missing a valid ID.")
        if q.question_id in question_ids:
            raise QuestionGenerationError(f"Duplicate question ID detected: {q.question_id}")
        question_ids.add(q.question_id)

        clean_text = q.text.strip()
        if len(clean_text) < 15:
            raise QuestionGenerationError(f"Question #{idx} text is too short ({len(clean_text)} chars).")
        if not clean_text.endswith("?"):
            raise QuestionGenerationError(f"Question #{idx} must end with a question mark.")
        if clean_text.lower() in question_texts:
            raise QuestionGenerationError(f"Duplicate question content detected in question #{idx}.")
        question_texts.add(clean_text.lower())

        # Check relevance to selected skills
        overlap = set(q.skills).intersection(selected_set)
        if not overlap:
            raise QuestionGenerationError(
                f"Question #{idx} targets {q.skills}, which does not match any selected skill {selected_skills}."
            )


class QuestionGeneratorInterface(ABC):
    @abstractmethod
    def generate(
        self,
        skills: List[str],
        question_count: int = 2,
        allow_fallback: bool = True
    ) -> Tuple[List[QuestionModel], QuestionGenerationMode]:
        """Generate questions for the given skills."""
        pass


class HybridQuestionGenerator(QuestionGeneratorInterface):
    """Generates questions using LLM if configured; otherwise falls back deterministically."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 8.0
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.LLM_MODEL
        self.timeout_seconds = timeout_seconds

    def _select_fallback_questions(self, skills: List[str]) -> List[QuestionModel]:
        """Select exactly two high-quality questions matching selected skills."""
        selected_set = set(skills)
        chosen: List[Dict[str, object]] = []

        # If exactly one skill is selected, use the two predefined questions for that skill
        if len(skills) == 1 and skills[0] in PREDEFINED_QUESTIONS:
            chosen = list(PREDEFINED_QUESTIONS[skills[0]])
        elif len(skills) > 1:
            # Multi-skill: pick 1 question from each selected skill
            for s in skills:
                if s in PREDEFINED_QUESTIONS and len(chosen) < 2:
                    chosen.append(PREDEFINED_QUESTIONS[s][0])
            # If still need more questions
            if len(chosen) < 2:
                for s in skills:
                    if s in PREDEFINED_QUESTIONS and len(chosen) < 2:
                        for item in PREDEFINED_QUESTIONS[s]:
                            if item not in chosen:
                                chosen.append(item)
                                if len(chosen) == 2:
                                    break
        else:
            # Fallback to any predefined questions matching skills
            for s in skills:
                if s in PREDEFINED_QUESTIONS:
                    chosen.extend(PREDEFINED_QUESTIONS[s])
                    if len(chosen) >= 2:
                        break

        # Fallback to default if somehow chosen is still less than 2
        if len(chosen) < 2:
            for item in FALLBACK_BANK:
                if any(s in selected_set for s in item["skills"]) and item not in chosen:
                    chosen.append(item)
                    if len(chosen) == 2:
                        break

        # Convert to QuestionModel with unique generated question IDs per session
        questions: List[QuestionModel] = []
        for idx, item in enumerate(chosen[:2], start=1):
            unique_qid = f"q_{uuid.uuid4().hex[:8]}"
            filtered_skills = [s for s in item["skills"] if s in selected_set]
            if not filtered_skills:
                filtered_skills = [skills[0]]
            questions.append(
                QuestionModel(
                    question_id=unique_qid,
                    text=str(item["text"]),
                    skills=filtered_skills
                )
            )

        validate_question_list(questions, skills)
        return questions

    def _call_llm(self, skills: List[str]) -> List[QuestionModel]:
        """Call LLM API to generate two technical interview questions."""
        if not self.api_key:
            raise QuestionGenerationError("No LLM API key configured.")

        system_prompt = (
            "You are an expert technical interviewer. Generate exactly two practical, scenario-based "
            "technical interview questions based on the candidate's selected skills. "
            "Return ONLY valid JSON matching this schema: "
            '{"questions": [{"text": "...", "skills": ["..."]}]}'
        )
        user_prompt = (
            f"Candidate selected skills: {', '.join(skills)}.\n"
            "Requirements:\n"
            "- Generate exactly 2 questions.\n"
            "- Focus on practical system design, debugging, or concurrency scenarios.\n"
            "- Each question must clearly target at least one of the selected skills.\n"
            "- Both questions must end with a question mark."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                if res.status_code != 200:
                    raise QuestionGenerationError(f"LLM API returned status {res.status_code}: {res.text}")
                
                body = res.json()
                content = body["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                raw_questions = parsed.get("questions", [])

                result_questions: List[QuestionModel] = []
                for q in raw_questions:
                    qid = f"q_{uuid.uuid4().hex[:8]}"
                    # Ensure skills are subset of selected skills
                    q_skills = [s for s in q.get("skills", []) if s in skills]
                    if not q_skills:
                        q_skills = [skills[0]]
                    result_questions.append(
                        QuestionModel(
                            question_id=qid,
                            text=q.get("text", "").strip(),
                            skills=q_skills
                        )
                    )

                validate_question_list(result_questions, skills)
                return result_questions

        except Exception as e:
            logger.warning("LLM question generation failed: %s", str(e))
            raise QuestionGenerationError(f"LLM generation failed: {str(e)}") from e

    def generate(
        self,
        skills: List[str],
        question_count: int = 2,
        allow_fallback: bool = True
    ) -> Tuple[List[QuestionModel], QuestionGenerationMode]:
        """Generate questions using the deterministic question bank (no external LLM required)."""
        questions = self._select_fallback_questions(skills)
        return questions, "fallback"


_default_question_generator = HybridQuestionGenerator()


def get_question_generator() -> QuestionGeneratorInterface:
    """FastAPI dependency provider for question generator."""
    return _default_question_generator
