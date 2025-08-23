import requests
import json
import os
import random
import redis
import re
from datetime import datetime

class BloodDonationChatbot:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True  # store strings, not bytes
        )
        
        # Mistral API configuration
        api_keys_env = os.getenv('MISTRAL_API_KEYS') or os.getenv('MISTRAL_API_KEY')
        if api_keys_env:
            self.mistral_api_keys = [k.strip() for k in api_keys_env.split(',') if k.strip()]
        else:
            self.mistral_api_keys = [
                "3OyOnjAypy79EewldzfcBczW01mET0fM",
                "tZKRscT6hDUurE5B7ex5j657ZZQDQw3P",
                "dvXrS6kbeYxqBGXR35WzM0zMs4Nrbco2",
                "5jMPffjLAwLyyuj6ZwFHhbLZxb2TyfUR",
                "LY1MwjaPpQnvApjHW0p7pgexEHvhK9Ew"
            ]
        self.mistral_api_url = "https://api.mistral.ai/v1/chat/completions"
        self._api_key_index = 0
        
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
                "🩸 Welcome to the Blood Donation Assistant! 💉 I'm here to help you with all your blood donation questions. How can I assist you today?",
                "❤️ Hello! I'm your friendly blood donation helper. Ask me anything about donating blood, eligibility, or finding donation centers!",
                "🌟 Welcome! Thank you for your interest in blood donation. I can answer your questions and help you save lives through donation!"
            ],
            'hi': [
                "🩸 रक्तदान सहायक में आपका स्वागत है! 💉 मैं आपके सभी रक्तदान संबंधी प्रश्नों में आपकी सहायता के लिए यहां हूं। आज मैं आपकी कैसे मदद कर सकता हूं?",
                "❤️ नमस्ते! मैं आपका मित्रवत रक्तदान सहायक हूं। रक्तदान, पात्रता, या दान केंद्रों को खोजने के बारे में मुझसे कुछ भी पूछें!",
                "🌟 स्वागत है! रक्तदान में आपकी रुचि के लिए धन्यवाद। मैं आपके प्रश्नों का उत्तर दे सकता हूं और दान के माध्यम से जीवन बचाने में आपकी मदद कर सकता हूं!"
            ],
            'mr': [
                "🩸 रक्तदान सहाय्यकात तुमचे स्वागत आहे! 💉 मी तुमच्या सर्व रक्तदानासंबंधीच्या प्रश्नांमध्ये मदत करण्यासाठी इथे आहे. आज मी तुमची कशी मदत करू शकतो?",
                "❤️ नमस्कार! मी तुमचा मैत्रीपूर्ण रक्तदान सहाय्यक आहे. रक्तदान, पात्रता किंवा दान केंद्रे शोधण्याबद्दल मला काहीही विचारा!",
                "🌟 स्वागत आहे! रक्तदानात तुमच्या स्वारस्याबद्दल धन्यवाद. मी तुमच्या प्रश्नांची उत्तरे देऊ शकतो आणि दानाद्वारे जीवन वाचवण्यात तुमची मदत करू शकतो!"
            ],
            'hinglish': [
                "🩸 Blood Donation Assistant में आपका welcome है! 💉 Main आपके सभी blood donation questions में help के लिए यहां हूं। आज main आपकी कैसे help कर सकta हूं?",
                "❤️ Hello! Main आपका friendly blood donation helper हूं। Blood donation, eligibility, ya donation centers के बारे में mujhse कुछ भी पूछिए!",
                "🌟 Welcome! Blood donation में आपकी interest के लिए thank you। Main आपके questions के answers दे सकta हूं aur donation के through lives बचाने में help कर सकta हूं!"
            ],
            'manglish': [
                "🩸 Blood Donation Assistant मध्ये तुमचे welcome आहे! 💉 मी तुमच्या सर्व blood donation questions मध्ये help करण्यासाठी इथे आहे. आज मी तुमची कशी help करू शकतो?",
                "❤️ Hello! मी तुमचा friendly blood donation helper आहे. Blood donation, eligibility, किंवा donation centers बद्दल मला काहीही विचारा!",
                "🌟 Welcome! Blood donation मध्ये तुमच्या interest साठी thank you. मी तुमच्या questions ची answers देऊ शकतो आणि donation द्वारे lives वाचवण्यात help करू शकतो!"
            ]
        }
        
        # Language detection patterns
        self.language_patterns = {
            'hi': ['कि', 'है', 'में', 'का', 'की', 'को', 'से', 'पर', 'और', 'या', 'हूं', 'हैं', 'था', 'थी', 'गया', 'गई'],
            'mr': ['आहे', 'आहेत', 'मध्ये', 'ला', 'ची', 'चा', 'चे', 'ने', 'वर', 'आणि', 'किंवा', 'होते', 'होता', 'गेला', 'गेली'],
            'hinglish': ['main', 'mujhe', 'kya', 'hai', 'hoon', 'kaise', 'kahan', 'kyun'],
            'manglish': ['mala', 'tumhala', 'kay', 'kase', 'kuthe', 'ka']
        }
        
        # Blood donation knowledge base
        self.blood_donation_knowledge = {
            'en': """
            BLOOD DONATION - SAVE LIVES! 🩸
            
            What is Blood Donation?
            💉 A voluntary procedure where a person donates blood to be used for transfusions
            ❤️ One donation can save up to three lives
            🌟 Blood cannot be manufactured; it can only come from volunteer donors
            
            Importance of Blood Donation:
            🏥 Essential for surgeries, cancer treatment, chronic illnesses, and traumatic injuries
            🔄 Blood has a limited shelf life (red cells: 42 days, platelets: 5-7 days)
            🤝 Regular donations are needed to maintain adequate supplies
            
            Eligibility Requirements:
            ✅ Age: 18-65 years (may vary by country)
            ✅ Weight: At least 50 kg (110 lbs)
            ✅ Hemoglobin: Minimum 12.5 g/dL for women, 13.0 g/dL for men
            ✅ Generally in good health on donation day
            
            Common Questions:
            ❓ How often can I donate? Whole blood: Every 56 days (3 months)
            ❓ Does it hurt? Only a brief pinch when the needle is inserted
            ❓ How long does it take? About 10 minutes for donation, 45-60 minutes total process
            ❓ Is it safe? Yes, sterile equipment is used only once
            
            After Donation:
            🥤 Drink plenty of fluids
            🍫 Have a snack if provided
            ⚠️ Avoid heavy lifting or strenuous exercise for 24 hours
            
            Sant Nirankari Mission Blood Donation:
            🙏 The mission organizes regular blood donation camps
            📅 First camp: 1986
            🏆 Millions of units collected to date
            🌍 Part of their humanitarian service initiatives
            """,
            
            'hi': """
            रक्तदान - जीवन बचाएं! 🩸
            
            रक्तदान क्या है?
            💉 एक स्वैच्छिक प्रक्रिया जहां एक व्यक्ति आधान के लिए रक्त दान करता है
            ❤️ एक दान तीन जीवन बचा सकता है
            🌟 रक्त निर्मित नहीं किया जा सकता; यह केवल स्वयंसेवक दाताओं से आ सकता है
            
            रक्तदान का महत्व:
            🏥 सर्जरी, कैंसर उपचार, पुरानी बीमारियों और आघात संबंधी चोटों के लिए आवश्यक
            🔄 रक्त की सीमित शेल्फ लाइफ होती है (लाल रक्त कोशिकाएं: 42 दिन, प्लेटलेट्स: 5-7 दिन)
            🤝 पर्याप्त आपूर्ति बनाए रखने के लिए नियमित दान की आवश्यकता होती है
            
            पात्रता आवश्यकताएँ:
            ✅ आयु: 18-65 वर्ष (देश के अनुसार भिन्न हो सकती है)
            ✅ वजन: कम से कम 50 किग्रा (110 पाउंड)
            ✅ हीमोग्लोबिन: महिलाओं के लिए न्यूनतम 12.5 g/dL, पुरुषों के लिए 13.0 g/dL
            ✅ दान के दिन आम तौर पर अच्छे स्वास्थ्य में
            
            सामान्य प्रश्न:
            ❓ मैं कितनी बार दान कर सकता हूं? संपूर्ण रक्त: हर 56 दिन (3 महीने)
            ❓ क्या यह दर्दनाक है? सुई लगाने पर केवल एक संक्षिप्त चुभन
            ❓ इसमें कितना समय लगता है? दान के लिए लगभग 10 मिनट, कुल प्रक्रिया 45-60 मिनट
            ❓ क्या यह सुरक्षित है? हां, बाँझ उपकरण का केवल एक बार उपयोग किया जाता है
            
            दान के बाद:
            🥤 खूब सारे तरल पदार्थ पिएं
            🍫 यदि प्रदान किया जाए तो नाश्ता करें
            ⚠️ 24 घंटे तक भारी उठाने या ज़ोरदार व्यायाम से बचें
            
            संत निरंकारी मिशन रक्तदान:
            🙏 मिशन नियमित रक्तदान शिविर आयोजित करता है
            📅 पहला शिविर: 1986
            🏆 अब तक लाखों यूनिट एकत्र की गई हैं
            🌍 उनके मानवीय सेवा पहलों का हिस्सा
            """,
            
            'mr': [
                "रक्तदान - जीवन वाचवा! 🩸",
                "",
                "रक्तदान म्हणजे काय?",
                "💉 एक स्वयंसेवक प्रक्रिया जिथे एखादी व्यक्ती रक्ताभिसरणासाठी रक्त दान करते",
                "❤️ एक दान तीन जीवने वाचवू शकते",
                "🌟 रक्त तयार केले जाऊ शकत नाही; ते केवळ स्वयंसेवक दात्यांकडूनच येऊ शकते",
                "",
                "रक्तदानाचे महत्व:",
                "🏥 शस्त्रक्रिया, कर्करोग उपचार, चिरकालिक आजार आणि आघाताद्वारे होणाऱ्या दुखापतींसाठी आवश्यक",
                "🔄 रक्ताची मर्यादित शेल्फ लाइफ असते (लाल पेशी: ४२ दिवस, प्लेटलेट्स: ५-७ दिवस)",
                "🤝 पुरेशा पुरवठ्यासाठी नियमित दान आवश्यक आहे",
                "",
                "पात्रता आवश्यकता:",
                "✅ वय: १८-६५ वर्षे (देशानुसार बदलू शकते)",
                "✅ वजन: किमान ५० किलो (११० पौंड)",
                "✅ हिमोग्लोबिन: महिलांसाठी किमान १२.५ g/dL, पुरुषांसाठी १३.० g/dL",
                "✅ दानाच्या दिवशी साधारणपणे चांगले आरोग्य",
                "",
                "सामान्य प्रश्न:",
                "❓ मी किती वेळा दान करू शकतो? संपूर्ण रक्त: दर ५६ दिवसांनी (३ महिने)",
                "❓ यात वेदना होते का? सुई टाकताना फक्त एक संक्षिप्त चटका",
                "❓ यास किती वेळ लागतो? दानासाठी सुमारे १० मिनिटे, एकूण प्रक्रिया ४५-६० मिनिटे",
                "❓ हे सुरक्षित आहे का? होय, निर्जंतुक उपकरणे फक्त एकदाच वापरली जातात",
                "",
                "दानानंतर:",
                "🥤 भरपूर द्रव प्या",
                "🍫 दिले असल्यास नाश्ता करा",
                "⚠️ २४ तासांसाठी जड वजन उचलणे किंवा तीव्र व्यायाम टाळा",
                "",
                "संत निरंकारी मिशन रक्तदान:",
                "🙏 मिशन नियमित रक्तदान शिबिरे आयोजित करते",
                "📅 पहिले शिबिर: १९८६",
                "🏆 आजपर्यंत लाखो युनिट्स गोळा केल्या आहेत",
                "🌍 त्यांच्या मानवतावादी सेवा उपक्रमांचा भाग"
            ],
            
            'hinglish': [
                "Blood Donation - Save Lives! 🩸",
                "",
                "Blood Donation kya hai?",
                "💉 Ek voluntary procedure jahan ek person transfusions ke liye blood donate karta hai",
                "❤️ Ek donation teen lives bacha sakta hai",
                "🌟 Blood manufacture nahi kiya ja sakta; yeh only volunteer donors se aa sakta hai",
                "",
                "Blood Donation ka importance:",
                "🏥 Surgeries, cancer treatment, chronic illnesses, aur traumatic injuries ke liye essential",
                "🔄 Blood ki limited shelf life hoti hai (red cells: 42 days, platelets: 5-7 days)",
                "🤝 Regular donations adequate supplies maintain karne ke liye needed hain",
                "",
                "Eligibility Requirements:",
                "✅ Age: 18-65 years (country ke hisaab se vary ho sakta hai)",
                "✅ Weight: At least 50 kg (110 lbs)",
                "✅ Hemoglobin: Minimum 12.5 g/dL for women, 13.0 g/dL for men",
                "✅ Generally good health on donation day",
                "",
                "Common Questions:",
                "❓ Main kitni baar donate kar sakta hoon? Whole blood: Har 56 days (3 months)",
                "❓ Kya dard hota hai? Only ek brief pinch jab needle insert hoti hai",
                "❓ Kitna time lagta hai? About 10 minutes donation ke liye, 45-60 minutes total process",
                "❓ Kya yeh safe hai? Yes, sterile equipment ek hi baar use hota hai",
                "",
                "Donation ke baad:",
                "🥤 Plenty fluids piyein",
                "🍫 Snack karein agar provide kiya gaya ho",
                "⚠️ 24 hours tak heavy lifting ya strenuous exercise avoid karein",
                "",
                "Sant Nirankari Mission Blood Donation:",
                "🙏 Mission regular blood donation camps organize karti hai",
                "📅 Pehla camp: 1986",
                "🏆 Ab tak millions units collect ki gayi hain",
                "🌍 Unke humanitarian service initiatives ka part"
            ],
            
            'manglish': [
                "Blood Donation - Lives Vachva! 🩸",
                "",
                "Blood Donation mhanje kay?",
                "💉 Ek voluntary procedure jithe ek vyakti transfusions sathi blood dan karto",
                "❤️ Ek dan tin jivan vachvu shakto",
                "🌟 Blood manufacture karu shakat nahi; te keval volunteer donors kadun yeu shakto",
                "",
                "Blood Donation che mahatva:",
                "🏥 Surgeries, cancer treatment, chronic illnesses, ani traumatic injuries sathi essential",
                "🔄 Blood chi limited shelf life aste (red cells: 42 days, platelets: 5-7 days)",
                "🤝 Regular donations adequate supplies maintain karanyasathi needed ahet",
                "",
                "Eligibility Requirements:",
                "✅ Vay: 18-65 years (country nusar badalu shakto)",
                "✅ Vajan: Kamitami 50 kg (110 lbs)",
                "✅ Hemoglobin: Minimum 12.5 g/dL for women, 13.0 g/dL for men",
                "✅ Generally danacya divashi changle arogy",
                "",
                "Common Questions:",
                "❓ Mi kiti vela dan karu shakto? Whole blood: Dare 56 days (3 months)",
                "❓ Jyata dukhyayla lagte ka? Fakta ek brief pinch jevha needle takli jate",
                "❓ Kiti vel lagte? About 10 minutes danasathi, 45-60 minutes total process",
                "❓ He safe ahe ka? Yes, sterile equipment ekdach vapratat",
                "",
                "Dananantar:",
                "🥤 Plenty fluids pya",
                "🍫 Snack kara jar provide kela gela tar",
                "⚠️ 24 hours paryant heavy lifting kinva strenuous exercise tala",
                "",
                "Sant Nirankari Mission Blood Donation:",
                "🙏 Mission regular blood donation camps ayojit karte",
                "📅 Pahila camp: 1986",
                "🏆 Aja paryant millions units ghetlya ahet",
                "🌍 Tyancya humanitarian service initiatives cha bhag"
            ]
        }
        
        # Multi-language response patterns
        self.response_patterns = {
            'en': {
                'eligibility': "To donate blood, you generally need to be: ✅ 18-65 years old ✅ At least 50 kg (110 lbs) ✅ In good health ✅ Have hemoglobin levels of at least 12.5g/dL (women) or 13.0g/dL (men). Some medications or health conditions might require a waiting period. Would you like more specific information?",
                'frequency': "You can donate: 🩸 Whole blood: Every 56 days (about 3 months) 💉 Platelets: Every 7 days, up to 24 times a year 🧪 Plasma: Every 28 days, up to 13 times a year. Your body replaces the plasma within 24-48 hours, and red blood cells in 4-6 weeks!",
                'process': "The blood donation process: 1️⃣ Registration & health screening (10-15 min) 2️⃣ Donation (8-10 min) 3️⃣ Rest & refreshments (10-15 min). Total time is about 45-60 minutes. The actual needle time is only 8-10 minutes!",
                'safety': "Blood donation is very safe! 🦠 All equipment is sterile and used only once. ❤️ You donate about 450ml of blood (less than 10% of your total blood volume). 🌟 Most people feel fine afterward and can resume normal activities the same day.",
                'nirankari': "Sant Nirankari Mission has been organizing blood donation camps since 1986! 🙏 They've collected millions of units of blood to date. 🌍 This service is part of their humanitarian initiatives to help those in need. 🏆 Their first camp was organized with great success and the tradition continues!"
            },
            'hi': {
                'eligibility': "रक्तदान के लिए, आपको आमतौर पर होना चाहिए: ✅ 18-65 वर्ष की आयु ✅ कम से कम 50 किग्रा (110 पाउंड) ✅ अच्छे स्वास्थ्य में ✅ हीमोग्लोबिन स्तर कम से कम 12.5g/dL (महिलाएं) या 13.0g/dL (पुरुष)। कुछ दवाएं या स्वास्थ्य स्थितियों के लिए प्रतीक्षा अवधि की आवश्यकता हो सकती है। क्या आप और अधिक विशिष्ट जानकारी चाहते हैं?",
                'frequency': "आप दान कर सकते हैं: 🩸 संपूर्ण रक्त: हर 56 दिन (लगभग 3 महीने) 💉 प्लेटलेट्स: हर 7 दिन, साल में 24 बार तक 🧪 प्लाज्मा: हर 28 दिन, साल में 13 बार तक। आपका शरीर 24-48 घंटों में प्लाज्मा और 4-6 सप्ताह में लाल रक्त कोशिकाओं को प्रतिस्थापित करता है!",
                'process': "रक्तदान प्रक्रिया: 1️⃣ पंजीकरण और स्वास्थ्य जांच (10-15 मिनट) 2️⃣ दान (8-10 मिनट) 3️⃣ आराम और जलपान (10-15 मिनट)। कुल समय लगभग 45-60 मिनट है। वास्तविक सुई का समय केवल 8-10 मिनट है!",
                'safety': "रक्तदान बहुत सुरक्षित है! 🦠 सभी उपकरण बाँझ होते हैं और केवल एक बार उपयोग किए जाते हैं। ❤️ आप लगभग 450ml रक्त दान करते हैं (आपके कुल रक्त की मात्रा का 10% से कम)। 🌟 ज्यादातर लोग बाद में ठीक महसूस करते हैं और उसी दिन सामान्य गतिविधियों को फिर से शुरू कर सकते हैं।",
                'nirankari': "संत निरंकारी मिशन 1986 से रक्तदान शिविर आयोजित कर रहा है! 🙏 उन्होंने अब तक लाखों यूनिट रक्त एकत्र किया है। 🌍 यह सेवा जरूरतमंदों की मदद के लिए उनकी मानवीय पहलों का हिस्सा है। 🏆 उनका पहला शिविर बहुत सफलता के साथ आयोजित किया गया था और परंपरा जारी है!"
            },
            'mr': {
                'eligibility': "रक्तदान करण्यासाठी, साधारणपणे आपण असणे आवश्यक आहे: ✅ 18-65 वर्षे वय ✅ किमान 50 किलो (110 पौंड) ✅ चांगले आरोग्य ✅ किमान 12.5g/dL (महिला) किंवा 13.0g/dL (पुरुष) हिमोग्लोबिन पातळी. काही औषधे किंवा आरोग्य स्थितीसाठी प्रतीक्षा कालावधी आवश्यक असू शकतो. तुम्हाला अधिक विशिष्ट माहिती हवी आहे का?",
                'frequency': "तुम्ही दान करू शकता: 🩸 संपूर्ण रक्त: दर 56 दिवस (सुमारे 3 महिने) 💉 प्लेटलेट्स: दर 7 दिवस, वर्षातून 24 वेळा 🧪 प्लाझ्मा: दर 28 दिवस, वर्षातून 13 वेळा. तुमचे शरीर 24-48 तासांत प्लाझ्मा आणि 4-6 आठवड्यांत लाल रक्त पेशी पुनर्स्थापित करते!",
                'process': "रक्तदान प्रक्रिया: 1️⃣ नोंदणी आणि आरोग्य तपासणी (10-15 मिनिटे) 2️⃣ दान (8-10 मिनिटे) 3️⃣ विश्रांती आणि जलपान (10-15 मिनिटे). एकूण वेळ सुमारे 45-60 मिनिटे आहे. वास्तविक सुईची वेळ फक्त 8-10 मिनिटे आहे!",
                'safety': "रक्तदान खूप सुरक्षित आहे! 🦠 सर्व साधने निर्जंतुक आहेत आणि फक्त एकदाच वापरली जातात. ❤️ तुम्ही सुमारे 450ml रक्त दान करता (तुमच्या एकूण रक्ताच्या प्रमाणापेक्षा 10% पेक्षा कमी). 🌟 बहुतेक लोक नंतर ठीक वाटतात आणि त्याच दिवशी सामान्य क्रिया पुन्हा सुरू करू शकतात.",
                'nirankari': "संत निरंकारी मिशन 1986 पासून रक्तदान शिबिरे आयोजित करत आहे! 🙏 त्यांनी आजपर्यंत लाखो युनिट रक्त गोळा केले आहे. 🌍 ही सेवा गरजूंना मदत करण्यासाठी त्यांच्या मानवतावादी उपक्रमांचा भाग आहे. 🏆 त्यांचे पहिले शिबिर खूप यशस्वीपणे आयोजित करण्यात आले होते आणि परंपरा चालू आहे!"
            },
            'hinglish': {
                'eligibility': "Blood donate karne ke liye, aapko generally hona chahiye: ✅ 18-65 years old ✅ At least 50 kg (110 lbs) ✅ Good health mein ✅ Hemoglobin levels at least 12.5g/dL (women) ya 13.0g/dL (men). Kuch medications ya health conditions ke liye waiting period ki zarurat ho sakti hai. Kya aap aur specific information chahte hain?",
                'frequency': "Aap donate kar sakte hain: 🩸 Whole blood: Har 56 days (about 3 months) 💉 Platelets: Har 7 days, saal mein 24 times tak 🧪 Plasma: Har 28 days, saal mein 13 times tak. Aapka body 24-48 hours mein plasma replace kar deta hai, aur red blood cells 4-6 weeks mein!",
                'process': "Blood donation process: 1️⃣ Registration & health screening (10-15 min) 2️⃣ Donation (8-10 min) 3️⃣ Rest & refreshments (10-15 min). Total time about 45-60 minutes hai. Actual needle time only 8-10 minutes hai!",
                'safety': "Blood donation bahut safe hai! 🦠 All equipment sterile hai aur ek hi baar use hota hai. ❤️ Aap about 450ml blood donate karte hain (aapke total blood volume ka 10% se kam). 🌟 Most people baad mein fine feel karte hain aur same day normal activities resume kar sakte hain.",
                'nirankari': "Sant Nirankari Mission 1986 se blood donation camps organize kar raha hai! 🙏 Unhone ab tak millions units blood collect kiya hai. 🌍 Yeh service need walon ki help ke liye unke humanitarian initiatives ka part hai. 🏆 Unka pehla camp bahut success ke sath organize kiya gaya tha aur tradition continue hai!"
            },
            'manglish': {
                'eligibility': "Blood dan karyasathi, sagharnapane tumhi asane avashyak ahe: ✅ 18-65 years vay ✅ Kamitami 50 kg (110 lbs) ✅ Changle arogyat ✅ Hemoglobin patali kamitami 12.5g/dL (women) kinva 13.0g/dL (men). Kahi ausadhe kinva arogy sthitisasathi pratiksha kalavachi garaj ashu shakte. Tumhala adhik specific mahiti havi ahe ka?",
                'frequency': "Tumhi dan karu shakata: 🩸 Whole blood: Dare 56 days (about 3 months) 💉 Platelets: Dare 7 days, varshatur 24 vela 🧪 Plasma: Dare 28 days, varshatur 13 vela. Tumache shareer 24-48 hoursat plasma replace karte, ani red blood cells 4-6 weeksat!",
                'process': "Blood dan prakriya: 1️⃣ Registration & health screening (10-15 min) 2️⃣ Dan (8-10 min) 3️⃣ Rest & refreshments (10-15 min). Total time about 45-60 minutes ahe. Actual needle vel fakta 8-10 minutes ahe!",
                'safety': "Blood dan khup safe ahe! 🦠 Sarva sadhane sterile ahet ani ekdach vapratat. ❤️ Tumhi about 450ml blood dan karta (tumachya total blood volume peksha 10% kami). 🌟 Most people nantar bare vatatat ani same day normal activities resume karu shaktat.",
                'nirankari': "Sant Nirankari Mission 1986 pasun blood donation camps ayojit karat ahe! 🙏 Tyanni aja paryant millions units blood ghetle ahe. 🌍 He seva garaj asalelyanna madat karanyasathi tyancya humanitarian initiatives cha bhag ahe. 🏆 Tyanca pahila camp khup success sobat ayojit kela gela hota ani parampara calu ahe!"
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
            You are a friendly Blood Donation Assistant 🤖, here to help people with all their blood donation questions.
            
            IMPORTANT:
            - Only answer questions related to blood donation. 
            - If the user asks about general knowledge, coding, recipes, countries, or any unrelated topic 
            (e.g., 'what is India', 'how to make pasta', 'write a Python script'), politely handle it and say: 
            "I am specially designed for blood donation camp."
            - If the user asks about *development*, politely say: 
            "I am an artificial intelligence machine specially designed to help you, developed by Prushal Technology Pvt. Ltd. Team."
            - If the user asks about *Prushal Technology* or *Prushal Tech*, politely suggest: 
            "Please visit https://prushal.com/ for more details."
            
            PERSONALITY:
            - Only respond with 'Dhan Nirankar Ji' if the user input is exactly 'Dhan Nirankar' or 'Dhan Nirankar Ji'.
            - Be warm, encouraging, and informative
            - Use simple, clear language that's easy to understand
            - Keep answers concise but helpful (2-4 sentences typically)
            - Use emojis appropriately 🩸💉❤️
            - Be positive about blood donation and its life-saving impact
            - If you don't know something, suggest contacting a local blood bank
            
            KNOWLEDGE BASE:
            {self.blood_donation_knowledge['en']}
            
            IMPORTANT: Always encourage blood donation as a safe, noble act that saves lives!
            """,
                
            'hi': f"""
            आप एक मित्रवत रक्तदान सहायक 🤖 हैं, जो लोगों की उनके सभी रक्तदान संबंधी प्रश्नों में मदद करने के लिए यहां हैं।
            
            केवल रक्तदान से संबंधित प्रश्नों के उत्तर दें। यदि उपयोगकर्ता सामान्य ज्ञान, कोडिंग, रेसिपी, देश, या कोई असंबंधित विषय (जैसे 'भारत क्या है', 'पास्ता कैसे बनाएं', 'पायथन स्क्रिप्ट लिखो') पूछे, तो विनम्रता से उत्तर दें: 'माफ़ कीजिए, मैं केवल रक्तदान से संबंधित प्रश्नों में सहायता कर सकता हूँ।'
            
            केवल हिंदी में जवाब दें।
            
            व्यक्तित्व:
            - केवल तब 'धन निरंकार जी' उत्तर दें जब उपयोगकर्ता का इनपुट बिल्कुल 'धन निरंकार' या 'धन निरंकार जी' हो।
            - गर्मजोशी, प्रोत्साहन और जानकारीपूर्ण बनें
            - सरल, स्पष्ट भाषा का उपयोग करें जो समझने में आसान हो
            - उत्तर संक्षिप्त लेकिन मददगार रखें (आमतौर पर 2-4 वाक्य)
            - उचित रूप से इमोजी का उपयोग करें 🩸💉❤️
            - रक्तदान और इसके जीवन रक्षक प्रभाव के बारे में सकारात्मक रहें
            - यदि आप कुछ नहीं जानते हैं, तो स्थानीय रक्त बैंक से संपर्क करने का सुझाव दें
            
            ज्ञान आधार:
            {self.blood_donation_knowledge['hi']}
            
            महत्वपूर्ण: हमेशा रक्तदान को एक सुरक्षित, महान कार्य के रूप में प्रोत्साहित करें जो जीवन बचाता है!
            """,
            
            'mr': f"""
            तुम्ही एक मैत्रीपूर्ण रक्तदान सहाय्यक 🤖 आहात, लोकांना त्यांच्या सर्व रक्तदान संबंधीच्या प्रश्नांमध्ये मदत करण्यासाठी इथे आहात.
            
            कृपया फक्त रक्तदानाशी संबंधित प्रश्नांचीच उत्तरे द्या. जर वापरकर्त्याने सामान्य ज्ञान, कोडिंग, रेसिपी, देश, किंवा कोणताही असंबंधित विषय (उदा. 'भारत काय आहे', 'पास्ता कसा बनवायचा', 'पायथन स्क्रिप्ट लिहा') विचारला, तर नम्रपणे उत्तर द्या: 'माफ करा, मी फक्त रक्तदानाशी संबंधित प्रश्नांमध्येच मदत करू शकतो.'
            
            फक्त मराठीत उत्तर द्या.
            
            व्यक्तिमत्व:
            - फक्त तेव्हाच 'धन निरंकार जी' उत्तर द्या जेव्हा वापरकर्त्याचा इनपुट अगदी 'धन निरंकार' किंवा 'धन निरंकार जी' असेल.
            - उबदार, प्रोत्साहन आणि माहितीपूर्ण व्हा
            - साधी, स्पष्ट भाषा वापरा जी समजण्यास सोपी असेल
            - उत्तरे संक्षिप्त पण उपयुक्त ठेवा (साधारणपणे 2-4 वाक्ये)
            - योग्य प्रकारे इमोजी वापरा 🩸💉❤️
            - रक्तदान आणि त्याच्या जीवन वाचवणाऱ्या प्रभावाबद्दल सकारात्मक रहा
            - जर तुम्हाला काही माहित नसेल तर स्थानिक रक्तबँकेशी संपर्क साधण्याचा सल्ला द्या
            
            ज्ञान आधार:
            {self.blood_donation_knowledge['mr']}
            
            महत्वाचे: नेहमी रक्तदानाला एक सुरक्षित, महान कृती म्हणून प्रोत्साहन द्या जी जीवन वाचवते!
            """,
            
            'hinglish': f"""
            Aap ek friendly Blood Donation Assistant 🤖 hain, logon ki unke sare blood donation related questions mein help karne ke liye yahan hain.
            
            Sirf blood donation se related questions ke answers dein. Agar user general knowledge, coding, recipe, country, ya koi unrelated topic (jaise 'India kya hai', 'pasta kaise banaye', 'Python script likho') pooche, toh politely reply karein: 'Sorry, main sirf blood donation se related questions mein madad kar sakta hoon.'
            
            HINGLISH (Hindi + English MIX) mein respond karein.
            
            PERSONALITY:
            - Sirf tabhi 'Dhan Nirankar Ji' reply dein jab user ka input exactly 'Dhan Nirankar' ya 'Dhan Nirankar Ji' ho.
            - Warm, encouraging, aur informative banein
            - Simple, clear language use karein jo samajh mein aasan ho
            - Answers concise but helpful rakhein (typically 2-4 sentences)
            - Appropriately emojis use karein 🩸💉❤️
            - Blood donation aur uske life-saving impact ke bare mein positive rahein
            - Agar aap kuch nahi jante hain, to local blood bank se contact karne ka suggest karein
            
            KNOWLEDGE BASE:
            {self.blood_donation_knowledge['hinglish']}
            
            IMPORTANT: Hamesha blood donation ko ek safe, noble act ke roop mein encourage karein jo lives bachata hai!
            """,
            
            'manglish': f"""
            Tumhi ek friendly Blood Donation Assistant 🤖 ahat, lokanna tyancya sarv blood donation related prashnamdyat madat karanyasathi ithe ahat.
            
            Krupaya fakta blood donation sambandhit prashnanchi uttar dya. Jar user general knowledge, coding, recipe, country, kimva kahi unrelated topic (ud. 'India kay ahe', 'pasta kasa banvaycha', 'Python script lihaa') vicharto, tar namr pane uttar dya: 'Sorry, mi fakta blood donation sambandhit prashnanch madat karu shakto.'
            
            MANGLISH (Marathi + English MIX) madhe respond kara.
            
            PERSONALITY:
            - Fakta tevha 'Dhan Nirankar Ji' reply dya jya vela user cha input exact 'Dhan Nirankar' kiwa 'Dhan Nirankar Ji' asel.
            - Warm, encouraging, ani informative vha
            - Simple, clear language vapara je samajanyat sope asel
            - Answers concise pan helpful theva (typically 2-4 sentences)
            - Appropriately emojis vapara 🩸💉❤️
            - Blood donation ani tyache life-saving impact baddal positive raha
            - Jar tumhala kahi mahiti nasel tar, local blood bank shi contact karanyacha suggest kara
            
            KNOWLEDGE BASE:
            {self.blood_donation_knowledge['manglish']}
            
            IMPORTANT: Nirmiti blood donation la ek safe, noble act mhanun encourage kara je jivan vachavte!
            """
        }
        
        return prompts.get(language, prompts['en'])
    
    def call_mistral_api(self, user_message, language, conversation_history=[]):
        """Call Mistral API with language-specific context, rotating API keys if one fails/hits limit."""
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

        last_error = None
        for i in range(len(self.mistral_api_keys)):
            api_key = self.mistral_api_keys[self._api_key_index]
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            try:
                response = requests.post(self.mistral_api_url, headers=headers, json=payload, timeout=30)
                if response.status_code == 429 or response.status_code == 403:
                    # Rate limit or forbidden, try next key
                    print(f"API key {self._api_key_index+1} hit limit or forbidden, rotating to next key...")
                    self._api_key_index = (self._api_key_index + 1) % len(self.mistral_api_keys)
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    continue
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content']
            except Exception as e:
                print(f"API Error with key {self._api_key_index+1}: {e}")
                self._api_key_index = (self._api_key_index + 1) % len(self.mistral_api_keys)
                last_error = str(e)
                continue
        # If all keys fail, fallback
        print(f"All API keys failed. Last error: {last_error}")
        return self.get_fallback_response(user_message, language)
    
    def get_fallback_response(self, user_message, language):
        """Language-specific fallback responses"""
        message_lower = user_message.lower()
        
        # Greeting responses
        if any(word in message_lower for word in ['hello', 'hi', 'namaste', 'hey', 'नमस्ते', 'हॅलो', 'नमस्कार']):
            return random.choice(self.welcome_messages[language])
        
        # Blood donation questions
        elif any(word in message_lower for word in ['eligible', 'पात्र', 'पात्रता', 'योग्य', 'who can donate', 'कौन दान कर सकता']):
            return self.response_patterns[language]['eligibility']
        
        elif any(word in message_lower for word in ['how often', 'कितनी बार', 'किती वेळा', 'frequency', 'अंतराल']):
            return self.response_patterns[language]['frequency']
        
        elif any(word in message_lower for word in ['process', 'प्रक्रिया', 'कैसे दान', 'कसे दान']):
            return self.response_patterns[language]['process']
        
        elif any(word in message_lower for word in ['safe', 'सुरक्षित', 'risk', 'जोखिम']):
            return self.response_patterns[language]['safety']
        
        elif any(word in message_lower for word in ['nirankari', 'निरंकारी', 'mission', 'मिशन']):
            return self.response_patterns[language]['nirankari']
        
        # Default response by language
        defaults = {
            'en': "Thank you for your interest in blood donation! ❤️ Your questions help spread awareness about this life-saving act. Could you tell me more about what you'd like to know? I'm here to help! 🩸",
            'hi': "रक्तदान में आपकी रुचि के लिए धन्यवाद! ❤️ आपके प्रश्न इस जीवन रक्षक कार्य के बारे में जागरूकता फैलाने में मदद करते हैं। क्या आप मुझे और बता सकते हैं कि आप क्या जानना चाहते हैं? मैं मदद करने के लिए यहां हूं! 🩸",
            'mr': "रक्तदानात तुमच्या स्वारस्याबद्दल धन्यवाद! ❤️ तुमचे प्रश्न या जीवन वाचवणाऱ्या कृतीबद्दल जागरूकता पसरवण्यास मदत करतात. तुम्हाला काय जाणून घ्यायचे आहे ते मला अधिक सांगू शकता का? मी मदत करण्यासाठी इथे आहे! 🩸",
            'hinglish': "Blood donation mein aapki interest ke liye thank you! ❤️ Aapke questions is life-saving act ke bare mein awareness failane mein help karte hain. Kya aap mujhe aur bata sakte hain ki aap kya janna chahte hain? Main help karne ke liye yahan hoon! 🩸",
            'manglish': "Blood donation madhye tumachyā svārasyābadal dhanyavād! ❤️ Tumace praśn yā jīvan vācavaṇāṟyā kr̥tībaddala jāgarūkatā pasaraviṇyāsa madata karatāta. Tumhālā kāy jāṇūna ghyāyacē āhē tē malā adhika sāṅgū śakatā ka? Mī madata karaṇyāsāṭhī ithe āhē! 🩸"
        }
        
        return defaults.get(language, defaults['en'])
   
   
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
    
    CHAT_HISTORY_FILE = "blood_donation_chat_history.json"
    
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

    def chat(self, session_id: str, user_message: str) -> str:
        """Handles a chat message for a given session (sid)"""
        
        # Append user message to Redis history
        self.update_user_history(session_id, "user", user_message)

        # Auto-detect language if enabled
        if self.auto_detect:
            self.current_language = self.detect_language(user_message)

        # Get last 6 messages for context
        conversation_history = self.get_user_history(session_id)[-6:]
        
        # Call Mistral API
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