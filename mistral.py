import os
from typing import TypedDict, AsyncGenerator, Generator

import httpx
from mistralai_private import MistralPrivate, TextChunk
from mistralai_private.models.conversationevents import ResponseStartedEvent, MessageOutputEvent, ConversationEvents

url = "https://api.mistral.ai/"
api_key = os.environ.get("MISTRAL_API_KEY")

client = httpx.Client(
    headers={
        "X-Private-Access": os.environ.get("MISTRAL_AGENTS_PRIVATE_ACCESS")
    },
    follow_redirects=True
)

client = MistralPrivate(
    server_url=url,
    api_key=api_key,
    client=client
)

DEFAULT_MODEL = "mistral-large-2411"

class ConversationStartResponse(TypedDict):
    conversation_id: str
    outputs: str


def parse_conversation_event(
    event: ConversationEvents,
    conversation_id: str = "",
) -> ConversationStartResponse:
    outputs = ""
    print(f"{event=}")
    if isinstance(event.data, ResponseStartedEvent):
        conversation_id = event.data.conversation_id
    if isinstance(event.data, MessageOutputEvent):
        if isinstance(event.data.content, str):
            outputs = event.data.content
        elif isinstance(event.data.content, list):
            for content in [
                c for c in event.data.content
                if isinstance(c, TextChunk)
            ]:
                outputs += content.text

    print(f"{outputs=}")
    return ConversationStartResponse(
        conversation_id=conversation_id,
        outputs=outputs
    )


def start_conversation(
    inputs: "str"
) -> Generator[ConversationStartResponse, None, None]:
    resp = client.beta.conversations.start_stream(
        model=DEFAULT_MODEL,
        inputs=inputs,
    )
    conversation_id = ""
    for event in resp:
        resp = parse_conversation_event(
            conversation_id=conversation_id,
            event=event
        )
        conversation_id = resp["conversation_id"]
        yield resp



def append_conversation(
    conversation_id: str,
    inputs: str,
) -> Generator[ConversationStartResponse, None, None]:
    resp = client.beta.conversations.append_stream(
        conversation_id=conversation_id,
        inputs=inputs,
    )
    for event in resp:
        resp = parse_conversation_event(
            conversation_id=conversation_id,
            event=event
        )
        yield resp
