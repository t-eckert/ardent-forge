import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from forge.connectors import ConnectorRegistry
from forge.orchestrator import ForgeOrchestrator
from forge.store import TaskStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat")

_store: TaskStore | None = None
_connectors: ConnectorRegistry | None = None
_orchestrator: ForgeOrchestrator | None = None
_anthropic_api_key: str | None = None
_chat_model: str = "claude-sonnet-4-20250514"


def _default_anthropic_client(api_key: str):
    import anthropic
    return anthropic.AsyncAnthropic(api_key=api_key)


_anthropic_client_factory = _default_anthropic_client


def set_anthropic_client_factory(factory):
    """For testing — replace the Anthropic client factory."""
    global _anthropic_client_factory
    _anthropic_client_factory = factory


def configure(
    store: TaskStore,
    connectors: ConnectorRegistry | None = None,
    orchestrator: ForgeOrchestrator | None = None,
    anthropic_api_key: str | None = None,
    model: str | None = None,
):
    global _store, _connectors, _orchestrator, _anthropic_api_key, _chat_model
    _store = store
    if connectors is not None:
        _connectors = connectors
    if orchestrator is not None:
        _orchestrator = orchestrator
    _anthropic_api_key = anthropic_api_key
    if model:
        _chat_model = model


def get_connectors() -> ConnectorRegistry:
    if _connectors is None:
        raise RuntimeError("Chat connector registry not configured")
    return _connectors


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
        fallback = "Chat is not configured. Set FORGE_ANTHROPIC_API_KEY to enable."
        await store.save_chat_message(role="assistant", content=fallback)

        async def fallback_stream():
            yield fallback

        return StreamingResponse(fallback_stream(), media_type="text/plain")

    orchestrator = _orchestrator
    connectors = _connectors
    if orchestrator is not None:
        system_prompt = orchestrator.system_prompt()
        tool_schemas = orchestrator.tool_schemas()
    else:
        # Back-compat path if the orchestrator wasn't wired (e.g. isolated tests).
        from forge.orchestrator.persona import PERSONA
        system_prompt = PERSONA
        tool_schemas = (
            [t.to_anthropic_schema() for t in connectors.all_tools()] if connectors else []
        )

    client = _anthropic_client_factory(_anthropic_api_key)

    history = await store.list_chat_messages(limit=50)
    messages: list[dict] = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
        if msg["role"] in ("user", "assistant")
    ]

    async def generate():
        full_response = ""
        try:
            for _ in range(5):  # cap tool-use loops to prevent runaway
                stream_kwargs: dict = {
                    "model": _chat_model,
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": messages,
                }
                if tool_schemas:
                    stream_kwargs["tools"] = tool_schemas

                async with client.messages.stream(**stream_kwargs) as stream:
                    async for text in stream.text_stream:
                        full_response += text
                        yield text
                    final_message = await stream.get_final_message()

                if final_message.stop_reason != "tool_use":
                    break

                # Append assistant message with tool use blocks
                messages.append(
                    {"role": "assistant", "content": final_message.content}
                )

                # Execute each tool_use block via the connector registry.
                tool_results = []
                for block in final_message.content:
                    if block.type != "tool_use":
                        continue
                    if orchestrator is not None:
                        tool, _shape = orchestrator.resolve_tool_call(block.name)
                    else:
                        tool = connectors.find_tool(block.name) if connectors else None
                    if tool is None:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Unknown tool: {block.name}",
                            "is_error": True,
                        })
                        continue
                    try:
                        result = await tool.execute(**block.input)
                    except Exception as exc:  # noqa: BLE001 — tool-level failures surface to Claude
                        logger.exception("Tool %s raised", block.name)
                        result = {"error": str(exc)}
                    is_error = isinstance(result, dict) and "error" in result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                        "is_error": is_error,
                    })

                messages.append({"role": "user", "content": tool_results})
        except Exception as e:
            logger.exception("Chat streaming error")
            error_msg = f"\n\n[Error: {e}]"
            full_response += error_msg
            yield error_msg
        finally:
            await store.save_chat_message(role="assistant", content=full_response)

    return StreamingResponse(generate(), media_type="text/plain")
