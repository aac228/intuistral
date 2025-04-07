from textual import work, on
from textual.app import App


from textual.widgets import Header, Footer, Input, Markdown

from mistral import start_conversation, append_conversation
from textual.containers import VerticalScroll

class Message(Markdown):
    ...


class LeChat(App):
    conversation_id: str | None = None

    _messages: list[str]

    def compose(self):
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        with VerticalScroll(id="messages"):
            yield Message()
        yield Input(placeholder="How can I help you?")

    @on(Input.Submitted)
    async def on_input(self, event: Input.Submitted) -> None:
        messages = self.query_one("#messages")
        event.input.clear()
        await messages.mount(Message(event.value))
        await messages.mount(message := Message())
        message.anchor()
        self.send_prompt(event.value, message)

    @work(thread=True)
    def send_prompt(self, prompt: str, message: Message) -> None:
        content = ""
        if self.conversation_id is None:
            resp = start_conversation(inputs=prompt)
            for chunk in resp:
                self.conversation_id = chunk["conversation_id"]
                content += chunk["outputs"]
                self.call_from_thread(message.update, content)
        else:
            resp = append_conversation(conversation_id=self.conversation_id, inputs=prompt)
            for chunk in resp:
                content += chunk["outputs"]
                self.call_from_thread(message.update, content)


if __name__ == "__main__":
    app = LeChat()
    app.run()
