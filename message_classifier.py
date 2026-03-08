# message_classifier.py

import re

LOW_VALUE = {
    "ok","yes","no","lol","haha","hi","hello",
    "thanks","cool","nice"
}

def classify_message(text):

    text = text.strip().lower()

    if text.endswith("?"):
        return "question"

    if text in LOW_VALUE:
        return "reaction"

    words = text.split()

    if len(words) <= 3:
        return "short_answer"

    if re.match(r"^[a-zA-Z\s]+$", text):
        return "answer"

    return "other"
