# File: app/api/v2/advanced_courses.py

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.dependencies import (
    get_current_active_user,
    get_db,
    get_pagination_params,
    PaginationParams
)
from app.models.user import User
from app.schemas.course import CourseResponse, CourseAnalytics
from app.services.advanced_course_service import AdvancedCourseService
from app.services.analytics_service import AnalyticsService
from app.services.ai_service import AIService

router = APIRouter()


class CourseRecommendationRequest(BaseModel):
    """Course recommendation request."""
    interests: List[str]
    skill_level: str
    learning_goals: List[str]
    time_commitment_hours: int
    preferred_formats: List[str]


class LearningPathRequest(BaseModel):
    """Learning path creation request."""
    goal: str
    current_skills: List[str]
    target_skills: List[str]
    timeline_weeks: int
    difficulty_preference: str


class CourseOptimizationRequest(BaseModel):
    """Course optimization request."""
    course_id: int
    optimization_goals: List[str]
    target_metrics: Dict[str, float]


@router.get("/recommendations")
async def get_course_recommendations(
    limit: int = Query(10, ge=1, le=50),
    include_reasoning: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get AI-powered course recommendations."""
    advanced_course_service = AdvancedCourseService(db)
    ai_service = AIService()
    
    # Get user learning history and preferences
    user_data = await advanced_course_service.get_user_learning_profile(current_user.id)
    
    # Generate recommendations using AI
    recommendations = await ai_service.generate_course_recommendations(
        user_data=user_data,
        limit=limit,
        include_reasoning=include_reasoning
    )
    
    return {
        "recommendations": recommendations,
        "user_profile": {
            "learning_style": user_data.get("learning_style"),
            "skill_level": user_data.get("average_skill_level"),
            "interests": user_data.get("interests", []),
            "completed_courses": user_data.get("completed_courses", 0)
        },
        "generated_at": datetime.utcnow()
    }


@router.post("/recommendations/custom")
async def get_custom_recommendations(
    request: CourseRecommendationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get customized course recommendations based on specific criteria."""
    advanced_course_service = AdvancedCourseService(db)
    ai_service = AIService()
    
    recommendations = await ai_service.generate_custom_recommendations(
        user_id=current_user.id,
        interests=request.interests,
        skill_level=request.skill_level,
        learning_goals=request.learning_goals,
        time_commitment=request.time_commitment_hours,
        preferred_formats=request.preferred_formats
    )
    
    return {
        "recommendations": recommendations,
        "criteria": request.dict(),
        "total_found": len(recommendations)
    }


@router.get("/learning-paths")
async def get_learning_paths(
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get available learning paths."""
    advanced_course_service = AdvancedCourseService(db)
    
    learning_paths = await advanced_course_service.get_learning_paths(
        category=category,
        difficulty=difficulty,
        user_id=current_user.id
    )
    
    return {
        "learning_paths": [
            {
                "id": path.id,
                "title": path.title,
                "description": path.description,
                "total_courses": len(path.courses),
                "estimated_duration_weeks": path.estimated_duration_weeks,
                "difficulty": path.difficulty,
                "completion_rate": path.completion_rate,
                "user_progress": path.user_progress.get(str(current_user.id), 0)
            }
            for path in learning_paths
        ]
    }


@router.post("/learning-paths/create")
async def create_custom_learning_path(
    request: LearningPathRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create a custom learning path using AI."""
    advanced_course_service = AdvancedCourseService(db)
    ai_service = AIService()
    
    # Generate learning path using AI
    learning_path = await ai_service.create_learning_path(
        goal=request.goal,
        current_skills=request.current_skills,
        target_skills=request.target_skills,
        timeline_weeks=request.timeline_weeks,
        difficulty_preference=request.difficulty_preference,
        user_id=current_user.id
    )
    
    # Save the learning path
    saved_path = await advanced_course_service.save_learning_path(
        user_id=current_user.id,
        learning_path_data=learning_path
    )
    
    # Send notification about new learning path
    background_tasks.add_task(
        advanced_course_service.send_learning_path_notification,
        current_user.id,
        saved_path.id
    )
    
    return {
        "learning_path_id": saved_path.id,
        "title": saved_path.title,
        "total_courses": len(saved_path.courses),
        "estimated_duration": saved_path.estimated_duration_weeks,
        "courses": [
            {
                "course_id": course["id"],
                "title": course["title"],
                "order": course["order"],
                "estimated_hours": course["estimated_hours"]
            }
            for course in saved_path.courses
        ]
    }


@router.get("/analytics/{course_id}")
async def get_course_analytics(
    course_id: int,
    time_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> CourseAnalytics:
    """Get detailed course analytics."""
    advanced_course_service = AdvancedCourseService(db)
    analytics_service = AnalyticsService(db)
    
    # Check if user owns the course or is admin
    course = await advanced_course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    if course.instructor_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    analytics = await analytics_service.get_course_analytics(
        course_id=course_id,
        time_range=time_range
    )
    
    return CourseAnalytics(**analytics)


@router.get("/performance/dashboard")
async def get_performance_dashboard(
    time_range: str = Query("30d"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get instructor performance dashboard."""
    analytics_service = AnalyticsService(db)
    
    dashboard_data = await analytics_service.get_instructor_dashboard(
        instructor_id=current_user.id,
        time_range=time_range
    )
    
    return {
        "overview": {
            "total_courses": dashboard_data["total_courses"],
            "total_students": dashboard_data["total_students"],
            "total_revenue": dashboard_data["total_revenue"],
            "avg_rating": dashboard_data["avg_rating"]
        },
        "recent_activity": dashboard_data["recent_activity"],
        "top_performing_courses": dashboard_data["top_courses"],
        "student_engagement": dashboard_data["engagement_metrics"],
        "growth_metrics": dashboard_data["growth_metrics"]
    }


@router.post("/optimize/{course_id}")
async def optimize_course(
    course_id: int,
    request: CourseOptimizationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Optimize course using AI analysis."""
    advanced_course_service = AdvancedCourseService(db)
    ai_service = AIService()
    
    # Check permissions
    course = await advanced_course_service.get_course_by_id(course_id)
    if not course or course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Get course performance data
    course_data = await advanced_course_service.get_course_performance_data(course_id)
    
    # Generate optimization suggestions
    optimization_results = await ai_service.analyze_course_optimization(
        course_data=course_data,
        optimization_goals=request.optimization_goals,
        target_metrics=request.target_metrics
    )
    
    # Save optimization report
    report_id = await advanced_course_service.save_optimization_report(
        course_id=course_id,
        user_id=current_user.id,
        optimization_results=optimization_results
    )
    
    # Schedule background task to implement auto-suggestions
    background_tasks.add_task(
        advanced_course_service.apply_optimization_suggestions,
        course_id,
        optimization_results.get("auto_applicable", [])
    )
    
    return {
        "report_id": report_id,
        "optimization_score": optimization_results["score"],
        "suggestions": optimization_results["suggestions"],
        "projected_improvements": optimization_results["projections"],
        "auto_applied": len(optimization_results.get("auto_applicable", [])),
        "requires_manual_review": len(optimization_results.get("manual_review", []))
    }


@router.get("/trends/market")
async def get_market_trends(
    category: Optional[str] = Query(None),
    time_range: str = Query("90d"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get market trends and insights."""
    analytics_service = AnalyticsService(db)
    
    trends = await analytics_service.get_market_trends(
        category=category,
        time_range=time_range
    )
    
    return {
        "trending_topics": trends["trending_topics"],
        "skill_demand": trends["skill_demand"],
        "pricing_insights": trends["pricing_insights"],
        "competition_analysis": trends["competition_analysis"],
        "growth_opportunities": trends["growth_opportunities"]
    }


@router.get("/cohorts/{course_id}")
async def get_course_cohorts(
    course_id: int,
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get course cohort analysis."""
    advanced_course_service = AdvancedCourseService(db)
    
    # Check permissions
    course = await advanced_course_service.get_course_by_id(course_id)
    if not course or course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    cohorts = await advanced_course_service.get_course_cohorts(
        course_id=course_id,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    return {
        "cohorts": [
            {
                "cohort_id": cohort.id,
                "start_date": cohort.start_date,
                "student_count": cohort.student_count,
                "completion_rate": cohort.completion_rate,
                "avg_progress": cohort.avg_progress,
                "avg_rating": cohort.avg_rating,
                "performance_metrics": cohort.performance_metrics
            }
            for cohort in cohorts
        ],
        "total": len(cohorts)
    }


@router.post("/experiments/ab-test")
async def create_ab_test(
    course_id: int,
    experiment_config: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create A/B test experiment for course."""
    advanced_course_service = AdvancedCourseService(db)
    
    # Check permissions
    course = await advanced_course_service.get_course_by_id(course_id)
    if not course or course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    experiment = await advanced_course_service.create_ab_experiment(
        course_id=course_id,
        instructor_id=current_user.id,
        config=experiment_config
    )
    
    return {
        "experiment_id": experiment.id,
        "status": experiment.status,
        "start_date": experiment.start_date,
        "estimated_duration": experiment.estimated_duration_days,
        "variants": experiment.variants,
        "success_metrics": experiment.success_metrics
    }


@router.get("/experiments/{experiment_id}/results")
async def get_experiment_results(
    experiment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get A/B test experiment results."""
    advanced_course_service = AdvancedCourseService(db)
    
    experiment = await advanced_course_service.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found"
        )
    
    # Check permissions
    if experiment.instructor_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    results = await advanced_course_service.get_experiment_results(experiment_id)
    
    return {
        "experiment_id": experiment_id,
        "status": experiment.status,
        "duration_days": (datetime.utcnow() - experiment.start_date).days,
        "statistical_significance": results["statistical_significance"],
        "winning_variant": results["winning_variant"],
        "confidence_level": results["confidence_level"],
        "variant_performance": results["variant_performance"],
        "recommendations": results["recommendations"]
    }


@router.post("/bulk-operations/update")
async def bulk_update_courses(
    course_ids: List[int],
    updates: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Bulk update multiple courses."""
    advanced_course_service = AdvancedCourseService(db)
    
    # Validate permissions for all courses
    valid_courses = await advanced_course_service.validate_instructor_courses(
        course_ids=course_ids,
        instructor_id=current_user.id
    )
    
    if len(valid_courses) != len(course_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Some courses are not accessible"
        )
    
    # Schedule bulk update task
    background_tasks.add_task(
        advanced_course_service.bulk_update_courses,
        course_ids,
        updates,
        current_user.id
    )
    
    return {
        "message": f"Bulk update scheduled for {len(course_ids)} courses",
        "course_ids": course_ids,
        "updates": updates,
        "estimated_completion": "5-10 minutes"
    }