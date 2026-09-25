# 💊 Prescription Reader

**Prescription Reader** is a full-stack web application designed to help patients understand handwritten or printed doctor prescriptions in plain, simple language.

Instead of relying on classic OCR (which struggles with medical handwriting and abbreviations), it leverages the **Google Gemini Multimodal API (`gemini-2.0-flash`)** to visually analyze prescription photos and reason through drug names, dosages, and doctor notes.

---

## ✨ Features

- **Multimodal Handwriting Recognition**: Sends prescription images directly to Gemini 2.0 Flash to decipher doctor handwriting and cursive notation.
- **Drug Knowledge Correction**: Employs pharmacological intelligence to correct common handwriting and OCR misreads into authentic medication names.
- **Safety First (Strict Illegibility Handling)**: If a medicine name, dosage, or frequency is unreadable or ambiguous, it refuses to hallucinate and labels the field `"unclear — please confirm with your pharmacist"`.
- **Plain-Language Summary**: Generates a comforting, one-paragraph overview explaining what the medications treat and how to manage the daily routine.
- **Structured Medicine Cards**: Breaks down every prescription item into clean, color-coded badges for **Dosage**, **Frequency**, **Duration**, and **Special Instructions**.
- **Prominent Medical Disclaimer**: Reminds patients prominently that the tool is an AI reading aid, not medical advice.
- **Quota & Busy Handling**: Intercepts HTTP 429 and Gemini rate-limit errors gracefully with a user-friendly message (*"Service is temporarily busy, please try again in a minute"*).
- **One-Click Sample Prescription**: Built-in test prescription image to demo the flow end-to-end with a single click.
- **Clean Single Page**: Mobile-friendly, drag-and-drop file upload, printable instructions, zero external JS framework dependencies.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12+, FastAPI, Uvicorn, Google GenAI SDK (`google-genai`), Python-dotenv, Pillow
- **Frontend**: Plain HTML5, CSS3, Vanilla JavaScript (Single Page)
- **Model**: `gemini-2.0-flash` (Multimodal Vision)

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.10+ installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Gemini API Key
Create a `.env` file in the project root (you can copy `.env.example`):
```bash
cp .env.example .env
```
Open `.env` and add your Google Gemini API key:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```
*(You can obtain a free API key at [Google AI Studio](https://aistudio.google.com/app/apikey))*

### 4. Run the Application
Start the FastAPI server using Uvicorn:
```bash
uvicorn main:app --reload --port 8000
```

### 5. Open in Your Browser
Open your browser and navigate to:
```
http://localhost:8000
```

---

## 🧪 Testing the Application

1. Click **"Try with Sample Prescription"** on the web page to load the bundled realistic prescription image.
2. Click **"Interpret Prescription"**.
3. View the patient summary and structured medicine cards.
4. Try uploading your own doctor prescription image (drag-and-drop or file picker) in JPG, PNG, or WEBP format.

---

## 📁 Project Structure

```
maj_proj/
├── main.py                  # FastAPI server, Gemini multimodal API endpoint & error handlers
├── requirements.txt         # Python package dependencies
├── .env.example             # Template for GEMINI_API_KEY
├── .gitignore               # Excludes .env, caches, and virtual envs
├── README.md                # Documentation and run instructions
└── static/
    ├── index.html           # Accessible single-page frontend with disclaimer & cards
    ├── style.css            # Modern healthcare-inspired design system
    ├── script.js            # Drag-and-drop, API integration, and dynamic DOM rendering
    └── sample_prescription.png  # Bundled sample prescription asset
```

---

## ⚠️ Medical Notice
> **Disclaimer**: This application is an AI-assisted reading aid and does NOT provide medical advice, diagnosis, or treatment. Always verify prescription details and medication instructions with a qualified doctor or licensed pharmacist before consumption.
