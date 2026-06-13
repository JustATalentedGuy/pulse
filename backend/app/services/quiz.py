import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.groq import GroqChatClient
from app.config import get_settings
from app.database import SessionLocal
from app.enrichment.parser import extract_json_array
from app.enrichment.quota_manager import QuotaManager, reserve_quota
from app.models.article import Article
from app.models.quiz import QuizAttempt, QuizSession
from app.schemas.quiz import (
    QuizAnswer,
    QuizAnswerResult,
    QuizQuestion,
    QuizSubmitResponse,
)


QUIZ_SESSION_TTL_SECONDS = 10 * 60


class QuizGenerationClient(Protocol):
    async def complete(self, prompt: str) -> str: ...


class QuizQuotaExhausted(RuntimeError):
    pass


class QuizGenerationState(TypedDict, total=False):
    summary: str
    entities: dict
    client: QuizGenerationClient
    questions: list[QuizQuestion]


class QuizEvaluationState(TypedDict, total=False):
    questions: list[QuizQuestion]
    answers: list[QuizAnswer]
    results: list[QuizAnswerResult]
    score: float
    correct_count: int


class QuizSessionStore:
    def __init__(self, ttl_seconds: int = QUIZ_SESSION_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds

    async def get(self, article_id: UUID) -> list[QuizQuestion] | None:
        async with SessionLocal() as session:
            questions = await session.scalar(
                select(QuizSession.questions).where(
                    QuizSession.article_id == article_id,
                    QuizSession.expires_at > datetime.now(UTC),
                )
            )
        if questions is None:
            return None
        return [
            QuizQuestion.model_validate(question)
            for question in questions
        ]

    async def set(
        self,
        article_id: UUID,
        questions: list[QuizQuestion],
    ) -> None:
        expires_at = datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)
        async with SessionLocal() as session:
            statement = (
                insert(QuizSession)
                .values(
                    article_id=article_id,
                    questions=[
                        question.model_dump()
                        for question in questions
                    ],
                    expires_at=expires_at,
                )
                .on_conflict_do_update(
                    index_elements=[QuizSession.article_id],
                    set_={
                        "questions": [
                            question.model_dump()
                            for question in questions
                        ],
                        "expires_at": expires_at,
                    },
                )
            )
            await session.execute(statement)
            await session.commit()

    async def consume(self, article_id: UUID) -> list[QuizQuestion] | None:
        async with SessionLocal() as session:
            questions = (
                await session.execute(
                    delete(QuizSession)
                    .where(
                        QuizSession.article_id == article_id,
                        QuizSession.expires_at > datetime.now(UTC),
                    )
                    .returning(QuizSession.questions)
                )
            ).scalar_one_or_none()
            await session.commit()
        if questions is None:
            return None
        return [
            QuizQuestion.model_validate(question)
            for question in questions
        ]

    async def clear(self) -> None:
        async with SessionLocal() as session:
            await session.execute(delete(QuizSession))
            await session.commit()


def build_question_prompt(summary: str, entities: dict) -> str:
    entity_values = [
        value
        for values in entities.values()
        if isinstance(values, list)
        for value in values
        if isinstance(value, str) and value.strip()
    ]
    entity_text = ", ".join(entity_values) if entity_values else "None identified"
    return f"""Generate 3 multiple-choice questions to test understanding of this article.

For each question:
- Question should test the concept, not just fact recall
- 4 options (A-D), one correct
- Include a 1-sentence explanation for the correct answer

Return ONLY a JSON array. No preamble.

Article summary: {summary}
Key entities: {entity_text}

Format: [{{"question": "...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct": "B", "explanation": "..."}}]"""


async def generate_questions(
    state: QuizGenerationState,
) -> dict[str, list[QuizQuestion]]:
    response = await state["client"].complete(
        build_question_prompt(state["summary"], state["entities"])
    )
    raw_questions = extract_json_array(response)
    if len(raw_questions) != 3:
        raise ValueError("Quiz generation must return exactly three questions")
    questions = [
        QuizQuestion.model_validate({"id": index, **question})
        for index, question in enumerate(raw_questions, start=1)
    ]
    return {"questions": questions}


async def evaluate_answer(
    state: QuizEvaluationState,
) -> dict[str, list[QuizAnswerResult]]:
    answers = {answer.question_id: answer for answer in state["answers"]}
    results: list[QuizAnswerResult] = []
    for question in state["questions"]:
        selected = answers[question.id].selected
        is_correct = selected == question.correct
        feedback = (
            f"Good reasoning. {question.explanation}"
            if is_correct
            else (
                f"What distinction makes option {question.correct} fit better "
                f"than option {selected}? {question.explanation}"
            )
        )
        results.append(
            QuizAnswerResult(
                question_id=question.id,
                correct=is_correct,
                feedback=feedback,
                explanation=question.explanation,
            )
        )
    return {"results": results}


async def compute_score(
    state: QuizEvaluationState,
) -> dict[str, float | int]:
    correct_count = sum(result.correct for result in state["results"])
    return {
        "correct_count": correct_count,
        "score": round(correct_count / len(state["questions"]), 2),
    }


generation_builder = StateGraph(QuizGenerationState)
generation_builder.add_node("generate_questions", generate_questions)
generation_builder.add_edge(START, "generate_questions")
generation_builder.add_edge("generate_questions", END)
generation_graph = generation_builder.compile()

evaluation_builder = StateGraph(QuizEvaluationState)
evaluation_builder.add_node("evaluate_answer", evaluate_answer)
evaluation_builder.add_node("compute_score", compute_score)
evaluation_builder.add_edge(START, "evaluate_answer")
evaluation_builder.add_edge("evaluate_answer", "compute_score")
evaluation_builder.add_edge("compute_score", END)
evaluation_graph = evaluation_builder.compile()

quiz_sessions = QuizSessionStore()
quiz_generation_lock = asyncio.Lock()


async def create_quiz(
    article: Article,
    *,
    client: QuizGenerationClient | None = None,
    quota_manager: QuotaManager | None = None,
) -> list[QuizQuestion]:
    cached = await quiz_sessions.get(article.id)
    if cached is not None:
        return cached

    async with quiz_generation_lock:
        cached = await quiz_sessions.get(article.id)
        if cached is not None:
            return cached

        settings = get_settings()
        generation_client = client
        if generation_client is None:
            if not await reserve_quota(quota_manager, settings):
                raise QuizQuotaExhausted
            generation_client = GroqChatClient(
                api_key=settings.groq_api_key,
                model=settings.groq_model,
            )
        elif quota_manager is not None and not await reserve_quota(
            quota_manager,
            settings,
        ):
            raise QuizQuotaExhausted

        result = await generation_graph.ainvoke(
            {
                "summary": article.summary or "",
                "entities": article.entities or {},
                "client": generation_client,
            }
        )
        questions = result["questions"]
        await quiz_sessions.set(article.id, questions)
        return questions


async def submit_quiz(
    session: AsyncSession,
    article: Article,
    answers: list[QuizAnswer],
    duration_seconds: int,
) -> QuizSubmitResponse:
    questions = await quiz_sessions.consume(article.id)
    if questions is None:
        raise ValueError("Quiz session expired. Generate a new quiz and try again.")

    result = await evaluation_graph.ainvoke(
        {"questions": questions, "answers": answers}
    )
    score = result["score"]
    answer_map = {answer.question_id: answer.selected for answer in answers}
    result_map = {item.question_id: item for item in result["results"]}
    stored_questions = [
        {
            **question.model_dump(),
            "user_answer": answer_map[question.id],
            "is_correct": result_map[question.id].correct,
            "feedback": result_map[question.id].feedback,
        }
        for question in questions
    ]
    session.add(
        QuizAttempt(
            article_id=article.id,
            questions=stored_questions,
            score=Decimal(str(score)),
            duration_s=duration_seconds,
        )
    )
    article.quiz_attempted = True
    article.quiz_score = Decimal(str(score))
    await session.commit()
    return QuizSubmitResponse(
        score=score,
        correct_count=result["correct_count"],
        total_questions=len(questions),
        results=result["results"],
    )
