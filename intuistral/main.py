from typing import Generator

from mistralai_private import TextChunk, ToolReferenceChunk

from textual import work, on
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.app import (
    App,
    ComposeResult,
    RenderResult
)
from textual.containers import (
    Horizontal,
    VerticalScroll,
    Container
)
from textual.widgets import (
    RadioButton,
    RadioSet,
    Header,
    Footer,
    Input,
    Static,
    Markdown
)
from PIL import Image
from rich_pixels import Pixels, HalfcellRenderer
from intuistral.mistral import (
    start_conversation,
    append_conversation,
    list_conversations, ConversationStartResponse, get_messages
)
import sys
from pathlib import Path

cwd = Path(__file__).parent


class UserMessage(Markdown):
    ...

class AssistantMessage(Markdown):
    ...

class Prompt(Input):
    ...

class Logo(Static):

    def render(self) -> RenderResult:
        pixels = Pixels.from_image_path(
            cwd / "resources/logo.png",
            resize=(45, 37),
            renderer=HalfcellRenderer()
        )
        return pixels

class Img(Static):

    def __init__(self, image: Image, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image = image

    def render(self) -> RenderResult:
        pixels = Pixels.from_image(
            self.image,
            resize=(65, 65),
            renderer=HalfcellRenderer()
        )
        return pixels


class LoadConversationScreen(Screen):
    BORDER_TITLE = "Select conversation"
    BINDINGS = [("escape", "go_back", "Go back to chat")]

    CSS = """
    Screen {
        align: center middle;
    }
    
    RadioSet {
        border: round orange 50%;
        background: black 0%;
    }
    RadioButton {
    
    }
    """

    def __init__(self, *args, current_conversation_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_conversation_id = current_conversation_id

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            with Horizontal():
                with RadioSet(id="focus_me"):
                    for conv in list_conversations():
                        button = RadioButton(label=conv.name, name=conv.id)
                        yield button

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        selected_conversation = event.pressed.name
        self.app.switch_screen(LeChatScreen(conversation_id=selected_conversation))

    def on_mount(self) -> None:
        self.query_one(RadioSet).focus()

    def action_go_back(self):
        self.app.switch_screen(LeChatScreen(conversation_id=self.current_conversation_id))


class LeChatScreen(Screen):

    AUTO_FOCUS = "Input"

    BINDINGS = [("ctrl+l", "chat_list", "View previous chats"), ("ctrl+n", "new_chat", "Start a new chat")]

    CSS = """
    UserMessage {
        background: black 0%;
        border: round #242427;
        color: $text;
        margin: 1;
        margin-right: 8;
        padding: 1 2 0 1;
    }

    AssistantMessage {
        background: black 0%;
        color: $text;
        margin: 1;
        border: round orange 50%;
        margin-left: 8;
        padding: 1 2 0 1;
    }
    Prompt {
        border: round orange 50%;
    }
    #logo-container {
        position: relative;
        align: center middle;
        text-align: center;
        align: center middle;
    }
    
    #gen-image {
        margin-left: 75;
        position: relative;
        align: center middle;
        text-align: center;
    }
    """
    def __init__(
        self,
        *args,
        conversation_id: str | None = None,
        initial_message: str | None = None,
        **kwargs
    ) -> None:
        self.conversation_id = conversation_id
        self.initial_message = initial_message
        super().__init__(*args, **kwargs)

    def compose(self):
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        with VerticalScroll(id="messages"):
            with Container(id="logo-container"):
                yield Logo(id="logo")
        yield Prompt(placeholder="Ask le chat")

    async def on_mount(self):
        remove_logo = False
        messages = self.query_one("#messages")

        if self.conversation_id:
            remove_logo = True
            history = get_messages(self.conversation_id)
            for message in history:
                if message.role == "assistant":
                    if isinstance(message.content, str):
                        await messages.mount(AssistantMessage(message.content))
                    if isinstance(message.content, list):
                        content = ""
                        for c in message.content:
                            if isinstance(c, str):
                                content += c
                            elif isinstance(c, TextChunk):
                                content += c.text
                            elif isinstance(c, ToolReferenceChunk):
                                content += f" [[{c.title}]({c.url})] "
                        await  messages.mount(AssistantMessage(content))
                if message.role == "user":
                    await messages.mount(UserMessage(message.content))

        if self.initial_message:
            remove_logo = True
            await self.add_assistant_response(self.initial_message)

        if remove_logo:
            logo = self.query_one("#logo")
            await logo.remove()


    @on(Input.Submitted)
    async def on_input(self, event: Input.Submitted) -> None:
        event.input.clear()
        try:
            logo = self.query_one("#logo")
            await logo.remove()
        except NoMatches:
            pass
        await self.add_assistant_response(event.value)

    async def add_assistant_response(self, prompt: str):
        messages = self.query_one("#messages")
        await messages.mount(UserMessage(prompt))
        if self.conversation_id is None:
            resp = start_conversation(inputs=prompt)
        else:
            resp = append_conversation(conversation_id=self.conversation_id, inputs=prompt)
        self.display_response(resp)

    @work(exclusive=True, thread=True)
    async def display_response(
        self,
        chunks: Generator[ConversationStartResponse, None, None]
    ) -> None:
        messages = self.query_one("#messages")
        message = None
        content = ""
        for chunk in chunks:
            self.conversation_id = chunk["conversation_id"]
            if chunk["outputs"] and chunk["outputs"] != "":
                content += chunk["outputs"]
                if message is None:
                    message = AssistantMessage()
                    self.app.call_from_thread(messages.mount, message)
                    message.anchor()
                self.app.call_from_thread(message.update, content)
            if chunk["image"]:
                img = Img(image=chunk["image"], id="gen-image")
                self.app.call_from_thread(messages.mount, img)
                messages = None
                content = ""

    def action_chat_list(self):
        self.app.switch_screen(LoadConversationScreen(current_conversation_id=self.conversation_id))

    def action_new_chat(self):
        self.app.switch_screen(LeChatScreen())

class LeChatApp(App):

    def __init__(self, message: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def on_mount(self) -> None:
        self.push_screen(LeChatScreen(initial_message=self.message))

def tui():
    args = sys.argv
    if len(args) == 2:
        LeChatApp(args[1]).run()
    else:
        LeChatApp().run()

if __name__ == "__main__":
    tui()
