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
            "stars": 0,
            "last_seen": 0
        }

    s = student_memory[user_id]

    s["messages"] += 1

    if msg_type == "question":
        s["questions"] += 1

    if msg_type in ["answer", "short_answer"]:
        s["answers"] += 1


def check_bingo(answer_text, bingo_keywords):

    answer = answer_text.lower()

    for word in bingo_keywords:
        if word.lower() in answer:
            return True

    return False


def award_star(user_id, amount=1):

    if user_id not in student_memory:
        return

    student_memory[user_id]["stars"] += amount


def register_bingo(user_id):

    if user_id not in student_memory:
        return

    student_memory[user_id]["bingo_hits"] += 1
    award_star(user_id, 2) def register_bingo(user_id):

    if user_id not in student_memory:
        return

    student_memory[user_id]["bingo_hits"] += 1
    award_star(user_id, 2)


def get_rank(stars):

    if stars < 5:
        return "Beginner"
    elif stars < 15:
        return "Explorer"
    elif stars < 30:
        return "Challenger"
    elif stars < 60:
        return "Master"
    else:
        return "AI Champion"



def get_leaderboard(top=5):

    ranked = sorted(
        student_memory.items(),
        key=lambda x: x[1]["stars"],
        reverse=True
    )

    return ranked[:top]
