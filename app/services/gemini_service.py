"""
BIS SmartAI — AI Engine Service (Groq Llama 3.3 70B & Gemini Multi-Provider)
Provides natural, human-friendly, accurate, and ultra-fast Indian Standards & BIS intelligence.
"""
import json
import logging
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Try importing Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("Groq SDK not installed. Falling back to Gemini.")

# Try importing Google GenAI
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


BIS_SYSTEM_PROMPT = """You are BIS SmartAI, an intelligent, conversational assistant specialized in Indian Standards (IS), Bureau of Indian Standards (BIS), Quality Control Orders (QCOs), product certification, testing requirements, laboratories, and compliance processes in India.

YOUR CORE MISSION:
Help Indian industries, manufacturers, importers, laboratories, professionals, and consumers understand BIS standards and regulations in a friendly, conversational, clear, and structured manner.

COMMUNICATION & CONVERSATIONAL STYLE:
- Be conversational, helpful, and human-friendly. Do NOT sound like a cold legal document or a robotic database dump.
- Always start with a short, direct answer in plain English.
- If the user asks a simple conceptual question (e.g. "What does QCO mean?"), provide a clear, concise, conversational explanation without forcing irrelevant technical sections.
- If the user asks a detailed compliance question (e.g. "What are the BIS requirements for TMT steel bars?"), provide a comprehensive structured breakdown.
- Maintain conversational context across follow-up questions (e.g., if the user asks "What about steel?" and then "What tests are required?", answer specifically in the context of steel).
- If the question is ambiguous, give a helpful answer and ask a concise clarification.

HANDLING OFF-TOPIC & GENERAL QUESTIONS:
- If the user asks something unrelated to BIS/Indian Standards (e.g., "Who is Ratan Tata?", "What is the capital of India?", "Tell me a joke", "Explain quantum physics"), answer it NATURALLY and HELPFULLY using your general knowledge.
- Never refuse to answer general questions.

STRICT HONESTY & VERIFICATION RULES:
- Never fabricate IS numbers, standard titles, QCO dates, mandatory deadlines, test clauses, or laboratory names.
- If uncertain about a standard or regulation, explicitly set "verification_status" to "needs_verification".
- If no official standard applies, set "verification_status" to "no_source_found".
- Prioritize official sources: bis.gov.in, manakonline.in, dpiit.gov.in, and The Gazette of India (egazette.gov.in). Never invent URLs.

CONSUMER & BUYER PRECAUTIONS (MANDATORY):
- At the end of every response, ALWAYS provide 2 to 3 practical, actionable safety/buyer precautions for the user/consumer (e.g. verifying the genuine ISI Mark and 7/8 digit CML Licence Number on the BIS Care Mobile App, checking product rating plate and batch codes, proper voltage/earthing installation, and avoiding non-certified fake goods).
- In the markdown `answer`, present these clearly under the header: `### 🛡️ Consumer & Buyer Safety Precautions`.

OUTPUT FORMAT:
Always return valid, clean JSON with this exact schema:
{
  "answer": "Conversational, direct, human-friendly answer. If explaining a multi-step process, use clean markdown headers and separate bullet lines:\\n\\n### Step 1: Step Title\\nBrief step description.\\n- Sub-item 1\\n- Sub-item 2\\n\\n### 🛡️ Consumer & Buyer Safety Precautions\\n- Precaution 1 (e.g., Check genuine ISI Mark and verify CML number via BIS Care App)\\n- Precaution 2\\n- Precaution 3\\n\\nAlways use bold formatting like **IS 302-2-15** or **ISI Mark** for key standard names, schemes, and terms. Put every bullet point on its own newline with '- '.",
  "is_bis_related": true,
  "applicable_standard": {
    "reference": "e.g., IS 302-2-15 or IS 1786, or null if not applicable",
    "title": "Full official title of the standard, or null if not applicable",
    "status": "Active / Superseded / Under Revision / null",
    "applicability": "Product scope in simple language, or null",
    "verification_status": "verified / needs_verification / no_source_found"
  },
  "requirements": [
    "Key requirement 1 in simple terms",
    "Key requirement 2 in simple terms"
  ],
  "qco": {
    "applicable": true,
    "reference": "e.g., Steel and Steel Products (Quality Control) Order, or null",
    "details": "Clear explanation of whether certification is mandatory, or null",
    "effective_date": "Date if verified, or Needs Verification",
    "verification_status": "verified / needs_verification / no_source_found"
  },
  "testing": [
    "Test 1 (e.g., Tensile strength test)",
    "Test 2 (e.g., Chemical composition analysis)"
  ],
  "certification": [
    "Scheme-I (Product Certification Scheme / ISI Mark)",
    "Online application via BIS Manakonline (manakonline.in)"
  ],
  "laboratories": [
    "BIS Central / Regional Laboratories",
    "NABL-accredited & BIS-recognized testing facilities"
  ],
  "consumer_precautions": [
    "Verify genuine ISI Mark and active CML number using the BIS Care App before purchase",
    "Inspect manufacturer address, batch code, and statutory rating label on packaging",
    "Follow mandatory installation, earthing, and safe usage guidelines"
  ],
  "sources": [
    {
      "title": "Bureau of Indian Standards Official Portal",
      "url": "https://www.bis.gov.in",
      "domain": "bis.gov.in",
      "source_type": "official",
      "relevance": "National Standards Body of India"
    }
  ],
  "verification_status": "verified / needs_verification / no_source_found"
}

If a section is not applicable (e.g., for off-topic or general questions), you may set arrays to [] and objects to null, but keep 'answer' rich, warm, and helpful.
Do not output Markdown outside the JSON. Return strictly valid JSON."""


class AIService:
    """
    High-Performance AI Service supporting Groq (Llama 3.3 70B) as primary
    with fallback to Google Gemini.
    """

    def __init__(self):
        self._groq_client: Optional[Any] = None
        self._gemini_clients: list[Any] = []
        self._gemini_index: int = 0
        self._gemini_exhausted: list[bool] = []

        # Initialize Groq
        if GROQ_AVAILABLE and settings.is_groq_configured:
            try:
                self._groq_client = Groq(api_key=settings.groq_api_key)
                logger.info("⚡ Groq Llama 3.3 70B AI client initialized successfully!")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")

        # Initialize Gemini fallback
        if GENAI_AVAILABLE and settings.is_gemini_configured:
            for key in settings.gemini_api_keys:
                try:
                    client = genai.Client(api_key=key)
                    self._gemini_clients.append(client)
                    self._gemini_exhausted.append(False)
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini client: {e}")

    @property
    def is_configured(self) -> bool:
        return (self._groq_client is not None) or (len(self._gemini_clients) > 0)

    # ------------------------------------------------------------------
    # Main Generation
    # ------------------------------------------------------------------

    def generate_response(self, prompt: str, history: Optional[list] = None) -> Dict[str, Any]:
        """
        Generate structured BIS intelligence response.
        Uses Groq (Llama 3.3 70B) first for speed and accuracy.
        Falls back to Gemini if Groq fails.
        """
        if not self.is_configured:
            return self._get_unconfigured_response(prompt)

        # 1. Try Groq (Primary)
        if self._groq_client:
            try:
                result = self._generate_with_groq(prompt, history)
                if result:
                    logger.info("⚡ Response generated successfully using Groq Llama 3.3 70B.")
                    return result
            except Exception as e:
                logger.warning(f"Groq generation failed: {e}. Trying fallback...")

        # 2. Try Gemini (Fallback)
        if self._gemini_clients:
            try:
                result = self._generate_with_gemini(prompt, history)
                if result:
                    logger.info("Response generated successfully using Gemini.")
                    return result
            except Exception as e:
                logger.error(f"Gemini fallback failed: {e}")

        return self._get_fallback_response(prompt, "Both Groq and Gemini generation failed.")

    # ------------------------------------------------------------------
    # Groq Implementation
    # ------------------------------------------------------------------

    def _generate_with_groq(self, prompt: str, history: Optional[list] = None) -> Optional[Dict[str, Any]]:
        messages = [{"role": "system", "content": BIS_SYSTEM_PROMPT}]

        if history:
            for msg in history[-8:]:
                role = "user" if msg.role == "user" else "assistant"
                messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": prompt})

        # Try standard high-performance ultra-fast Groq models (~1s)
        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
            try:
                completion = self._groq_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
                content = completion.choices[0].message.content.strip()
                parsed = json.loads(content)
                logger.info(f"⚡ Groq response OK using model: {model}")
                return self._standardize_response(parsed)
            except Exception as e:
                logger.warning(f"Groq model {model} failed: {e}. Trying next model...")
                continue

        return None

    # ------------------------------------------------------------------
    # Gemini Implementation (Fallback)
    # ------------------------------------------------------------------

    def _generate_with_gemini(self, prompt: str, history: Optional[list] = None) -> Optional[Dict[str, Any]]:
        if not self._gemini_clients:
            return None

        contents = []
        if history:
            for msg in history[-8:]:
                role = "user" if msg.role == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))
        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

        client = self._gemini_clients[self._gemini_index % len(self._gemini_clients)]
        for model in ["models/gemini-3.5-flash-lite", "models/gemini-3.6-flash", "models/gemini-3.7-flash", "models/gemini-3.5-flash"]:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=BIS_SYSTEM_PROMPT,
                        temperature=0.2,
                        top_p=0.9,
                        response_mime_type="application/json",
                    ),
                )
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                parsed = json.loads(text.strip())
                return self._standardize_response(parsed)
            except Exception as e:
                logger.warning(f"Gemini model {model} failed: {e}. Trying next model...")
                continue
        return None

    # ------------------------------------------------------------------
    # Helper & Standardizer
    # ------------------------------------------------------------------

    def _standardize_response(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        if "summary" not in parsed and "answer" in parsed:
            parsed["summary"] = parsed["answer"]
        if "standard" not in parsed and "applicable_standard" in parsed:
            std = parsed["applicable_standard"]
            if std and isinstance(std, dict):
                parsed["standard"] = {
                    "number": std.get("reference", ""),
                    "title": std.get("title", ""),
                    "status": std.get("status", "Active"),
                    "category": std.get("applicability", "Indian Standard"),
                    "qco_applicable": (
                        parsed.get("qco", {}).get("applicable", False)
                        if isinstance(parsed.get("qco"), dict)
                        else False
                    ),
                    "verification_status": std.get("verification_status", "needs_verification"),
                }
        return parsed

    def _get_unconfigured_response(self, prompt: str) -> Dict[str, Any]:
        return {
            "answer": (
                "Hello! I am ready to help you with Indian Standards and BIS compliance. "
                "Please configure GROQ_API_KEY or GEMINI_API_KEY in `backend/.env`."
            ),
            "summary": "AI API key is not configured.",
            "is_bis_related": False,
            "applicable_standard": None,
            "requirements": [],
            "qco": None,
            "testing": [],
            "certification": [],
            "laboratories": [],
            "sources": [
                {
                    "title": "Bureau of Indian Standards",
                    "url": "https://www.bis.gov.in",
                    "domain": "bis.gov.in",
                    "source_type": "official",
                    "relevance": "National Standards Body of India",
                }
            ],
            "verification_status": "no_source_found",
        }

    def _get_fallback_response(self, prompt: str, error_msg: str) -> Dict[str, Any]:
        return {
            "answer": f"I encountered an issue processing your request ({error_msg}). Please try again.",
            "summary": f"Query regarding '{prompt}' could not be processed.",
            "is_bis_related": False,
            "applicable_standard": None,
            "requirements": [],
            "qco": None,
            "testing": [],
            "certification": [],
            "laboratories": [],
            "sources": [],
            "verification_status": "needs_verification",
        }


# Singleton instance exported as gemini_service for backward compatibility
gemini_service = AIService()
