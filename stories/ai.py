from ollama import chat

MODEL_NAME = "qwen2.5:3b"


def generate_story(prompt):
    response = chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]