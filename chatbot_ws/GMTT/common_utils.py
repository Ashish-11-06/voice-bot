import os
import json
import re
import random
import logging
from datetime import datetime
from fuzzywuzzy import fuzz
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import spacy
import requests
from urllib.parse import urljoin, urldefrag
import traceback

nlp = spacy.load("en_core_web_sm")
sentiment_analyzer = SentimentIntensityAnalyzer()
MISTRAL_API_KEYS = ["3OyOnjAypy79EewldzfcBczW01mET0fM", "tZKRscT6hDUurE5B7ex5j657ZZQDQw3P", "dvXrS6kbeYxqBGXR35WzM0zMs4Nrbco2", "5jMPffjLAwLyyuj6ZwFHhbLZxb2TyfUR"]

def call_mistral_model(prompt: str, max_tokens: int = 100) -> str:
    url = "https://api.mistral.ai/v1/chat/completions"
    payload = {"model": "mistral-medium", "messages": [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}], "temperature": 0.5, "max_tokens": max_tokens}
    for api_key in MISTRAL_API_KEYS:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        logging.debug(f"Using API Key: {api_key}")
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content'].strip()
            else:
                logging.error(f"API Key {api_key} failed: {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"Exception with API Key {api_key}: {e}")
    return "I'm having trouble accessing information right now. Please try again later."

def is_mistral_follow_up(bot_message: str) -> bool:
    prompt = f"""
Determine if the following chatbot message is a follow-up question.
Definition:
A follow-up question encourages the user to respond with interest or elaboration.
Examples: "Would you like to know more?", "Shall I explain further?"
Chatbot message:
"{bot_message}"
Answer only with "YES" or "NO".
"""
    try:
        response = call_mistral_model(prompt).strip().upper()
        return response.startswith("YES")
    except Exception as e:
        logging.error(f"Failed follow-up check: {e}")
        return False

def load_json_data(file_path: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading {file_path}: {e}")
        return {}

def load_session_history(file_path: str):
    return load_json_data(file_path) if os.path.exists(file_path) else []

def save_session_history(file_path: str, history: list):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history[-5:], f, indent=2)
    except Exception as e:
        logging.error(f"Error saving session history: {e}")

def load_knowledge_base(file_path: str):
    print("load_knowledge_base() called from:")
    traceback.print_stack(limit=2)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            intents = data.get('faqs', {}).get('intents', [])
            return [{ 'tag': item.get('tag'), 'patterns': [k.lower() for k in item.get('patterns', [])], 'response': item.get('response', []), 'follow_up': item.get('follow_up', ''), 'next_suggestions': item.get('next_suggestions', []) } for item in intents]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading knowledge base {file_path}: {e}")
        return []

def search_knowledge_block(user_query: str, knowledge_base: list):
    user_query = user_query.lower().strip()

    # 1. Exact match
    for entry in knowledge_base:
        patterns = [p.lower() for p in entry.get("patterns", [])]
        if user_query in patterns:
            return entry

    # 2. Substring match
    for entry in knowledge_base:
        patterns = [p.lower() for p in entry.get("patterns", [])]
        if any(p in user_query for p in patterns):
            return entry

    # 3. Fuzzy match
    best_match, best_score = None, 0
    for entry in knowledge_base:
        for pattern in entry.get("patterns", []):
            score = fuzz.token_set_ratio(user_query, pattern.lower())
            if score > best_score:
                best_match, best_score = entry, score

    # Apply threshold
    if best_score >= 75:
        return best_match

    return None

def generate_nlp_response(msg: str, bot_name="infi"):
    msg_lower = msg.lower()
    if any(g in msg_lower for g in ["hi", "hello", "hey", "hii"]):
        return f"Hello! I'm {bot_name}. How can I help you today?"
    if "how are you" in msg_lower:
        return "I'm doing great, thanks for asking!"
    if msg_lower in ["great", "good", "awesome"]:
        return "Glad to hear that!"
    if "thank" in msg_lower:
        return "You're welcome!"
    if any(kw in msg_lower for kw in ["bye", "exit"]):
        return "Goodbye! Have a great day!"
    return None

CONVERSATION_PROMPTS = { 'intro': [ "Would you like to know about our current plantation projects?", "I can tell you about our volunteer opportunities if you're interested?", "Shall I share some success stories from our recent initiatives?" ], 'mid': [ "What aspect interests you most - our methodology, impact, or how to get involved?", "Would you like details about any specific region we work in?", "I could also share some interesting facts about Peepal trees if you'd like?" ], 'closing': [ "Before we wrap up, is there anything else you'd like to know?", "Would you like me to send you more information via email?", "Shall I connect you with our volunteer coordinator?" ] }

def get_conversation_driver(history, stage):
    if len(history) < 2:
        return random.choice(CONVERSATION_PROMPTS['intro'])
    last_question = history[-1]["user"].lower()
    if any(kw in last_question for kw in ["thank", "bye", "enough"]):
        return random.choice(CONVERSATION_PROMPTS['closing'])
    if len(history) > 4:
        return random.choice(CONVERSATION_PROMPTS['mid'])
    context_keywords = ["plant", "tree", "volunteer", "donat", "project"]
    for kw in context_keywords:
        if kw in last_question:
            return f"Would you like more details about our {kw} programs?"
    return random.choice(CONVERSATION_PROMPTS['mid'])
