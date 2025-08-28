import os
import json
import random
import redis
import re
import requests
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)
from dotenv import load_dotenv
import os

load_dotenv() 
class MultiLanguageBalSamagamChatbot:
    def __init__(self):
        self.redis_client = self._init_redis()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.openai_api_key:
            logger.error("OPENAI_API_KEY is not set in environment")
            raise RuntimeError("OPENAI_API_KEY is not set in environment")

        # Endpoints
        self.openai_chat_url = "https://api.openai.com/v1/chat/completions"
        self.openai_stt_url = "https://api.openai.com/v1/audio/transcriptions"
        self.openai_tts_url = "https://api.openai.com/v1/audio/speech"

        # Flags
        self.auto_detect = False
        self.current_language = 'en'

        # Initialize language resources
        self._init_language_resources()
        
        # History file
        self.history_file = "chat_history.json"
        self.all_sessions = self._load_all_sessions()

    def _init_redis(self):
        """Initialize Redis connection with error handling"""
        try:
            return redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=0,
                decode_responses=True,
                socket_connect_timeout=3,
                retry_on_timeout=True
            )
        except redis.ConnectionError as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory storage only.")
            return None

    def _init_language_resources(self):
        """Initialize language-specific resources"""
        # Supported languages
        self.languages = {
            'en': 'English',
            'hi': 'Hindi',
            'mr': 'Marathi',
            'hinglish': 'Hinglish (Hindi + English)',
            'manglish': 'Manglish (Marathi + English)'
        }

        # Language detection patterns
        self.language_patterns = {
            'hi': ['कि', 'है', 'में', 'का', 'की', 'को', 'से', 'पर', 'और', 'या', 'हूं', 'हैं', 'था', 'थी', 'गया', 'गई'],
            'mr': ['आहे', 'आहेत', 'मध्ये', 'ला', 'ची', 'चा', 'चे', 'ने', 'वर', 'आणि', 'किंवा', 'होते', 'होता', 'गेला', 'गेली'],
            'hinglish': ['main', 'mujhe', 'kya', 'hai', 'hoon', 'kaise', 'kahan', 'kyun'],
            'manglish': ['mala', 'tumhala', 'kay', 'kase', 'kuthe', 'ka']
        }

        # Load language resources from external files
        self._load_language_data()

    def _load_language_data(self):
        """Load language data from JSON files"""
        try:
            # Load from external JSON files if available
            json_path = os.path.join(os.path.dirname(__file__), 'json_files', 'language_data.json')
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    language_data = json.load(f)
                    
                self.welcome_messages = language_data.get('welcome_messages', {})
                self.bal_samagam_knowledge = language_data.get('bal_samagam_knowledge', {})
                self.response_patterns = language_data.get('response_patterns', {})
            else:
                # Fallback to hardcoded data
                self._load_hardcoded_language_data()
                
        except Exception as e:
            logger.error(f"Error loading language data: {e}")
            self._load_hardcoded_language_data()

    def _load_hardcoded_language_data(self):
        """Fallback hardcoded language data"""
        # Welcome messages, knowledge base, and response patterns would be here
        # (Your original hardcoded data, but trimmed for brevity)
        self.welcome_messages = {
            'en': ["🎉 Dhan Nirankar Ji! Welcome to Bal Samagam! 🎪..."],
            'hi': ["🎉 धन निरंकार जी! बाल समागम में आपका स्वागत है! 🎪..."],
            # ... other languages
        }
        
        self.bal_samagam_knowledge = {
            'en': "BAL SAMAGAM - A SPECIAL EVENT FOR KIDS! 🎪...",
            'hi': "बाल समागम - बच्चों के लिए विशेष कार्यक्रम! 🎪...",
            # ... other languages
        }
        
        self.response_patterns = {
            'en': {
                'god': "Dhan Nirankar Ji! 🙏 God is everywhere...",
                'sewa': "Dhan Nirankar Ji! 🙏 Sewa means helping others...",
                'simran': "Dhan Nirankar Ji! 🙏 Simran means keeping God..."
            },
            'hi': {
                'god': "धन निरंकार जी! 🙏 भगवान हर जगह हैं...",
                'sewa': "धन निरंकार जी! 🙏 सेवा का मतलब है...",
                'simran': "धन निरंकार जी! 🙏 सिमरन का मतलब है..."
            },
            # ... other languages and patterns
        }

    def detect_language(self, text):
        """Detect the language of input text with improved accuracy"""
        if not text or not isinstance(text, str):
            return self.current_language
            
        text_lower = text.lower()
        scores = {}

        # Count matches for each language
        for lang, patterns in self.language_patterns.items():
            score = sum(1 for pattern in patterns if pattern in text_lower)
            scores[lang] = score

        # Check for English patterns
        english_patterns = ['the', 'and', 'is', 'are', 'what', 'how', 'why', 'when', 'where']
        scores['en'] = sum(1 for pattern in english_patterns if pattern in text_lower)

        # Return language with highest score
        if max(scores.values()) > 0:
            detected = max(scores, key=scores.get)
            logger.debug(f"Detected language: {detected} with score: {scores[detected]}")
            return detected

        return self.current_language

    def get_system_prompt(self, language):
        """Get system prompt in specified language"""
        prompts = {
            'en': f"""You are "Guru Ji's Little Helper" 🤖...{self.bal_samagam_knowledge.get('en', '')}""",
            'hi': f"""आप "गुरु जी के छोटे सहायक" 🤖 हैं...{self.bal_samagam_knowledge.get('hi', '')}""",
            # ... other languages
        }
        return prompts.get(language, prompts['en'])

    def call_openai_chat(self, user_message, language, conversation_history=[]):
        """Call GPT-4o mini with language-specific context."""
        try:
            messages = [{"role": "system", "content": self.get_system_prompt(language)}]

            # Add conversation history (last 6 entries)
            for msg in conversation_history[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})

            messages.append({"role": "user", "content": user_message})

            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "max_tokens": 300,
                "temperature": 0.8
            }

            resp = requests.post(self.openai_chat_url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
            
        except requests.exceptions.Timeout:
            logger.error("OpenAI API request timed out")
            return self.get_fallback_response(user_message, language)
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API request failed: {e}")
            return self.get_fallback_response(user_message, language)
        except Exception as e:
            logger.error(f"Unexpected error in call_openai_chat: {e}")
            return self.get_fallback_response(user_message, language)

    def get_fallback_response(self, user_message, language):
        """Language-specific fallback responses"""
        message_lower = user_message.lower() if user_message else ""

        # Greeting responses
        if any(word in message_lower for word in ['hello', 'hi', 'namaste', 'hey', 'नमस्ते', 'हॅलो']):
            return random.choice(self.welcome_messages.get(language, self.welcome_messages['en']))

        # God/spiritual questions
        elif any(word in message_lower for word in ['god', 'भगवान', 'निरंकार', 'nirankar']):
            return self.response_patterns[language].get('god', 'Dhan Nirankar Ji! 🙏')

        elif any(word in message_lower for word in ['sewa', 'सेवा', 'help', 'मदद']):
            return self.response_patterns[language].get('sewa', 'Dhan Nirankar Ji! 🙏')

        elif any(word in message_lower for word in ['simran', 'सिमरन', 'prayer', 'प्रार्थना']):
            return self.response_patterns[language].get('simran', 'Dhan Nirankar Ji! 🙏')

        # Default response by language
        defaults = {
            'en': "Dhan Nirankar Ji! 🙏 That's such a great question!...",
            'hi': "धन निरंकार जी! 🙏 यह बहुत अच्छा सवाल है!...",
            'mr': "धन निरंकार जी! 🙏 हा खूप छान प्रश्न आहे!...",
            'hinglish': "Dhan Nirankar Ji! 🙏 यह बहुत great question है!...",
            'manglish': "Dhan Nirankar Ji! 🙏 हा खूप great question आहे!..."
        }

        return defaults.get(language, defaults['en'])

    def choose_language(self, default="auto"):
        """Set default language mode"""
        valid_choices = ["en", "hi", "mr", "hinglish", "manglish", "auto"]

        if default not in valid_choices:
            default = "auto"

        if default == "auto":
            self.auto_detect = True
            self.current_language = "en"
        else:
            self.auto_detect = False
            self.current_language = default

        logger.info(f"Language set to: {self.current_language}, auto-detect: {self.auto_detect}")
        return self.current_language

    # History Handling Methods
    def _load_all_sessions(self):
        """Load all chat histories"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
        return {}

    def _save_all_sessions(self):
        """Save all chat histories"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.all_sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")

    def get_user_history(self, user_id):
        """Get conversation history for one user"""
        try:
            if self.redis_client:
                history_json = self.redis_client.get(f"session:{user_id}")
                if history_json:
                    return json.loads(history_json)
        except Exception as e:
            logger.error(f"Error getting user history from Redis: {e}")
        return []

    def update_user_history(self, user_id, role, content):
        """Add a message to user's history"""
        try:
            history = self.get_user_history(user_id)
            history.append({"role": role, "content": content})
            
            # Keep only last 20 messages to prevent memory issues
            if len(history) > 20:
                history = history[-20:]
                
            if self.redis_client:
                self.redis_client.set(f"session:{user_id}", json.dumps(history), ex=86400)
        except Exception as e:
            logger.error(f"Error updating user history: {e}")

    def chat(self, session_id: str, user_message: str = None) -> str:
        """
        Handles ONE round of chat for a given session.
        Returns assistant text reply.
        """
        if not user_message:
            logger.warning("Empty user message received")
            return self.get_fallback_response("", self.current_language)

        logger.info(f"User {session_id}: {user_message}")

        # Auto-detect language if enabled
        if self.auto_detect:
            self.current_language = self.detect_language(user_message)

        # Save user message
        self.update_user_history(session_id, "user", user_message)

        # Get conversation history
        conversation_history = self.get_user_history(session_id)

        # Call GPT-4o mini (text response)
        try:
            bot_reply = self.call_openai_chat(
                user_message,
                self.current_language,
                conversation_history
            )
        except Exception as e:
            logger.error(f"Chat processing error: {e}")
            bot_reply = self.get_fallback_response(user_message, self.current_language)

        # Save bot reply
        self.update_user_history(session_id, "assistant", bot_reply)

        logger.info(f"Bot {session_id}: {bot_reply}")
        return bot_reply