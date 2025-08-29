import os
import json
import random
import redis
import requests
import logging

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


class MultiLanguageBalSamagamChatbot:
    def __init__(self):
        # Redis connection
        self.redis_client = self._init_redis()

        # OpenAI API
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.error("OPENAI_API_KEY is not set in environment")
            raise RuntimeError("OPENAI_API_KEY is not set in environment")

        # API endpoint
        self.openai_chat_url = "https://api.openai.com/v1/chat/completions"

        # Default language
        self.current_language = "en"

        # English resources only
        self.welcome_messages = [
            "🎉 Dhan Nirankar Ji! Welcome to Bal Samagam! 🎪 We are so happy to have you here!"
        ]

        # self.bal_samagam_knowledge = (
        #             """
        # BAL SAMAGAM - A SPECIAL EVENT FOR KIDS! 🎪
        
        # What is Bal Samagam?
        # 🎉 A super fun gathering where kids like you come together to learn about God and have amazing activities!
        # 🎭 Kids do singing (bhajans), give speeches, perform skits, tell stories, and play games
        # 🌟 It helps children build confidence and learn spiritual values in a fun way
        # 🤗 Young saints bond with each other and feel part of our big spiritual family
        
        # Key Teachings:
        # 🙏 "Dhan Nirankar Ji" - Our special greeting meaning "Blessed is the Formless God"
        # ❤ Sewa - Helping others without expecting anything back
        # 💭 Simran - Remembering God in our heart ("Tu Hi Nirankar")
        # 👨‍👩‍👧‍👦 Satsang - Coming together to learn good things
        # 🌍 Universal Brotherhood - We're all one big family under God""")

        # self.response_patterns = {
        #     "god": "Dhan Nirankar Ji! 🙏 God is everywhere, inside us and around us.",
        #     "sewa": "Dhan Nirankar Ji! 🙏 Sewa means helping others selflessly.",
        #     "simran": "Dhan Nirankar Ji! 🙏 Simran means remembering God with love."
        # }

        # Chat history storage (fallback if Redis is not available)
        self.history_file = "chat_history.json"
        self.all_sessions = self._load_all_sessions()
    

    def get_relevant_knowledge(self, user_message: str):
        """Return only small relevant snippets instead of full knowledge base"""
        text = user_message.lower()
        if "god" in text or "nirankar" in text:
            return "God is everywhere, inside us and around us."
        elif "sewa" in text or "help" in text:
            return "Sewa means helping others selflessly."
        elif "simran" in text or "prayer" in text:
            return "Simran means remembering God with love."
        elif "bal samagam" in text or "event" in text:
            return "Bal Samagam is a fun gathering for kids with songs, skits, stories, and games."
        return None

    def _init_redis(self):
        """Initialize Redis connection with error handling"""
        try:
            return redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=0,
                decode_responses=True,
                socket_connect_timeout=3,
                retry_on_timeout=True
            )
        except redis.ConnectionError as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory storage only.")
            return None

    def _load_all_sessions(self):
        """Load all chat histories from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
        return {}

    def _save_all_sessions(self):
        """Save all chat histories to file"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.all_sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")

    def get_system_prompt(self):
        return """You are "Guru Ji's Little Helper" 🤖, a friendly chatbot for kids at Bal Samagam.

            RULES:
            - Detect user language (English, Hindi, Marathi, etc.) and reply in same.
            - Keep replies short (1–3 sentences), simple, fun, child-friendly.
            - Use emojis 😊🎉🌟
            - Start greetings/farewells with "Dhan Nirankar Ji! 🙏"

            Tone: encouraging, playful, big-brother/sister style.
            """

    def call_openai_chat(self, user_message, conversation_history=[]):
        """Optimized OpenAI call with reduced tokens and selective knowledge"""
        try:
            # Start with system rules
            messages = [{"role": "system", "content": self.get_system_prompt()}]

            # Add last 4 messages only (enough context)
            for msg in conversation_history[-4:]:
                messages.append(msg)

            # Add knowledge only if relevant
            knowledge = self.get_relevant_knowledge(user_message)
            if knowledge:
                messages.append({"role": "system", "content": f"Extra info: {knowledge}"})

            # Add user message
            messages.append({"role": "user", "content": user_message})

            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "max_tokens": 120,   # smaller limit for short, kid-friendly replies
                "temperature": 0.7
            }

            resp = requests.post(self.openai_chat_url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self.get_fallback_response(user_message)
    
    def get_fallback_response(self, user_message):
        """Fallback if OpenAI fails"""
        text = user_message.lower()

        if any(word in text for word in ["hello", "hi", "namaste", "hey"]):
            return random.choice(self.welcome_messages)
        elif "god" in text or "nirankar" in text:
            return self.response_patterns["god"]
        elif "sewa" in text or "help" in text:
            return self.response_patterns["sewa"]
        elif "simran" in text or "prayer" in text:
            return self.response_patterns["simran"]

        return "Dhan Nirankar Ji! 🙏 That's such a great question! Let's learn together. 🌟"

    def get_user_history(self, user_id):
        """Get chat history for a user"""
        try:
            if self.redis_client:
                history_json = self.redis_client.get(f"session:{user_id}")
                if history_json:
                    return json.loads(history_json)
        except Exception as e:
            logger.error(f"Error getting user history from Redis: {e}")
        return []

    def update_user_history(self, user_id, role, content):
        """Update user history"""
        try:
            history = self.get_user_history(user_id)
            history.append({"role": role, "content": content})

            # Keep last 20 messages
            if len(history) > 20:
                history = history[-20:]

            if self.redis_client:
                self.redis_client.set(f"session:{user_id}", json.dumps(history), ex=86400)
        except Exception as e:
            logger.error(f"Error updating history: {e}")

    def chat(self, session_id: str, user_message: str = None) -> str:
        """Main chat handler"""
        if not user_message:
            return self.get_fallback_response("")

        logger.info(f"User {session_id}: {user_message}")

        # Save user message
        self.update_user_history(session_id, "user", user_message)

        # Get history
        conversation_history = self.get_user_history(session_id)

        # Call GPT
        bot_reply = self.call_openai_chat(user_message, conversation_history)

        # Save bot reply
        self.update_user_history(session_id, "assistant", bot_reply)

        logger.info(f"Bot {session_id}: {bot_reply}")
        return bot_reply
