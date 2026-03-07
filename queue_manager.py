WINDOW_SECONDS = 15
last_processing_time = time.time()


# ----- 15 second messages window -----
def check_message_window():

    global last_processing_time

    now = time.time()

    if now - last_processing_time >= WINDOW_SECONDS:

        process_message_window()

        last_processing_time = now


def process_message_window():

    if not message_queue:
        return

    print("\n=== PROCESSING WINDOW ===", flush=True)

    for msg in message_queue:
        print(msg, flush=True)

    print("Total messages:", len(message_queue), flush=True)

