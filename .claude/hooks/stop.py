#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
#     "anthropic",
#     "openai",
# ]
# ///

import argparse
import json
import os
import sys
import random
import subprocess
from pathlib import Path
from datetime import datetime
from utils.constants import ensure_session_log_dir

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def get_completion_messages():
    """Return list of creative and fun completion messages."""
    engineer_name = os.getenv("ENGINEER_NAME", "").strip()

    if engineer_name:
        return [
            f"Mission accomplished, {engineer_name}!",
            f"Crushed it, {engineer_name}!",
            f"Done and dusted, {engineer_name}!",
            f"Nailed it, {engineer_name}!",
            f"Boom! All yours, {engineer_name}!",
            f"{engineer_name}, we're cooking now!",
            f"Easy peasy, {engineer_name}!",
            f"{engineer_name}, another win in the books!",
            f"Code complete, {engineer_name}!",
            f"{engineer_name}, the stage is yours!",
        ]
    else:
        return [
            "Mission accomplished!",
            "Crushed it!",
            "Done and dusted!",
            "Nailed it!",
            "Boom! All set!",
            "We're cooking now!",
            "Easy peasy!",
            "Another win!",
            "Code complete!",
            "Victory!",
        ]


def get_tts_script_path():
    """
    Determine which TTS script to use based on available API keys.
    Priority order: ElevenLabs > OpenAI > pyttsx3
    """
    # Get current script directory and construct utils/tts path
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    # Check for ElevenLabs API key (highest priority)
    if os.getenv("ELEVENLABS_API_KEY"):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    # Check for OpenAI API key (second priority)
    if os.getenv("OPENAI_API_KEY"):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    # Fall back to pyttsx3 (no API key required)
    pyttsx3_script = tts_dir / "pyttsx3_tts.py"
    if pyttsx3_script.exists():
        return str(pyttsx3_script)

    return None


def get_recent_tool_context(session_id):
    """
    Read recent tool usage from session logs to provide context.

    Args:
        session_id: The session ID

    Returns:
        list: Recent tool usage data (last 5 tools), or empty list if unavailable
    """
    try:
        log_dir = ensure_session_log_dir(session_id)
        post_tool_log = log_dir / "post_tool_use.json"

        if not post_tool_log.exists():
            return []

        with open(post_tool_log, 'r') as f:
            tool_data = json.load(f)

        # Get last 5 tool uses
        recent_tools = tool_data[-5:] if len(tool_data) >= 5 else tool_data

        # Extract relevant context
        context = []
        for tool_event in recent_tools:
            tool_name = tool_event.get('tool_name', '')
            tool_input = tool_event.get('tool_input', {})
            description = tool_input.get('description', '')

            context.append({
                'tool_name': tool_name,
                'description': description,
                'tool_input': tool_input
            })

        return context
    except Exception:
        return []


def generate_contextual_completion_message(context):
    """
    Generate a contextual completion message using LLM based on what was actually done.

    Args:
        context: List of recent tool usage

    Returns:
        str: Generated completion message or None if failed
    """
    if not context:
        return None

    # Try Anthropic first
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic

            # Build context summary
            actions = []
            for tool in context:
                tool_name = tool.get('tool_name', '')
                description = tool.get('description', '')
                tool_input = tool.get('tool_input', {})

                if tool_name == 'Bash':
                    command = tool_input.get('command', '')[:100]
                    actions.append(f"Ran: {command}")
                elif tool_name == 'Write':
                    file_path = tool_input.get('file_path', '')
                    actions.append(f"Created: {Path(file_path).name if file_path else 'file'}")
                elif tool_name == 'Edit':
                    file_path = tool_input.get('file_path', '')
                    actions.append(f"Edited: {Path(file_path).name if file_path else 'file'}")
                elif tool_name == 'Read':
                    file_path = tool_input.get('file_path', '')
                    actions.append(f"Read: {Path(file_path).name if file_path else 'file'}")
                elif tool_name == 'Grep' or tool_name == 'Glob':
                    pattern = tool_input.get('pattern', '')
                    actions.append(f"Searched: {pattern}")
                elif tool_name == 'Task':
                    prompt = tool_input.get('prompt', '')[:50]
                    actions.append(f"Delegated task: {prompt}")

                if description:
                    actions.append(f"  ({description})")

            context_text = "\n".join(actions)

            engineer_name = os.getenv("ENGINEER_NAME", "").strip()
            name_instruction = f"ALWAYS include the engineer's name '{engineer_name}' naturally." if engineer_name else ""

            client = anthropic.Anthropic(api_key=api_key)

            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=50,
                temperature=0.8,
                messages=[{
                    "role": "user",
                    "content": f"""You are a friendly AI coding assistant. Generate a brief, creative completion message based on what you just accomplished.

Recent actions:
{context_text}

Generate a short completion message (under 10 words) that:
- References what you actually did
- Is positive, energetic, and occasionally witty
- Sounds natural and conversational
- {name_instruction}
- Do NOT include quotes or formatting
- Return ONLY the message

Examples:
- "Database migrated successfully, Dan! Ready to roll!"
- "Tests passing! Feeling good about this, Sarah!"
- "API endpoints all hooked up, boss!"
- "Refactored that code like a champ!"

Your message:"""
                }]
            )

            response = message.content[0].text.strip()
            response = response.strip('"').strip("'").strip()
            return response

        except Exception:
            pass

    # Try OpenAI if Anthropic fails
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI

            # Build context (same as above)
            actions = []
            for tool in context:
                tool_name = tool.get('tool_name', '')
                description = tool.get('description', '')
                actions.append(f"{tool_name}: {description}" if description else tool_name)

            context_text = ", ".join(actions[-3:])  # Last 3 actions

            engineer_name = os.getenv("ENGINEER_NAME", "").strip()
            name_instruction = f"Include '{engineer_name}' in the message." if engineer_name else ""

            client = OpenAI(api_key=api_key)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=30,
                temperature=0.8,
                messages=[{
                    "role": "user",
                    "content": f"Generate a brief (under 10 words), energetic completion message about: {context_text}. {name_instruction} Be creative and positive. Return only the message, no quotes."
                }]
            )

            message = response.choices[0].message.content.strip()
            message = message.strip('"').strip("'").strip()
            return message

        except Exception:
            pass

    return None


def get_llm_completion_message(session_id=None):
    """
    Generate completion message using available LLM services.
    Priority order: Contextual (if session_id) > OpenAI > Anthropic > fallback to random message

    Args:
        session_id: Optional session ID to generate contextual messages

    Returns:
        str: Generated or fallback completion message
    """
    # Try contextual message first if session_id is provided
    if session_id:
        context = get_recent_tool_context(session_id)
        if context:
            contextual_msg = generate_contextual_completion_message(context)
            if contextual_msg:
                return contextual_msg

    # Fall back to generic LLM-generated messages
    # Get current script directory and construct utils/llm path
    script_dir = Path(__file__).parent
    llm_dir = script_dir / "utils" / "llm"

    # Try Anthropic second
    if os.getenv("ANTHROPIC_API_KEY"):
        anth_script = llm_dir / "anth.py"
        if anth_script.exists():
            try:
                result = subprocess.run(
                    ["uv", "run", str(anth_script), "--completion"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

    # Try OpenAI first (highest priority)
    if os.getenv("OPENAI_API_KEY"):
        oai_script = llm_dir / "oai.py"
        if oai_script.exists():
            try:
                result = subprocess.run(
                    ["uv", "run", str(oai_script), "--completion"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

    # Fallback to random predefined message
    messages = get_completion_messages()
    return random.choice(messages)


def announce_completion(session_id=None):
    """Announce completion using the best available TTS service.

    Args:
        session_id: Optional session ID for contextual messages
    """
    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            return  # No TTS scripts available

        # Get completion message (contextual if session_id provided, or fallback)
        completion_message = get_llm_completion_message(session_id)

        # Call the TTS script with the completion message
        subprocess.run(
            ["uv", "run", tts_script, completion_message],
            capture_output=True,  # Suppress output
            timeout=10,  # 10-second timeout
        )

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Fail silently if TTS encounters issues
        pass
    except Exception:
        # Fail silently for any other errors
        pass


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--chat", action="store_true", help="Copy transcript to chat.json"
        )
        args = parser.parse_args()

        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Extract required fields
        session_id = input_data.get("session_id", "")
        stop_hook_active = input_data.get("stop_hook_active", False)

        # Ensure session log directory exists
        log_dir = ensure_session_log_dir(session_id)
        log_path = log_dir / "stop.json"

        # Read existing log data or initialize empty list
        if log_path.exists():
            with open(log_path, "r") as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []

        # Append new data
        log_data.append(input_data)

        # Write back to file with formatting
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)

        # Handle --chat switch
        if args.chat and "transcript_path" in input_data:
            transcript_path = input_data["transcript_path"]
            if os.path.exists(transcript_path):
                # Read .jsonl file and convert to JSON array
                chat_data = []
                try:
                    with open(transcript_path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    chat_data.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass  # Skip invalid lines

                    # Write to logs/chat.json
                    chat_file = os.path.join(log_dir, "chat.json")
                    with open(chat_file, "w") as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass  # Fail silently

        # Announce completion via TTS with contextual message
        announce_completion(session_id)

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
