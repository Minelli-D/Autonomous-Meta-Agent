from config import client, MODEL

print(f"Testing with model: {MODEL}")
try:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": "Say hello"},
        ],
        temperature=0
    )
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
