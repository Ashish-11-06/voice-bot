import os
import json
import random
import redis
import re
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class GMTTChatbot:
    def _load_doc_qa_pairs(self):
        """Load Q&A pairs and their embeddings from doc_embeddings.json."""
        doc_path = os.path.join(os.path.dirname(__file__), 'doc_embeddings.json')
        if not os.path.exists(doc_path):
            return []
        with open(doc_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
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

    def get_system_prompt(self):
        """Get system prompt for GMTT bot."""
        return f"""
        You are "Infi", the official AI assistant for Give Me Trees Trust (GMTT).

        MULTILINGUAL RULE:
        - Always detect the language of the user input (English, Hindi, etc.).
        - Respond only in the same language as the user’s input.
        - If the user types in English letters but in another language (e.g., "ped lagana kaise shuru kare"), 
        still recognize the intended language and respond in that language.
        - Keep your tone and wording professional, friendly, and easy to understand.

        DOMAIN GUARDRAILS:
        - Only answer questions related to GMTT, tree plantation, Peepal Baba, environmental conservation, volunteering, and official GMTT programs.
        - If the question is unrelated, reply: "I specialize in Give Me TreesTrust I can't help with that."
        - Never give medical, legal, or personal advice.
        - Never speculate or provide unofficial information.
        - If you don't know, say: "I couldn't find any official information related to that topic on our website, so I won't answer inaccurately."

        PERSONALITY:
        - Polite, professional, and encouraging
        - Use short, clear sentences
        - Add a friendly follow-up question if appropriate
        - Use emojis 🌳🌱 when talking about trees or environment

        ORGANIZATION INFO:
        - Name: Give Me Trees Trust
        - Founded: 1978 by Swami Prem Parivartan (Peepal Baba)
        - Focus: Environmental conservation through tree plantation
        - Website: https://www.givemetrees.org

        KNOWLEDGE BASE:
        Use only official information about GMTT, tree plantation, volunteering, and related topics.
        """

    def get_fallback_response(self, user_message):
        """Fallback responses for GMTT bot."""
        message_lower = user_message.lower()
        if any(word in message_lower for word in ['hello', 'hi', 'namaste', 'hey', 'greetings']):
            return random.choice([
                "🌳 Hello! Welcome to Give Me Trees Trust How can I help you with tree plantation or volunteering?",
                "🌱 Namaste! I'm Infi, your GMTT assistant. What would you like to know about our work?",
                "🌳 Hi there! Ask me anything about tree plantation, Peepal Baba, or volunteering with GMTT."
            ])
        elif any(word in message_lower for word in ['peepal baba', 'founder', 'swami']):
            return "🌳 Peepal Baba (Swami Prem Parivartan) founded Give Me Trees Trust in 1978. He has planted millions of trees across India!"
        elif any(word in message_lower for word in ['volunteer', 'join', 'help']):
            return "🌱 You can volunteer with GMTT by joining our plantation drives or supporting our awareness programs. Would you like details on how to sign up?"
        elif any(word in message_lower for word in ['plantation', 'trees', 'environment']):
            return "🌳 GMTT organizes tree plantation drives to promote environmental conservation. Would you like to know about our upcoming events?"
        return "I specialize in Give Me TreesTrust Could you please ask about tree plantation, volunteering, or our programs?"

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
            rag_context = "Use the following official GMTT information to answer the user's question.\n"
            for i, match in enumerate(top_matches):
                rag_context += f"Q{i+1}: {match['question']}\nA{i+1}: {match['answer']}\n"
            # Add system prompt with guardrails and personality
            system_prompt = self.get_system_prompt()
            conversation_history = self.get_user_history(session_id)[-6:]
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
                    temperature=0.7
                )
                bot_reply = response.choices[0].message.content
                print("[INFO] Responding from OpenAI chat model with RAG context and system prompt")
            except Exception as e:
                print(f"API Error: {e}")
                bot_reply = self.get_fallback_response(user_message)
        self.update_user_history(session_id, "assistant", bot_reply)
        return bot_reply