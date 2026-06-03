"""
ContextAR - Exhibit Recognizer
Sends a camera frame (or image file) to GPT-4o Vision and returns
structured information about the exhibit shown.
"""

import base64
import json
import os
import cv2
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are an expert museum guide AI assistant for ContextAR.
This installation covers the exhibition "Western European Paintings, 15th–20th Century"
at the Metropolitan Museum of Art. The six paintings on display are:

1. The Harvesters — Pieter Bruegel the Elder, 1565 (Flemish Renaissance landscape)
2. Young Woman with a Water Pitcher — Johannes Vermeer, c. 1662 (Dutch Golden Age interior)
3. Aristotle with a Bust of Homer — Rembrandt van Rijn, 1653 (philosopher resting hand on Homer's bust, gold chain)
4. Madame X — John Singer Sargent, 1883–84 (woman in black gown against brown background)
5. Wheat Field with Cypresses — Vincent van Gogh, 1889 (swirling Post-Impressionist landscape)
6. The Card Players — Paul Cézanne, c. 1890–95 (two peasants playing cards at a table)

When shown an image, identify which of these six paintings is visible, or respond 'unknown'
if none match. Respond ONLY in this exact JSON format (no markdown, no extra text):
{
  "name": "exact painting name from the list above, or 'unknown'",
  "type": "painting",
  "period": "time period or era, e.g. 'Dutch Golden Age, c. 1662'",
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
        response = client.chat.completions.create(
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
        return {"error": "invalid_response", "raw": raw}
    except Exception as e:
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
