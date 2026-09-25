import io
import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Optional

from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Cache client instances to reuse connection pools and avoid SSL re-handshake
_client_cache = {}

def get_genai_client(api_key: str):
    if api_key not in _client_cache:
        from google import genai
        _client_cache[api_key] = genai.Client(api_key=api_key)
    return _client_cache[api_key]

# Load environment variables from .env
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prescription_reader")

# Base directory paths (supports both normal python and PyInstaller frozen executables)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Prescription Reader API",
    description="Multimodal AI-assisted doctor prescription reader and translator",
    version="1.0.0"
)

# Enable CORS for convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# --- Pydantic Data Models ---

class MedicineItem(BaseModel):
    name: str = Field(
        ...,
        description="Brand or generic name of the medicine (e.g. 'Amoxicillin'). If handwriting is difficult, provide the most likely medication based on pharmacological context."
    )
    dosage: str = Field(
        ...,
        description="Dose amount and formulation (e.g. '500 mg capsule'). Never leave blank; provide the visible or standard clinical dosage."
    )
    frequency: str = Field(
        ...,
        description="How often to take the medication translated into plain English (e.g. 'Twice daily after meals'). Never leave blank."
    )
    duration: str = Field(
        ...,
        description="Duration of treatment (e.g. '7 days (complete entire course)', 'As needed'). Never leave blank; indicate standard duration if not explicitly written."
    )
    instructions: str = Field(
        ...,
        description="Special usage directions and practical patient precautions (e.g. 'Take with meals and plenty of water'). Never leave blank."
    )


class PrescriptionAnalysis(BaseModel):
    summary: str = Field(
        ...,
        description="A plain-language, non-medical one-paragraph summary of what the prescription contains, what it is typically prescribed for, and how the patient should take them."
    )
    medicines: List[MedicineItem] = Field(
        default_factory=list,
        description="List of identified medications and their schedules"
    )
    disclaimer: str = Field(
        default="This is an AI-assisted reading aid, not medical advice. Always confirm your prescription with your doctor or pharmacist before taking any medication.",
        description="Mandatory patient safety disclaimer"
    )


PRESCRIPTION_PROMPT = """
You are an expert clinical pharmacist and advanced medical transcription specialist.
Analyze this doctor's prescription image (handwritten, cursive, or printed) and thoroughly extract and explain all medication information so a patient can clearly and fully understand their treatment.

CRITICAL INSTRUCTIONS:
1. INTELLIGENT CLINICAL ANALYSIS (DO NOT LEAVE BLANKS):
   - Never leave any field empty, blank, or merely "unclear".
   - Thoroughly decipher the handwriting. Even if handwriting is messy, rushed, partially faint, or cursive, use your extensive pharmacological knowledge, common prescription patterns, brand/generic drug naming, and medical context (diagnosis, clinical notes, doctor specialty) to deduce the intended medications.
   - If a specific detail (such as dosage, exact duration, or frequency) is abbreviated or partially obscured on the prescription slip, analyze standard medical guidelines and typical prescribing regimens for that specific drug and condition to provide the most likely, recommended information (e.g. "500 mg (typical standard dose)", "Twice daily after meals", "7 days (standard antibiotic course; confirm with pharmacist)").

2. FOR EACH PRESCRIBED MEDICATION, EXTRACT:
   - name: The brand or generic medicine name (e.g., "Amoxicillin", "Ibuprofen").
   - dosage: Strength and formulation (e.g., "500 mg capsule", "10 ml syrup"). Provide the deduced standard strength if handwriting is faint.
   - frequency: Clear schedule in plain English (e.g., "Three times daily (every 8 hours)", "Once daily at bedtime"). Explain medical shorthand like 'tid', 'bid', 'od', 'prn'.
   - duration: How long to take the medicine (e.g., "7 days (finish full course)", "14 days", "As needed for pain"). If not explicitly written, provide the typical clinical duration.
   - instructions: Clear, practical patient instructions (e.g., "Take after food with plenty of water", "Take 30 minutes before breakfast", "Avoid alcohol while taking this medicine").

3. PATIENT-FRIENDLY ONE-PARAGRAPH SUMMARY:
   - Provide a warm, reassuring, plain-language one-paragraph summary in simple everyday language.
   - Explain what condition these medications are likely treating together, how the patient should organize their daily routine, and important general precautions.

4. STRUCTURED OUTPUT:
   - Return strictly valid JSON adhering to the specified schema with 'summary', 'medicines', and 'disclaimer'.
"""


@app.get("/api/health")
async def health_check():
    load_dotenv(override=True)
    api_key_set = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "status": "healthy",
        "gemini_api_key_configured": api_key_set
    }


@app.get("/api/sample-prescription")
async def get_sample_prescription():
    """Serves the bundled sample prescription image for one-click testing."""
    sample_path = STATIC_DIR / "sample_prescription.png"
    if not sample_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample prescription image not found."
        )
    return FileResponse(
        sample_path,
        media_type="image/png",
        filename="sample_prescription.png"
    )


@app.post("/api/analyze")
async def analyze_prescription(file: UploadFile = File(...)):
    """
    Accepts an uploaded prescription image, analyzes it using Gemini 2.0 multimodal vision,
    and returns structured medicine details and plain-language summary.
    """
    # 1. Check Gemini API Key (reload from .env in case it was updated)
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GEMINI_API_KEY is not configured. Please set your valid Gemini API key in the .env file."
        )

    # 2. Validate uploaded file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file selected."
        )

    content_type = file.content_type or ""
    valid_types = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"]
    
    # Read file content
    try:
        image_bytes = await file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read the uploaded image file."
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )

    # 15 MB limit
    if len(image_bytes) > 15 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image size exceeds the 15 MB limit. Please upload a smaller image."
        )

    # Fast image validation & preprocessing
    # Verifies file integrity, handles all Pillow color modes (LA, RGBA, P, CMYK, etc.),
    # and optimizes resolution to 1600px for high-precision cursive handwriting deciphering.
    try:
        with Image.open(io.BytesIO(image_bytes)) as pil_img:
            if pil_img.width > 1600 or pil_img.height > 1600:
                pil_img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=85, optimize=True)
            image_bytes = buf.getvalue()
            content_type = "image/jpeg"
    except Exception as img_err:
        logger.warning(f"Image validation/processing failed: {img_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid or readable image. Please upload a clear JPG, PNG, or WEBP photo."
        )

    # 3. Call Vision API
    try:
        from google.genai import types
        import asyncio

        client = get_genai_client(api_key)

        # Active working models prioritized by latency and available quota
        candidate_models = [
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite-preview",
            "gemini-3-flash-preview"
        ]
        response = None
        parsed_json = None
        last_model_err = None

        # Two-pass resilient retry loop
        for attempt in range(2):
            for model_name in candidate_models:
                try:
                    logger.info(f"Attempting analysis with model: {model_name} (pass {attempt + 1})")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[
                            types.Part.from_bytes(data=image_bytes, mime_type=content_type),
                            PRESCRIPTION_PROMPT
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=PrescriptionAnalysis,
                            temperature=0.1,
                            max_output_tokens=2048
                        )
                    )
                    if response and response.text:
                        raw_text = response.text.strip()
                        if raw_text.startswith("```json"):
                            raw_text = raw_text[7:]
                        elif raw_text.startswith("```"):
                            raw_text = raw_text[3:]
                        if raw_text.endswith("```"):
                            raw_text = raw_text[:-3]
                        
                        try:
                            parsed_json = json.loads(raw_text.strip())
                            logger.info(f"Successfully received and parsed analysis from {model_name}")
                            break
                        except Exception as json_err:
                            logger.warning(f"Model {model_name} produced invalid JSON: {json_err}")
                            continue
                except Exception as m_err:
                    last_model_err = m_err
                    m_err_str = str(m_err).lower()
                    logger.warning(f"Model {model_name} pass {attempt + 1} error: {m_err}")
                    
                    # If the image itself is rejected as invalid/corrupt, fail immediately without burning quota across models
                    if "invalid_argument" in m_err_str or "unable to process input image" in m_err_str:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Unable to process the image. The file appears to be corrupted or in an unsupported format. Please try taking a clearer photo."
                        )
                    continue

            if parsed_json:
                break

            # If all candidates experienced momentary cooldown/traffic on pass 1, wait 3s before pass 2
            if attempt == 0:
                logger.info("Candidate models busy, pausing 3 seconds before automated retry...")
                await asyncio.sleep(3)

        if not parsed_json:
            raise last_model_err or RuntimeError("No compatible model succeeded in analyzing the prescription.")

        # Ensure disclaimer is always present
        if not parsed_json.get("disclaimer"):
            parsed_json["disclaimer"] = (
                "This is an AI-assisted reading aid, not medical advice. "
                "Always confirm your prescription with your doctor or pharmacist before taking any medication."
            )

        return JSONResponse(status_code=status.HTTP_200_OK, content=parsed_json)

    except HTTPException:
        # Re-raise explicit HTTP exceptions without transforming them
        raise

    except Exception as exc:
        err_msg = str(exc)
        err_lower = err_msg.lower()
        err_code = getattr(exc, "code", None)

        logger.warning(f"API exception encountered: {err_msg} (code: {err_code})")

        # Catch DNS / network offline errors specifically (Errno 11001 getaddrinfo failed, socket errors)
        is_network_err = (
            "11001" in err_lower
            or "getaddrinfo" in err_lower
            or "connecterror" in err_lower
            or "name resolution" in err_lower
            or "connection reset" in err_lower
            or "nodename nor servname" in err_lower
        )
        if is_network_err:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "Network connection error: Unable to reach the server. Please check your internet connection or Wi-Fi and try again."
                }
            )

        # Catch 429, 503, or quota/busy exhaustion specifically
        is_quota = (
            err_code in [429, 503]
            or "429" in err_lower
            or "503" in err_lower
            or "resource_exhausted" in err_lower
            or "quota" in err_lower
            or "rate limit" in err_lower
            or "too many requests" in err_lower
            or "high demand" in err_lower
            or "unavailable" in err_lower
        )

        if is_quota:
            logger.warning("Caught 429/503/quota error from vision API.")
            import re
            match = re.search(r"retry in (\d+)", err_msg, re.IGNORECASE) or re.search(r"retryDelay': '(\d+)", err_msg)
            wait_sec = int(match.group(1)) if match else 20
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Service is temporarily busy. Please wait {wait_sec} seconds before trying again.",
                    "retry_after": wait_sec
                }
            )

        # Invalid API key error
        if "api_key_invalid" in err_lower or "api key not valid" in err_lower or "unauthenticated" in err_lower or "permission_denied" in err_lower:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid or unauthorized API Key. Please verify the GEMINI_API_KEY in your .env file."
                }
            )

        # Generic error fallback
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": f"An error occurred while reading the prescription: {err_msg}"
            }
        )


# Mount static directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def serve_index():
    """Serves the frontend single page app."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Prescription Reader API is running. Frontend static/index.html not found."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
