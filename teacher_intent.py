def map_action_to_intent(action):

    mapping = {

        "ANSWER_QUESTION": "teacher_answer",

        "EVALUATE_STUDENT_ANSWERS": "teacher_evaluate",

        "SUMMARIZE_AND_NEXT": "teacher_summary",

        "GENERAL_COMMENT": "teacher_comment",

        "WAKE_UP_SESSION": "teacher_wakeup",

        "ENCOURAGE_DISCUSSION": "teacher_encourage",

        "CORRECT_MISTAKES": "teacher_correct",

        "ASK_NEXT_TOPIC_QUESTION": "teacher_question"

    }

    return mapping.get(action, "teacher_comment")
