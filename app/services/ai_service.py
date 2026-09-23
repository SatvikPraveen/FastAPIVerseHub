# File: app/services/ai_service.py

from typing import Any

from app.core.time import utcnow


class AIService:
    """Service that wraps AI-powered course recommendation and learning path logic.

    Production usage would inject an LLM client (e.g. OpenAI, Anthropic) here.
    The stub implementations return sensible placeholder responses so all API
    endpoints are functional without external dependencies.
    """

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    async def generate_course_recommendations(
        self,
        user_data: dict[str, Any],
        limit: int = 10,
        include_reasoning: bool = False,
    ) -> list[dict[str, Any]]:
        """Generate personalised course recommendations for a user profile."""
        interests: list[str] = user_data.get("interests") or []
        skill_level: str = user_data.get("skill_level", "beginner")

        recommendations = [
            {
                "course_id": i + 1,
                "title": f"Recommended Course {i + 1}",
                "relevance_score": round(0.95 - i * 0.05, 2),
                "matched_interests": interests[:2] if interests else [],
                "skill_level": skill_level,
                "reasoning": (
                    f"Based on your interest in {', '.join(interests[:2]) or 'general topics'} "
                    f"and {skill_level} skill level."
                )
                if include_reasoning
                else None,
            }
            for i in range(min(limit, 5))
        ]
        return recommendations

    async def generate_custom_recommendations(
        self,
        user_id: int,
        interests: list[str],
        skill_level: str,
        learning_goals: list[str],
        time_commitment: int,
        preferred_formats: list[str],
    ) -> list[dict[str, Any]]:
        """Generate recommendations based on explicit user-supplied criteria."""
        return [
            {
                "course_id": i + 1,
                "title": f"Custom Recommendation {i + 1}",
                "relevance_score": round(0.90 - i * 0.05, 2),
                "matched_interests": interests[:2],
                "skill_level": skill_level,
                "estimated_hours": time_commitment // max(len(learning_goals), 1),
                "preferred_format": preferred_formats[0] if preferred_formats else "video",
            }
            for i in range(3)
        ]

    # ------------------------------------------------------------------
    # Learning paths
    # ------------------------------------------------------------------

    async def create_learning_path(
        self,
        goal: str,
        current_skills: list[str],
        target_skills: list[str],
        timeline_weeks: int,
        difficulty_preference: str,
        user_id: int,
    ) -> dict[str, Any]:
        """Generate a structured learning path to achieve a stated goal."""
        skill_gap = [s for s in target_skills if s not in current_skills]
        courses = [
            {
                "id": i + 1,
                "title": f"Master {skill}",
                "order": i + 1,
                "estimated_hours": max(2, timeline_weeks // max(len(skill_gap), 1)),
            }
            for i, skill in enumerate(skill_gap[:8])
        ]

        return {
            "id": 1,
            "title": f"Path to: {goal}",
            "description": (
                f"A {timeline_weeks}-week journey from "
                f"{', '.join(current_skills[:3]) or 'beginner'} "
                f"to {', '.join(target_skills[:3])}."
            ),
            "courses": courses,
            "estimated_duration_weeks": timeline_weeks,
            "difficulty_preference": difficulty_preference,
            "goal": goal,
            "created_at": utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Course optimisation
    # ------------------------------------------------------------------

    async def analyze_course_optimization(
        self,
        course_id: int,
        optimization_goals: list[str],
        target_metrics: dict[str, float],
        performance_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyse a course and propose optimisation suggestions."""
        suggestions = [
            {
                "area": goal,
                "suggestion": f"Improve {goal} by reviewing student dropout analytics.",
                "expected_impact": target_metrics.get(goal, 0.1),
                "priority": "high" if i == 0 else "medium",
            }
            for i, goal in enumerate(optimization_goals[:5])
        ]

        completion_rate = float((performance_data or {}).get("completion_rate", 0.0))
        score = round(min(100.0, 40.0 + completion_rate * 0.6), 1)
        return {
            "course_id": course_id,
            "score": score,
            "suggestions": suggestions,
            "projections": {
                goal: {"current": completion_rate, "target": target_metrics.get(goal, 0.0)}
                for goal in optimization_goals
            },
            "auto_applicable": [s for s in suggestions if s["priority"] != "high"],
            "manual_review": [s for s in suggestions if s["priority"] == "high"],
            "priority_actions": [s for s in suggestions if s["priority"] == "high"],
            "generated_at": utcnow().isoformat(),
        }
