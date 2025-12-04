"""LLM-based transcript cleanup using LM Studio."""

from openai import OpenAI
from config import LM_STUDIO_BASE_URL, LM_STUDIO_API_KEY
from storage import get_uncleaned_transcripts, update_cleaned_text


client = OpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key=LM_STUDIO_API_KEY,
)

CLEANUP_PROMPT = """You are a Swedish language expert. Your task is to clean up speech-to-text transcription errors.

Given a raw Swedish transcription that may contain:
- Misspelled words
- Incorrect word boundaries
- Missing or wrong punctuation
- Phonetically similar but incorrect words

Output ONLY the corrected Swedish text. Do not explain, do not translate, do not add anything else.
If the text is already correct, output it as-is.
If the text is empty or just noise, output: [empty]

Raw transcription:
{text}

Corrected text:"""


def clean_single(raw_text: str) -> str:
    """Clean a single transcript using LM Studio."""
    if not raw_text or not raw_text.strip():
        return "[empty]"

    try:
        response = client.chat.completions.create(
            model="local-model",  # LM Studio uses this placeholder
            messages=[
                {"role": "user", "content": CLEANUP_PROMPT.format(text=raw_text)}
            ],
            temperature=0.1,  # Low temperature for consistent corrections
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM cleanup error: {e}")
        return raw_text  # Return original if cleanup fails


def clean_batch(batch_size: int = 20):
    """Clean a batch of uncleaned transcripts."""
    uncleaned = get_uncleaned_transcripts(limit=batch_size)

    if not uncleaned:
        print("No uncleaned transcripts found.")
        return 0

    print(f"Cleaning {len(uncleaned)} transcripts...")

    cleaned_count = 0
    for id_, raw_text in uncleaned:
        cleaned = clean_single(raw_text)
        update_cleaned_text(id_, cleaned)
        cleaned_count += 1

        # Show progress
        print(f"  [{id_}] {raw_text[:40]}... → {cleaned[:40]}...")

    print(f"✓ Cleaned {cleaned_count} transcripts")
    return cleaned_count


def clean_all():
    """Clean all uncleaned transcripts."""
    total = 0
    while True:
        count = clean_batch(batch_size=20)
        if count == 0:
            break
        total += count
    return total


if __name__ == "__main__":
    print("Testing LM Studio connection...")
    print("Make sure LM Studio is running with a model loaded!")
    print()

    # Test with sample Swedish text
    test_text = "jag tror att det ar en bra ide"
    print(f"Test input: {test_text}")

    cleaned = clean_single(test_text)
    print(f"Cleaned: {cleaned}")
