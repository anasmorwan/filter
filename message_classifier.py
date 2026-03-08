# message_classifier.py

import re
from typing import Tuple

# كلمات ردود سطحية أو تفاعلية
LOW_VALUE = {
    "ok","yes","no","lol","haha","hi","hello",
    "thanks","cool","nice","bye","okey"
}

# كلمات مفتاحية لتحديد السؤال
QUESTION_KEYWORDS = {
    "what","who","when","where","why","how","can","is","are",
    "do","does","did","will","would","should","could","which"
}

def classify_message(text: str) -> Tuple[str, float]:
    """
    تصنيف الرسائل بدقة عالية مع إعطاء درجة ثقة.
    إرجاع: (message_type, confidence)
    message_type ∈ {"question", "answer", "short_answer", "reaction", "other"}
    confidence ∈ [0, 1]
    """
    text = text.strip().lower()
    
    if not text:
        return "other", 0.9  # فارغ أو غير مفهوم
    
    words = text.split()
    
    # --------- السؤال ---------
    # إذا انتهت بعلامة ? أو بدأت بكلمة مفتاحية
    if text.endswith("?") or any(text.startswith(w + " ") for w in QUESTION_KEYWORDS):
        return "question", 0.95
    
    # --------- ردود سطحية ---------
    if text in LOW_VALUE:
        return "reaction", 0.95
    
    # --------- إجابة قصيرة ---------
    if len(words) <= 3:
        # افحص إذا كانت كلمات مفيدة (تجنب الرموز)
        if re.match(r"^[a-zA-Z0-9]+$", text):
            return "short_answer", 0.85
        else:
            return "other", 0.8
    
    # --------- إجابة مفهومة ---------
    if re.match(r"^[a-zA-Z0-9\s,.'!?]+$", text):
        return "answer", 0.9
    
    # --------- غير معروف ---------
    return "other", 0.7
