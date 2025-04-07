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
    list_conversations
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

    def __init__(self, image: Image, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image = image

    def render(self) -> RenderResult:
        pixels = Pixels.from_image(
            self.image,
            resize=(45, 37),
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
                        button = RadioButton(conv)
                        yield button

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        selected_conversation= event.pressed.label
        self.app.switch_screen(LeChatScreen(selected_conversation))

    def on_mount(self) -> None:
        self.query_one(RadioSet).focus()

class LeChatScreen(Screen):
    conversation_id: str | None = None

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

    def compose(self):
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        with VerticalScroll(id="messages"):
            with Container(id="logo-container"):
                yield Logo(id="logo")
        yield Prompt(placeholder="Ask le chat")

    @on(Input.Submitted)
    async def on_input(self, event: Input.Submitted) -> None:
        messages = self.query_one("#messages")
        event.input.clear()
        await messages.remove_children("#logo")
        await messages.mount(UserMessage(event.value))
        self.receive_result(event.value)

    @work()
    async def receive_result(
        self,
        prompt: str
    ) -> None:
        messages = self.query_one("#messages")
        await messages.mount(message := AssistantMessage())
        message.anchor()
        content = ""
        if self.conversation_id is None:
            resp = start_conversation(inputs=prompt)
        else:
            resp = append_conversation(conversation_id=self.conversation_id, inputs=prompt)
        for chunk in resp:
            self.conversation_id = chunk["conversation_id"]
            if chunk["image"]:
                await messages.mount(Img(image_id=chunk["image"]))
                await messages.mount(message := AssistantMessage())
                message.anchor()
                content = ""
            if chunk["outputs"]:
                content += chunk["outputs"]
                await message.update(content)

class LeChatApp(App):
    def on_mount(self) -> None:
        self.push_screen(LoadConversationScreen())

if __name__ == "__main__":
    LeChatApp().run()
