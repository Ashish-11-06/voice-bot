import requests
import json
import os
import random
import re
from datetime import datetime

class MultiLanguageBalSamagamChatbot:
    def __init__(self):
        # Mistral API configuration
        self.mistral_api_key = os.getenv('MISTRAL_API_KEY', 'LY1MwjaPpQnvApjHW0p7pgexEHvhK9Ew')
        self.mistral_api_url = "https://api.mistral.ai/v1/chat/completions"
        
        self.auto_detect = False
        
        # Supported languages
        self.languages = {
            'en': 'English',
            'hi': 'Hindi', 
            'mr': 'Marathi',
            'hinglish': 'Hinglish (Hindi + English)',
            'manglish': 'Manglish (Marathi + English)'
        }
        
        self.current_language = 'en'  # Default language
        self.history_file = self.CHAT_HISTORY_FILE
        self.all_sessions = self._load_all_sessions()
        
        # Multi-language welcome messages
        self.welcome_messages = {
            'en': [
                "🎉 Dhan Nirankar Ji! Welcome to Bal Samagam! 🎪 I'm so excited you're here, little saint! What would you like to know?",
                "🌟 Dhan Nirankar Ji! Welcome to our special Bal Samagam! 🎊 This is going to be so much fun! Ask me anything!",
                "🎈 Dhan Nirankar Ji, my dear friend! Welcome to Bal Samagam 2025! 🎭 I'm here to help you learn and have fun!"
            ],
            'hi': [
                "🎉 धन निरंकार जी! बाल समागम में आपका स्वागत है! 🎪 मैं बहुत खुश हूं कि आप यहां हैं, छोटे संत! आप क्या जानना चाहते हैं?",
                "🌟 धन निरंकार जी! हमारे विशेष बाल समागम में आपका स्वागत है! 🎊 यह बहुत मजेदार होगा! मुझसे कुछ भी पूछिए!",
                "🎈 धन निरंकार जी, मेरे प्यारे दोस्त! बाल समागम 2025 में आपका स्वागत है! 🎭 मैं यहां आपकी सीखने में मदद करने के लिए हूं!"
            ],
            'mr': [
                "🎉 धन निरंकार जी! बाल समागमात तुमचे स्वागत आहे! 🎪 तुम्ही इथे आहात याची मला खूप आनंद आहे, लहान संत! तुम्हाला काय जाणून घ्यायचे आहे?",
                "🌟 धन निरंकार जी! आमच्या विशेष बाल समागमात तुमचे स्वागत आहे! 🎊 हे खूप मजेदार होणार आहे! मला काहीही विचारा!",
                "🎈 धन निरंकार जी, माझ्या प्रिय मित्रा! बाल समागम 2025 मध्ये तुमचे स्वागत आहे! 🎭 मी इथे तुम्हाला शिकण्यात मदत करण्यासाठी आहे!"
            ],
            'hinglish': [
                "🎉 Dhan Nirankar Ji! Bal Samagam में आपका welcome है! 🎪 Main बहुत excited हूं कि आप यहां हैं, little saint! आप क्या जानना चाहते हैं?",
                "🌟 Dhan Nirankar Ji! हमारे special Bal Samagam में welcome! 🎊 यह बहुत fun होगा! Mujhse कुछ भी पूछिए!",
                "🎈 Dhan Nirankar Ji, mere dear friend! Bal Samagam 2025 में welcome! 🎭 Main यहां आपकी learning में help करने के लिए हूं!"
            ],
            'manglish': [
                "🎉 Dhan Nirankar Ji! Bal Samagam मध्ये तुमचे welcome आहे! 🎪 तुम्ही इथे आहात याची मला खूप excitement आहे, little saint! तुम्हाला काय जाणून घ्यायचे आहे?",
                "🌟 Dhan Nirankar Ji! आमच्या special Bal Samagam मध्ये welcome! 🎊 हे खूप fun होणार आहे! मला काहीही विचारा!",
                "🎈 Dhan Nirankar Ji, माझ्या dear friend! Bal Samagam 2025 मध्ये welcome! 🎭 मी इथे तुम्हाला learning मध्ये help करण्यासाठी आहे!"
            ]
        }
        
        # Language detection patterns
        self.language_patterns = {
            'hi': ['कि', 'है', 'में', 'का', 'की', 'को', 'से', 'पर', 'और', 'या', 'हूं', 'हैं', 'था', 'थी', 'गया', 'गई'],
            'mr': ['आहे', 'आहेत', 'मध्ये', 'ला', 'ची', 'चा', 'चे', 'ने', 'वर', 'आणि', 'किंवा', 'होते', 'होता', 'गेला', 'गेली'],
            'hinglish': ['main', 'mujhe', 'kya', 'hai', 'hoon', 'kaise', 'kahan', 'kyun'],
            'manglish': ['mala', 'tumhala', 'kay', 'kase', 'kuthe', 'ka']
        }
        
        # Multi-language knowledge base
        self.bal_samagam_knowledge = {
            'en': """
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
            """,
            
            'hi': """
            बाल समागम - बच्चों के लिए विशेष कार्यक्रम! 🎪
            
            बाल समागम क्या है?
            🎉 एक मजेदार सभा जहां आप जैसे बच्चे भगवान के बारे में सीखने और अद्भुत गतिविधियां करने के लिए आते हैं!
            🎭 बच्चे भजन गाते हैं, भाषण देते हैं, नाटक करते हैं, कहानियां सुनाते हैं और खेल खेलते हैं
            🌟 यह बच्चों को आत्मविश्वास बढ़ाने और आध्यात्मिक मूल्य सीखने में मदद करता है
            🤗 युवा संत एक-दूसरे से जुड़ते हैं और हमारे बड़े आध्यात्मिक परिवार का हिस्सा महसूस करते हैं
            
            मुख्य शिक्षाएं:
            🙏 "धन निरंकार जी" - हमारा विशेष अभिवादन जिसका अर्थ है "निराकार भगवान धन्य हैं"
            ❤ सेवा - बिना कुछ अपेक्षा के दूसरों की मदद करना
            💭 सिमरन - अपने दिल में भगवान को याद रखना ("तू ही निरंकार")
            👨‍👩‍👧‍👦 सत्संग - अच्छी बातें सीखने के लिए एक साथ आना
            🌍 विश्वबंधुत्व - हम सभी भगवान के अधीन एक बड़ा परिवार हैं
            """,
            
            'mr': """
            बाल समागम - मुलांसाठी विशेष कार्यक्रम! 🎪
            
            बाल समागम म्हणजे काय?
            🎉 एक मजेदार सभा जिथे तुमच्यासारखी मुले भगवानाबद्दल शिकण्यासाठी आणि अद्भुत क्रियाकलाप करण्यासाठी एकत्र येतात!
            🎭 मुले भजन गातात, भाषणे देतात, नाटके करतात, कथा सांगतात आणि खेळ खेळतात
            🌟 हे मुलांना आत्मविश्वास वाढवण्यात आणि आध्यात्मिक मूल्ये शिकण्यात मदत करते
            🤗 तरुण संत एकमेकांशी जुळून राहतात आणि आमच्या मोठ्या आध्यात्मिक कुटुंबाचा भाग वाटतात
            
            मुख्य शिकवणी:
            🙏 "धन निरंकार जी" - आमचे विशेष अभिवादन ज्याचा अर्थ "निराकार भगवान धन्य आहेत"
            ❤ सेवा - काहीही अपेक्षा न ठेवता इतरांची मदत करणे
            💭 सिमरन - आपल्या हृदयात भगवानाला लक्षात ठेवणे ("तू ही निरंकार")
            👨‍👩‍👧‍👦 सत्संग - चांगल्या गोष्टी शिकण्यासाठी एकत्र येणे
            🌍 जागतिक बंधुत्व - आपण सर्व भगवानाच्या अधीन एक मोठे कुटुंब आहोत
            """,
            
            'hinglish': """
            BAL SAMAGAM - बच्चों के लिए SPECIAL EVENT! 🎪
            
            Bal Samagam क्या है?
            🎉 एक बहुत fun gathering जहां आप जैसे kids भगवान के बारे में सीखने और amazing activities करने आते हैं!
            🎭 Kids bhajan गाते हैं, speeches देते हैं, skits perform करते हैं, stories बताते हैं और games खेलते हैं
            🌟 यह children को confidence बढ़ाने और spiritual values सीखने में help करता है
            🤗 Young saints एक-दूसरे से bond करते हैं और हमारे big spiritual family का part feel करते हैं
            
            Main Teachings:
            🙏 "Dhan Nirankar Ji" - हमारा special greeting जिसका meaning है "Blessed is the Formless God"
            ❤ Sewa - बिना कुछ expect किए others की help करना
            💭 Simran - अपने heart में God को remember रखना ("Tu Hi Nirankar")
            👨‍👩‍👧‍👦 Satsang - अच्छी बातें सीखने के लिए together आना
            🌍 Universal Brotherhood - हम सब God के under एक big family हैं
            """,
            
            'manglish': """
            BAL SAMAGAM - मुलांसाठी SPECIAL EVENT! 🎪
            
            Bal Samagam म्हणजे काय?
            🎉 एक खूप fun gathering जिथे तुमच्यासारखी kids भगवानाबद्दल शिकण्यासाठी आणि amazing activities करण्यासाठी येतात!
            🎭 Kids bhajan गातात, speeches देतात, skits perform करतात, stories सांगतात आणि games खेळतात
            🌟 हे children ला confidence वाढवण्यात आणि spiritual values शिकण्यात help करते
            🤗 Young saints एकमेकांशी bond करतात आणि आमच्या big spiritual family चा part feel करतात
            
            Main Teachings:
            🙏 "Dhan Nirankar Ji" - आमचे special greeting ज्याचा meaning आहे "Blessed is the Formless God"
            ❤ Sewa - काहीही expect न करता others ची help करणे
            💭 Simran - आपल्या heart मध्ये God ला remember ठेवणे ("Tu Hi Nirankar")
            👨‍👩‍👧‍👦 Satsang - चांगल्या गोष्टी शिकण्यासाठी together येणे
            🌍 Universal Brotherhood - आपण सर्व God च्या under एक big family आहोत
            """
        }
        
        # Multi-language response patterns
        self.response_patterns = {
            'en': {
                'god': "Dhan Nirankar Ji! 🙏 God is everywhere - in you, me, your friends, even in trees and animals! God is formless, which means He doesn't have a body like us, but His love fills everything! 💕",
                'sewa': "Dhan Nirankar Ji! 🙏 Sewa means helping others with a happy heart! Like when you help mama with dishes or share your toys with friends - that's Sewa! 🌟",
                'simran': "Dhan Nirankar Ji! 🙏 Simran means keeping God as your best friend in your heart! You can remember God while playing, studying, or even eating ice cream! 😄"
            },
            'hi': {
                'god': "धन निरंकार जी! 🙏 भगवान हर जगह हैं - आप में, मुझमें, आपके दोस्तों में, यहां तक कि पेड़ों और जानवरों में भी! भगवान निराकार हैं, यानी उनका हमारे जैसा शरीर नहीं है, लेकिन उनका प्यार सब कुछ भर देता है! 💕",
                'sewa': "धन निरंकार जी! 🙏 सेवा का मतलब है खुशी से दूसरों की मदद करना! जैसे जब आप मम्मी के बर्तन धोने में मदद करते हैं या दोस्तों के साथ अपने खिलौने साझा करते हैं - यही सेवा है! 🌟",
                'simran': "धन निरंकार जी! 🙏 सिमरन का मतलब है भगवान को अपने दिल में अपना सबसे अच्छा दोस्त बनाकर रखना! आप खेलते समय, पढ़ते समय, या आइसक्रीम खाते समय भी भगवान को याद कर सकते हैं! 😄"
            },
            'mr': {
                'god': "धन निरंकार जी! 🙏 भगवान सर्वत्र आहेत - तुमच्यामध्ये, माझ्यामध्ये, तुमच्या मित्रांमध्ये, अगदी झाडे आणि प्राण्यांमध्येही! भगवान निराकार आहेत, म्हणजे त्यांचे आमच्यासारखे शरीर नाही, पण त्यांचे प्रेम सर्वकाही भरून टाकते! 💕",
                'sewa': "धन निरंकार जी! 🙏 सेवा म्हणजे आनंदाने इतरांची मदत करणे! जसे तुम्ही आईला भांडी धुण्यात मदत करता किंवा मित्रांसोबत तुमची खेळणी शेअर करता - तेच सेवा आहे! 🌟",
                'simran': "धन निरंकार जी! 🙏 सिमरन म्हणजे भगवानाला तुमच्या हृदयात तुमचा सर्वात चांगला मित्र म्हणून ठेवणे! तुम्ही खेळताना, अभ्यास करताना किंवा आईस्क्रीम खाताना देखील भगवानाला लक्षात ठेवू शकता! 😄"
            },
            'hinglish': {
                'god': "Dhan Nirankar Ji! 🙏 भगवान everywhere हैं - आप में, मुझमें, आपके friends में, यहां तक कि trees और animals में भी! God निराकार हैं, मतलब उनका हमारे जैसा body नहीं है, but उनका love सब कुछ fill करता है! 💕",
                'sewa': "Dhan Nirankar Ji! 🙏 Sewa का मतलब है खुशी से others की help करना! जैसे जब आप mama के dishes में help करते हैं या friends के साथ toys share करते हैं - यही Sewa है! 🌟",
                'simran': "Dhan Nirankar Ji! 🙏 Simran का मतलब है God को अपने heart में अपना best friend बनाकर रखना! आप playing, studying, या ice cream खाते time भी God को remember कर सकते हैं! 😄"
            },
            'manglish': {
                'god': "Dhan Nirankar Ji! 🙏 भगवान everywhere आहेत - तुमच्यामध्ये, माझ्यामध्ये, तुमच्या friends मध्ये, अगदी trees आणि animals मध्येही! God निराकार आहेत, म्हणजे त्यांचे आमच्यासारखे body नाही, but त्यांचे love सर्वकाही fill करते! 💕",
                'sewa': "Dhan Nirankar Ji! 🙏 Sewa म्हणजे आनंदाने others ची help करणे! जसे तुम्ही mama ला dishes मध्ये help करता किंवा friends सोबत toys share करता - तेच Sewa आहे! 🌟",
                'simran': "Dhan Nirankar Ji! 🙏 Simran म्हणजे God ला तुमच्या heart मध्ये तुमचा best friend म्हणून ठेवणे! तुम्ही playing, studying, किंवा ice cream खाताना देखील God ला remember करू शकता! 😄"
            }
        }
    
    def detect_language(self, text):
        """Detect the language of input text"""
        text_lower = text.lower()
        
        # Count matches for each language
        scores = {}
        for lang, patterns in self.language_patterns.items():
            score = sum(1 for pattern in patterns if pattern in text_lower)
            scores[lang] = score
        
        # Also check for English (default if no other language detected)
        english_patterns = ['the', 'and', 'is', 'are', 'what', 'how', 'why', 'when', 'where']
        scores['en'] = sum(1 for pattern in english_patterns if pattern in text_lower)
        
        # Return language with highest score, default to current language if tie
        if max(scores.values()) > 0:
            detected = max(scores, key=scores.get)
            return detected
        
        return self.current_language
    
    def get_system_prompt(self, language):
        """Get system prompt in specified language"""
        prompts = {
            'en': f"""
            You are "Guru Ji's Little Helper" 🤖, a loving chatbot for kids attending Bal Samagam of Sant Nirankari Mission.
            
            RESPOND IN ENGLISH ONLY.
            
            PERSONALITY:
            - Always start with "Dhan Nirankar Ji! 🙏"
            - Super friendly, like a big brother/sister
            - Use simple English words for 5-12 year olds
            - Keep answers short and fun (2-3 sentences)
            - Use emojis 😊🎉🌟
            - Give relatable examples
            - Always be encouraging and positive
            
            KNOWLEDGE BASE:
            {self.bal_samagam_knowledge['en']}
            """,
            
            'hi': f"""
            आप "गुरु जी के छोटे सहायक" 🤖 हैं, संत निरंकारी मिशन के बाल समागम में आने वाले बच्चों के लिए एक प्यारे चैटबॉट हैं।
            
            केवल हिंदी में जवाब दें।
            
            व्यक्तित्व:
            - हमेशा "धन निरंकार जी! 🙏" से शुरू करें
            - बहुत दोस्ताना, बड़े भाई/बहन की तरह
            - 5-12 साल के बच्चों के लिए सरल हिंदी शब्दों का उपयोग करें
            - जवाब छोटे और मजेदार रखें (2-3 वाक्य)
            - इमोजी का उपयोग करें 😊🎉🌟
            - समझने योग्य उदाहरण दें
            - हमेशा उत्साहजनक और सकारात्मक रहें
            
            ज्ञान आधार:
            {self.bal_samagam_knowledge['hi']}
            """,
            
            'mr': f"""
            तुम्ही "गुरु जींचे छोटे सहाय्यक" 🤖 आहात, संत निरंकारी मिशनच्या बाल समागमात येणाऱ्या मुलांसाठी एक प्रेमळ चॅटबॉट आहात.
            
            फक्त मराठीत उत्तर द्या.
            
            व्यक्तिमत्व:
            - नेहमी "धन निरंकार जी! 🙏" ने सुरुवात करा
            - खूप मैत्रीपूर्ण, मोठ्या भाऊ/बहिणीसारखे
            - 5-12 वर्षांच्या मुलांसाठी सोप्या मराठी शब्दांचा वापर करा
            - उत्तरे लहान आणि मजेदार ठेवा (2-3 वाक्ये)
            - इमोजी वापरा 😊🎉🌟
            - समजण्यासारखी उदाहरणे द्या
            - नेहमी उत्साहवर्धक आणि सकारात्मक राहा
            
            ज्ञान आधार:
            {self.bal_samagam_knowledge['mr']}
            """,
            
            'hinglish': f"""
            आप "Guru Ji के Little Helper" 🤖 हैं, Sant Nirankari Mission के Bal Samagam में आने वाले kids के लिए एक loving chatbot हैं।
            
            HINGLISH (Hindi + English MIX) में respond करें।
            
            PERSONALITY:
            - हमेशा "Dhan Nirankar Ji! 🙏" से start करें
            - बहुत friendly, big brother/sister की तरह
            - 5-12 साल के बच्चों के लिए simple Hinglish words use करें
            - Answers short और fun रखें (2-3 sentences)
            - Emojis use करें 😊🎉🌟
            - Relatable examples दें
            - हमेशा encouraging और positive रहें
            
            KNOWLEDGE BASE:
            {self.bal_samagam_knowledge['hinglish']}
            """,
            
            'manglish': f"""
            तुम्ही "Guru Ji चे Little Helper" 🤖 आहात, Sant Nirankari Mission च्या Bal Samagam मध्ये येणाऱ्या kids साठी एक loving chatbot आहात.
            
            MANGLISH (Marathi + English MIX) मध्ये respond करा.
            
            PERSONALITY:
            - नेहमी "Dhan Nirankar Ji! 🙏" ने start करा
            - खूप friendly, big brother/sister सारखे
            - 5-12 वर्षांच्या मुलांसाठी simple Manglish words use करा
            - Answers short आणि fun ठेवा (2-3 sentences)
            - Emojis use करा 😊🎉🌟
            - Relatable examples द्या
            - नेहमी encouraging आणि positive राहा
            
            KNOWLEDGE BASE:
            {self.bal_samagam_knowledge['manglish']}
            """
        }
        
        return prompts.get(language, prompts['en'])
    
    def call_mistral_api(self, user_message, language, conversation_history=[]):
        """Call Mistral API with language-specific context"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.mistral_api_key}"
        }
        
        messages = [{"role": "system", "content": self.get_system_prompt(language)}]
        
        # Add conversation history
        for msg in conversation_history[-6:]:
            messages.append(msg)
        
        messages.append({"role": "user", "content": user_message})
        
        payload = {
            "model": "mistral-medium",
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.8
        }
        
        try:
            response = requests.post(self.mistral_api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            print(f"API Error: {e}")
            return self.get_fallback_response(user_message, language)
    
    def get_fallback_response(self, user_message, language):
        """Language-specific fallback responses"""
        message_lower = user_message.lower()
        
        # Greeting responses
        if any(word in message_lower for word in ['hello', 'hi', 'namaste', 'hey', 'नमस्ते', 'हॅलो']):
            return random.choice(self.welcome_messages[language])
        
        # God/spiritual questions
        elif any(word in message_lower for word in ['god', 'भगवान', 'निरंकार', 'nirankar']):
            return self.response_patterns[language]['god']
        
        elif any(word in message_lower for word in ['sewa', 'सेवा', 'help', 'मदद']):
            return self.response_patterns[language]['sewa']
        
        elif any(word in message_lower for word in ['simran', 'सिमरन', 'prayer', 'प्रार्थना']):
            return self.response_patterns[language]['simran']
        
        # Default response by language
        defaults = {
            'en': "Dhan Nirankar Ji! 🙏 That's such a great question! You're so smart for asking! 🌟 Can you tell me more about what you're thinking? I love learning with you! 🤗",
            'hi': "धन निरंकार जी! 🙏 यह बहुत अच्छा सवाल है! आप पूछने के लिए बहुत होशियार हैं! 🌟 क्या आप मुझे और बता सकते हैं कि आप क्या सोच रहे हैं? मुझे आपके साथ सीखना अच्छा लगता है! 🤗",
            'mr': "धन निरंकार जी! 🙏 हा खूप छान प्रश्न आहे! तुम्ही विचारण्यासाठी खूप हुशार आहात! 🌟 तुम्ही काय विचार करत आहात ते मला अधिक सांगू शकता का? मला तुमच्यासोबत शिकायला आवडते! 🤗",
            'hinglish': "Dhan Nirankar Ji! 🙏 यह बहुत great question है! आप पूछने के लिए बहुत smart हैं! 🌟 क्या आप मुझे और बता सकते हैं कि आप क्या think कर रहे हैं? मुझे आपके साथ learning अच्छा लगता है! 🤗",
            'manglish': "Dhan Nirankar Ji! 🙏 हा खूप great question आहे! तुम्ही विचारण्यासाठी खूप smart आहात! 🌟 तुम्ही काय think करत आहात ते मला अधिक सांगू शकता का? मला तुमच्यासोबत learning आवडते! 🤗"
        }
        
        return defaults.get(language, defaults['en'])
    
    # def choose_language(self):
    #     """Interactive language selection"""
    #     print("\n" + "="*60)
    #     print("🌍 भाषा निवडा / Choose Language / भाषा चुनें")
    #     print("="*60)
    #     print("1. English 🇬🇧")
    #     print("2. हिंदी (Hindi) 🇮🇳") 
    #     print("3. मराठी (Marathi) 🇮🇳")
    #     print("4. Hinglish (Hindi + English) 🔀")
    #     print("5. Manglish (Marathi + English) 🔀")
    #     print("6. Auto-detect from my messages 🤖")
    #     print("-"*60)
        
    #     while True:
    #         try:
    #             choice = input("आपकी पसंद / Your choice / तुमची निवड (1-6): ").strip()
                
    #             if choice == '1':
    #                 self.current_language = 'en'
    #                 print("✅ Language set to English!")
    #                 break
    #             elif choice == '2':
    #                 self.current_language = 'hi'
    #                 print("✅ भाषा हिंदी में सेट की गई!")
    #                 break
    #             elif choice == '3':
    #                 self.current_language = 'mr'
    #                 print("✅ भाषा मराठीत सेट केली!")
    #                 break
    #             elif choice == '4':
    #                 self.current_language = 'hinglish'
    #                 print("✅ Language set to Hinglish!")
    #                 break
    #             elif choice == '5':
    #                 self.current_language = 'manglish'
    #                 print("✅ Language set to Manglish!")
    #                 break
    #             elif choice == '6':
    #                 self.current_language = 'en'  # Default, will auto-detect
    #                 print("✅ Auto-detection enabled! I'll respond in the language you use!")
    #                 break
    #             else:
    #                 print("❌ कृपया 1-6 में से चुनें / Please choose 1-6 / कृपया 1-6 मधून निवडा")
    #         except KeyboardInterrupt:
    #             print("\n👋 धन्यवाद! / Thank you! / धन्यवाद!")
    #             return False
        
    #     return True
  
    def choose_language(self, default="auto"):
        """
        Set default language mode.
        Options: en, hi, mr, hinglish, manglish, auto
        Default = auto-detect
        """
        valid_choices = ["en", "hi", "mr", "hinglish", "manglish", "auto"]

        if default not in valid_choices:
            default = "auto"

        if default == "en":
            self.current_language = "en"
        elif default == "hi":
            self.current_language = "hi"
        elif default == "mr":
            self.current_language = "mr"
        elif default == "hinglish":
            self.current_language = "hinglish"
        elif default == "manglish":
            self.current_language = "manglish"
        else:
            self.current_language = "en"   # default language base
            self.auto_detect = True        # flag to enable auto detection

        return self.current_language

    
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
        """Get history for one user."""
        return self.all_sessions.get(user_id, [])

    def update_user_history(self, user_id, role, content):
        """Add new message to user's history and save."""
        if user_id not in self.all_sessions:
            self.all_sessions[user_id] = []
        self.all_sessions[user_id].append({"role": role, "content": content})
        self._save_all_sessions()
        
    def load_history(self):
        """Load all chat histories (for backward compatibility)."""
        return self._load_all_sessions()

    def save_history(self, history):
        """Save all chat histories (for backward compatibility)."""
        self.all_sessions = history
        self._save_all_sessions()

        # ---------- Chat Function ----------
    def chat(self, session_id: str, user_message: str) -> str:
        """
        Handles a chat message for a given session (sid).
        Keeps track of history per user/session inside one JSON file.
        """
        history = self.load_history()

        # Ensure session exists
        if session_id not in history:
            history[session_id] = []

        # Append user message
        history[session_id].append({"role": "user", "content": user_message})

        # Add user message to persistent history
        self.update_user_history(session_id, "user", user_message)

        # Detect language if auto-detect is enabled
        if self.auto_detect:
            self.current_language = self.detect_language(user_message)

        # Get conversation history (last 6 turns max)
        conversation_history = self.get_user_history(session_id)
        

        # Call Mistral API via helper function
        try:
            bot_reply = self.call_mistral_api(
                user_message,
                self.current_language,
                conversation_history
            )
        except Exception as e:
            print(f"API Error: {e}")
            bot_reply = self.get_fallback_response(user_message, self.current_language)

        # Save bot reply
        self.update_user_history(session_id, "assistant", bot_reply)

        return bot_reply

    def start_conversation(self):
        """Start the interactive multi-language chat session"""
        print("\n" + "="*70)
        print("🎪✨ WELCOME TO BAL SAMAGAM 2025! ✨🎪")
        print("🤖 Guru Ji's Little Helper Bot (Multi-Language)")
        print("="*70)
        
        if not self.choose_language():
            return
        
        print(f"\n{random.choice(self.welcome_messages[self.current_language])}")
        
        # Multi-language help text
        help_texts = {
            'en': """
💡 You can ask me about:
   🙏 Spiritual questions (God, prayer, Sewa)
   🎪 Bal Samagam activities and fun
   🏫 School and friend problems
   👨‍👩‍👧‍👦 Family and daily life
   😊 Anything that's on your mind!

📝 Type 'bye' to end our chat
🌍 Type 'lang' to change language""",
            'hi': """
💡 आप मुझसे पूछ सकते हैं:
   🙏 आध्यात्मिक प्रश्न (भगवान, प्रार्थना, सेवा)
   🎪 बाल समागम गतिविधियां और मज़ा
   🏫 स्कूल और दोस्त की समस्याएं
   👨‍👩‍👧‍👦 परिवार और दैनिक जीवन
   😊 जो भी आपके मन में है!

📝 चैट समाप्त करने के लिए 'bye' टाइप करें
🌍 भाषा बदलने के लिए 'lang' टाइप करें""",
            'mr': """
💡 तुम्ही मला विचारू शकता:
   🙏 आध्यात्मिक प्रश्न (भगवान, प्रार्थना, सेवा)
   🎪 बाल समागम क्रियाकलाप आणि मजा
   🏫 शाळा आणि मित्रांच्या समस्या
   👨‍👩‍👧‍👦 कुटुंब आणि दैनंदिन जीवन
   😊 जे काही तुमच्या मनात आहे!

📝 चॅट संपवण्यासाठी 'bye' टाइप करा
🌍 भाषा बदलण्यासाठी 'lang' टाइप करा""",
            'hinglish': """
💡 आप मुझसे पूछ सकते हैं:
   🙏 Spiritual questions (God, prayer, Sewa)
   🎪 Bal Samagam activities और fun
   🏫 School और friend problems
   👨‍👩‍👧‍👦 Family और daily life
   😊 जो भी आपके mind में है!

📝 Chat end करने के लिए 'bye' type करें
🌍 Language change करने के लिए 'lang' type करें""",
            'manglish': """
💡 तुम्ही मला विचारू शकता:
   🙏 Spiritual questions (God, prayer, Sewa)
   🎪 Bal Samagam activities आणि fun
   🏫 School आणि friend problems
   👨‍👩‍👧‍👦 Family आणि daily life
   😊 जे काही तुमच्या mind मध्ये आहे!

📝 Chat end करण्यासाठी 'bye' type करा
🌍 Language change करण्यासाठी 'lang' type करा"""
        }
        
        print(help_texts[self.current_language])
        print("-"*70)
        
        conversation_history = []
        
        while True:
            try:
                user_input = input(f"\n🧒 आप/You/तुम्ही: ").strip()
                
                if not user_input:
                    responses = {
                        'en': "🤖 Bot: Dhan Nirankar Ji! 🙏 I'm waiting for your question! Don't be shy! 😊",
                        'hi': "🤖 Bot: धन निरंकार जी! 🙏 मैं आपके सवाल का इंतज़ार कर रहा हूं! शर्माइए मत! 😊",
                        'mr': "🤖 Bot: धन निरंकार जी! 🙏 मी तुमच्या प्रश्नाची वाट पाहत आहे! लाजू नका! 😊",
                        'hinglish': "🤖 Bot: Dhan Nirankar Ji! 🙏 मैं आपके question का wait कर रहा हूं! Shy मत होइए! 😊",
                        'manglish': "🤖 Bot: Dhan Nirankar Ji! 🙏 मी तुमच्या question ची wait करत आहे! Shy होऊ नका! 😊"
                    }
                    print(responses[self.current_language])
                    continue
                
                # Check for language change command
                if user_input.lower() == 'lang':
                    if self.choose_language():
                        print(f"\n{random.choice(self.welcome_messages[self.current_language])}")
                    continue
                
                # Check for exit commands
                if user_input.lower() in ['bye', 'goodbye', 'exit', 'quit', 'बाय', 'अलविदा', 'बाय बाय']:
                    exit_messages = {
                        'en': "🤖 Bot: Dhan Nirankar Ji! 🙏 It was SO much fun talking with you! Keep being amazing and enjoy Bal Samagam! See you later, little saint! 🌟👋",
                        'hi': "🤖 Bot: धन निरंकार जी! 🙏 आपसे बात करके बहुत मज़ा आया! आप हमेशा अच्छे रहिए और बाल समागम का आनंद लीजिए! फिर मिलेंगे, छोटे संत! 🌟👋",
                        'mr': "🤖 Bot: धन निरंकार जी! 🙏 तुमच्याशी बोलून खूप मजा आली! तुम्ही नेहमी चांगले राहा आणि बाल समागमचा आनंद घ्या! पुन्हा भेटू, लहान संत! 🌟👋",
                        'hinglish': "🤖 Bot: Dhan Nirankar Ji! 🙏 आपसे talk करके बहुत fun आया! आप हमेशा amazing रहिए और Bal Samagam enjoy कीजिए! See you later, little saint! 🌟👋",
                        'manglish': "🤖 Bot: Dhan Nirankar Ji! 🙏 तुमच्याशी talk करून खूप fun आली! तुम्ही नेहमी amazing राहा आणि Bal Samagam enjoy करा! See you later, little saint! 🌟👋"
                    }
                    print(f"\n{exit_messages[self.current_language]}")
                    break
                
                # Auto-detect language if set to auto-detect
                if self.current_language == 'en' and len(conversation_history) < 2:
                    detected_lang = self.detect_language(user_input)
                    if detected_lang != 'en':
                        self.current_language = detected_lang
                        print(f"🤖 Language detected: {self.languages[detected_lang]} / भाषा पहचानी गई")
                
                # Get response from API or fallback
                response = self.call_mistral_api(user_input, self.current_language, conversation_history)
                
                print(f"\n🤖 Bot: {response}")
                
                # Update conversation history
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})
                
                # Keep only recent conversation
                if len(conversation_history) > 12:
                    conversation_history = conversation_history[-12:]
                
            except KeyboardInterrupt:
                exit_messages = {
                    'en': "🤖 Bot: Dhan Nirankar Ji! 🙏 Thanks for chatting with me! Have fun at Bal Samagam! 🎉",
                    'hi': "🤖 Bot: धन निरंकार जी! 🙏 मुझसे बात करने के लिए धन्यवाद! बाल समागम का मज़ा लीजिए! 🎉",
                    'mr': "🤖 Bot: धन निरंकार जी! 🙏 माझ्याशी बोलल्याबद्दल धन्यवाद! बाल समागमचा आनंद घ्या! 🎉",
                    'hinglish': "🤖 Bot: Dhan Nirankar Ji! 🙏 मुझसे chat करने के लिए thanks! Bal Samagam का fun लीजिए! 🎉",
                    'manglish': "🤖 Bot: Dhan Nirankar Ji! 🙏 माझ्याशी chat केल्याबद्दल thanks! Bal Samagam चा fun घ्या! 🎉"
                }
                print(f"\n\n{exit_messages[self.current_language]}")
                break
            except Exception as e:
                error_messages = {
                    'en': "🤖 Bot: Dhan Nirankar Ji! 🙏 Oops, something went wrong, but I'm still here to help! 😊",
                    'hi': "🤖 Bot: धन निरंकार जी! 🙏 ओह, कुछ गलत हो गया, लेकिन मैं अभी भी आपकी मदद के लिए यहां हूं! 😊",
                    'mr': "🤖 Bot: धन निरंकार जी! 🙏 अरे, काहीतरी चूक झाली, पण मी अजूनही तुमच्या मदतीसाठी इथे आहे! 😊",
                    'hinglish': "🤖 Bot: Dhan Nirankar Ji! 🙏 Oops, कुछ wrong हो गया, but मैं अभी भी आपकी help के लिए यहां हूं! 😊",
                    'manglish': "🤖 Bot: Dhan Nirankar Ji! 🙏 Oops, काहीतरी wrong झाले, but मी अजूनही तुमच्या help साठी इथे आहे! 😊"
                }
                print(f"\n{error_messages[self.current_language]}")
    
    def chat_once(self, message, language='en'):
        """Single message chat with language specification"""
        return self.call_mistral_api(message, language)
    
    def get_language_examples(self):
        """Get example conversations in different languages"""
        examples = {
            'English': {
                'input': "What is Bal Samagam?",
                'output': "Dhan Nirankar Ji! 🎉 Bal Samagam is the most fun event ever! We sing, dance, tell stories, and learn about God together! Are you excited? I am! 🎪"
            },
            'Hindi': {
                'input': "सेवा क्या है?",
                'output': "धन निरंकार जी! 🙏 सेवा का मतलब है खुशी से दूसरों की मदद करना! जैसे जब आप मम्मी के बर्तन धोने में मदद करते हैं या दोस्तों के साथ अपने खिलौने साझा करते हैं - यही सेवा है! 🌟"
            },
            'Marathi': {
                'input': "सिमरन म्हणजे काय?",
                'output': "धन निरंकार जी! 🙏 सिमरन म्हणजे भगवानाला तुमच्या हृदयात तुमचा सर्वात चांगला मित्र म्हणून ठेवणे! तुम्ही खेळताना, अभ्यास करताना किंवा आईस्क्रीम खाताना देखील भगवानाला लक्षात ठेवू शकता! 😄"
            },
            'Hinglish': {
                'input': "Main school में अपने friends के साथ कैसे peace spread करूं?",
                'output': "Dhan Nirankar Ji! 🙏 School में आप सबके साथ friendly रहकर, classmates की help करके, और fight नहीं करके peace spread कर सकते हैं! Sun की तरह बनो - सबको happy feel कराओ! ☀"
            },
            'Manglish': {
                'input': "मला Bal Samagam मध्ये perform करायला nervous वाटतं",
                'output': "Dhan Nirankar Ji! 🙏 Nervous feel करणे normal आहे! But remember, इथे सगळे तुम्हाला family सारखे love करतात! Deep breaths घ्या आणि know करा कि God तुमच्यासोबत आहे! 🌟"
            }
        }
        return examples

def main():
    """Main function to run the multi-language chatbot"""
    print("🚀 Starting Multi-Language Bal Samagam Kids Chatbot...")
    
    # Check if API key is set
    if not os.getenv('MISTRAL_API_KEY') or os.getenv('MISTRAL_API_KEY') == 'your-mistral-api-key-here':
        print("⚠  Warning: Mistral API key not set. Using fallback responses only.")
        print("💡 To use AI responses, set: export MISTRAL_API_KEY=your_actual_key")
        input("Press Enter to continue with basic responses...")
    
    # Initialize and start chatbot
    chatbot = MultiLanguageBalSamagamChatbot()
    chatbot.start_conversation()

if __name__ == "__main__":
    main()

# Example usage for integration:
# 
# from multi_lang_bal_samagam_chatbot import MultiLanguageBalSamagamChatbot
# 
# chatbot = MultiLanguageBalSamagamChatbot()
# 
# # Chat in specific language
# response_english = chatbot.chat_once("What is Sewa?", "en")
# response_hindi = chatbot.chat_once("सेवा क्या है?", "hi")
# response_marathi = chatbot.chat_once("सेवा म्हणजे काय?", "mr")
# 
# # Get example conversations
# examples = chatbot.get_language_examples()
# print(examples)