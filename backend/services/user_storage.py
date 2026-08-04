import uuid
from datetime import datetime

from services.firestore_service import db

USERS_COLLECTION = "users"
SESSIONS_COLLECTION = "sessions"
CONVERSATIONS_COLLECTION = "conversations"


# ==========================================================
# USERS
# ==========================================================

def get_user(email: str):
    """Fetch a single user document by email. Returns dict or None."""
    try:
        doc = db.collection(USERS_COLLECTION).document(email).get()

        if not doc.exists:
            return None

        return doc.to_dict()

    except Exception as e:
        print("Firestore get_user error:", e)
        return None


def user_exists(email: str) -> bool:
    return get_user(email) is not None


def create_user(email: str, data: dict) -> bool:
    """Create a new user document. data should NOT include email as a key."""
    try:
        db.collection(USERS_COLLECTION).document(email).set(data)
        print(f"✅ User created: {email}")
        return True

    except Exception as e:
        print("Firestore create_user error:", e)
        return False


def update_user(email: str, data: dict) -> bool:
    """Partial update of an existing user document."""
    try:
        db.collection(USERS_COLLECTION).document(email).update(data)
        return True

    except Exception as e:
        print("Firestore update_user error:", e)
        return False


# ==========================================================
# SESSIONS
# ==========================================================

def get_session(session_token: str):
    """Returns the email tied to a session token, or None."""
    try:
        doc = db.collection(SESSIONS_COLLECTION).document(session_token).get()

        if not doc.exists:
            return None

        return doc.to_dict().get("email")

    except Exception as e:
        print("Firestore get_session error:", e)
        return None


def create_session(session_token: str, email: str) -> bool:
    try:
        db.collection(SESSIONS_COLLECTION).document(session_token).set({
            "email": email,
            "created_at": datetime.utcnow().isoformat()
        })
        return True

    except Exception as e:
        print("Firestore create_session error:", e)
        return False


def delete_session(session_token: str) -> bool:
    try:
        db.collection(SESSIONS_COLLECTION).document(session_token).delete()
        return True

    except Exception as e:
        print("Firestore delete_session error:", e)
        return False


# ==========================================================
# FIRESTORE CONVERSATIONS
# ==========================================================

def create_conversation(
    user_id: str = None,
    title: str = "New Chat"
):
    try:
        conversation_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conversation_data = {
            "id": conversation_id,
            "user_id": user_id,
            "title": title,
            "pinned": False,
            "messages": [],
            "message_count": 0,
            "created_at": now,
            "updated_at": now
        }

        db.collection(CONVERSATIONS_COLLECTION) \
            .document(conversation_id) \
            .set(conversation_data)

        return conversation_id

    except Exception as e:
        print("\n❌ Firestore CREATE error")
        print(e)
        raise


def get_conversation(conversation_id):
    try:
        doc = (
            db.collection(CONVERSATIONS_COLLECTION)
            .document(conversation_id)
            .get()
        )

        if not doc.exists:
            return None

        return doc.to_dict()

    except Exception as e:
        print("Firestore get conversation error:", e)
        return None


def get_user_conversations(user_id):
    try:
        docs = (
            db.collection(CONVERSATIONS_COLLECTION)
            .where("user_id", "==", user_id)
            .stream()
        )

        conversations = [doc.to_dict() for doc in docs]

        conversations.sort(
            key=lambda x: (
                not x.get("pinned", False),
                x.get("updated_at", "")
            ),
            reverse=True
        )

        return conversations

    except Exception as e:
        print("❌ Firestore conversation fetch error:", e)
        return []


def add_message_to_conversation(
    conversation_id,
    role,
    content,
    sources=None
):
    try:
        conversation = get_conversation(conversation_id)

        if not conversation:
            print("Conversation not found while saving message:", conversation_id)
            return False

        now = datetime.utcnow().isoformat()

        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "sources": sources or [],
            "timestamp": now
        }

        messages = conversation.get("messages", [])
        messages.append(message)

        update_data = {
            "messages": messages,
            "message_count": len(messages),
            "updated_at": now
        }

        if role == "user" and conversation.get("title") == "New Chat":
            title = content.strip()
            if len(title) > 50:
                title = title[:50] + "..."
            update_data["title"] = title

        db.collection(CONVERSATIONS_COLLECTION) \
            .document(conversation_id) \
            .update(update_data)

        return True

    except Exception as e:
        print("\n❌ Firestore message save error")
        print(e)
        return False


def rename_conversation(conversation_id, title):
    try:
        db.collection(CONVERSATIONS_COLLECTION) \
            .document(conversation_id) \
            .update({
                "title": title,
                "updated_at": datetime.utcnow().isoformat()
            })
        return True

    except Exception as e:
        print("Rename conversation error:", e)
        return False


def toggle_pin_conversation(conversation_id, pinned):
    try:
        db.collection(CONVERSATIONS_COLLECTION) \
            .document(conversation_id) \
            .update({
                "pinned": pinned,
                "updated_at": datetime.utcnow().isoformat()
            })
        return True

    except Exception as e:
        print("Toggle pin error:", e)
        return False


def delete_conversation(conversation_id):
    try:
        db.collection(CONVERSATIONS_COLLECTION) \
            .document(conversation_id) \
            .delete()
        return True

    except Exception as e:
        print("Delete conversation error:", e)
        return False