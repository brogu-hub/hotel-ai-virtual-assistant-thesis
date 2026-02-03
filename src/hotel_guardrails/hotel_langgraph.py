# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Hotel LangGraph Agent - Embedded State Machine

A LangGraph-based agent for hotel operations that runs directly in the
hotel_guardrails server (no external HTTP calls required).

Uses:
- OpenRouter (qwen/qwen3-max) with NVIDIA fallback for LLM
- OpenRouter (qwen/qwen3-embedding-8b) for embeddings
- Hotel tools from src/agent/hotel_tools.py

Architecture:
    START
      |
      v
    primary_assistant
      |
      +---> hotel_booking (booking operations)
      |         |
      |         v
      |     booking_tools --> hotel_booking
      |
      +---> hotel_service (info queries)
      |         |
      |         v
      |     service_tools --> hotel_service
      |
      +---> hotel_knowledge (RAG search)
      |
      +---> other_talk (greetings, off-topic)
      |
      v
     END
"""

import os
import yaml
import logging
from typing import Annotated, TypedDict, Dict, List, Literal, Optional, Any, Callable
from datetime import datetime

from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import tools_condition, ToolNode
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# State Definition
# =============================================================================

class HotelState(TypedDict):
    """State for the hotel assistant agent."""
    messages: Annotated[List[AnyMessage], add_messages]
    session_id: str
    user_id: str
    language: str  # 'th', 'en', or 'auto'
    current_intent: str  # booking, service, knowledge, other
    tool_calls_made: List[Dict[str, Any]]


# =============================================================================
# Routing Tools (for sub-agent dispatch)
# =============================================================================

class ToHotelBooking(BaseModel):
    """Route to hotel booking assistant for reservations, check-in/out, updates."""
    query: str = Field(description="The booking-related request")

class ToHotelService(BaseModel):
    """Route to service assistant for hotel services and amenities info."""
    query: str = Field(description="The service-related question")

class ToHotelKnowledge(BaseModel):
    """Route to RAG search for hotel information from knowledge base."""
    query: str = Field(description="The information query")

class HandleOtherTalk(BaseModel):
    """Handle greetings, small talk, and off-topic queries."""
    query: str = Field(description="The greeting or off-topic message")


# =============================================================================
# Load Prompts
# =============================================================================

def load_hotel_prompts() -> Dict[str, Any]:
    """Load prompts from hotel_prompt.yaml."""
    # Try multiple paths for Railway compatibility
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "agent", "hotel_prompt.yaml"),
        "/app/src/agent/hotel_prompt.yaml",
        "src/agent/hotel_prompt.yaml",
    ]

    for prompt_path in possible_paths:
        try:
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompts = yaml.safe_load(f)
                    logger.info(f"Loaded prompts from: {prompt_path}")
                    return prompts
        except Exception as e:
            logger.warning(f"Failed to load prompts from {prompt_path}: {e}")

    logger.warning("Using default prompts - no prompt file found")
    return {
        "main_prompt": """You are a professional hotel assistant for The Grand Horizon Hotel.
You can communicate fluently in both Thai and English.
Always respond in the same language the guest uses.

For Thai speakers, use polite particles (ครับ/ค่ะ).
For English speakers, be professional and warm.
"""
    }


# =============================================================================
# LLM Initialization with Fallback
# =============================================================================

def get_llm(temperature: float = 0.7, max_tokens: int = 1024, streaming: bool = False):
    """Get LLM with OpenRouter -> NVIDIA fallback."""
    try:
        from src.common.llm_fallback import get_llm_with_fallback
        return get_llm_with_fallback(
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )
    except Exception as e:
        logger.warning(f"Fallback LLM init failed: {e}, trying OpenRouter directly")
        from src.common.llm_openrouter import get_openrouter_llm
        return get_openrouter_llm(
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )


# =============================================================================
# Tool Node with Fallback
# =============================================================================

def create_tool_node_with_fallback(tools: List) -> ToolNode:
    """Create a tool node with error handling."""
    # Simple ToolNode without complex fallback (more compatible)
    return ToolNode(tools)


# =============================================================================
# Agent Nodes
# =============================================================================

class HotelAssistant:
    """
    Base assistant that routes to specialized sub-agents.
    Similar to the primary_assistant in the original agent.
    """

    def __init__(self, prompt: str, tools: List):
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt),
            MessagesPlaceholder("messages"),
        ])
        self.tools = tools

    async def __call__(self, state: HotelState, config: RunnableConfig) -> Dict:
        llm_settings = config.get('configurable', {}).get('llm_settings', {})
        temperature = llm_settings.get('temperature', 0.7)
        max_tokens = llm_settings.get('max_tokens', 1024)

        llm = get_llm(temperature=temperature, max_tokens=max_tokens)
        runnable = self.prompt_template | llm.bind_tools(self.tools)

        result = await runnable.ainvoke(state, config)
        return {"messages": [result]}


async def handle_booking(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle hotel booking operations."""
    from src.agent.hotel_tools import (
        check_room_availability,
        create_reservation,
        confirm_reservation,
        update_reservation,
        cancel_reservation,
        check_in_guest,
        check_out_guest,
        get_reservation_details,
        get_guest_reservations,
    )

    prompts = load_hotel_prompts()
    booking_prompt = prompts.get('booking_flow', '') + "\n\n" + prompts.get('main_prompt', '')

    booking_tools = [
        check_room_availability,
        create_reservation,
        confirm_reservation,
        update_reservation,
        cancel_reservation,
        check_in_guest,
        check_out_guest,
        get_reservation_details,
        get_guest_reservations,
    ]

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", booking_prompt),
        MessagesPlaceholder("messages"),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.3),
        max_tokens=llm_settings.get('max_tokens', 1024)
    )

    runnable = prompt_template | llm.bind_tools(booking_tools)
    result = await runnable.ainvoke(state, config)

    return {"messages": [result], "current_intent": "booking"}


async def handle_service(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle hotel service queries."""
    from src.agent.hotel_tools import get_hotel_services, create_service_request

    prompts = load_hotel_prompts()
    service_prompt = prompts.get('service_prompt', '') + "\n\n" + prompts.get('main_prompt', '')

    service_tools = [get_hotel_services, create_service_request]

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", service_prompt),
        MessagesPlaceholder("messages"),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.5),
        max_tokens=llm_settings.get('max_tokens', 1024)
    )

    runnable = prompt_template | llm.bind_tools(service_tools)
    result = await runnable.ainvoke(state, config)

    return {"messages": [result], "current_intent": "service"}


async def handle_knowledge(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle RAG-based knowledge queries."""
    from src.agent.hotel_tools import search_hotel_knowledge

    prompts = load_hotel_prompts()
    main_prompt = prompts.get('main_prompt', '')

    # Get last user message
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    # Search knowledge base
    try:
        knowledge_result = search_hotel_knowledge.invoke(last_user_message)
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        knowledge_result = "ขออภัย ไม่สามารถค้นหาข้อมูลได้ / Sorry, information search failed."

    # Generate response using the retrieved knowledge
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", f"""{main_prompt}

Use the following retrieved information to answer the user's question.
Be concise and helpful. Answer in the same language the user asked.

Retrieved Knowledge:
{knowledge_result}
"""),
        MessagesPlaceholder("messages"),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.5),
        max_tokens=llm_settings.get('max_tokens', 1024)
    )

    runnable = rag_prompt | llm
    result = await runnable.ainvoke(state, config)

    return {"messages": [result], "current_intent": "knowledge"}


async def handle_other_talk(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle greetings and off-topic queries."""
    prompts = load_hotel_prompts()

    # Detect language and use appropriate greeting template
    greeting_templates = prompts.get('greeting_templates', {})
    main_prompt = prompts.get('main_prompt', '')

    other_prompt = f"""{main_prompt}

You are handling a greeting or general conversation.
Be friendly and welcoming. Offer to help with hotel services.

For Thai speakers, use polite particles (ครับ/ค่ะ).
For English speakers, be professional and warm.
"""

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", other_prompt),
        MessagesPlaceholder("messages"),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.7),
        max_tokens=llm_settings.get('max_tokens', 512)
    )

    runnable = prompt_template | llm
    result = await runnable.ainvoke(state, config)

    return {"messages": [result], "current_intent": "other"}


# =============================================================================
# Entry Nodes (for tool call routing)
# =============================================================================

def create_entry_node(assistant_name: str) -> Callable:
    """Create an entry node that acknowledges routing to a sub-agent."""
    def entry_node(state: HotelState) -> Dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=f"Routing to {assistant_name}. Processing request...",
                    tool_call_id=tool_call_id,
                )
            ]
        }
    return entry_node


# =============================================================================
# Routing Functions
# =============================================================================

def route_primary_assistant(state: HotelState) -> Literal[
    "enter_booking",
    "enter_service",
    "enter_knowledge",
    "other_talk",
    "__end__"
]:
    """Route from primary assistant to specialized handlers."""
    route = tools_condition(state)
    if route == END:
        return END

    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        tool_name = tool_calls[0]["name"]
        if tool_name == ToHotelBooking.__name__:
            return "enter_booking"
        elif tool_name == ToHotelService.__name__:
            return "enter_service"
        elif tool_name == ToHotelKnowledge.__name__:
            return "enter_knowledge"
        elif tool_name == HandleOtherTalk.__name__:
            return "other_talk"

    return END


def route_booking(state: HotelState) -> Literal["booking_tools", "__end__"]:
    """Route from booking assistant to tools or end."""
    route = tools_condition(state)
    if route == END:
        return END
    return "booking_tools"


def route_service(state: HotelState) -> Literal["service_tools", "__end__"]:
    """Route from service assistant to tools or end."""
    route = tools_condition(state)
    if route == END:
        return END
    return "service_tools"


# =============================================================================
# Build the Graph
# =============================================================================

def build_hotel_graph():
    """Build and return the hotel LangGraph agent."""

    # Load prompts
    prompts = load_hotel_prompts()
    main_prompt = prompts.get('main_prompt', 'You are a hotel assistant.')

    # Primary assistant prompt
    primary_prompt = f"""{main_prompt}

## Your Role
You are the primary router for guest requests. Based on the guest's message,
route to the appropriate specialist:

1. **ToHotelBooking** - For reservations, room availability, check-in/out,
   booking modifications, cancellations
2. **ToHotelService** - For service requests, hotel amenities info, spa, gym, pool
3. **ToHotelKnowledge** - For general hotel information (WiFi, breakfast, policies)
4. **HandleOtherTalk** - For greetings, thank you, and off-topic messages

Analyze the guest's request and use the appropriate tool to route it.
"""

    # Primary assistant tools (routing only)
    primary_tools = [ToHotelBooking, ToHotelService, ToHotelKnowledge, HandleOtherTalk]

    # Import hotel tools
    from src.agent.hotel_tools import (
        check_room_availability,
        create_reservation,
        confirm_reservation,
        update_reservation,
        cancel_reservation,
        check_in_guest,
        check_out_guest,
        get_reservation_details,
        get_guest_reservations,
        get_hotel_services,
        create_service_request,
    )

    booking_tools = [
        check_room_availability,
        create_reservation,
        confirm_reservation,
        update_reservation,
        cancel_reservation,
        check_in_guest,
        check_out_guest,
        get_reservation_details,
        get_guest_reservations,
    ]

    service_tools = [get_hotel_services, create_service_request]

    # Build the graph
    builder = StateGraph(HotelState)

    # Primary assistant node
    builder.add_node("primary_assistant", HotelAssistant(primary_prompt, primary_tools))

    # Entry nodes for sub-agents
    builder.add_node("enter_booking", create_entry_node("Booking Assistant"))
    builder.add_node("enter_service", create_entry_node("Service Assistant"))
    builder.add_node("enter_knowledge", create_entry_node("Knowledge Assistant"))

    # Sub-agent nodes
    builder.add_node("hotel_booking", handle_booking)
    builder.add_node("hotel_service", handle_service)
    builder.add_node("hotel_knowledge", handle_knowledge)
    builder.add_node("other_talk", handle_other_talk)

    # Tool nodes
    builder.add_node("booking_tools", create_tool_node_with_fallback(booking_tools))
    builder.add_node("service_tools", create_tool_node_with_fallback(service_tools))

    # Edges from START
    builder.add_edge(START, "primary_assistant")

    # Conditional edges from primary assistant
    builder.add_conditional_edges(
        "primary_assistant",
        route_primary_assistant,
        {
            "enter_booking": "enter_booking",
            "enter_service": "enter_service",
            "enter_knowledge": "enter_knowledge",
            "other_talk": "other_talk",
            END: END,
        }
    )

    # Entry -> Sub-agent edges
    builder.add_edge("enter_booking", "hotel_booking")
    builder.add_edge("enter_service", "hotel_service")
    builder.add_edge("enter_knowledge", "hotel_knowledge")

    # Sub-agent routing
    builder.add_conditional_edges("hotel_booking", route_booking)
    builder.add_conditional_edges("hotel_service", route_service)

    # Tool -> Sub-agent edges (loop back)
    builder.add_edge("booking_tools", "hotel_booking")
    builder.add_edge("service_tools", "hotel_service")

    # End edges
    builder.add_edge("hotel_knowledge", END)
    builder.add_edge("other_talk", END)

    # Compile with memory checkpointer
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)

    return graph


# =============================================================================
# Global Graph Instance
# =============================================================================

_hotel_graph = None


def get_hotel_graph():
    """Get or create the hotel LangGraph agent."""
    global _hotel_graph
    if _hotel_graph is None:
        try:
            logger.info("Building hotel LangGraph agent...")
            _hotel_graph = build_hotel_graph()
            logger.info("Hotel LangGraph agent ready")
        except Exception as e:
            logger.error(f"Failed to build hotel LangGraph agent: {e}")
            import traceback
            traceback.print_exc()
            raise
    return _hotel_graph


# =============================================================================
# Async Invocation
# =============================================================================

async def invoke_hotel_agent(
    message: str,
    session_id: str,
    user_id: str = "guest",
    language: str = "auto",
    conversation_history: Optional[List[Dict[str, str]]] = None,
    llm_settings: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Invoke the hotel LangGraph agent.

    Args:
        message: User message
        session_id: Session ID for conversation tracking
        user_id: User/guest identifier
        language: Response language preference
        conversation_history: Previous messages
        llm_settings: LLM configuration overrides

    Returns:
        Dict with response, success status, and metadata
    """
    graph = get_hotel_graph()

    # Build messages list
    messages = []
    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))

    messages.append(HumanMessage(content=message))

    # Build initial state
    initial_state = {
        "messages": messages,
        "session_id": session_id,
        "user_id": user_id,
        "language": language,
        "current_intent": "",
        "tool_calls_made": [],
    }

    # Config with session thread
    config = RunnableConfig(
        configurable={
            "thread_id": session_id,
            "llm_settings": llm_settings or {},
        }
    )

    try:
        # Invoke the graph
        result = await graph.ainvoke(initial_state, config)

        # Extract final response
        final_messages = result.get("messages", [])
        response_text = ""
        tool_calls = []

        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage):
                if msg.content:
                    response_text = msg.content
                if msg.tool_calls:
                    tool_calls = [
                        {"name": tc["name"], "args": tc.get("args", {})}
                        for tc in msg.tool_calls
                    ]
                break

        return {
            "success": True,
            "response": response_text,
            "path": "langgraph",
            "intent": result.get("current_intent", ""),
            "tool_calls": tool_calls,
            "session_id": session_id,
        }

    except Exception as e:
        logger.error(f"Hotel LangGraph agent error: {e}")
        return {
            "success": False,
            "response": None,
            "path": "langgraph",
            "error": str(e),
        }
