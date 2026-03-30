import os
import uuid
from typing import Dict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from pymongo import MongoClient

from chatbot import ContextAwareChatBot

app = FastAPI(title="BBBot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to MongoDB
MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    print("Warning: MONGO_URI is not set. Please obtain a MongoDB connection string.")
    client = None
    db = None
    sessions_col = None
else:
    client = MongoClient(MONGO_URI)
    db = client["bbbot"]
    sessions_col = db["sessions"]

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chats")
async def create_new_chat():
    """ Creates a new chat session and returns its ID """
    chat_id = str(uuid.uuid4())
    if sessions_col is not None:
        sessions_col.insert_one({
            "_id": chat_id,
            "title": "New Chat",
            "history": []
        })
    return {"id": chat_id, "title": "New Chat"}

@app.get("/api/chats")
async def get_all_chats():
    """ Lists all previous chat sessions from MongoDB """
    if sessions_col is None:
        return {"chats": []}
    
    chat_list = []
    # sessions_col.find() returns a cursor
    for doc in sessions_col.find({}, {"_id": 1, "title": 1}):
        chat_list.append({"id": doc["_id"], "title": doc.get("title", "New Chat")})
    return {"chats": chat_list}

@app.get("/api/chat/{chat_id}")
async def get_chat_history(chat_id: str):
    """ Fetch the full history of a specific session """
    if sessions_col is None:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
        
    doc = sessions_col.find_one({"_id": chat_id})
    if not doc:
        return JSONResponse({"error": "Chat not found"}, status_code=404)
        
    # Temporary bot to easily calculate tokens using existing method
    temp_bot = ContextAwareChatBot(max_history_tokens=200, existing_history=doc.get("history", []))
    
    # Extract the internal history structure for the frontend
    history_out = []
    for msg in temp_bot.history:
        role = msg.get('role', 'user')
        text = msg.get('parts', [{}])[0].get('text', '')
        history_out.append({"role": role, "text": text})
        
    return {
        "id": chat_id,
        "title": doc.get("title", "New Chat"),
        "history": history_out,
        "tokens_used": temp_bot.get_history_token_count()
    }

@app.post("/api/chat/{chat_id}")
async def send_chat_message(chat_id: str, payload: ChatRequest):
    """ Send a message to a specific chat session """
    if sessions_col is None:
        return JSONResponse({"error": "Database not configured"}, status_code=500)
        
    doc = sessions_col.find_one({"_id": chat_id})
    if not doc:
        return JSONResponse({"error": "Chat not found"}, status_code=404)
        
    user_input = payload.message.strip()
    if not user_input:
        return JSONResponse({"error": "Message is empty"}, status_code=400)
        
    # Instantiate bot with loaded history
    bot = ContextAwareChatBot(max_history_tokens=200, existing_history=doc.get("history", []))
    title = doc.get("title", "New Chat")
    
    # Automatically set title to first message if it's currently 'New Chat'
    if title == "New Chat" and len(bot.history) == 0:
        title = user_input[:25] + "..." if len(user_input) > 25 else user_input
        
    response_text = bot.chat(user_input)
    
    # Save the updated history and title back to MongoDB
    sessions_col.update_one(
        {"_id": chat_id}, 
        {"$set": {
            "history": bot.history,
            "title": title
        }}
    )
    
    return {
        "reply": response_text,
        "title": title,
        "tokens_used": bot.get_history_token_count(),
        "history_length": len(bot.history)
    }

# Mount static files (HTML, CSS, JS) at root
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    print("Starting BBBot server at http://127.0.0.1:8000")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
