from __future__ import annotations

import os
import json
from typing import Optional, AsyncIterator
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse

from agno.os import AgentOS
from agno.agent import Agent
from agno.exceptions import InputCheckError
from fastapi.middleware.cors import CORSMiddleware

# Use the agent defined in runtime_rag_knowledge
from runtime_rag_knowledge import build_agent
from input_validation_pre_hook import STANDARD_REJECTION_MESSAGE

# Load environment variables early
load_dotenv()

def get_agent_config() -> dict:
    """Get agent configuration from environment variables."""
    return {
        "agent_id": os.getenv("AGENT_ID", "colby-rag"),
        "agent_name": os.getenv("AGENT_NAME", "Colby RAG Assistant"),
        "os_id": os.getenv("AGENT_OS_ID", "runtime-rag-os"),
        "os_description": os.getenv(
            "AGENT_OS_DESCRIPTION",
            "Runtime RAG OS exposing the knowledge-based assistant via API"
        ),
        "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
        "max_timeout": int(os.getenv("REQUEST_TIMEOUT", "300")),
    }


def create_assistant() -> Agent:
    """Create and configure the assistant agent."""
    assistant = build_agent()
    config = get_agent_config()
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


# Initialize agent and AgentOS
assistant: Agent = create_assistant()
agent_os: AgentOS = create_agent_os(assistant)
app = agent_os.get_app()

# Configure root_path for Platform.sh routing
# This tells FastAPI that all routes are prefixed with /chatbot-api
app.root_path = "/chatbot-api"

# Setup CORS
config = get_agent_config()
setup_cors(app, config["cors_origins"])


class AskRequest(BaseModel):
    """Request model for asking the assistant a question."""
    message: str = Field(..., description="The question or message to send to the assistant")


class AskResponse(BaseModel):
    """Response model containing the assistant's answer."""
    content: str = Field(..., description="The assistant's response content")
    agent_id: str = Field(..., description="The ID of the agent that processed the request")


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
    try:
        response = await assistant.arun(req.message)
        content = extract_content(response)
        return AskResponse(
            content=content,
            agent_id=assistant.id,
        )
    except InputCheckError as e:
        # Return the standard rejection message as a normal response
        return AskResponse(
            content=STANDARD_REJECTION_MESSAGE,
            agent_id=assistant.id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


async def _stream_agent_response(message: str, request: Request) -> AsyncIterator[str]:
    """Stream agent responses via SSE using Agno's native streaming."""
    try:
        async for chunk in assistant.arun(message, stream=True):
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
                    
    except InputCheckError as e:
        # Return the standard rejection message as a normal response
        yield f"data: {json.dumps({'content': STANDARD_REJECTION_MESSAGE})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': f'Streaming error: {str(e)}'})}\n\n"


@app.get("/ask/stream")
async def ask_stream_get(message: str, request: Request):
    """Stream assistant responses via GET query parameter."""
    return StreamingResponse(
        _stream_agent_response(message, request),
        media_type="text/event-stream"
    )


@app.post("/ask/stream")
async def ask_stream_post(req: AskRequest, request: Request):
    """Stream assistant responses via POST JSON body."""
    return StreamingResponse(
        _stream_agent_response(req.message, request),
        media_type="text/event-stream"
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_id": assistant.id,
        "agent_name": assistant.name
    }


@app.get("/info")
async def info():
    """Get information about the API and agent configuration."""
    config = get_agent_config()
    return {
        "agent": {
            "id": assistant.id,
            "name": assistant.name,
            "model": getattr(assistant.model, "id", "unknown") if hasattr(assistant, "model") else "unknown",
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
        }
    }


if __name__ == "__main__":
    agent_os.serve(app="api:app", reload=True)
