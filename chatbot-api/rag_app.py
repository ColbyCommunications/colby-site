from __future__ import annotations

import os
import json
from typing import Optional, AsyncIterator

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from agno.os import AgentOS
from agno.agent import Agent
from agno.exceptions import InputCheckError

from config_db import init_config_schema
from runtime_rag_knowledge import build_agent, build_agent_query_with_context
from input_validation_pre_hook import get_standard_rejection_message


# Load environment variables early and ensure the config schema exists.
load_dotenv()
init_config_schema()


def get_agent_config() -> dict:
    """Get agent configuration from environment variables."""
    return {
        "agent_id": os.getenv("AGENT_ID", "colby-rag"),
        "agent_name": os.getenv("AGENT_NAME", "Colby RAG Assistant"),
        "os_id": os.getenv("AGENT_OS_ID", "runtime-rag-os"),
        "os_description": os.getenv(
            "AGENT_OS_DESCRIPTION",
            "Runtime RAG OS exposing the knowledge-based assistant via API",
        ),
        "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
        "max_timeout": int(os.getenv("REQUEST_TIMEOUT", "300")),
    }


def create_assistant() -> Agent:
    """Create and configure a fresh assistant agent for each request."""
    assistant = build_agent()
    config = get_agent_config()
    # Agent IDs / names are kept in env for now; the underlying model + prompts
    # are configured via the config DB (see runtime_rag_knowledge.build_agent).
    assistant.id = config["agent_id"]
    assistant.name = config["agent_name"]
    return assistant


def create_agent_os(assistant: Agent) -> AgentOS:
    """Create AgentOS instance with the assistant."""
    config = get_agent_config()
    return AgentOS(
        os_id=config["os_id"],
        description=config["os_description"],
        agents=[assistant],
    )


def setup_cors(app, origins: list[str]):
    """Configure CORS middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Initialize agent and AgentOS (bootstrap agent used only for AgentOS wiring).
bootstrap_assistant: Agent = create_assistant()
agent_os: AgentOS = create_agent_os(bootstrap_assistant)
app = agent_os.get_app()

# Configure root_path for Platform.sh routing
# This tells FastAPI that all routes are prefixed with /chatbot-api
app.root_path = "/chatbot-api"

# Setup CORS
_config = get_agent_config()
setup_cors(app, _config["cors_origins"])


class AskRequest(BaseModel):
    """Request model for asking the assistant a question."""

    message: str = Field(
        ...,
        description="The question or message to send to the assistant",
    )


class AskResponse(BaseModel):
    """Response model containing the assistant's answer."""

    content: str = Field(..., description="The assistant's response content")
    agent_id: str = Field(
        ...,
        description="The ID of the agent that processed the request",
    )


def extract_content(response) -> str:
    """Extract content from agent response."""
    if response is None:
        return ""
    elif hasattr(response, "content"):
        return str(response.content)
    else:
        return str(response)


def should_filter_content(content: str) -> bool:
    """Filter out tool call completion messages."""
    if not isinstance(content, str):
        return False
    # Filter out any tool call completion messages (e.g., "function_name(...) completed in X.XXXs.")
    return "completed in" in content and "(" in content


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    """
    Run the agent and return the final response.
    For streaming responses, use /ask/stream.
    """
    local_assistant = create_assistant()
    try:
        enhanced_input = build_agent_query_with_context(req.message)
        response = await local_assistant.arun(enhanced_input)
        content = extract_content(response)
        return AskResponse(
            content=content,
            agent_id=local_assistant.id,
        )
    except InputCheckError:
        # Return the standard rejection message as a normal response
        return AskResponse(
            content=get_standard_rejection_message(),
            agent_id=local_assistant.id,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


async def _stream_agent_response(
    message: str,
    request: Request,  # noqa: ARG001
    assistant: Agent,
) -> AsyncIterator[str]:
    """Stream agent responses via SSE using Agno's native streaming."""
    try:
        enhanced_input = build_agent_query_with_context(message)
        async for chunk in assistant.arun(enhanced_input, stream=True):
            if chunk is None:
                continue

            content = None
            if isinstance(chunk, str):
                content = chunk
            elif hasattr(chunk, "content"):
                content = str(chunk.content) if chunk.content else None
            elif isinstance(chunk, dict):
                content = chunk.get("content")

            if not content or should_filter_content(content):
                continue

            yield f"data: {json.dumps({'content': content})}\n\n"

    except InputCheckError:
        # Return the standard rejection message as a normal response
        yield f"data: {json.dumps({'content': get_standard_rejection_message()})}\n\n"
    except Exception as e:  # noqa: BLE001
        yield f"data: {json.dumps({'error': f'Streaming error: {str(e)}'})}\n\n"


@app.get("/ask/stream")
async def ask_stream_get(message: str, request: Request):
    """Stream assistant responses via GET query parameter."""
    return StreamingResponse(
        _stream_agent_response(message, request, create_assistant()),
        media_type="text/event-stream",
    )


@app.post("/ask/stream")
async def ask_stream_post(req: AskRequest, request: Request):
    """Stream assistant responses via POST JSON body."""
    return StreamingResponse(
        _stream_agent_response(req.message, request, create_assistant()),
        media_type="text/event-stream",
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    config = get_agent_config()
    return {
        "status": "healthy",
        "agent_id": config["agent_id"],
        "agent_name": config["agent_name"],
    }


@app.get("/info")
async def info():
    """Get information about the API and agent configuration."""
    config = get_agent_config()
    # Build a fresh assistant to report the current model ID coming from the config DB.
    try:
        current_assistant: Optional[Agent] = create_assistant()
    except Exception:  # noqa: BLE001
        current_assistant = None

    model_id: str = "unknown"
    if current_assistant is not None and hasattr(current_assistant, "model"):
        try:
            model_id = getattr(current_assistant.model, "id", "unknown")
        except Exception:  # noqa: BLE001
            model_id = "unknown"
    return {
        "agent": {
            "id": config["agent_id"],
            "name": config["agent_name"],
            "model": model_id,
        },
        "endpoints": {
            "ask": "/ask (POST) - Synchronous agent interaction",
            "stream_get": "/ask/stream (GET) - Streaming responses via query param",
            "stream_post": "/ask/stream (POST) - Streaming responses via JSON body",
            "health": "/health (GET) - Health check",
            "info": "/info (GET) - API information",
        },
        "configuration": {
            "os_id": config["os_id"],
            "max_timeout": config["max_timeout"],
        },
    }


if __name__ == "__main__":
    agent_os.serve(app="rag_app:app", reload=True)


