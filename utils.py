import json
import re

def extract_json(text):
    """
    استخراج JSON من النص حتى لو كان داخله شرح أو markdown
    """

    # إزالة markdown
    text = re.sub(r"```json|```", "", text)

    # البحث عن أول JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("No JSON found")

    return match.group()


def heal_json(text):
    """
    إصلاح الأخطاء الشائعة في JSON
    """

    # إزالة الفواصل الزائدة
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    # تحويل ' إلى "
    text = text.replace("'", '"')

    # إزالة newline داخل النصوص
    text = text.replace("\n", " ")

    return text
