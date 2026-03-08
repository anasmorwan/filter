from openai import OpenAI
from prompts import TEACHER_SYSTEM_PROMPT, ACTION_PROMPTS

client = OpenAI(api_key="YOUR_API_KEY")

def generate_ai_response(action, messages):
    """
    توليد الرد المناسب حسب action و context الرسائل
    """

    context = list(messages)[-5:]  # آخر 5 رسائل فقط

    prompt = build_prompt(action, context)

    response = call_ai(prompt)
    return response


def build_prompt(action, context):
    """
    بناء prompt مع system + action prompt
    """

    conversation = ""
    for msg in context:
        conversation += f"{msg['user']}: {msg['text']}\n"

    action_prompt = ACTION_PROMPTS.get(action, "")

    prompt = f"""
{TEACHER_SYSTEM_PROMPT}

Conversation:
{conversation}

Instruction:
{action_prompt}
"""
    return prompt


def call_ai(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful English teacher."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content
