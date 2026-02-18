# database.py
"""
Database connection and ORM models for MatchMyJobs
Uses SQLAlchemy with PostgreSQL
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DECIMAL, TIMESTAMP, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import QueuePool

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    # Fallback to localhost for local development
    "postgresql://postgres:postgres@localhost:5432/matchmyjobs"
)

# Fix for Render's postgres:// URL (should be postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL query logging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# ═══════════════════════════════════════════════════════════════════════════════
# ORM Models (matching your existing database schema)
# ═══════════════════════════════════════════════════════════════════════════════

class User(Base):
    """User model - stores user account information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    tier = Column(String(50), default="free")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    usage_records = relationship("Usage", back_populates="user")
    payments = relationship("Payment", back_populates="user")


class Usage(Base):
    """Usage tracking model - tracks monthly analysis counts"""
    __tablename__ = "usage"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month_year = Column(String(7), nullable=False)  # Format: "2025-02"
    analyses_count = Column(Integer, default=0)
    optimizations_count = Column(Integer, default=0)
    
    # Composite unique constraint
    __table_args__ = (
        Index("idx_usage_user_month", "user_id", "month_year"),
    )
    
    # Relationships
    user = relationship("User", back_populates="usage_records")


class Payment(Base):
    """Payment model - stores transaction records"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    tier = Column(String(50), nullable=False)
    transaction_id = Column(String(255), unique=True)
    status = Column(String(50), default="completed")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="payments")


# ═══════════════════════════════════════════════════════════════════════════════
# Database Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_db():
    """
    Dependency for FastAPI routes to get database session.
    
    Usage in routes:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables.
    Run this once when setting up the application.
    
    NOTE: Your tables already exist, so this is optional.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")


def check_db_connection():
    """Test database connection"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# User Service Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_user_by_email(db, email: str):
    """Get user by email address"""
    return db.query(User).filter(User.email == email).first()


def create_user(db, email: str, full_name: str, password_hash: str, tier: str = "free"):
    """Create a new user"""
    user = User(
        email=email,
        full_name=full_name,
        password_hash=password_hash,
        tier=tier
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_month_usage(db, user_id: int):
    """Get usage count for current month"""
    current_month = datetime.now().strftime("%Y-%m")
    
    usage = db.query(Usage).filter(
        Usage.user_id == user_id,
        Usage.month_year == current_month
    ).first()
    
    if not usage:
        # Create new usage record for this month
        usage = Usage(
            user_id=user_id,
            month_year=current_month,
            analyses_count=0,
            optimizations_count=0
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)
    
    return usage


def increment_analysis_count(db, user_id: int):
    """Increment analysis count for current month"""
    usage = get_current_month_usage(db, user_id)
    usage.analyses_count += 1
    db.commit()
    return usage.analyses_count


# Tier limits — single source of truth, importable by other modules
TIER_LIMITS = {
    "free":       {"analyses": 5,    "optimizations": 1},
    "job_seeker": {"analyses": 120,  "optimizations": 5},
    "unlimited":  {"analyses": 500,  "optimizations": 15},
    "recruiter":  {"analyses": 1000, "optimizations": 50},
}


def check_analysis_limit(db, user_id: int):
    """
    Check if user has reached their analysis limit.
    Returns: (can_analyze: bool, current_count: int, limit: int)
    """
    user  = db.query(User).filter(User.id == user_id).first()
    usage = get_current_month_usage(db, user_id)

    tier_config = TIER_LIMITS.get(user.tier, TIER_LIMITS["free"])
    limit       = tier_config["analyses"]
    can_analyze = usage.analyses_count < limit

    return can_analyze, usage.analyses_count, limit


# ═══════════════════════════════════════════════════════════════════════════════
# Example Usage (for testing)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test database connection
    print("Testing database connection...")
    if check_db_connection():
        print("✅ Database connected successfully!")
        
        # Example: Query users
        db = SessionLocal()
        users = db.query(User).all()
        print(f"Total users in database: {len(users)}")
        
        for user in users[:5]:  # Show first 5
            print(f"  - {user.email} ({user.tier})")
        
        db.close()
    else:
        print("❌ Database connection failed!")
        print("Check your DATABASE_URL environment variable")
