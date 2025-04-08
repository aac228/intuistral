import io
import os
from typing import TypedDict, AsyncGenerator, Generator, NotRequired, List

import httpx
from PIL import Image
from mistralai_private import MistralPrivate, ToolReferenceChunk, ToolExecutionStartedEvent, ToolFileChunk
from mistralai_private.models.conversationevents import ResponseStartedEvent, MessageOutputEvent, ConversationEvents
from pydantic import BaseModel

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
    image: Image

tool_call_map = {
    "web_search": "Searching the web",
    "news_search": "Searching the web",
    "generate_image": "Generating an image",
}

class ConvTitle(BaseModel):
    title: str

def parse_conversation_event(
    event: ConversationEvents,
    conversation_id: str = "",
) -> ConversationStartResponse:
    outputs = ""
    image = None
    if isinstance(event.data, ResponseStartedEvent):
        conversation_id = event.data.conversation_id
    if isinstance(event.data, MessageOutputEvent):
        if isinstance(event.data.content, str):
            outputs = event.data.content
        elif isinstance(event.data.content, ToolReferenceChunk):
            outputs += f" [[{event.data.content.title}]({event.data.content.url})] "
        elif isinstance(event.data.content, ToolFileChunk):
            file_bytes = client.files.download(file_id=event.data.content.file_id).read()
            image = Image.open(io.BytesIO(file_bytes))
    if isinstance(event.data, ToolExecutionStartedEvent):
        if outputs:
            outputs += "\n"
        outputs += f"{tool_call_map[event.data.name]}\n\n"
    return ConversationStartResponse(
        conversation_id=conversation_id,
        outputs=outputs,
        image=image
    )


def start_conversation(
    inputs: "str"
) -> Generator[ConversationStartResponse, None, None]:
    # conv_title = client.chat.parse(
    #     response_format=ConvTitle,
    #     model=DEFAULT_MODEL,
    #     messages=[
    #         {
    #             "role": "user",
    #             "content": f"Create a title for the conversation with the first message being: \n\n{inputs}"
    #         }
    #     ],
    #     temperature=0,
    # )
    resp = client.beta.conversations.start_stream(
        model=DEFAULT_MODEL,
        inputs=inputs,
        name=inputs[:30] + "...",
        tools=[{"type": "web_search"}, {"type": "generate_image"}]
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

def list_conversations():
    return [
        conv for conv in client.beta.conversations.list(page_size=100)
        if conv.name
    ]


def get_messages(conversation_id: str):
    return [
        msg for msg in client.beta.conversations.get_messages(conversation_id=conversation_id).messages
    ]
