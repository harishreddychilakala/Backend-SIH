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


BIS_SYSTEM_PROMPT = """You are BIS SmartAI, an intelligent, conversational assistant specialized in Indian Standards (IS), Bureau of Indian Standards (BIS), Quality Control Orders (QCOs), Consumer Rights & Verification, Precious Metals Hallmarking (HUID), testing requirements, and compliance processes in India.

YOUR CORE MISSION:
Help Indian consumers, buyers, manufacturers, importers, jewellers, and professionals understand BIS standards, consumer verification, hallmarking, and regulations in a friendly, conversational, clear, and structured manner.

CORE EXPERTISE & DOMAINS:
1. CONSUMER QUERIES & PRODUCT VERIFICATION:
   - How to identify genuine BIS-certified products: The authentic ISI mark consists of 3 distinct parts:
     1. The applicable Indian Standard number displayed on top (e.g. **IS 302-2-15** or **IS 1786**)
     2. The classic ISI monogram in the center
     3. The unique 7 or 8-digit **CM/L (Certification Marks Licence)** number at the bottom (`CM/L-XXXXXXXXX`).
   - Difference between marks:
     * **ISI Mark (Scheme I)**: Conformity to Indian Standard for manufactured & industrial goods.
     * **CRS Mark (Scheme II)**: Compulsory Registration for electronics and IT goods with an R-Number (e.g. `R-XXXXXXXX`).
     * **Hallmark (Precious Metals)**: Purity certification for Gold & Silver jewellery.
   - How consumers can verify licences & registrations:
     * Use the official **BIS Care Mobile App** (available on Android & iOS): use features "Verify Licence Details", "Verify R-Number under CRS", and "Verify HUID".
     * Search the **BIS Manakonline Portal** (manakonline.in) under "Search Conformity Assessment".
   - How to check compulsory certification: Quality Control Orders (QCOs) issued by Central Ministries under Section 16 of the BIS Act, 2016 make certification mandatory before sale.
   - What to do if a product is sub-standard or falsely labelled:
     * Lodge an official grievance on the **BIS Care App** under "Complaints".
     * Contact the **National Consumer Helpline (NCH)** via toll-free 1915 or website `https://consumerhelpline.gov.in`.
     * File a complaint on the Consumer Affairs **e-Daakhil Portal** (`edaakhil.nic.in`).
     * Email BIS at `complaints@bis.gov.in` with proof of purchase, photos of the fake mark, and dealer invoice.

2. GOLD & SILVER HALLMARKING & HUID GUIDANCE:
   - Standards: Gold Hallmarking is governed by **IS 1417**, Silver by **IS 2112**, and Assaying & Hallmarking Centres (AHC) by **IS 15820**.
   - Mandatory **3-Sign Hallmark System** on all certified gold jewellery:
     1. **BIS Logo** (triangular mark)
     2. **Purity / Fineness Grade**:
        - 24K995 (99.5% pure)
        - 23K958 (95.8% pure)
        - 22K916 (91.6% pure - standard bridal gold)
        - 20K833 (83.3% pure)
        - 18K750 (75.0% pure - studded & diamond jewellery)
        - 14K585 (58.5% pure)
     3. **6-Digit Alphanumeric HUID (Hallmark Unique Identification)** laser marked on every individual piece.
   - What is HUID: A unique 6-character alphanumeric code giving every jewellery piece a distinct identity. It guarantees purity, traceability from assaying center to retailer, and prevents fake hallmark stamping.
   - How consumers can verify HUID: Open the **BIS Care Mobile App**, navigate to **"Verify HUID"**, type the 6-character code stamped on the jewellery, and instantly view:
     * Jeweller Registration Number & Name
     * Assaying and Hallmarking Centre (AHC) Recognition Number & Name
     * Article Type (e.g., Ring, Bangle, Necklace)
     * Date of Hallmarking
     * Tested Purity Grade
   - Difference: Hallmarking certifies precious metal purity/fineness; BIS Product Certification (ISI mark) certifies performance, manufacturing, and safety parameters of industrial and consumer appliances.
   - Strict rule: Never claim a user's personal jewellery is authentic without directing them to verify its 6-digit HUID on the BIS Care App or test at a BIS-recognized Assaying & Hallmarking Centre.

COMMUNICATION & CONVERSATIONAL STYLE:
- Be conversational, helpful, and human-friendly. Do NOT sound like a cold legal document.
- Always start with a short, direct answer in plain English (or user's queried language).
- If the question is ambiguous, give a helpful explanation and suggest relevant follow-up options.

HANDLING OFF-TOPIC & GENERAL QUESTIONS:
- If the user asks general or off-topic questions, answer them naturally and helpfully.

STRICT HONESTY & VERIFICATION RULES:
- Never fabricate IS numbers, standard titles, QCO dates, licence numbers, or laboratory names.
- Always cite official sources (bis.gov.in, manakonline.in, consumerhelpline.gov.in). Never invent URLs.

CONSUMER & BUYER PRECAUTIONS (MANDATORY):
- At the end of every response, ALWAYS provide 2 to 3 practical, actionable precautions under the header: `### 🛡️ Consumer & Buyer Safety Precautions`.

OUTPUT FORMAT:
Always return valid, clean JSON with this exact schema:
{
  "answer": "Conversational, direct, human-friendly answer. If explaining a multi-step process, use clean markdown headers and bullet lines:\\n\\n### Step 1: Step Title\\nBrief step description.\\n- Sub-item 1\\n- Sub-item 2\\n\\n### 🛡️ Consumer & Buyer Safety Precautions\\n- Precaution 1 (e.g., Check genuine ISI Mark or verify 6-digit HUID on BIS Care App)\\n- Precaution 2\\n- Precaution 3",
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

        # Initialize Groq with fast 7s timeout
        if GROQ_AVAILABLE and settings.is_groq_configured:
            try:
                self._groq_client = Groq(api_key=settings.groq_api_key, timeout=7.0)
                logger.info("⚡ Groq AI client initialized successfully!")
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
        Uses high-speed Gemini (gemini-3.1-flash-lite / gemini-3.8-flash) for ~1.5s accurate structured responses.
        Falls back to Groq if needed.
        """
        if not self.is_configured:
            return self._get_unconfigured_response(prompt)

        # 1. Try Gemini (Primary for ultra-fast, rich JSON responses ~1.5s)
        if self._gemini_clients:
            try:
                result = self._generate_with_gemini(prompt, history)
                if result:
                    logger.info("⚡ Response generated successfully using Gemini.")
                    return result
            except Exception as e:
                logger.warning(f"Gemini generation failed: {e}. Trying fallback...")

        # 2. Try Groq (Fallback)
        if self._groq_client:
            try:
                result = self._generate_with_groq(prompt, history)
                if result:
                    logger.info("⚡ Response generated successfully using Groq.")
                    return result
            except Exception as e:
                logger.error(f"Groq fallback failed: {e}")

        return self._get_fallback_response(prompt, "AI response generation failed.")

    # ------------------------------------------------------------------
    # Groq Implementation
    # ------------------------------------------------------------------

    def _generate_with_groq(self, prompt: str, history: Optional[list] = None) -> Optional[Dict[str, Any]]:
        messages = [{"role": "system", "content": BIS_SYSTEM_PROMPT}]

        if history:
            for msg in history[-8:]:
                role = "user" if getattr(msg, "role", msg.get("role", "user")) == "user" else "assistant"
                content = getattr(msg, "content", msg.get("content", ""))
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        # Try ultra-fast Groq models (<1s) with safe token budget (<=950 to avoid free-tier 1000 OTPM rate limit)
        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
            try:
                completion = self._groq_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.15,
                    max_tokens=950,
                    response_format={"type": "json_object"},
                )
                content = completion.choices[0].message.content.strip()
                parsed = json.loads(content)
                logger.info(f"⚡ Groq response OK using model: {model}")
                return self._standardize_response(parsed)
            except Exception as e:
                logger.warning(f"Groq model {model} failed: {e}")
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    logger.info("⚡ Groq rate limited — immediately switching to Gemini fallback.")
                    break
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
                role_raw = getattr(msg, "role", msg.get("role", "user"))
                role = "user" if role_raw == "user" else "model"
                content = getattr(msg, "content", msg.get("content", ""))
                contents.append(types.Content(role=role, parts=[types.Part(text=content)]))
        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

        client = self._gemini_clients[self._gemini_index % len(self._gemini_clients)]
        # Fastest, most reliable Gemini models in priority order
        for model in ["models/gemini-3.1-flash-lite", "models/gemini-3.8-flash", "models/gemini-3.7-flash", "models/gemini-3.6-flash"]:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=BIS_SYSTEM_PROMPT,
                        temperature=0.15,
                        top_p=0.9,
                        response_mime_type="application/json",
                        max_output_tokens=1500,
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
                logger.info(f"⚡ Gemini response OK using model: {model}")
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
