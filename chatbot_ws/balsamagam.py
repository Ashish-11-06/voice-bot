
import requests
import json
import os
from dotenv import load_dotenv
import random
import redis
import re
from datetime import datetime
import numpy as np

load_dotenv()  

from openai import OpenAI  

class BalSamagamChatbot:
    def _load_doc_qa_pairs(self):
        """Load Q&A pairs and their embeddings from doc_embeddings.json."""
        doc_path = os.path.join(os.path.dirname(__file__), 'doc_embeddings.json')
        if not os.path.exists(doc_path):
            return []
        with open(doc_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Each item: {"question": ..., "answer": ..., "embedding": [...]}
        return data

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

        # Load Q&A pairs from doc_embeddings.json
        self.qa_pairs = self._load_doc_qa_pairs()

    def get_embedding(self, text):
        """Get embedding for a text using OpenAI embedding API."""
        try:
            response = self.client.embeddings.create(
                input=[text],
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding API Error: {e}")
            return None

    def cosine_similarity(self, a, b):
        a = np.array(a)
        b = np.array(b)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def find_top_doc_matches(self, user_message, top_n=3):
        """Return top N most similar Q&A pairs from doc_embeddings.json."""
        if not self.qa_pairs:
            return []
        user_emb = self.get_embedding(user_message)
        if user_emb is None:
            return []
        scored = []
        for item in self.qa_pairs:
            q_emb = item.get("embedding")
            if not q_emb:
                continue
            score = self.cosine_similarity(user_emb, q_emb)
            scored.append({"score": score, "question": item.get("question"), "answer": item.get("answer")})
        scored.sort(key=lambda x: x["score"], reverse=True)
        print(f"[DEBUG] Top doc matches:")
        for i, match in enumerate(scored[:top_n]):
            print(f"  {i+1}. '{match['question']}' (score={match['score']:.3f})")
        return scored[:top_n]

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
        self.update_user_history(session_id, "user", user_message)
        top_matches = self.find_top_doc_matches(user_message, top_n=3)
        # If best match is very high similarity, answer directly
        if top_matches and top_matches[0]["score"] >= 0.85:
            print("[INFO] Responding directly from doc_embeddings.json (high similarity)")
            bot_reply = top_matches[0]["answer"]
        else:
            # Build RAG context from top matches
            rag_context = "Use the following information to answer the user's question.\n"
            for i, match in enumerate(top_matches):
                rag_context += f"Q{i+1}: {match['question']}\nA{i+1}: {match['answer']}\n"
            # Add system prompt with guardrails and personality
            system_prompt = (
                "You are 'Guru Ji's Little Helper' 🤖, a friendly female chatbot for kids at Bal Samagam (Sant Nirankari Mission).\n"
                "Say you are designed for Bal Samagam and love helping kids!\n"
                "Use 'Dhan Nirankar Ji! 🙏' only for greetings and farewells, not every response.\n"
                "Address the user as 'Sant' or by their name if they share it.\n"
                "Be caring, positive, and sound like a big sister.\n"
                "Use emojis, short sentences, and playful examples.\n"
                "Answer about Bal Samagam, Sant Nirankari Mission, spirituality, and general knowledge.\n"
                "Use doc context if available, else use your own knowledge.\n"
                "If you don't know, say 'Dhan Nirankar Ji! 🙏 That's a great question! Can you ask in another way?'\n"
                "Never give medical, legal, or personal advice.\n"
                "Keep answers safe, kind, and child-appropriate.\n"
                "Add friendly fillers like 'Hmm...', 'Let me think...', 'Oh wow!', 'That's interesting!' to sound human."
            )
            conversation_history = self.get_user_history(session_id)[-6:]
            # Insert system prompt and RAG context as system messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": rag_context},
            ]
            for msg in conversation_history:
                messages.append(msg)
            messages.append({"role": "user", "content": user_message})
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=300,
                    temperature=0.8
                )
                bot_reply = response.choices[0].message.content
                print("[INFO] Responding from OpenAI chat model with RAG context and system prompt")
            except Exception as e:
                print(f"API Error: {e}")
                bot_reply = self.get_fallback_response(user_message)
        self.update_user_history(session_id, "assistant", bot_reply)
        return bot_reply
