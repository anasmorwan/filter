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



#__________ spam detecter______
def is_spam(text):
    # هذا النمط يبحث عن أي نص يبدأ بـ http أو https أو www 
    # ويحتوي على نطاق (domain) مثل .com أو .net إلخ
    url_pattern = r'(https?://[^\s]+|www\.[^\s]+)'
    
    # البحث عن النمط داخل النص
    if re.search(url_pattern, text):
        return True  # وجد رابطاً، إذاً نعتبرها سبام
    
    return False # لم يجد أي روابط




#________ 
def should_store_message(text):

    if is_spam(text):
        return False

    if is_only_emoji(text):
        return False

    if not is_english(text):
        return False

    return True
