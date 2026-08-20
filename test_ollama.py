from ollama import chat

response = chat(
    model="qwen2.5:3b",
    messages=[
        {
            "role": "user",
            "content": "Write a 50-word mystery story."
        }
    ]
)

print(response["message"]["content"])