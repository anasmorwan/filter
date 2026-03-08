def map_action_to_intent(action):

    mapping = {

"INTRO_LESSON": "teacher_intro",

"WAKE_UP_SESSION": "teacher_wakeup",

"ANSWER_QUESTION": "teacher_answer",

"EVALUATE_STUDENT_ANSWERS": "teacher_evaluate",

"GIVE_HINT": "teacher_hint",

"ASK_FOLLOWUP": "teacher_followup",

"ENCOURAGE_DISCUSSION": "teacher_encourage",

"CORRECT_MISTAKES": "teacher_correct",

"CALL_ON_STUDENT": "teacher_direct",

"SUMMARIZE_DISCUSSION": "teacher_summary",

"ASK_NEW_TOPIC_QUESTION": "teacher_question",

"LIGHT_COMMENT": "teacher_comment",

"REFRAME_TOPIC": "teacher_reframe",

"CHECK_UNDERSTANDING": "teacher_check",

"GENERAL_COMMENT": "teacher_comment"

    }

    return mapping.get(action, "teacher_comment")
