#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import json
import os
import sys
import subprocess
import random
from pathlib import Path
from utils.constants import ensure_session_log_dir

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def should_announce_progress(recent_tools, progress_counter):
    """
    Determine if we should announce progress based on recent activity.

    Returns: bool
    """
    # Don't announce too frequently - every 3-6 tools (randomized)
    min_tools = 3
    max_tools = 6
    threshold = random.randint(min_tools, max_tools)

    if progress_counter < threshold:
        return False

    # Only announce for meaningful tools
    meaningful_tools = ['Bash', 'Write', 'Edit', 'Grep', 'Glob', 'Task']
    has_meaningful = any(t.get('tool_name') in meaningful_tools for t in recent_tools[-threshold:])

    return has_meaningful


def announce_contextual_progress(recent_tools):
    """Generate and announce contextual progress update."""
    try:
        script_dir = Path(__file__).parent
        announcer_script = script_dir / "utils" / "progress_announcer.py"

        if not announcer_script.exists():
            return

        # Pass recent tool data to the announcer
        tools_json = json.dumps(recent_tools[-5:])  # Last 5 tools for context

        # Call the announcer script
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
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Extract session_id
        session_id = input_data.get('session_id', 'unknown')

        # Ensure session log directory exists
        log_dir = ensure_session_log_dir(session_id)
        log_path = log_dir / 'post_tool_use.json'
        progress_state_path = log_dir / 'progress_state.json'

        # Read existing log data or initialize empty list
        if log_path.exists():
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []

        # Append new data
        log_data.append(input_data)

        # Write back to file with formatting
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)

        # Progress announcement logic
        # Read progress state
        if progress_state_path.exists():
            with open(progress_state_path, 'r') as f:
                try:
                    progress_state = json.load(f)
                    progress_counter = progress_state.get('counter', 0)
                except (json.JSONDecodeError, ValueError):
                    progress_counter = 0
        else:
            progress_counter = 0

        progress_counter += 1

        # Check if we should announce progress
        if should_announce_progress(log_data, progress_counter):
            announce_contextual_progress(log_data)
            progress_counter = 0  # Reset counter

        # Save progress state
        with open(progress_state_path, 'w') as f:
            json.dump({'counter': progress_counter}, f)

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Exit cleanly on any other error
        sys.exit(0)

if __name__ == '__main__':
    main()