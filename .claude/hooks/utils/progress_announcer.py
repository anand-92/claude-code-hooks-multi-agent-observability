#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "anthropic",
#     "python-dotenv",
# ]
# ///

import os
import sys
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def get_tts_script_path():
    """Determine which TTS script to use."""
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "tts"

    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    pyttsx3_script = tts_dir / "pyttsx3_tts.py"
    if pyttsx3_script.exists():
        return str(pyttsx3_script)

    return None


def generate_fallback_update(recent_tools):
    """Generate a simple fallback update without API."""
    import random

    engineer_name = os.getenv("ENGINEER_NAME", "").strip()

    # Get the most recent meaningful tool
    for tool in reversed(recent_tools):
        tool_name = tool.get('tool_name', '')
        tool_input = tool.get('tool_input', {})
        description = tool.get('description', '')

        if tool_name == 'Bash':
            command = tool_input.get('command', '')
            if 'install' in command.lower() or 'npm' in command.lower():
                action = "Just installed some packages"
            elif 'build' in command.lower():
                action = "Building the project"
            elif 'test' in command.lower():
                action = "Running tests"
            else:
                action = "Executed a command"
        elif tool_name == 'Write':
            action = "Created a new file"
        elif tool_name == 'Edit':
            action = "Updated some code"
        elif tool_name == 'Read':
            action = "Reviewing the code"
        elif tool_name == 'Grep':
            action = "Searching through the codebase"
        else:
            continue

        next_actions = ["moving on to the next step", "checking the results", "continuing with the work", "reviewing what's next"]
        next_action = random.choice(next_actions)

        if engineer_name:
            return f"{action}, {engineer_name}. Now {next_action}"
        else:
            return f"{action}. Now {next_action}"

    return None


def generate_contextual_update(recent_tools):
    """
    Generate a contextual progress update based on recent tool usage.

    Args:
        recent_tools: List of recent tool usage dicts with tool_name, description, etc.

    Returns:
        str: Natural language update, or None if error
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return generate_fallback_update(recent_tools)

    try:
        import anthropic

        # Build context from recent tools
        context = []
        for tool in recent_tools:
            tool_name = tool.get('tool_name', 'unknown')
            description = tool.get('description', '')
            tool_input = tool.get('tool_input', {})

            # Extract meaningful context
            if tool_name == 'Bash':
                command = tool_input.get('command', '')[:100]  # Truncate long commands
                context.append(f"Ran command: {command}")
            elif tool_name == 'Write':
                file_path = tool_input.get('file_path', '')
                context.append(f"Created file: {Path(file_path).name if file_path else 'new file'}")
            elif tool_name == 'Edit':
                file_path = tool_input.get('file_path', '')
                context.append(f"Edited file: {Path(file_path).name if file_path else 'file'}")
            elif tool_name == 'Read':
                file_path = tool_input.get('file_path', '')
                context.append(f"Read file: {Path(file_path).name if file_path else 'file'}")
            elif tool_name == 'Grep':
                pattern = tool_input.get('pattern', '')
                context.append(f"Searched for: {pattern}")
            elif tool_name == 'Glob':
                pattern = tool_input.get('pattern', '')
                context.append(f"Found files matching: {pattern}")

            if description:
                context.append(f"  ({description})")

        context_text = "\n".join(context)

        engineer_name = os.getenv("ENGINEER_NAME", "").strip()
        name_instruction = f"Include the engineer's name '{engineer_name}' naturally in the update." if engineer_name else ""

        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            temperature=0.7,
            messages=[{
                "role": "user",
                "content": f"""You are a friendly AI coding assistant providing quick progress updates.

Recent actions:
{context_text}

Generate a brief, natural progress update (under 15 words) about what you just did and what you're doing next.

Requirements:
- Be casual and conversational
- Mention specific files/actions when relevant
- Sound like you're making progress
- {name_instruction}
- Do NOT include quotes or formatting
- Return ONLY the update message

Examples:
- "Just installed the three.js package, now reviewing the design"
- "Created the API endpoint, moving on to tests"
- "Dan, finished the database migration, checking the schema now"

Your update:"""
            }]
        )

        response = message.content[0].text.strip()
        # Clean up response
        response = response.strip('"').strip("'").strip()
        return response

    except Exception as e:
        return None


def announce_progress(message):
    """Announce progress via TTS."""
    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            return

        subprocess.run(
            ["uv", "run", tts_script, message],
            capture_output=True,
            timeout=10
        )
    except Exception:
        pass


if __name__ == "__main__":
    # Test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_tools = [
            {
                "tool_name": "Bash",
                "tool_input": {"command": "npm install three"},
                "description": "Install three.js package"
            },
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "/path/to/design.md"},
                "description": "Review design document"
            }
        ]

        update = generate_contextual_update(test_tools)
        if update:
            print(f"Generated update: {update}")
            announce_progress(update)
        else:
            print("No update generated")
    else:
        # Read tool data from stdin
        try:
            tools_data = json.loads(sys.stdin.read())
            update = generate_contextual_update(tools_data)
            if update:
                announce_progress(update)
        except Exception:
            # Fail silently
            pass
