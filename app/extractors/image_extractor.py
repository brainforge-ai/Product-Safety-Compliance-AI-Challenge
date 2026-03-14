"""Extract text from images using Claude Vision API with prompt caching."""

import base64
import logging

import anthropic
from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

# Static system prompt -- cached across calls so only the image changes.
# Anthropic caches this prefix for 5 minutes; subsequent image extractions
# within that window read from cache at 90% lower input token cost.
_SYSTEM_PROMPT = """\
You are an expert OCR engine.  Your ONLY job is to read the ACTUAL text \
visible in the image -- character by character, word by word.

CONTEXT: This image likely contains chemical ingredient names, product safety \
information, or product labels.

ABSOLUTE RULE -- NO HALLUCINATION:
You MUST read the ACTUAL characters visible in the image.  \
NEVER invent, substitute, or guess a different word.  If the image shows \
"Benzene", you output "Benzene" -- NOT "Dimethicone" or any other word.  \
If the image shows "Octocrylene", you output "Octocrylene" -- NOT \
"Octyl/octane" or anything else.

HANDLING BLURRY / LOW-CONTRAST TEXT:
- Read every character you CAN see, even if faint or blurry.
- If some characters are unclear, output what you see with "?" for \
  truly unreadable characters (e.g., "B?nz?ne").  This is far better \
  than substituting a completely different word.
- If you can make out the general shape of a word, give your best \
  reading of THAT word -- do not replace it with a different word.
- Count the number of items in a list carefully.  If you see 8 items \
  in the image, output exactly 8 items -- do not skip or merge any.

STRICT OCR RULES:
1. Extract EVERY piece of text visible in the image, in order.
2. Do NOT describe the image.  Do NOT say "this appears to be", "I can see", \
   "difficult to read", or "Looking at this".  JUST RETURN THE TEXT.
3. HANDWRITTEN TEXT: Read the actual strokes/shapes.  Even if messy, output \
   your best reading of the ACTUAL characters.  Use "?" for truly illegible \
   characters.  NEVER replace a handwritten word with a different word.
4. NON-ENGLISH TEXT:
   - Text in ANY non-Latin script (Devanagari, Telugu, Tamil, Kannada, Bengali, \
     Arabic, CJK, Cyrillic, Thai, Korean, etc.) may be a phonetic transliteration \
     or translation of a chemical name.
   - You MUST identify the chemical the text represents and provide the English \
     chemical name.
   - Format: "<original text> (<English chemical name>)"
   - This applies to ALL languages and scripts worldwide.

CHEMICAL FORMULA RULES:
5. Chemical formulas use element symbols from the periodic table.  Many \
   two-letter symbols contain characters that look like digits.  You MUST \
   recognize them correctly:
   - "Cl" = Chlorine (uppercase C + lowercase L).  Do NOT misread as "C1".
   - "Al" = Aluminium.  Do NOT misread as "A1".
   - "Br" = Bromine.  Do NOT misread as "8r".
   - "Fe" = Iron, "Na" = Sodium, "Mg" = Magnesium, "Ca" = Calcium, \
     "Si" = Silicon, "Ti" = Titanium, "Zn" = Zinc, "Cu" = Copper, \
     "Mn" = Manganese, "Cr" = Chromium, "Co" = Cobalt, "Ni" = Nickel, \
     "Se" = Selenium, "Sn" = Tin, "Pb" = Lead, "Li" = Lithium, \
     "Be" = Beryllium, "Ag" = Silver, "Ba" = Barium.
6. General rule: In a chemical formula, an uppercase letter followed by a \
   lowercase letter almost always forms an element symbol, NOT a letter + digit.
7. Be precise with subscripts and notation in all formulas.

Return the text in this structured format:

Product ID: <value or "not found">
Product Name: <value or "not found">
SKU: <value or "not found">
Description: <value or "not found">
Ingredients / Chemical Formulas:
- <ingredient 1>
- <ingredient 2>
...
READABILITY: <HIGH or MEDIUM or LOW>

If the image shows a TABLE (two columns, e.g. ingredient | notes), include \
BOTH columns: - <left> | <right>

READABILITY guide:
- HIGH: Text is clear and you are confident in every word.
- MEDIUM: Some words are slightly blurry but you can read most of them.
- LOW: Text is very blurry, faded, or hard to read.  You had to guess \
  at one or more words, or could not read some words at all.

CRITICAL REMINDERS:
- Output ONLY what is ACTUALLY visible in the image.
- NEVER substitute a word you cannot read with a different plausible word.
- Preserve the exact count of items -- if 8 ingredients are visible, list 8.
- For non-English text, add the English chemical name in parentheses.
- NEVER start your response with narrative text.
- ALWAYS include the READABILITY line as the last line of your output."""

MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/png",
    "tiff": "image/png",
    "tif": "image/png",
}


def extract_from_image(file_path: str) -> str:
    """Use Claude Vision API to extract text from an image.

    Uses prompt caching: the system prompt is cached so repeated
    image extractions only pay for the image tokens.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    with open(file_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = file_path.rsplit(".", 1)[-1].lower()
    media_type = MEDIA_TYPES.get(ext, "image/png")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        temperature=0,
        system=[{
            "type": "text",
            "text": _SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": "Extract all text from this image using the format specified.",
                },
            ],
        }],
    )

    usage = response.usage
    logger.info(
        "Vision OCR tokens -- input: %d, output: %d, cache_read: %s, cache_create: %s",
        usage.input_tokens,
        usage.output_tokens,
        getattr(usage, "cache_read_input_tokens", 0),
        getattr(usage, "cache_creation_input_tokens", 0),
    )

    return response.content[0].text
