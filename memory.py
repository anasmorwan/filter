student_memory = {}

def update_student_memory(user_id, username, msg_type):

    if user_id not in student_memory:
        student_memory[user_id] = {
            "name": username,
            "messages": 0,
            "questions": 0,
            "answers": 0,
            "mistakes": 0,
            "bingo_hits": 0,
            "last_seen": 0
        }

    s = student_memory[user_id]

    s["messages"] += 1

    if msg_type == "question":
        s["questions"] += 1

    if msg_type in ["answer", "short_answer"]:
        s["answers"] += 1
