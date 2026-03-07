def generate_ai_response():

    context = list(message_queue)[-5:]

    prompt = build_prompt(context)

    response = call_ai(prompt)

    return response


def build_prompt(context):

    conversation = ""

    for msg in context:
        conversation += f"{msg['user']}: {msg['text']}\n"

    prompt = f"""
You are an English teacher helping students think in English.

Conversation:
{conversation}

Respond like a teacher speaking slowly and clearly.
"""

    return prompt


from openai import OpenAI

client = OpenAI(api_key="YOUR_API_KEY")

def call_ai(prompt):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful English teacher."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content


