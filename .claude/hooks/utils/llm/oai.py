#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

import os
import sys
from dotenv import load_dotenv


def prompt_llm(prompt_text):
    """
    Base OpenAI LLM prompting method using fastest model.

    Args:
        prompt_text (str): The prompt to send to the model

    Returns:
        str: The model's response text, or None if error
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4.1-nano",  # Fastest OpenAI model
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=100,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    except Exception:
        return None


def generate_completion_message():
    """
    Generate a completion message using OpenAI LLM.

    Returns:
        str: A natural language completion message, or None if error
    """
    engineer_name = os.getenv("ENGINEER_NAME", "").strip()

    if engineer_name:
        name_instruction = f"ALWAYS include the engineer's name '{engineer_name}' in a natural way."
        examples = f"""Examples of the style (mix professional, playful, and occasionally humorous):
- "{engineer_name}, mission accomplished!", "Crushed it, {engineer_name}!", "{engineer_name}, we're cooking now!"
- "Done and dusted, {engineer_name}!", "{engineer_name}, another one bites the dust!", "Nailed it, {engineer_name}!"
- "{engineer_name}, your code is poetry!", "Boom! Done, {engineer_name}!", "{engineer_name}, that was easy!"
- "All yours, {engineer_name}!", "{engineer_name}, the stage is yours!", "Ready when you are, {engineer_name}!" """
    else:
        name_instruction = ""
        examples = """Examples of the style: "Mission accomplished!", "Crushed it!", "Done and dusted!", "Boom! All set!", "Another win!" """

    prompt = f"""Generate a short, creative, and engaging completion message for when an AI coding assistant finishes a task.

Requirements:
- Keep it under 10 words
- Make it positive, energetic, and occasionally humorous
- Vary the tone: professional, playful, confident, or witty
- Use natural, conversational language
- Do NOT include quotes, formatting, or explanations
- Return ONLY the completion message text
{name_instruction}

{examples}

Generate ONE creative completion message:"""

    response = prompt_llm(prompt)

    # Clean up response - remove quotes and extra formatting
    if response:
        response = response.strip().strip('"').strip("'").strip()
        # Take first line if multiple lines
        response = response.split("\n")[0].strip()

    return response


def main():
    """Command line interface for testing."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--completion":
            message = generate_completion_message()
            if message:
                print(message)
            else:
                print("Error generating completion message")
        else:
            prompt_text = " ".join(sys.argv[1:])
            response = prompt_llm(prompt_text)
            if response:
                print(response)
            else:
                print("Error calling OpenAI API")
    else:
        print("Usage: ./oai.py 'your prompt here' or ./oai.py --completion")


if __name__ == "__main__":
    main()