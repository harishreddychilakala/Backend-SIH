"""
Documents API Endpoints
POST   /api/documents
GET    /api/documents
GET    /api/documents/{id}
DELETE /api/documents/{id}
"""
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Document Analysis"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload and analyze a product photo, technical specification, or BIS document."""
    file_type = file.content_type or "application/octet-stream"
    file_bytes = await file.read()
    doc = DocumentService.create_document_analysis(
        db=db,
        user=current_user,
        filename=file.filename or "uploaded_document",
        file_type=file_type,
        file_bytes=file_bytes,
    )
    return doc


@router.get("", response_model=List[DocumentResponse])
def get_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all uploaded documents for the authenticated user."""
    return DocumentService.get_user_documents(db=db, user=current_user)


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analysis details for a specific document."""
    return DocumentService.get_document(db=db, user=current_user, doc_id=doc_id)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document record for the authenticated user."""
    DocumentService.delete_document(db=db, user=current_user, doc_id=doc_id)
    return None
