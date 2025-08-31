#!/usr/bin/env python3
"""
File Location: scripts/generate_fake_data.py

Generate fake data for testing the FastAPIVerseHub application.
This script creates sample users, courses, and other test data.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import List

from faker import Faker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Import your models and database setup
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.models.base import Base
from app.models.user import User
from app.models.course import Course
from app.core.security import hash_password

fake = Faker()

# Database setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class DataGenerator:
    def __init__(self, session):
        self.session = session
        self.created_users = []
        self.created_courses = []
    
    def generate_users(self, count: int = 50) -> List[User]:
        """Generate fake users"""
        print(f"Generating {count} fake users...")
        
        users = []
        for i in range(count):
            user = User(
                email=fake.unique.email(),
                hashed_password=hash_password("password123"),  # Same password for all test users
                full_name=fake.name(),
                bio=fake.text(max_nb_chars=200) if random.choice([True, False]) else None,
                is_active=random.choice([True, True, True, False]),  # 75% active
                is_superuser=False,
                avatar_url=fake.image_url() if random.choice([True, False]) else None,
                date_joined=fake.date_time_between(start_date='-2y', end_date='now'),
                last_login=fake.date_time_between(start_date='-30d', end_date='now') if random.choice([True, False]) else None
            )
            users.append(user)
            
            if (i + 1) % 10 == 0:
                print(f"  Created {i + 1} users...")
        
        # Add one superuser
        admin_user = User(
            email="admin@example.com",
            hashed_password=hash_password("admin123"),
            full_name="Administrator",
            bio="System Administrator",
            is_active=True,
            is_superuser=True,
            date_joined=datetime.utcnow() - timedelta(days=365),
            last_login=datetime.utcnow() - timedelta(hours=1)
        )
        users.append(admin_user)
        
        self.session.add_all(users)
        self.session.commit()
        self.created_users = users
        print(f"✓ Generated {len(users)} users")
        return users
    
    def generate_courses(self, count: int = 30) -> List[Course]:
        """Generate fake courses"""
        print(f"Generating {count} fake courses...")
        
        categories = ['Programming', 'Web Development', 'Data Science', 'Mobile Development', 
                     'DevOps', 'Design', 'Business', 'Marketing', 'Photography', 'Music']
        
        difficulties = ['beginner', 'intermediate', 'advanced']
        
        courses = []
        for i in range(count):
            # Select random instructor from created users
            instructor = random.choice(self.created_users)
            
            course = Course(
                title=self._generate_course_title(),
                description=fake.text(max_nb_chars=500),
                category=random.choice(categories),
                difficulty=random.choice(difficulties),
                estimated_duration=random.randint(30, 480),  # 30 minutes to 8 hours
                instructor_id=instructor.id,
                is_published=random.choice([True, True, True, False]),  # 75% published
                created_at=fake.date_time_between(start_date='-1y', end_date='now'),
                updated_at=fake.date_time_between(start_date='-30d', end_date='now'),
                thumbnail_url=fake.image_url() if random.choice([True, False]) else None,
                price=random.choice([0, 9.99, 19.99, 29.99, 49.99, 99.99]) if random.choice([True, False]) else 0,
                rating=round(random.uniform(3.0, 5.0), 1) if random.choice([True, False]) else None,
                enrollment_count=random.randint(0, 1000)
            )
            courses.append(course)
            
            if (i + 1) % 10 == 0:
                print(f"  Created {i + 1} courses...")
        
        self.session.add_all(courses)
        self.session.commit()
        self.created_courses = courses
        print(f"✓ Generated {len(courses)} courses")
        return courses
    
    def _generate_course_title(self) -> str:
        """Generate realistic course titles"""
        tech_words = ['Python', 'JavaScript', 'React', 'Django', 'FastAPI', 'Node.js', 'SQL', 
                     'Docker', 'AWS', 'Machine Learning', 'Data Analysis', 'Web Design']
        
        action_words = ['Complete Guide to', 'Master', 'Learn', 'Build', 'Create', 
                       'Develop', 'Introduction to', 'Advanced', 'Practical']
        
        descriptors = ['for Beginners', 'from Scratch', 'in 30 Days', 'Masterclass', 
                      'Bootcamp', 'Workshop', 'Tutorial', 'Course']
        
        tech = random.choice(tech_words)
        action = random.choice(action_words)
        descriptor = random.choice(descriptors)
        
        templates = [
            f"{action} {tech} {descriptor}",
            f"{tech} {descriptor}",
            f"{action} {tech}",
            f"{tech}: {action} {descriptor}"
        ]
        
        return random.choice(templates)
    
    def generate_user_course_enrollments(self, enrollment_rate: float = 0.3):
        """Generate course enrollments for users"""
        print("Generating course enrollments...")
        
        enrollments_created = 0
        for user in self.created_users:
            if user.is_superuser:
                continue
                
            # Each user enrolls in random courses
            num_enrollments = random.randint(0, min(10, len(self.created_courses)))
            enrolled_courses = random.sample(self.created_courses, num_enrollments)
            
            for course in enrolled_courses:
                if random.random() < enrollment_rate:
                    # In a real app, you'd have an enrollment model
                    # For now, we'll just update the course enrollment count
                    course.enrollment_count += 1
                    enrollments_created += 1
        
        self.session.commit()
        print(f"✓ Generated {enrollments_created} course enrollments")
    
    def generate_sample_files(self):
        """Generate sample file records (without actual files)"""
        print("Generating sample file records...")
        
        # This would create file upload records
        # In a real implementation, you'd have a File model
        file_types = ['.pdf', '.docx', '.mp4', '.jpg', '.png']
        files_created = 0
        
        for user in random.sample(self.created_users, min(20, len(self.created_users))):
            num_files = random.randint(0, 5)
            for _ in range(num_files):
                filename = f"{fake.word()}{random.choice(file_types)}"
                # Create file record logic would go here
                files_created += 1
        
        print(f"✓ Generated {files_created} file records")
    
    def print_summary(self):
        """Print generation summary"""
        print("\n" + "="*50)
        print("DATA GENERATION SUMMARY")
        print("="*50)
        print(f"Users created: {len(self.created_users)}")
        print(f"Courses created: {len(self.created_courses)}")
        print(f"Active users: {sum(1 for u in self.created_users if u.is_active)}")
        print(f"Published courses: {sum(1 for c in self.created_courses if c.is_published)}")
        print("\nTest Accounts:")
        print("- Email: admin@example.com, Password: admin123 (Admin)")
        print("- All other users: Password: password123")
        print("="*50)

def clear_existing_data(session):
    """Clear existing test data"""
    print("Clearing existing data...")
    session.query(Course).delete()
    session.query(User).delete()
    session.commit()
    print("✓ Cleared existing data")

async def main():
    """Main function to generate all fake data"""
    print("FastAPIVerseHub Fake Data Generator")
    print("==================================")
    
    # Create database session
    session = SessionLocal()
    
    try:
        # Ask user if they want to clear existing data
        clear_data = input("Clear existing data? (y/N): ").lower().strip()
        if clear_data == 'y':
            clear_existing_data(session)
        
        # Initialize data generator
        generator = DataGenerator(session)
        
        # Get user input for data amounts
        try:
            user_count = int(input("Number of users to generate (default 50): ") or 50)
            course_count = int(input("Number of courses to generate (default 30): ") or 30)
        except ValueError:
            print("Invalid input, using defaults...")
            user_count = 50
            course_count = 30
        
        # Generate data
        print(f"\nGenerating data...")
        generator.generate_users(user_count)
        generator.generate_courses(course_count)
        generator.generate_user_course_enrollments()
        generator.generate_sample_files()
        
        # Print summary
        generator.print_summary()
        
    except Exception as e:
        print(f"Error generating data: {e}")
        session.rollback()
        raise
    
    finally:
        session.close()

if __name__ == "__main__":
    # Install required packages if not present
    try:
        import faker
    except ImportError:
        print("Installing required packages...")
        os.system("pip install faker")
        import faker
    
    # Run the data generation
    asyncio.run(main())