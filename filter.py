import re
#_____________ emoji filter_______
def is_only_emoji(text):
    return not re.search(r"[a-zA-Z]", text)

#____ language filter_____
def is_english(text):

    letters = sum(c.isalpha() for c in text)
    english = sum(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in text)

    if letters == 0:
        return False

    return english / letters > 0.7





#________ 
def should_store_message(text):

    if is_spam(text):
        return False

    if is_only_emoji(text):
        return False

    if not is_english(text):
        return False

    return True