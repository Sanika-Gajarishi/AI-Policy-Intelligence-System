from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from services.user_storage import (
    create_conversation,
    get_conversation,
    add_message_to_conversation,
    get_user_conversations,
    delete_conversation,
    rename_conversation,
    toggle_pin_conversation
)

router = APIRouter()
class RenameConversationRequest(BaseModel):
    title: str

class CreateConversationRequest(BaseModel):
    user_id: Optional[str] = None
    title: str = "New Chat"


class AddMessageRequest(BaseModel):
    conversation_id: str
    role: str  # "user" or "assistant"
    content: str
    sources: Optional[List[dict]] = None


@router.post("/conversations")
def create_conversation_endpoint(request: CreateConversationRequest):
    """Create a new conversation"""
    try:
        conversation_id = create_conversation(
            user_id=request.user_id,
            title=request.title
        )
        conversation = get_conversation(conversation_id)
        return {"conversation": conversation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}")
def get_conversation_endpoint(conversation_id: str):
    """Get a conversation by ID"""
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation": conversation}


@router.post("/conversations/message")
def add_message_endpoint(request: AddMessageRequest):
    """Add a message to a conversation"""
    success = add_message_to_conversation(
        conversation_id=request.conversation_id,
        role=request.role,
        content=request.content,
        sources=request.sources
    )
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation = get_conversation(request.conversation_id)
    return {"conversation": conversation}


@router.get("/conversations/user/{user_id}")
def get_user_conversations_endpoint(user_id: str):
    """Get all conversations for a user"""
    conversations = get_user_conversations(user_id)
    return {"conversations": conversations}


@router.delete("/conversations/{conversation_id}")
def delete_conversation_endpoint(conversation_id: str):
    """Delete a conversation"""
    success = delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted successfully"}

@router.put("/conversations/{conversation_id}/rename")
def rename_conversation_endpoint(
    conversation_id: str,
    request: RenameConversationRequest
):
    success = rename_conversation(
        conversation_id,
        request.title
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

    return {"message": "Conversation renamed"}

@router.put("/conversations/{conversation_id}/pin")
def pin_conversation_endpoint(
    conversation_id: str,
    pinned: bool
):
    success = toggle_pin_conversation(
        conversation_id,
        pinned
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

    return {
        "message": "Conversation updated"
    }