import json
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index
)
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sessions = relationship("SessionRecord", back_populates="user", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="owner", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="owner", cascade="all, delete-orphan")

class SessionRecord(Base):
    __tablename__ = "sessions"

    id_hash = Column(String(64), primary_key=True)  # SHA-256 of raw session token
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    csrf_token = Column(String(64), nullable=False)  # Session-bound CSRF token
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="ready", nullable=False)
    original_filename = Column(String(255), nullable=False)
    row_count = Column(Integer, default=0, nullable=False)
    schema_json = Column(Text, default="{}", nullable=False)
    profile_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="datasets")
    rows = relationship("DatasetRow", back_populates="dataset", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="dataset", cascade="all, delete-orphan")

class DatasetRow(Base):
    __tablename__ = "dataset_rows"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    source_row_number = Column(Integer, nullable=False)  # 1-indexed original CSV row
    raw_json = Column(Text, nullable=False)              # Raw cell string values
    typed_json = Column(Text, nullable=False)            # Coerced typed values or null
    issues_json = Column(Text, default="[]", nullable=False) # List of row-level issues
    structurally_valid = Column(Boolean, default=True, nullable=False)

    dataset = relationship("Dataset", back_populates="rows")

    __table_args__ = (
        Index("ix_dataset_rows_dataset_id_source_row", "dataset_id", "source_row_number"),
    )

class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    filter_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="reports")
    dataset = relationship("Dataset", back_populates="reports")
    blocks = relationship("ReportBlock", back_populates="report", cascade="all, delete-orphan", order_by="ReportBlock.position")
    share_links = relationship("ShareLink", back_populates="report", cascade="all, delete-orphan")

class ReportBlock(Base):
    __tablename__ = "report_blocks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(50), nullable=False)  # metric, bar_chart, line_chart, top_n_table, note
    position = Column(Integer, nullable=False, default=0)
    config_json = Column(Text, default="{}", nullable=False)

    report = relationship("Report", back_populates="blocks")

    @property
    def title(self):
        try:
            return json.loads(self.config_json or "{}").get("title")
        except Exception:
            return None

    __table_args__ = (
        Index("ix_report_blocks_report_id_position", "report_id", "position"),
    )

class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True) # SHA-256 digest
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    report = relationship("Report", back_populates="share_links")
