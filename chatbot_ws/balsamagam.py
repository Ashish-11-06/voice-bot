import requests
import json
import os
import random
import redis
import re
from datetime import datetime

from openai import OpenAI  

class BalSamagamChatbot:
    CHAT_HISTORY_FILE = "chat_history.json"

    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True
        )
    
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.client = OpenAI(api_key=self.openai_api_key)
        
        self.history_file = self.CHAT_HISTORY_FILE
        self.all_sessions = self._load_all_sessions()

    def call_openai_api(self, user_message, conversation_history=[]):
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        for msg in conversation_history[-6:]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=300,
                temperature=0.8
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return "Dhan Nirankar Ji! 🙏 Sorry, I am having trouble answering right now. Please try again later!"

        # ...existing code...

    # English only welcome messages
    welcome_messages = [
        "🎉 Dhan Nirankar Ji! Welcome to Bal Samagam! 🎪 I'm so excited you're here, little saint! What would you like to know?",
        "🌟 Dhan Nirankar Ji! Welcome to our special Bal Samagam! 🎊 This is going to be so much fun! Ask me anything!",
        "🎈 Dhan Nirankar Ji, my dear friend! Welcome to Bal Samagam 2025! 🎭 I'm here to help you learn and have fun!"
    ]

    # English only knowledge base
    bal_samagam_knowledge = """
    BAL SAMAGAM - A SPECIAL EVENT FOR KIDS! 🎪

    What is Bal Samagam?
    🎉 A super fun gathering where kids like you come together to learn about God and have amazing activities!
    🎭 Kids do singing (bhajans), give speeches, perform skits, tell stories, and play games
    🌟 It helps children build confidence and learn spiritual values in a fun way
    🤗 Young saints bond with each other and feel part of our big spiritual family

    Key Teachings:
    🙏 "Dhan Nirankar Ji" - Our special greeting meaning "Blessed is the Formless God"
    ❤ Sewa - Helping others without expecting anything back
    💭 Simran - Remembering God in our heart ("Tu Hi Nirankar")
    👨‍👩‍👧‍👦 Satsang - Coming together to learn good things
    🌍 Universal Brotherhood - We're all one big family under God
    """

    # English only response patterns
    response_patterns = {
        'god': "Dhan Nirankar Ji! 🙏 God is everywhere - in you, me, your friends, even in trees and animals! God is formless, which means He doesn't have a body like us, but His love fills everything! 💕",
        'sewa': "Dhan Nirankar Ji! 🙏 Sewa means helping others with a happy heart! Like when you help mama with dishes or share your toys with friends - that's Sewa! 🌟",
        'simran': "Dhan Nirankar Ji! 🙏 Simran means keeping God as your best friend in your heart! You can remember God while playing, studying, or even eating ice cream! 😄"
    }

    def get_system_prompt(self):
        """Get system prompt in English only."""
        return f"""
        You are "Guru Ji's Little Helper" 🤖, a loving chatbot for kids attending Bal Samagam of Sant Nirankari Mission.

            MULTILINGUAL RULE:
            - Always detect the language of the user input (English, Hindi, Marathi, etc.).
            - Respond only in the same language as the user’s input.
            - If the user types in English letters but in another language (e.g., "tumhi kon ahe"), 
            still recognize the intended language and respond in that language.
            - Keep your tone and wording simple and child-friendly in every language.

            PERSONALITY:
            - For greetings/farewells (hi, hello, good morning, bye, good night, dhan nirankar, etc.), 
            always start with "Dhan Nirankar Ji! 🙏"
            - Otherwise, respond normally without it
            - Super friendly, like a big brother/sister
            - Use simple words that 5–12 year olds can understand
            - Keep answers short and fun (2-3 sentences)
            - Use emojis 😊🎉🌟
            - Give relatable, playful examples (stories, games, school life, friends)
            - Always be encouraging and positive


        KNOWLEDGE BASE:
        {self.bal_samagam_knowledge}
        """
    
    def get_fallback_response(self, user_message):
        """English fallback responses only."""
        message_lower = user_message.lower()
        # Greeting responses
        if any(word in message_lower for word in ['hello', 'hi', 'namaste', 'hey']):
            return random.choice(self.welcome_messages)
        # God/spiritual questions
        elif any(word in message_lower for word in ['god', 'nirankar']):
            return self.response_patterns['god']
        elif any(word in message_lower for word in ['sewa', 'help']):
            return self.response_patterns['sewa']
        elif any(word in message_lower for word in ['simran', 'prayer']):
            return self.response_patterns['simran']
        # Default response
        return "Dhan Nirankar Ji! 🙏 That's such a great question! You're so smart for asking! 🌟 Can you tell me more about what you're thinking? I love learning with you! 🤗"

    
    # ---------- History Handling ----------
    CHAT_HISTORY_FILE = "chat_history.json"

    def _load_all_sessions(self):
        """Load all chat histories (multiple users)."""
        if os.path.exists(self.history_file):
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_all_sessions(self):
        """Save all chat histories back to file."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.all_sessions, f, ensure_ascii=False, indent=2)

    def get_user_history(self, user_id):
        """Get conversation history for one user from Redis"""
        history_json = self.redis_client.get(f"session:{user_id}")
        if history_json:
            return json.loads(history_json)
        return []

    def update_user_history(self, user_id, role, content):
        """Add a message to user's history in Redis"""
        history = self.get_user_history(user_id)
        history.append({"role": role, "content": content})
        # Save back to Redis with TTL of 24 hours
        self.redis_client.set(f"session:{user_id}", json.dumps(history), ex=86400)

    def load_history(self):
        """Load all chat histories (for backward compatibility)."""
        return self._load_all_sessions()

    def save_history(self, history):
        """Save all chat histories (for backward compatibility)."""
        self.all_sessions = history
        self._save_all_sessions()

    # ---------- Chat Function ----------
    def chat(self, session_id: str, user_message: str) -> str:
        """Handles a chat message for a given session (sid)"""
        # Append user message to Redis history
        self.update_user_history(session_id, "user", user_message)
        # Get last 6 messages for context
        conversation_history = self.get_user_history(session_id)[-6:]
        # Call OpenAI API
        try:
            bot_reply = self.call_openai_api(
                user_message,
                conversation_history
            )
        except Exception as e:
            print(f"API Error: {e}")
            bot_reply = self.get_fallback_response(user_message)
        # Save bot reply
        self.update_user_history(session_id, "assistant", bot_reply)
        return bot_reply
