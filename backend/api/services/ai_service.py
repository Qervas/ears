"""AI/LLM service for generating explanations and chat."""

import json as json_module
from typing import Optional
from openai import OpenAI

from ..dependencies import load_settings, db


class AIService:
    """Service for AI-powered features."""

    # Track bulk generation status
    bulk_status = {
        "running": False,
        "current": 0,
        "total": 0,
        "completed": 0,
        "failed": 0,
        "failed_words": []
    }

    @staticmethod
    def get_client() -> OpenAI:
        """Get OpenAI-compatible client based on current settings."""
        settings = load_settings()
        provider = settings.get("ai_provider", "lm-studio")
        timeout = 60.0

        if provider == "lm-studio":
            return OpenAI(
                base_url=settings.get("lm_studio_url", "http://localhost:1234/v1"),
                api_key="lm-studio",
                timeout=timeout
            )
        elif provider == "copilot-api":
            return OpenAI(
                base_url=settings.get("copilot_api_url", "http://localhost:4141") + "/v1",
                api_key="copilot",
                timeout=timeout
            )
        elif provider == "openai":
            return OpenAI(
                api_key=settings.get("openai_api_key", ""),
                timeout=timeout
            )
        else:
            return OpenAI(
                base_url="http://localhost:1234/v1",
                api_key="lm-studio",
                timeout=timeout
            )

    @staticmethod
    def get_model() -> str:
        """Get the appropriate model name based on current settings."""
        settings = load_settings()
        provider = settings.get("ai_provider", "lm-studio")

        if provider == "copilot-api":
            return settings.get("copilot_model", "gpt-4o-mini")
        elif provider == "openai":
            return "gpt-3.5-turbo"
        else:
            return "local-model"

    @classmethod
    def get_explanation_prompt(cls, word: str, context: str = "") -> str:
        """Generate prompt for word explanation."""
        return f"""You are a Swedish language teacher helping English speakers learn Swedish.

Explain the Swedish word: "{word}"
{f'Context where learner saw it: "{context}"' if context else ''}

Provide a structured JSON explanation in this exact format:
{{
  "translation": "primary English translation",
  "type": "word type (noun/verb/adjective/preposition/etc.)",
  "usagePatterns": [
    {{"pattern": "swedish phrase", "meaning": "english meaning", "category": "type like 'accompaniment' or 'instrument'"}},
    {{"pattern": "another phrase", "meaning": "its meaning", "category": "category"}}
  ],
  "relatedWords": [
    {{"word": "swedish word", "relation": "opposite/similar/related", "translation": "english"}},
    {{"word": "another word", "relation": "type", "translation": "english"}}
  ],
  "tip": "One helpful sentence about usage or memory trick",
  "note": "Cultural note or important grammar point (or null if none)"
}}

Focus on practical, common usage. Include 2-3 usage patterns and 2-3 related words."""

    @classmethod
    async def generate_explanation(cls, word: str, context: str = "") -> dict:
        """Generate AI explanation for a single word."""
        try:
            client = cls.get_client()
            prompt = cls.get_explanation_prompt(word, context)

            response = client.chat.completions.create(
                model=cls.get_model(),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )

            explanation_text = response.choices[0].message.content.strip()

            # Validate JSON
            try:
                json_module.loads(explanation_text)
                await db.update_word_explanation(word, explanation_text)
                return {"success": True, "word": word, "explanation": explanation_text}
            except json_module.JSONDecodeError:
                return {"success": False, "word": word, "error": "Invalid JSON response"}

        except Exception as e:
            return {"success": False, "word": word, "error": str(e)}

    @classmethod
    async def generate_explanations_batch(cls, words: list[str]):
        """Background task to generate explanations for multiple words."""
        from .backup_service import BackupService
        import asyncio

        cls.bulk_status["running"] = True
        cls.bulk_status["total"] = len(words)
        cls.bulk_status["current"] = 0
        cls.bulk_status["completed"] = 0
        cls.bulk_status["failed"] = 0
        cls.bulk_status["failed_words"] = []

        client = cls.get_client()

        for i, word in enumerate(words):
            cls.bulk_status["current"] = i + 1

            try:
                contexts = await db.get_word_contexts(word, limit=2)
                context = contexts[0] if contexts else ""
                prompt = cls.get_explanation_prompt(word, context)

                response = client.chat.completions.create(
                    model=cls.get_model(),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=800,
                )

                explanation_text = response.choices[0].message.content.strip()

                try:
                    json_module.loads(explanation_text)
                    await db.update_word_explanation(word, explanation_text)
                    cls.bulk_status["completed"] += 1
                    print(f"✓ Generated explanation for: {word} ({i+1}/{len(words)})")
                except json_module.JSONDecodeError:
                    cls.bulk_status["failed"] += 1
                    cls.bulk_status["failed_words"].append({"word": word, "error": "Invalid JSON response"})
                    print(f"✗ Invalid JSON for: {word}")

            except Exception as e:
                error_msg = str(e)
                cls.bulk_status["failed"] += 1

                if "timeout" in error_msg.lower() or "headers timeout" in error_msg.lower():
                    error_type = "Timeout"
                    print(f"✗ Timeout error for {word} ({i+1}/{len(words)})")
                elif "connection" in error_msg.lower() or "fetch failed" in error_msg.lower():
                    error_type = "Connection error"
                    print(f"✗ Connection error for {word} ({i+1}/{len(words)})")
                else:
                    error_type = error_msg[:50]
                    print(f"✗ Error for {word}: {error_msg} ({i+1}/{len(words)})")

                cls.bulk_status["failed_words"].append({"word": word, "error": error_type})
                await asyncio.sleep(1)

        print(f"\n🎉 Bulk generation complete: {cls.bulk_status['completed']} succeeded, {cls.bulk_status['failed']} failed")

        if cls.bulk_status["failed_words"]:
            print("\n❌ Failed words:")
            for item in cls.bulk_status["failed_words"][:10]:
                print(f"   - {item['word']}: {item['error']}")
            if len(cls.bulk_status["failed_words"]) > 10:
                print(f"   ... and {len(cls.bulk_status['failed_words']) - 10} more")

        if cls.bulk_status['completed'] > 0:
            print("\n📦 Creating post-generation backup...")
            BackupService.create_backup()

        cls.bulk_status["running"] = False

    @classmethod
    async def chat(cls, message: str, context: str = "") -> str:
        """Chat with AI tutor about Swedish."""
        client = cls.get_client()

        system_prompt = """You are a friendly Swedish language tutor. Help the user learn Swedish.
- Answer questions about Swedish grammar, vocabulary, and usage
- Provide examples with translations
- Correct mistakes gently
- Use both Swedish and English in your responses"""

        if context:
            system_prompt += f"\n\nThe user is currently studying these Swedish words: {context}"

        response = client.chat.completions.create(
            model=cls.get_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.7,
            max_tokens=1000,
        )

        return response.choices[0].message.content

    @classmethod
    async def generate_grammar_quiz(cls, patterns: list[dict]) -> list[dict]:
        """Generate fill-in-the-blank grammar questions."""
        client = cls.get_client()

        pattern_text = "\n".join([f"- {p['pattern']}: \"{p['example']}\"" for p in patterns[:5]])

        prompt = f"""Based on these Swedish grammar patterns and examples:
{pattern_text}

Generate 5 fill-in-the-blank questions to test these patterns. Return as JSON array:
[
  {{
    "question": "Swedish sentence with ___ for blank",
    "answer": "correct word",
    "hint": "grammar hint",
    "pattern": "which pattern this tests"
  }}
]

Make questions progressively harder. Use natural Swedish sentences."""

        response = client.chat.completions.create(
            model=cls.get_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000,
        )

        try:
            content = response.choices[0].message.content
            start = content.find('[')
            end = content.rfind(']') + 1
            if start >= 0 and end > start:
                return json_module.loads(content[start:end])
        except:
            pass

        return []
