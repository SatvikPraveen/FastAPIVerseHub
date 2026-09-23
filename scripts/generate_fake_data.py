#!/usr/bin/env python3
"""
Generate fake data for local development.

Creates users (one admin), courses, enrollments, reviews and file-upload
records using the real ORM models, so the seeded database is exactly what
the application expects.

    python scripts/generate_fake_data.py --yes --users 50 --courses 30
    python scripts/generate_fake_data.py --clear --yes

Uses the synchronous driver derived from DATABASE_URL (psycopg2 / sqlite).
"""

from __future__ import annotations

import argparse
import os
import random
import re
import sys
from datetime import timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models  # noqa: F401 - register every table
from app.core.config import settings
from app.core.security import get_password_hash
from app.core.time import utcnow
from app.models.course import (
    Course,
    CourseReview,
    CourseStatus,
    DifficultyLevel,
    Enrollment,
    EnrollmentStatus,
)
from app.models.user import FileUpload, User

fake = Faker()
Faker.seed(42)
random.seed(42)

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"
USER_PASSWORD = "password123"

CATEGORIES = [
    "programming",
    "web-development",
    "data-science",
    "mobile-development",
    "devops",
    "design",
    "business",
    "marketing",
]
TAGS = ["python", "fastapi", "sql", "docker", "react", "aws", "ml", "testing", "async"]


def sync_database_url() -> str:
    """Strip async drivers so a plain synchronous engine can be used."""
    url = settings.DATABASE_URL
    return url.replace("+asyncpg", "").replace("+aiosqlite", "")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class DataGenerator:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users: list[User] = []
        self.courses: list[Course] = []
        self.enrollments = 0
        self.reviews = 0
        self.files = 0

    # ------------------------------------------------------------------

    def generate_users(self, count: int) -> None:
        print(f"Generating {count} users...")
        password_hash = get_password_hash(USER_PASSWORD)  # hash once: bcrypt is slow on purpose
        for _ in range(count):
            self.users.append(
                User(
                    email=fake.unique.email(),
                    hashed_password=password_hash,
                    full_name=fake.name(),
                    bio=fake.text(max_nb_chars=160) if random.random() < 0.5 else None,
                    is_active=random.random() < 0.9,
                    is_verified=random.random() < 0.7,
                    avatar_url=fake.image_url() if random.random() < 0.4 else None,
                    location=fake.city(),
                    skill_level=random.choice(["beginner", "intermediate", "advanced"]),
                    interests=random.sample(TAGS, k=random.randint(1, 3)),
                    last_login_at=utcnow() - timedelta(days=random.randint(0, 30)),
                    login_count=random.randint(0, 50),
                )
            )
        self.users.append(
            User(
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                full_name="Administrator",
                bio="System administrator",
                is_active=True,
                is_verified=True,
                is_superuser=True,
                last_login_at=utcnow() - timedelta(hours=1),
            )
        )
        self.session.add_all(self.users)
        self.session.commit()
        print(f"  created {len(self.users)} users (admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD})")

    def generate_courses(self, count: int) -> None:
        print(f"Generating {count} courses...")
        instructors = [u for u in self.users if u.is_active] or self.users
        used_slugs: set[str] = set()
        for i in range(count):
            title = self._course_title()
            slug = slugify(title)
            if slug in used_slugs:
                slug = f"{slug}-{i}"
            used_slugs.add(slug)
            published = random.random() < 0.75
            price = random.choice([0, 9.99, 19.99, 29.99, 49.99, 99.99])
            self.courses.append(
                Course(
                    title=title,
                    slug=slug,
                    description=fake.text(max_nb_chars=500),
                    short_description=fake.sentence(nb_words=12),
                    instructor_id=random.choice(instructors).id,
                    category=random.choice(CATEGORIES),
                    tags=random.sample(TAGS, k=random.randint(1, 4)),
                    difficulty=random.choice(list(DifficultyLevel)),
                    estimated_duration_hours=random.randint(1, 40),
                    learning_objectives=[fake.sentence() for _ in range(3)],
                    price=Decimal(str(price)),
                    is_free=price == 0,
                    status=CourseStatus.PUBLISHED if published else CourseStatus.DRAFT,
                    is_published=published,
                    is_featured=random.random() < 0.1,
                    published_at=utcnow() - timedelta(days=random.randint(1, 365))
                    if published
                    else None,
                    thumbnail_url=fake.image_url() if random.random() < 0.5 else None,
                )
            )
        self.session.add_all(self.courses)
        self.session.commit()
        print(f"  created {len(self.courses)} courses")

    def generate_enrollments(self, enrollment_rate: float = 0.3) -> None:
        print("Generating enrollments and reviews...")
        published = [c for c in self.courses if c.is_published]
        for user in self.users:
            if user.is_superuser or not published:
                continue
            for course in random.sample(published, k=min(len(published), random.randint(0, 6))):
                if random.random() > enrollment_rate or course.instructor_id == user.id:
                    continue
                status = random.choices(
                    [EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED, EnrollmentStatus.DROPPED],
                    weights=[6, 3, 1],
                )[0]
                progress = (
                    Decimal("100.00")
                    if status == EnrollmentStatus.COMPLETED
                    else Decimal(str(round(random.uniform(0, 95), 2)))
                )
                self.session.add(
                    Enrollment(
                        user_id=user.id,
                        course_id=course.id,
                        status=status,
                        progress_percentage=progress,
                        payment_amount=None if course.is_free else course.price,
                        payment_currency=None if course.is_free else course.currency,
                        total_time_spent_minutes=random.randint(0, 600),
                        completed_at=utcnow() - timedelta(days=random.randint(0, 60))
                        if status == EnrollmentStatus.COMPLETED
                        else None,
                    )
                )
                self.enrollments += 1
                if status == EnrollmentStatus.COMPLETED and random.random() < 0.6:
                    self.session.add(
                        CourseReview(
                            user_id=user.id,
                            course_id=course.id,
                            rating=random.randint(3, 5),
                            title=fake.sentence(nb_words=5),
                            content=fake.paragraph(),
                            is_verified_purchase=not course.is_free,
                        )
                    )
                    self.reviews += 1
        self.session.commit()
        print(f"  created {self.enrollments} enrollments and {self.reviews} reviews")

    def generate_files(self) -> None:
        print("Generating file-upload records (metadata only)...")
        extensions = {"pdf": "application/pdf", "png": "image/png", "docx": "application/msword"}
        for user in random.sample(self.users, k=min(20, len(self.users))):
            for _ in range(random.randint(0, 4)):
                ext, mime = random.choice(list(extensions.items()))
                name = f"{fake.word()}-{fake.word()}.{ext}"
                self.session.add(
                    FileUpload(
                        user_id=user.id,
                        filename=f"{fake.uuid4()}.{ext}",
                        original_filename=name,
                        file_path=f"{settings.UPLOAD_PATH}/{user.id}/{name}",
                        file_size=random.randint(10_000, 5_000_000),
                        content_type=mime,
                        category=random.choice(["documents", "images", "general"]),
                        is_public=random.random() < 0.3,
                        download_count=random.randint(0, 40),
                    )
                )
                self.files += 1
        self.session.commit()
        print(f"  created {self.files} file records")

    # ------------------------------------------------------------------

    @staticmethod
    def _course_title() -> str:
        tech = random.choice(
            ["Python", "FastAPI", "React", "SQL", "Docker", "AWS", "Machine Learning", "Testing"]
        )
        action = random.choice(["Complete Guide to", "Master", "Practical", "Introduction to"])
        descriptor = random.choice(["for Beginners", "from Scratch", "Masterclass", "Bootcamp"])
        return random.choice(
            [f"{action} {tech} {descriptor}", f"{tech} {descriptor}", f"{action} {tech}"]
        )

    def print_summary(self) -> None:
        print("\n" + "=" * 50)
        print("DATA GENERATION SUMMARY")
        print("=" * 50)
        print(f"Users:        {len(self.users)}")
        print(
            f"Courses:      {len(self.courses)} ({sum(c.is_published for c in self.courses)} published)"
        )
        print(f"Enrollments:  {self.enrollments}")
        print(f"Reviews:      {self.reviews}")
        print(f"File records: {self.files}")
        print(f"\nAdmin login: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"Other users: <any email above> / {USER_PASSWORD}")


def clear_existing_data(session: Session) -> None:
    print("Clearing existing data...")
    for model in (CourseReview, Enrollment, FileUpload, Course, User):
        session.execute(delete(model))
    session.commit()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate fake users, courses and enrollments.")
    parser.add_argument("--users", type=int, default=50, help="number of users (default: 50)")
    parser.add_argument("--courses", type=int, default=30, help="number of courses (default: 30)")
    parser.add_argument("--clear", action="store_true", help="delete existing rows first")
    parser.add_argument("-y", "--yes", action="store_true", help="never prompt")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    print("FastAPIVerseHub Fake Data Generator")
    print("==================================")

    engine = create_engine(sync_database_url())
    session_factory = sessionmaker(bind=engine, autoflush=False)
    with session_factory() as session:
        clear = args.clear
        if not args.yes and not clear:
            clear = input("Clear existing data? (y/N): ").lower().strip() == "y"
        if clear:
            clear_existing_data(session)

        generator = DataGenerator(session)
        generator.generate_users(args.users)
        generator.generate_courses(args.courses)
        generator.generate_enrollments()
        generator.generate_files()
        generator.print_summary()


if __name__ == "__main__":
    main()
