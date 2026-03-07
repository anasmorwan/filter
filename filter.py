import re
import time
from collections import deque

# آخر الرسائل لمنع التكرار
recent_messages = deque(maxlen=100)

# تتبع نشاط المستخدم
user_last_message = {}
user_last_time = {}
LOW_VALUE_WORDS = {
    "ok", "okay", "k",
    "yes", "no", "yeah", "yep", "nah", "nope",
    "lol", "haha", "hehe",
    "hi", "hello", "hey",
    "thanks", "thank you", "thx", "ty",
    "nice", "cool",
    "same", "true",
}
# ---------- طول الرسالة ----------
def is_too_short(text):
    return len(text.strip()) < 3


# ---------- التكرار ----------
def normalize(text):
    return text.lower().strip()

def is_duplicate(text):
    text = normalize(text)

    if text in recent_messages:
        return True

    recent_messages.append(text)
    return False


# ---------- إغراق المستخدم ----------
def is_user_spamming(user_id, text):

    now = time.time()

    # منع الرسائل السريعة
    last_time = user_last_time.get(user_id)

    if last_time and now - last_time < 2:
        return True

    user_last_time[user_id] = now

    # منع تكرار نفس الرسالة
    if user_last_message.get(user_id) == text:
        return True

    user_last_message[user_id] = text

    return False


# ---------- ايموجي فقط ----------
def is_only_emoji(text):
    return not re.search(r"[a-zA-Z]", text)


# ---------- اللغة ----------
def is_english(text):
    letters = sum(c.isalpha() for c in text)

    if letters == 0:
        return False

    english = sum(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in text)

    return english / letters > 0.7


# ---------- روابط ----------
def is_spam(text):
    url_pattern = r"(https?://[^\s]+|www\.[^\s]+)"
    spam_words = ["join my", "subscribe", "dm me"]

    if re.search(url_pattern, text):
        return True

    lower = text.lower()

    for w in spam_words:
        if w in lower:
            return True

    return False
# ---------- تنظيف  ----------
def clean_text(text):
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = " ".join(t.split())
    return t

# ---------- فلترة الضحك  ----------
def is_laughing(text):
    t = clean_text(text)
    return bool(re.match(r"^(ha)+$|^(lol)+$", t))

# ---------- قيمة أقل  ----------
def is_low_value(text):
    t = clean_text(text)

    if t in LOW_VALUE_WORDS:
        return True

    if is_laughing(t):
        return True

    return False


# ---------- الدالة الرئيسية ----------
def should_store_message(text, user_id=None):

    if is_too_short(text):
        return False

    if is_low_value(text):
        return False

    if is_spam(text) or is_only_emoji(text) or not is_english(text):
        return False

    if is_duplicate(text):
        return False
    
    if user_id and is_user_spamming(user_id, text):
        return False

    return True
