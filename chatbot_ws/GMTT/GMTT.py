
import os
import json
import re
import uuid
import random
from django.contrib.auth import get_user_model

from .common_utils import (
    load_knowledge_base,
    load_session_history,
    save_session_history,
    search_knowledge_block,
    call_mistral_model,
    is_mistral_follow_up,
    get_conversation_driver,
    generate_nlp_response,
    is_contact_request,
    is_info_request,
    CONTACT_EMAIL,
)
from .models import ChatbotConversation
from .serializers import ChatbotConversationSerializer

User = get_user_model()

# -------------------- Config --------------------
CHATBOT_NAME = "Infi"

current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")
content_path = os.path.join(json_dir, "trees.json")
history_file_path = os.path.join(json_dir, "session_history_gmtt.json")

os.makedirs(json_dir, exist_ok=True)
if not os.path.exists(history_file_path):
    with open(history_file_path, "w") as f:
        json.dump([], f)

gmtt_kb = load_knowledge_base(content_path)


# -------------------- DB Utils --------------------
def store_session_in_db(history, user, chatbot_type):
    """Persist session in DB"""
    session_id = str(uuid.uuid4())
    for turn in history:
        ChatbotConversation.objects.create(
            user=user,
            chatbot_type=chatbot_type,
            session_id=session_id,
            query=turn["user"],
            response=turn["bot"],
        )
    return session_id



# Removed website crawling and scraping related code
GMTT_INDEX = []


# -------------------- Mistral Response --------------------
def get_mistral_gmtt_response(user_query, history):
    """LLM response restricted to GMTT rules"""
    try:
        if is_contact_request(user_query):
            return (
                f"Please share your query/feedback/message with me and I'll forward it "
                f"to our team at {CONTACT_EMAIL}. Could you please tell me your name and email address?"
            )

        if is_info_request(user_query):
            return (
                f"Thank you for sharing your details! I've noted your information and will "
                f"share it with our team at {CONTACT_EMAIL}. Is there anything specific you'd like us to know?"
            )


        match = search_knowledge_block(user_query, gmtt_kb)
        # Website scraping removed, so no website_match or relevant_text
        prompt = f"""
            You are an AI assistant created exclusively for **Give Me Trees Foundation (GMTT)**.

            STRICT RULES:
            1. Detect the language of the user's query and respond ONLY in that language.
            2. If matching content is found, respond strictly using that content, rephrased naturally in the detected language.
            3. If no relevant content is found, reply in the detected language with:
            "I couldn't find any official information related to that topic on our website, so I won't answer inaccurately."
            4. If the user greets or makes small talk, respond politely in the detected language.
            5. If the question is unrelated to GMTT, reply in the detected language with:
            "I specialize in Give Me Trees Foundation. I can't help with that."

            Organization Info:
            - Name: Give Me Trees Foundation
            - Founded: 1978 by Swami Prem Parivartan (Peepal Baba)
            - Focus: Environmental conservation through tree plantation
            - Website: https://www.givemetrees.org

            User Query: {user_query}
            """

        response = call_mistral_model(prompt)
        cleaned = re.sub(r'\[.*?\]|(Answer:|Follow-up question:)', '', response, flags=re.I).strip()
        return cleaned[0].upper() + cleaned[1:] if cleaned else cleaned

    except Exception:
        driver = get_conversation_driver(history, "mid")
        return f"I'd be happy to tell you more. {driver}"


# -------------------- Meta & KB --------------------
def handle_meta_questions(user_input):
    """Handle 'what can I ask you' style queries"""
    meta_phrases = [
        "what can i ask you", "suggest me some topics", "what topics can i ask",
        "how can you help", "what do you know", "what programs do you run",
        "what questions can i ask", "what information do you have",
        "what can you tell me", "what should i ask",
    ]
    lowered = user_input.lower()
    if any(p in lowered for p in meta_phrases):
        return random.choice([
            "I'm here to help with all things related to Give Me Trees Foundation! You can ask me about plantation drives, volunteering, or our environmental impact.",
            "As a GMTT assistant, I can tell you about our conservation projects, Peepal tree initiatives, and how to support our cause.",
            "You can ask about: our plantation drives, how to volunteer, the impact of our work, or ways to donate and partner with us.",
            "I specialize in GMTT's environmental work — ask me about Peepal Baba, our methodology, success stories, or upcoming events.",
            "Here are some ideas: why we focus on Peepal trees, how we ensure survival of planted trees, volunteer stories, or our school programs.",
        ])
    return None


def format_kb_for_prompt(intent_entry):
    """Convert KB entry into formatted text for prompt"""
    return "\n".join([
        f"Tag: {intent_entry.get('tag', '')}",
        f"User Patterns: {'; '.join(intent_entry.get('patterns', []))}",
        f"Responses: {'; '.join(intent_entry.get('response', []))}",
        f"Follow-up Question: {intent_entry.get('follow_up', '')}",
    ]).strip()


def search_intents_and_respond(user_input):
    """Search KB and build response"""
    block = search_knowledge_block(user_input, gmtt_kb)
    if not block:
        return None

    context = format_kb_for_prompt(block)
    prompt = f"""
You are a helpful assistant from Give Me Trees Foundation.
Answer ONLY using the given context. Speak as "we". End with a related follow-up question.

Context:
{context}

User Question: {user_input}
"""
    try:
        response = call_mistral_model(prompt, max_tokens=90)
        cleaned = re.sub(r'\[.*?\]', '', response).strip()
        return cleaned if cleaned.endswith(('.', '!', '?')) else f"{cleaned}."
    except Exception:
        return "We're having trouble processing your request right now. Could you please try again?"


# -------------------- Response Pipeline --------------------
def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type="gmtt"):
    """Append to history and enhance response"""
    history = load_session_history(history_file_path)

    if not is_mistral_follow_up(current_response):
        driver = get_conversation_driver(history, "intro" if len(history) < 2 else "mid")
        current_response += f" {driver}"

    if any(h["user"].lower() == user_input.lower() for h in history[-3:]):
        current_response = f"Returning to your question, {current_response.lower()}"

    history.append({"user": user_input, "bot": current_response})
    save_session_history(history_file_path, history)
    return current_response


def get_gmtt_response(user_input, user=None):
    """Main chatbot pipeline"""
    if not isinstance(user_input, str) or not user_input.strip():
        return "Please provide a valid input."

    history = load_session_history(history_file_path)
    last_bot_msg = history[-1].get("bot", "") if history else ""

    # Handle follow-up answers
    if history and is_mistral_follow_up(last_bot_msg):
        affirmative_check = call_mistral_model(
            f'Analyze if this agrees: "{last_bot_msg}" vs "{user_input}". Reply ONLY YES/NO.'
        )
        if "YES" in affirmative_check.upper():
            topic = call_mistral_model(
                f"What was the main topic before this? Question: '{last_bot_msg}'"
            ).strip()
            topic_match = search_knowledge_block(topic, GMTT_INDEX)
            matched_context = (topic_match or {}).get("text", "")[:500]
            detail_prompt = f"""
Explain '{topic}' in 2–3 short points for GMTT, using a professional tone.
Context: {matched_context}
"""
            response = call_mistral_model(detail_prompt).strip()
            return update_and_respond_with_history(user_input, response, user=user)

    # Website guide and matched_url removed
    response = (
        f"My name is {CHATBOT_NAME}. What would you like to know about GMTT?" if "your name" in user_input.lower()
        else handle_meta_questions(user_input)
        or generate_nlp_response(user_input)
        or search_intents_and_respond(user_input)
        or get_mistral_gmtt_response(user_input, history)
        or "I couldn't find specific information about that. Could you rephrase?"
    )

    final_response = update_and_respond_with_history(user_input, response, user=user)

    if len(history) > 3 and not final_response.strip().endswith("?"):
        follow_up = get_conversation_driver(history, "mid")
        final_response += f" {follow_up}"

    return final_response
