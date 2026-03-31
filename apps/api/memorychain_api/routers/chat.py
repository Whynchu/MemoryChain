from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..schemas import ChatRequest, ChatResponse, ConversationMessage
from ..services.chat import handle_chat
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, repo: Repository = Depends(protected_repo)) -> ChatResponse:
    return handle_chat(repo, payload)


@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessage])
def get_conversation_messages(
    conversation_id: str,
    user_id: str,
    limit: int = 50,
    repo: Repository = Depends(protected_repo),
) -> list[ConversationMessage]:
    return repo.list_conversation_messages(conversation_id=conversation_id, limit=limit, user_id=user_id)

