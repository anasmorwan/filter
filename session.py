import time

session = {
    "active": False,
    "topic": None,
    "difficulty": None,
    "start_time": None
}


def start_session(topic="general", difficulty="normal"):

    session["active"] = True
    session["topic"] = topic
    session["difficulty"] = difficulty
    session["start_time"] = time.time()

    print("\n=== SESSION STARTED ===")
    print("Topic:", topic)
    print("Difficulty:", difficulty)


def stop_session():

    session["active"] = False

    print("\n=== SESSION STOPPED ===")


def session_is_active():

    return session["active"]


def get_session_info():

    return session
