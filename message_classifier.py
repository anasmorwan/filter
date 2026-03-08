import re

def classify_message(text):
    """
    Returns one of: "question", "answer", "reaction", "noise"
    """
    text = text.strip().lower()

    # سؤال: غالبًا ينتهي بعلامة استفهام
    if text.endswith("?"):
        return "question"

    # إجابة: كلمات شائعة للإجابات أو أكثر من 2 كلمة بالإنجليزية
    if re.match(r"^[a-z\s]{2,50}$", text):
        return "answer"

    # رد فعل قصير: كلمات منخفضة القيمة
    LOW_VALUE = {"ok", "yes", "no", "lol", "hi", "thanks"}
    if text in LOW_VALUE:
        return "reaction"

    # كل شيء آخر
    return "noise"
