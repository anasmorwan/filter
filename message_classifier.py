# message_classifier.py

import re
from typing import Tuple


LOW_VALUE = {
    "ok","yes","no","lol","haha","hi","hello",
    "thanks","cool","nice","bye","okey", "تمام", "واضح", "نعم", "لا"
}

QUESTION_KEYWORDS = {
    "what","who","when","where","why","how","can","is","are",
    "do","does","did","will","would","should","could","which",
    "لماذا", "كيف", "متى", "أين", "من", "ماذا", "هل"
}

# كلمات تدل على حاجة فورية للتوضيح
URGENT_TRIGGERS = {
    "عيد", "لم افهم", "ما معنى", "اعد", "توقف", "لحظة", "شرح",
    "repeat", "explain", "mean", "stop", "wait", "confused", " understand"
}

def classify_message(text: str) -> Tuple[str, float]:
    text = text.strip().lower()
    if not text: return "other", 0.9
    
    words = text.split()
    
    # --------- منطق الأسئلة المطور ---------
    is_question_format = text.endswith("?") or any(text.startswith(w + " ") for w in QUESTION_KEYWORDS)
    
    if is_question_format:
        # فحص هل السؤال عاجل (توضيحي) أم آجل (استقصائي)
        is_urgent = any(trigger in text for trigger in URGENT_TRIGGERS) or len(text) < 25
        
        if is_urgent:
            return "urgent_question", 0.98
        else:
            return "question", 0.92
    
    # --------- باقي التصنيفات كما هي ---------
    if text in LOW_VALUE:
        return "reaction", 0.95
    
    if len(words) <= 3:
        return "short_answer", 0.85 if re.match(r"^[\w\s]+$", text) else "other", 0.8
    
    if re.match(r"^[\w\s,.'!?]+$", text):
        return "answer", 0.9
    
    return "other", 0.7
