from typing import Generator

from textual import work, on
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
    Label,
    Header,
    Footer,
    Input,
    Static,
    Markdown
)
from PIL import Image
from rich_pixels import Pixels, HalfcellRenderer
from mistral import (
    start_conversation,
    append_conversation,
    list_conversations, ConversationStartResponse, get_messages
)


class UserMessage(Markdown):
    ...

class AssistantMessage(Markdown):
    ...

class Prompt(Input):
    ...

class Logo(Static):

    def render(self) -> RenderResult:
        pixels = Pixels.from_image_path(
            "./resources/logo.png",
            resize=(45, 37),
            renderer=HalfcellRenderer()
        )
        return pixels

class Img(Static):

    CSS = """
    #gen-image {
        height: 50%;
        width: 100%;
        position: relative;
        align: center middle;
        text-align: center;
    }
    """

    def __init__(self, image: Image, *args, **kwargs):
        super().__init__(*args, **kwargs, id="gen-image")
        self.image = image

    def render(self) -> RenderResult:
        pixels = Pixels.from_image(
            self.image,
            resize=(65, 65),
            renderer=HalfcellRenderer()
        )
        return pixels


class LoadConversationScreen(Screen):
    CSS_PATH = "load-convo.tcss"
    BORDER_TITLE = "Select conversation"
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

class LeChatScreen(Screen):

    AUTO_FOCUS = "Input"

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
        height: 50%;
        width: 100%;
        position: relative;
        align: center middle;
        text-align: center;
        align: center middle;
    }
    """
    def __init__(self, *args, conversation_id: str | None = None, **kwargs) -> None:
        self.conversation_id: str | None = conversation_id
        super().__init__(*args, **kwargs)

    def compose(self):
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        with VerticalScroll(id="messages"):
            with Container(id="logo-container"):
                yield Logo(id="logo")
            if self.conversation_id:
                print(f"{self.conversation_id=}")
                messages = get_messages(self.conversation_id)
                print(f"{messages=}")
                for message in messages:
                    if message.role == "assistant":
                        yield AssistantMessage(message.content)
                    if message.role == "user":
                        yield UserMessage(message.content)
        yield Prompt(placeholder="Ask le chat")

    @on(Input.Submitted)
    async def on_input(self, event: Input.Submitted) -> None:
        messages = self.query_one("#messages")
        event.input.clear()
        await messages.remove_children("#logo")
        await messages.mount(UserMessage(event.value))
        if self.conversation_id is None:
            resp = start_conversation(inputs=event.value)
        else:
            resp = append_conversation(conversation_id=self.conversation_id, inputs=event.value)
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
                img = Img(image=chunk["image"])
                self.app.call_from_thread(messages.mount, img)
                messages = None
                content = ""


class LeChatApp(App):
    def on_mount(self) -> None:
        self.push_screen(LoadConversationScreen())

if __name__ == "__main__":
    LeChatApp().run()
