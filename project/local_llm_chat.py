#!/usr/bin/env python3
"""
Local LLM Chat - Talk to Ollama models on your Pi
Built by Claude on Raspberry Pi 5

Chat with locally running AI models via Ollama.
"""

import json
import sys
import urllib.request
import urllib.error

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

console = Console()

OLLAMA_URL = "http://localhost:11434"


def get_models():
    """Get list of available models"""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as response:
            data = json.loads(response.read())
            return [m['name'] for m in data.get('models', [])]
    except Exception as e:
        return []


def chat(model, message, context=None):
    """Send a message to Ollama and stream the response"""
    data = {
        "model": model,
        "prompt": message,
        "stream": True
    }
    if context:
        data["context"] = context

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}
    )

    full_response = ""
    new_context = None

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            console.print("[cyan]AI: [/cyan]", end="")
            for line in response:
                chunk = json.loads(line.decode())
                text = chunk.get("response", "")
                console.print(text, end="")
                full_response += text
                if chunk.get("done"):
                    new_context = chunk.get("context")
            console.print()  # newline

        return full_response, new_context

    except urllib.error.URLError as e:
        console.print(f"\n[red]Error connecting to Ollama: {e}[/red]")
        return None, None
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        return None, None


def interactive_chat(model):
    """Interactive chat session"""
    console.print(Panel(
        f"[bold cyan]Local LLM Chat[/bold cyan]\n"
        f"[dim]Model: {model}[/dim]\n"
        f"[dim]Running on your Raspberry Pi 5[/dim]",
        border_style="cyan"
    ))

    console.print("\n[dim]Type 'quit' or 'exit' to end the conversation[/dim]")
    console.print("[dim]Type 'clear' to start a new conversation[/dim]\n")

    context = None

    while True:
        try:
            user_input = Prompt.ask("[green]You[/green]")

            if user_input.lower() in ['quit', 'exit', 'q']:
                console.print("\n[dim]Goodbye![/dim]")
                break

            if user_input.lower() == 'clear':
                context = None
                console.print("[dim]Conversation cleared.[/dim]\n")
                continue

            if not user_input.strip():
                continue

            response, context = chat(model, user_input, context)

            console.print()  # spacing

        except KeyboardInterrupt:
            console.print("\n\n[dim]Interrupted. Goodbye![/dim]")
            break


def one_shot(model, message):
    """Single message mode"""
    console.print(f"[dim]Sending to {model}...[/dim]\n")
    response, _ = chat(model, message)
    if response:
        console.print()


def main():
    # Check Ollama is running
    models = get_models()

    if not models:
        console.print(Panel(
            "[red]Ollama is not running or has no models![/red]\n\n"
            "Start Ollama with: [cyan]sudo systemctl start ollama[/cyan]\n"
            "Pull a model with: [cyan]ollama pull gemma:2b[/cyan]",
            title="Error",
            border_style="red"
        ))
        sys.exit(1)

    console.print(Panel(
        "[bold cyan]Local LLM Chat[/bold cyan]\n"
        "[dim]Built by Claude - Chat with AI running on your Pi![/dim]",
        border_style="cyan"
    ))

    # Show available models
    console.print(f"\n[green]Available models:[/green] {', '.join(models)}\n")

    # Parse arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            console.print("""
[yellow]Usage:[/yellow]
  python3 local_llm_chat.py              # Interactive chat (default model)
  python3 local_llm_chat.py gemma:2b     # Interactive chat with specific model
  python3 local_llm_chat.py -m "Hello!"  # Single message mode

[dim]Available models are shown above[/dim]
""")
            return

        if sys.argv[1] == '-m' and len(sys.argv) > 2:
            # Single message mode
            message = ' '.join(sys.argv[2:])
            model = models[0]
            one_shot(model, message)
            return

        # Model specified
        model = sys.argv[1]
        if model not in models:
            console.print(f"[red]Model '{model}' not found. Available: {models}[/red]")
            return
    else:
        model = models[0]

    interactive_chat(model)


if __name__ == '__main__':
    main()
