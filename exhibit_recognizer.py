"""
ContextAR - Exhibit Recognizer
Sends a camera frame (or image file) to GPT-4o Vision and returns
structured information about the exhibit shown.
"""

import base64
import json
import logging
import os

import cv2
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key)

SYSTEM_PROMPT = """You are a visual recognition assistant for MuseXR, a museum AR system.

Your task: determine whether the image shows one of the twelve specific sculptures below.
Each entry lists visual features that MUST ALL be present to confirm a match.

1. Winged Victory of Samothrace
   MUST HAVE: large stone wings, headless female figure, standing on a ship's prow

2. Venus de Milo
   MUST HAVE: both arms completely missing, female nude torso, heavy draped fabric below waist

3. Cupid and Psyche
   MUST HAVE: two figures, one with wings, both reclining and embracing, faces very close

4. The Borghese Gladiator
   MUST HAVE: fully nude male, extreme diagonal lunge pose, one arm thrust upward, no weapon visible

5. The Dying Slave
   MUST HAVE: tall standing male, one arm raised behind the head, eyes closed or downcast, rough unfinished stone at the base

6. The Seated Scribe
   MUST HAVE: cross-legged seated male figure, scroll or flat surface across lap, Egyptian style, small scale

7. Bastet Cat Statue
   MUST HAVE: an upright seated cat, Egyptian bronze, small scale (under 50 cm)

8. Air (Maillol)
   MUST HAVE: nude female figure oriented horizontally as if floating, arms extended above the head

9. Miles Franklin Statue
   MUST HAVE: standing woman in early 20th-century dress and wide-brimmed hat, pale white/cream stone (NOT bronze), closed parasol held at her side, raised dark plinth, outdoor street setting

10. La Nuit (Night)
    MUST HAVE: compact bronze female figure seated on the ground, knees drawn up to chest, head bowed and buried in folded arms, no face visible

11. L'Hommage à Cézanne
    MUST HAVE: bronze or lead female figure in semi-reclining pose, upper body slightly raised, one arm resting on a bent knee, legs extended, outdoor garden setting

12. La Siesta
    MUST HAVE: marble reclining female figure lying on her side, fully horizontal, head resting on a pillow, draped fabric, indoor museum setting

RULES:
- Every listed MUST HAVE feature must be clearly visible before you return that sculpture's name.
- If even one required feature is absent or unclear, return "unknown".
- Generic statues, unidentified figures, people, buildings, or anything not matching the criteria above: return "unknown".
- Do NOT choose the closest match. Either it matches all criteria or it is "unknown".

Respond ONLY in this exact JSON format (no markdown, no extra text):
{
  "name": "exact sculpture name from the list above, or 'unknown'",
  "type": "sculpture",
  "period": "time period or era",
  "brief": "one sentence description suitable for a museum visitor",
  "confidence": "high | medium | low"
}"""


def _encode_image(image: np.ndarray) -> str:
    """Encode a BGR OpenCV frame to base64 JPEG string."""
    _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


def _encode_file(image_path: str) -> str:
    """Encode an image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def recognize_exhibit(image: np.ndarray | str, detail: str = "low") -> dict:
    """
    Identify the exhibit in an image using GPT-4o Vision.

    Args:
        image: BGR numpy array (from cv2) or path to an image file
        detail: "low" (faster, cheaper) or "high" (better for detailed artifacts)

    Returns:
        {
            "name": str,
            "type": str,
            "period": str,
            "brief": str,
            "confidence": str
        }
        On failure, returns a dict with "error" key.
    """
    if isinstance(image, str):
        b64 = _encode_file(image)
    else:
        b64 = _encode_image(image)

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": detail,
                            },
                        },
                        {
                            "type": "text",
                            "text": "What exhibit is shown in this image?",
                        },
                    ],
                },
            ],
            max_tokens=300,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].removeprefix("json").strip()
        return json.loads(raw)

    except json.JSONDecodeError:
        logger.warning("vision_invalid_response", extra={"raw": raw})
        return {"error": "invalid_response", "raw": raw}
    except Exception as e:
        logger.exception("vision_call_failed")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Standalone demo — captures one frame from webcam and identifies it
# ---------------------------------------------------------------------------

def run():
    print("ContextAR - Exhibit Recognizer")
    print("Press SPACE to capture and identify | Q to quit\n")

    cap = cv2.VideoCapture(0)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        cv2.putText(frame, "SPACE: identify  |  Q: quit", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        cv2.imshow("ContextAR - Exhibit Recognizer", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord(' '):
            print("Sending to GPT-4o Vision...")
            result = recognize_exhibit(frame)
            if "error" in result:
                print(f"Error: {result}")
            else:
                print(f"\n  Exhibit : {result['name']}")
                print(f"  Type    : {result['type']}")
                print(f"  Period  : {result['period']}")
                print(f"  Info    : {result['brief']}")
                print(f"  Confidence: {result['confidence']}\n")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
