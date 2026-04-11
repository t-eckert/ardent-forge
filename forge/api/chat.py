import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from forge.store import TaskStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat")

_store: TaskStore | None = None
_anthropic_api_key: str | None = None
_chat_model: str = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are Ardent Forge's assistant. You help the user manage tasks, check on agent activity, and answer questions about their projects. Be concise and helpful. When the user asks you to do something that sounds like a task (write code, research something, generate a report), let them know they can create a task for it."""


def configure(store: TaskStore, anthropic_api_key: str | None = None, model: str | None = None):
    global _store, _anthropic_api_key, _chat_model
    _store = store
    _anthropic_api_key = anthropic_api_key
    if model:
        _chat_model = model


def get_store() -> TaskStore:
    if _store is None:
        raise RuntimeError("Chat store not configured")
    return _store


class ChatRequest(BaseModel):
    content: str


@router.get("/messages")
async def list_messages():
    store = get_store()
    messages = await store.list_chat_messages()
    return messages


@router.delete("/messages")
async def clear_messages():
    store = get_store()
    await store.clear_chat_messages()
    return {"status": "cleared"}


@router.post("")
async def send_message(req: ChatRequest):
    store = get_store()

    # Save user message
    await store.save_chat_message(role="user", content=req.content)

    if not _anthropic_api_key:
        # No API key — return a streaming-compatible plaintext response
        fallback = "Chat is not configured. Set FORGE_ANTHROPIC_API_KEY to enable."
        await store.save_chat_message(role="assistant", content=fallback)

        async def fallback_stream():
            yield fallback

        return StreamingResponse(fallback_stream(), media_type="text/plain")

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=_anthropic_api_key)

    # Build message history from stored messages
    history = await store.list_chat_messages(limit=50)
    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
        if msg["role"] in ("user", "assistant")
    ]

    async def generate():
        full_response = ""
        try:
            async with client.messages.stream(
                model=_chat_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text
                    yield text
        except Exception as e:
            logger.exception("Chat streaming error")
            error_msg = f"\n\n[Error: {e}]"
            full_response += error_msg
            yield error_msg
        finally:
            # Save the complete assistant response
            await store.save_chat_message(role="assistant", content=full_response)

    return StreamingResponse(generate(), media_type="text/plain")
