from memory import update_student_memory, 
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



last_daily_report = None

def build_daily_report():

    leaders = get_leaderboard()

    if not leaders:
        return None

    text = "🏆 Daily Activity Report\n\n"

    for i, (uid, data) in enumerate(leaders, 1):

        stars = data["stars"]
        rank = get_rank(stars)

        text += f"{i}. {data['name']} ⭐{stars} ({rank})\n"

    return text



def get_daily_report_if_changed():

    global last_daily_report

    report = build_daily_report()

    if report != last_daily_report:
        last_daily_report = report
        return report

    return None


last_daily_report = None

def build_daily_report():

    leaders = get_leaderboard()

    if not leaders:
        return None

    text = "🏆 Daily Activity Report\n\n"

    for i, (uid, data) in enumerate(leaders, 1):

        stars = data["stars"]
        rank = get_rank(stars)

        text += f"{i}. {data['name']} ⭐{stars} ({rank})\n"

    return text

def get_daily_report_if_changed():

    global last_daily_report

    report = build_daily_report()

    if report != last_daily_report:
        last_daily_report = report
        return report

    return None
