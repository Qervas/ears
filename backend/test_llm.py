"""Test LM Studio connection."""
from openai import OpenAI

client = OpenAI(base_url='http://localhost:1234/v1', api_key='lm-studio')

print("Testing LM Studio connection...")
response = client.chat.completions.create(
    model='local-model',
    messages=[{'role': 'user', 'content': 'Explain the Swedish word "hej" in English. Keep it short.'}],
    temperature=0.3,
    max_tokens=100,
)
print("Response:", response.choices[0].message.content)
