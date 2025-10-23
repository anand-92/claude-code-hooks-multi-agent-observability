#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "anthropic",
#     "google-generativeai",
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
    """Generate a simple fallback update without API, trying to infer the goal."""
    import random

    engineer_name = os.getenv("ENGINEER_NAME", "").strip()

    # Try to infer goal from patterns of actions
    tool_names = [t.get('tool_name', '') for t in recent_tools[-5:]]

    # Pattern: Multiple Reads/Greps = investigating/researching
    if tool_names.count('Read') + tool_names.count('Grep') >= 3:
        goals = [
            "Investigating the codebase",
            "Researching the implementation",
            "Understanding how this works",
            "Reviewing the code structure"
        ]
        goal = random.choice(goals)
    # Pattern: Edit + Bash = fixing/testing something
    elif 'Edit' in tool_names and 'Bash' in tool_names:
        goals = [
            "Making some fixes and testing",
            "Updating code and running checks",
            "Tweaking the implementation"
        ]
        goal = random.choice(goals)
    # Pattern: Write + Edit = building/creating
    elif 'Write' in tool_names or tool_names.count('Edit') >= 2:
        goals = [
            "Building out the feature",
            "Setting things up",
            "Adding new functionality"
        ]
        goal = random.choice(goals)
    # Pattern: Bash commands = running operations
    elif 'Bash' in tool_names:
        for tool in reversed(recent_tools):
            if tool.get('tool_name') == 'Bash':
                command = tool.get('tool_input', {}).get('command', '')
                if 'install' in command.lower():
                    goal = "Installing dependencies"
                elif 'build' in command.lower():
                    goal = "Building the project"
                elif 'test' in command.lower():
                    goal = "Running tests"
                else:
                    goal = "Running some commands"
                break
    else:
        goal = "Working through the task"

    if engineer_name:
        return f"{engineer_name}, {goal.lower()}"
    else:
        return goal

    return None


def generate_contextual_update(recent_tools):
    """
    Generate a contextual progress update based on recent tool usage.

    Args:
        recent_tools: List of recent tool usage dicts with tool_name, description, etc.

    Returns:
        str: Natural language update, or None if error
    """
    # Build context from recent tools (shared logic)
    context = []
    for tool in recent_tools:
        tool_name = tool.get('tool_name', 'unknown')
        tool_input = tool.get('tool_input', {})
        description = tool_input.get('description', '')

        # Extract meaningful context - use description as primary, with details as secondary
        if description:
            # Prefer human-written descriptions as they're more meaningful
            context.append(description)
        else:
            # Fallback to auto-generated context if no description
            if tool_name == 'Bash':
                command = tool_input.get('command', '')[:80]
                context.append(f"Running: {command}")
            elif tool_name == 'Write':
                file_path = tool_input.get('file_path', '')
                context.append(f"Creating {Path(file_path).name if file_path else 'new file'}")
            elif tool_name == 'Edit':
                file_path = tool_input.get('file_path', '')
                context.append(f"Editing {Path(file_path).name if file_path else 'a file'}")
            elif tool_name == 'Read':
                file_path = tool_input.get('file_path', '')
                context.append(f"Reading {Path(file_path).name if file_path else 'a file'}")
            elif tool_name == 'Grep':
                pattern = tool_input.get('pattern', '')
                context.append(f"Searching codebase for '{pattern}'")
            elif tool_name == 'Glob':
                pattern = tool_input.get('pattern', '')
                context.append(f"Finding files: {pattern}")

    context_text = "\n".join(context)
    engineer_name = os.getenv("ENGINEER_NAME", "").strip()
    name_instruction = f"Start with the engineer's name '{engineer_name},' at the beginning" if engineer_name else "Do not include any name"

    # Try Gemini first (cheapest and fastest)
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        try:
            import google.generativeai as genai

            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-lite-latest')

            prompt = f"""You are providing factual work status updates.

Recent actions:
{context_text}

Based ONLY on these actions, state what task is being worked on. Use 8-12 words maximum.

STRICT RULES:
- {name_instruction}
- Be LITERAL and SPECIFIC - mention actual files/topics from the actions
- Use present continuous tense ("-ing" verbs)
- NO praise, NO motivation, NO excitement, NO generic statements
- If you can't infer a clear task, describe the most recent action
- Return ONLY the statement, nothing else

GOOD (specific, factual):
- "Nick, checking temperature settings in announcement files"
- "Reviewing session log directory structure"
- "Searching for TTS model configuration"

BAD (generic, praise-y, vague):
- "Your search was successful" ← TOO VAGUE
- "Making great progress" ← TOO GENERIC
- "Code is looking good" ← PRAISE (FORBIDDEN)
- "Working on improvements" ← NOT SPECIFIC

Statement:"""

            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'max_output_tokens': 50,
                }
            )

            text = response.text.strip()
            text = text.strip('"').strip("'").strip()
            return text

        except Exception:
            pass

    # Fallback to Anthropic
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=anthropic_api_key)

            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=50,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": f"""You are providing factual work status updates.

Recent actions:
{context_text}

Based ONLY on these actions, state what task is being worked on. Use 8-12 words maximum.

STRICT RULES:
- {name_instruction}
- Be LITERAL and SPECIFIC - mention actual files/topics from the actions
- Use present continuous tense ("-ing" verbs)
- NO praise, NO motivation, NO excitement, NO generic statements
- If you can't infer a clear task, describe the most recent action
- Return ONLY the statement, nothing else

GOOD (specific, factual):
- "Nick, checking temperature settings in announcement files"
- "Reviewing session log directory structure"
- "Searching for TTS model configuration"

BAD (generic, praise-y, vague):
- "Your search was successful" ← TOO VAGUE
- "Making great progress" ← TOO GENERIC
- "Code is looking good" ← PRAISE (FORBIDDEN)
- "Working on improvements" ← NOT SPECIFIC

Statement:"""
                }]
            )

            response = message.content[0].text.strip()
            response = response.strip('"').strip("'").strip()
            return response

        except Exception:
            pass

    # Final fallback to simple update
    return generate_fallback_update(recent_tools)


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
