"""
Questionnaire template management endpoints.

Provides CRUD operations for questionnaire templates - the structure
that defines what questions to ask in a conversational questionnaire.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import protected_repo
from ..schemas import QuestionnaireTemplate, QuestionnaireTemplateCreate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/questionnaires", tags=["questionnaires"])


@router.post("/templates", response_model=QuestionnaireTemplate)
def create_template(
    template: QuestionnaireTemplateCreate, 
    repo: Repository = Depends(protected_repo)
) -> QuestionnaireTemplate:
    """Create a new questionnaire template."""
    return repo.create_questionnaire_template(template)


@router.get("/templates", response_model=list[QuestionnaireTemplate])
def list_templates(
    user_id: str,
    active_only: bool = True, 
    repo: Repository = Depends(protected_repo)
) -> list[QuestionnaireTemplate]:
    """List questionnaire templates for the authenticated user."""
    return repo.list_questionnaire_templates(user_id, active_only=active_only)


@router.get("/templates/{template_id}", response_model=QuestionnaireTemplate)
def get_template(
    template_id: str, 
    user_id: str,
    repo: Repository = Depends(protected_repo)
) -> QuestionnaireTemplate:
    """Get a specific questionnaire template."""
    template = repo.get_questionnaire_template(template_id, user_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Template not found"
        )
    return template


# TODO: Add update/delete endpoints if needed in later phases