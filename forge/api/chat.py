import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from forge.connectors import ConnectorRegistry
from forge.orchestrator import ForgeOrchestrator
from forge.store import TaskStore
from forge.thread_store import ThreadStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat")

_store: TaskStore | None = None
_connectors: ConnectorRegistry | None = None
_orchestrator: ForgeOrchestrator | None = None
_thread_store: ThreadStore | None = None
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
    thread_store: ThreadStore | None = None,
    anthropic_api_key: str | None = None,
    model: str | None = None,
):
    global _store, _connectors, _orchestrator, _thread_store, _anthropic_api_key, _chat_model
    _store = store
    if connectors is not None:
        _connectors = connectors
    if orchestrator is not None:
        _orchestrator = orchestrator
    if thread_store is not None:
        _thread_store = thread_store
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
    # Optional — when provided, the chat turn is persisted to the thread via
    # ThreadStore instead of the singleton chat log. Unknown thread_id → 404.
    thread_id: str | None = None


async def _handle_dispatch(
    *,
    block,
    thread_id: str | None,
    orchestrator: ForgeOrchestrator | None,
    store: TaskStore,
    dispatches_so_far: int,
    max_dispatches: int,
) -> tuple[dict, bool, bool]:
    """Create a Task from a dispatch_task tool_use and link it to the thread.

    Returns (tool_result_payload, is_error, dispatched). ``dispatched`` is True
    iff a Task row was actually created (used for metrics + turn shape).
    """
    # Dispatch only makes sense inside a thread — the resolution post-back
    # needs somewhere to land. A threadless dispatch is a programming error;
    # surface it loudly to Claude so it can recover by using a sync tool.
    if thread_id is None or _thread_store is None:
        return (
            {"error": "dispatch_task requires a thread context — no thread_id in this chat turn"},
            True,
            False,
        )
    if orchestrator is None or orchestrator.agents is None:
        return ({"error": "No agent registry configured"}, True, False)

    if dispatches_so_far >= max_dispatches:
        return (
            {"error": f"Dispatch cap reached ({max_dispatches}/turn). Try the remaining work inline or in a follow-up turn."},
            True,
            False,
        )

    args = block.input or {}
    task_type = args.get("task_type")
    title = args.get("title")
    description = args.get("description")
    if not task_type or not title or not description:
        return (
            {"error": "dispatch_task requires task_type, title, and description"},
            True,
            False,
        )

    agent = orchestrator.agents.get(task_type)
    if agent is None:
        known = sorted({a.task_type for a in orchestrator.agents.list()})
        return (
            {"error": f"Unknown task_type: {task_type!r}. Known: {known}"},
            True,
            False,
        )

    # Create the Task. Use the backend TaskType enum when the string matches
    # a known member, otherwise pass the raw string — the backend models
    # layer accepts both.
    from forge.models import Task, TaskSource, TaskType
    try:
        tt = TaskType(task_type)
    except ValueError:
        tt = task_type  # type: ignore[assignment]

    task = Task.new(
        task_type=tt,  # type: ignore[arg-type]
        source=TaskSource.CHAT,
        title=title,
        description=description,
    )
    await store.save(task)
    await _thread_store.link_task(
        thread_id=thread_id, task_id=task.id, relation="origin"
    )
    await _thread_store.append_message(
        thread_id=thread_id,
        role="assistant",
        content=f"dispatched {task_type} — {title}",
        variant="task-dispatched",
        task_id=task.id,
        tool_use_id=block.id,
    )
    return (
        {"status": "queued", "task_id": task.id, "task_type": task_type},
        False,
        True,
    )


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
    from forge.metrics import CHAT_TURNS_TOTAL, CHAT_TURN_DURATION_SECONDS
    import time as _time

    turn_start = _time.monotonic()
    turn_shape = "synchronous"  # updated inside generate() if tools are used
    store = get_store()

    # Thread-scoped vs singleton-log persistence. If the request names a
    # thread_id, we validate it exists and route the whole turn through
    # ThreadStore. Otherwise we fall back to the singleton chat log so the
    # Today composer keeps working.
    thread_id = req.thread_id
    if thread_id is not None:
        if _thread_store is None:
            raise HTTPException(status_code=500, detail="Thread store not configured")
        if await _thread_store.get(thread_id) is None:
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

    # Save user message to whichever log applies.
    if thread_id is not None:
        await _thread_store.append_message(
            thread_id=thread_id, role="user", content=req.content
        )
        await _thread_store.mark_activity(thread_id, unread=False)
    else:
        await store.save_chat_message(role="user", content=req.content)

    if not _anthropic_api_key:
        fallback = "Chat is not configured. Set FORGE_ANTHROPIC_API_KEY to enable."
        if thread_id is not None:
            await _thread_store.append_message(
                thread_id=thread_id, role="assistant", content=fallback
            )
        else:
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

    # Build history from whichever log applies. For threads, we include the
    # prose content of every message Claude can reason about (text,
    # task-dispatched, task-resolved narrations); dispatch/resolve cards are
    # flattened to their narration for LLM context, variants stay distinct
    # in the UI via the stored 'variant' column.
    if thread_id is not None:
        thread_msgs = await _thread_store.list_messages(thread_id, limit=50)
        messages: list[dict] = [
            {"role": m.role, "content": m.content}
            for m in thread_msgs
            if m.role in ("user", "assistant") and m.content
        ]
    else:
        history = await store.list_chat_messages(limit=50)
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
            if msg["role"] in ("user", "assistant")
        ]

    # Soft cap on how many tasks a single assistant turn can dispatch.
    # Matches the spirit of the tool-use loop cap below — it's a runaway
    # guard, not a product limit. See specs/2026-04-14-chat-dispatch-wiring.md.
    MAX_DISPATCHES_PER_TURN = 5

    async def generate():
        nonlocal turn_shape
        full_response = ""
        tool_use_happened = False
        dispatch_happened = False
        dispatches_this_turn = 0
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

                tool_use_happened = True
                # Append assistant message with tool use blocks
                messages.append(
                    {"role": "assistant", "content": final_message.content}
                )

                # Execute each tool_use block. Dispatch meta-tool is handled
                # specially — it creates a Task and returns a queued receipt
                # rather than executing inline.
                tool_results = []
                for block in final_message.content:
                    if block.type != "tool_use":
                        continue

                    # ─── Dispatch branch ───────────────────────────────────
                    if block.name == "dispatch_task":
                        result_payload, is_error, dispatched = await _handle_dispatch(
                            block=block,
                            thread_id=thread_id,
                            orchestrator=orchestrator,
                            store=store,
                            dispatches_so_far=dispatches_this_turn,
                            max_dispatches=MAX_DISPATCHES_PER_TURN,
                        )
                        if dispatched:
                            dispatch_happened = True
                            dispatches_this_turn += 1
                        try:
                            from forge.metrics import CHAT_TOOL_CALLS_TOTAL
                            CHAT_TOOL_CALLS_TOTAL.labels(
                                tool="dispatch_task",
                                connector="orchestrator",
                                result="error" if is_error else "ok",
                            ).inc()
                        except Exception:
                            pass
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result_payload),
                            "is_error": is_error,
                        })
                        continue

                    # ─── Synchronous connector tool ────────────────────────
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
                    try:
                        from forge.metrics import CHAT_TOOL_CALLS_TOTAL
                        CHAT_TOOL_CALLS_TOTAL.labels(
                            tool=block.name,
                            connector=getattr(tool, "connector_name", "unknown"),
                            result="error" if is_error else "ok",
                        ).inc()
                    except Exception:
                        pass
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                        "is_error": is_error,
                    })

                messages.append({"role": "user", "content": tool_results})
            if dispatch_happened:
                turn_shape = "task_dispatch"
            elif tool_use_happened:
                turn_shape = "synchronous_tool"
        except Exception as e:
            logger.exception("Chat streaming error")
            error_msg = f"\n\n[Error: {e}]"
            full_response += error_msg
            yield error_msg
            turn_shape = "error"
        finally:
            if thread_id is not None:
                await _thread_store.append_message(
                    thread_id=thread_id,
                    role="assistant",
                    content=full_response,
                    variant="text",
                )
                await _thread_store.mark_activity(thread_id, unread=False)
            else:
                await store.save_chat_message(role="assistant", content=full_response)
            try:
                CHAT_TURNS_TOTAL.labels(shape=turn_shape).inc()
                CHAT_TURN_DURATION_SECONDS.observe(_time.monotonic() - turn_start)
            except Exception:
                pass

    return StreamingResponse(generate(), media_type="text/plain")
