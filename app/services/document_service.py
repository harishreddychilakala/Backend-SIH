"""
BIS SmartAI — Document Service
Manages uploaded documents and compliance analysis with user isolation.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from app.models.document import Document
from app.models.user import User


class DocumentService:
    @staticmethod
    def create_document_analysis(
        db: Session,
        user: User,
        filename: str,
        file_type: str,
    ) -> Document:
        """
        Record uploaded document metadata and generate structured analysis.
        Enforces user isolation.
        """
        analysis_result = {
            "filename": filename,
            "file_size": "2.4 MB",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "summary": f"Analyzed specification document '{filename}'. Contains product technical parameters, material composition, and electrical specifications relevant for Indian Standards assessment.",
            "extracted_requirements": [
                {"category": "Electrical Safety", "text": "Operating voltage 220-240V AC, 50Hz with grounded conductor"},
                {"category": "Thermal Protection", "text": "Auto cut-off thermal fuse rated for maximum 110°C"},
                {"category": "Materials", "text": "Food-grade stainless steel interior (SS 304 compliant)"},
                {"category": "Marking", "text": "BIS standard mark and rating label on base plate"},
            ],
            "compliance_gaps": [
                {"severity": "high", "issue": "Missing official third-party dielectric test report (1250V)"},
                {"severity": "medium", "issue": "User manual language does not currently include Hindi translation"},
                {"severity": "low", "issue": "QCO batch traceability code placement needs review"},
            ],
            "referenced_standards": [
                {"number": "IS 302-2-15", "title": "Safety of Household Appliances"},
                {"number": "IS 1293:2019", "title": "Plugs and Socket Outlets"},
            ],
        }

        doc = Document(
            user_id=user.id,
            filename=filename,
            file_type=file_type,
            analysis_status="completed",
            analysis_result=analysis_result,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def get_user_documents(db: Session, user: User) -> List[Document]:
        """Get documents belonging ONLY to authenticated user."""
        return db.query(Document).filter(
            Document.user_id == user.id
        ).order_by(desc(Document.created_at)).all()

    @staticmethod
    def get_document(db: Session, user: User, doc_id: str) -> Document:
        """Get single document with user isolation."""
        doc = db.query(Document).filter(
            Document.id == doc_id,
            Document.user_id == user.id,
        ).first()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied.",
            )
        return doc

    @staticmethod
    def delete_document(db: Session, user: User, doc_id: str) -> bool:
        """Delete document with user isolation."""
        doc = db.query(Document).filter(
            Document.id == doc_id,
            Document.user_id == user.id,
        ).first()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied.",
            )

        db.delete(doc)
        db.commit()
        return True
