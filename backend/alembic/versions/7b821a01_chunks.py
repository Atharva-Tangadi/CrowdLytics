"""Version progressive chunks, including installations initialized by create_all.

Revision ID: 7b821a01
Revises: 2f3e752c631b
"""
from alembic import op
import sqlalchemy as sa

revision = "7b821a01"
down_revision = "2f3e752c631b"
branch_labels = depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("analysis_chunks"):
        op.create_table("analysis_chunks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("start_timestamp", sa.Float(), nullable=False),
            sa.Column("end_timestamp", sa.Float(), nullable=False),
            sa.Column("frame_count", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("frame_data_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False))
        op.create_index("ix_analysis_chunks_job_id", "analysis_chunks", ["job_id"])
        op.create_index("ix_analysis_chunks_chunk_index", "analysis_chunks", ["chunk_index"])


def downgrade():
    op.drop_table("analysis_chunks")
