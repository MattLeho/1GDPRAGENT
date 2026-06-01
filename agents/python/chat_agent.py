"""
GDPR Chat Endpoint
Provides conversational AI support for GDPR requests using the RLM agent
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import sys
import os

# Add parent directory to path to import gdpr_agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdpr_agent import GDPRRequestDrafter

app = FastAPI(title="GDPR Chat Agent")

# Initialize the GDPR agent
agent = GDPRRequestDrafter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict] = None
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    response: str
    status: str = "success"


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Handle chat messages with GDPR context
    """
    try:
        # Build conversation context
        context_str = ""
        if request.context:
            context_str = f"""
Current Request Context:
- Company: {request.context.get('company_name', 'Unknown')}
- Request Type: {request.context.get('request_type', 'Unknown')}
- Status: {request.context.get('status', 'Unknown')}
- Policy URL: {request.context.get('policy_url', 'Not provided')}
"""

        # Build conversation history
        history_str = ""
        if request.history:
            history_str = "\n\nConversation History:\n"
            for msg in request.history[-5:]:  # Last 5 messages for context
                role = "User" if msg.role == "user" else "Assistant"
                history_str += f"{role}: {msg.content}\n"

        # Create comprehensive prompt for the agent
        full_prompt = f"""You are a GDPR compliance AI assistant helping with an access request.

{context_str}
{history_str}

User Question: {request.message}

Please provide a helpful, accurate response. If the question is about GDPR law, reference specific articles. If it's about the current request, use the context provided. Be concise but thorough."""

        # Use the agent's LLM call
        response = await agent._call_llm(full_prompt)
        
        if not response:
            response = "I apologize, but I'm having trouble generating a response right now. Please try again."

        return ChatResponse(response=response, status="success")

    except Exception as e:
        print(f"[Chat Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "GDPR Chat Agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
