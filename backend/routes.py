from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
import os
import requests
import json
import google.generativeai as genai
import assemblyai as aai
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

router = APIRouter()

# 1. CONFIGURE GOOGLE GEMINI (The Brain)
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
# Use the model that supports JSON output well
model = genai.GenerativeModel('gemini-2.0-flash')

# Define the Empty State
DEFAULT_ORDER_STATE = {
    "drinkType": None,
    "size": None,
    "milk": None,
    "extras": [],
    "name": None,
    "is_complete": False
}

@router.get("/health")
async def health_check():
    return HTMLResponse(content="<h1>Barista Agent Running ☕</h1>", status_code=200)

@router.post("/server")
async def server(request: dict):
    # Simple TTS endpoint for the greeting
    MURF_API_KEY = os.getenv('MURF_AI_API_KEY')
    endpoint = "https://api.murf.ai/v1/speech/generate"
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    data = {
        "text": request.get("text"),
        "voice_id": "en-UK-ruby", 
        "style": "Conversational", 
        "multiNativeLocale": "en-US"
    }
    try:
        response = requests.post(endpoint, headers=headers, data=json.dumps(data))
        return JSONResponse(content={"audioUrl": response.json().get('audioFile')}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# --- MAIN BARISTA LOGIC ---
@router.post("/chat-with-voice")
async def chat_with_voice(
    file: UploadFile = File(...), 
    current_state: str = Form(...)  # Receive state as a JSON string
):
    try:
        # A. SETUP & PARSE STATE
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
        murf_api_key = os.getenv('MURF_AI_API_KEY')
        
        # Parse the incoming state string back into a Python Dictionary
        try:
            state_dict = json.loads(current_state)
        except:
            state_dict = DEFAULT_ORDER_STATE

        # B. LISTEN (Transcribe)
        print("🎧 Transcribing...")
        audio_data = await file.read()
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)
        user_text = transcript.text
        
        if not user_text:
             return JSONResponse(content={"error": "No speech detected"}, status_code=400)

        print(f"🗣️ User: {user_text}")
        print(f"☕ Current State: {state_dict}")

        # C. THINK (Gemini as Barista)
        # We give Gemini strict instructions to output ONLY JSON
        system_prompt = f"""
        You are a friendly Starbucks Barista. Your goal is to take a complete coffee order.
        
        Current Order State: {json.dumps(state_dict)}
        
        User just said: "{user_text}"
        
        1. Update the 'drinkType', 'size', 'milk', 'extras', and 'name' based on what the user said.
        2. If 'extras' are mentioned, add them to the list.
        3. If fields are missing (None), politely ask for them.
        4. If all fields are filled, set 'is_complete' to true and confirm the full order.
        5. Keep your 'reply' short, friendly, and conversational (max 2 sentences).
        
        Respond ONLY in this JSON format:
        {{
            "updated_state": {{
                "drinkType": "string or null",
                "size": "string or null",
                "milk": "string or null",
                "extras": ["string"],
                "name": "string or null",
                "is_complete": boolean
            }},
            "reply": "Your response text here"
        }}
        """

        # Generate response in JSON mode
        result = model.generate_content(
            system_prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Parse Gemini's response
        ai_response = json.loads(result.text)
        updated_state = ai_response["updated_state"]
        barista_reply = ai_response["reply"]

        print(f"🤖 Barista: {barista_reply}")

        # D. SAVE IF COMPLETE
        if updated_state.get("is_complete"):
            order_entry = {
                "timestamp": datetime.now().isoformat(),
                "order": updated_state
            }
            # Append to a local file
            with open("completed_orders.json", "a") as f:
                f.write(json.dumps(order_entry) + "\n")
            print("✅ Order Saved to completed_orders.json")

        # E. SPEAK (Murf AI)
        murf_url = "https://api.murf.ai/v1/speech/generate"
        murf_headers = {"api-key": murf_api_key, "Content-Type": "application/json"}
        murf_data = {
            "text": barista_reply,
            "voice_id": "en-UK-ruby", 
            "style": "Conversational",
            "multiNativeLocale": "en-US"
        }
        
        murf_res = requests.post(murf_url, headers=murf_headers, data=json.dumps(murf_data))
        audio_url = murf_res.json().get('audioFile')

        # F. RETURN EVERYTHING
        return {
            "user_transcript": user_text,
            "ai_text": barista_reply,
            "audio_url": audio_url,
            "updated_state": updated_state # Send new state back to frontend
        }

    except Exception as e:
        print(f"Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})