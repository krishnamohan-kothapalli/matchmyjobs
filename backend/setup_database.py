#!/usr/bin/env python3
"""
Database Setup & Test Script for MatchMyJobs
Run this to verify database connection and create test user
"""

import os
import sys
from datetime import datetime

# Set DATABASE_URL if not already set
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql://matchmyjobs_user:LeKAnOFlykhEAsSy55ce1582PRR6UYzx@dpg-d68uqbmr433s73cpfg5g-a.oregon-postgres.render.com/matchmyjobs"

from database import (
    SessionLocal, User, Usage, Payment,
    check_db_connection, get_user_by_email,
    get_current_month_usage, check_analysis_limit
)


def test_connection():
    """Test database connection"""
    print("🔌 Testing database connection...")
    if check_db_connection():
        print("✅ Database connected successfully!\n")
        return True
    else:
        print("❌ Database connection failed!")
        print("Check your DATABASE_URL environment variable\n")
        return False


def list_users():
    """List all users in database"""
    print("👥 Current users in database:")
    print("-" * 60)
    
    db = SessionLocal()
    users = db.query(User).all()
    
    if not users:
        print("   (No users found)")
    else:
        for user in users:
            print(f"   📧 {user.email}")
            print(f"      Name: {user.full_name}")
            print(f"      Tier: {user.tier}")
            print(f"      Created: {user.created_at}")
            
            # Get current month usage
            usage = get_current_month_usage(db, user.id)
            can_analyze, current, limit = check_analysis_limit(db, user.id)
            
            print(f"      Usage this month: {current}/{limit} analyses")
            print()
    
    db.close()
    print(f"Total users: {len(users)}\n")


def create_test_user(email="test@matchmyjobs.com"):
    """Create a test user if doesn't exist"""
    db = SessionLocal()
    
    # Check if user exists
    existing = get_user_by_email(db, email)
    if existing:
        print(f"ℹ️  Test user already exists: {email}")
        print(f"   Tier: {existing.tier}")
        
        usage = get_current_month_usage(db, existing.id)
        print(f"   Usage: {usage.analyses_count} analyses this month\n")
        db.close()
        return existing
    
    # Create new test user
    print(f"➕ Creating test user: {email}")
    
    user = User(
        email=email,
        password_hash="$2b$12$dummy_hash_for_testing",  # Dummy bcrypt hash
        full_name="Test User",
        tier="free"
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    print(f"✅ Test user created!")
    print(f"   Email: {user.email}")
    print(f"   Tier: {user.tier}")
    print(f"   ID: {user.id}\n")
    
    db.close()
    return user


def reset_user_usage(email):
    """Reset usage count for a user"""
    db = SessionLocal()
    
    user = get_user_by_email(db, email)
    if not user:
        print(f"❌ User not found: {email}")
        db.close()
        return
    
    usage = get_current_month_usage(db, user.id)
    old_count = usage.analyses_count
    
    usage.analyses_count = 0
    usage.optimizations_count = 0
    db.commit()
    
    print(f"✅ Usage reset for {email}")
    print(f"   Before: {old_count} analyses")
    print(f"   After: 0 analyses\n")
    
    db.close()


def show_usage_for_user(email):
    """Show detailed usage for a specific user"""
    db = SessionLocal()
    
    user = get_user_by_email(db, email)
    if not user:
        print(f"❌ User not found: {email}")
        db.close()
        return
    
    print(f"📊 Usage details for {email}")
    print("-" * 60)
    print(f"Tier: {user.tier}")
    
    # Get limit
    limits = {"free": 2, "analysis_pro": 50, "optimize": 50}
    limit = limits.get(user.tier, 2)
    
    # Get usage
    usage = get_current_month_usage(db, user.id)
    can_analyze, current, _ = check_analysis_limit(db, user.id)
    
    print(f"Current month ({usage.month_year}):")
    print(f"  Analyses: {usage.analyses_count}/{limit}")
    print(f"  Optimizations: {usage.optimizations_count}")
    print(f"  Can analyze: {'✅ Yes' if can_analyze else '❌ No (limit reached)'}")
    print()
    
    db.close()


def main():
    """Main setup script"""
    print("=" * 60)
    print("🗄️  MatchMyJobs Database Setup & Test")
    print("=" * 60)
    print()
    
    # Test connection
    if not test_connection():
        sys.exit(1)
    
    # List existing users
    list_users()
    
    # Create test user
    test_user = create_test_user("test@matchmyjobs.com")
    
    # Show usage
    show_usage_for_user("test@matchmyjobs.com")
    
    print("=" * 60)
    print("✅ Setup complete!")
    print()
    print("Next steps:")
    print("1. Test API: curl https://your-backend.onrender.com/api/usage/check \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"email\": \"test@matchmyjobs.com\"}'")
    print()
    print("2. Reset usage: curl 'https://your-backend.onrender.com/api/usage/reset-demo?email=test@matchmyjobs.com'")
    print()
    print("3. Add DATABASE_URL to Render environment variables")
    print("=" * 60)


if __name__ == "__main__":
    main()
