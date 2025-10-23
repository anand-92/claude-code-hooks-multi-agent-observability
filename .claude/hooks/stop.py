#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import argparse
import json
import sys
import subprocess
from pathlib import Path
from utils.constants import ensure_session_log_dir

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional




def announce_if_work_done(session_id):
    """
    Announce progress ONLY if actual work was done this turn.
    Uses the same factual progress announcer as post_tool_use hook.

    Args:
        session_id: The session ID
    """
    try:
        log_dir = ensure_session_log_dir(session_id)
        post_tool_log = log_dir / "post_tool_use.json"
        stop_state_path = log_dir / "stop_state.json"

        # Read current tool count
        if not post_tool_log.exists():
            return  # No tools used, nothing to announce

        with open(post_tool_log, 'r') as f:
            tool_data = json.load(f)

        current_tool_count = len(tool_data)

        # Read last tool count from previous stop
        last_tool_count = 0
        if stop_state_path.exists():
            with open(stop_state_path, 'r') as f:
                try:
                    state = json.load(f)
                    last_tool_count = state.get('tool_count', 0)
                except (json.JSONDecodeError, ValueError):
                    pass

        # Save current count for next time
        with open(stop_state_path, 'w') as f:
            json.dump({'tool_count': current_tool_count}, f)

        # If no new tools used this turn, SILENT
        if current_tool_count <= last_tool_count:
            return

        # Get recent tools for context
        recent_tools = tool_data[-5:] if len(tool_data) >= 5 else tool_data

        # Extract context in same format as progress_announcer expects
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

        # Call progress announcer with same factual approach
        script_dir = Path(__file__).parent
        announcer_script = script_dir / "utils" / "progress_announcer.py"

        if not announcer_script.exists():
            return

        tools_json = json.dumps(context)
        subprocess.run(
            ["uv", "run", str(announcer_script)],
            input=tools_json,
            capture_output=True,
            text=True,
            timeout=15
        )

    except Exception:
        # Fail silently
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
            transcript_path = Path(input_data["transcript_path"])
            if transcript_path.exists():
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
                    chat_file = log_dir / "chat.json"
                    with open(chat_file, "w") as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass  # Fail silently

        # Announce ONLY if actual work was done this turn
        announce_if_work_done(session_id)

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
