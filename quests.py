import datetime

QUESTS = {
    "Bevs4Life": {
        "description": "(Post a bev 7 days in a row)",
        "reward_text": "I don't know how you have that money but awesome!"
    },

    "Perfect Performative": {
        "description": "(Post matcha from 50 different places)",
        "reward_text": "You're the reason we have a matcha shortage"
    },

    "Heavens Chosen": {
        "description": "(Post from Bigway 20 times)",
        "reward_text": "Congrats you've become heaven's chosen one"
    }
}



import datetime

def has_quest(cursor, user_id, quest_name):
    cursor.execute("""
        SELECT 1 FROM user_quests
        WHERE user_id = ? AND quest_name = ?
    """, (user_id, quest_name))

    return cursor.fetchone() is not None

def unlock_quest(cursor, conn, user_id, quest_name):
    if has_quest(cursor, user_id, quest_name):
        return None

    unlocked_at = int(datetime.datetime.now().timestamp())

    cursor.execute("""
        INSERT INTO user_quests
        (user_id, quest_name, unlocked_at)
        VALUES (?, ?, ?)
    """, (user_id, quest_name, unlocked_at))

    conn.commit()
    return quest_name

def check_heavens_chosen(cursor, conn, user_id):
    cursor.execute("""
    SELECT COUNT(*)
    FROM entries
    WHERE user_id = ?
    AND place = 'bigway'
    """, (user_id,))

    total = cursor.fetchone()[0]

    if total >= 20:
        return unlock_quest(cursor, conn, user_id, "Heavens Chosen")

    return False

def check_perfect_performative(cursor, conn, user_id):
    cursor.execute("""
        SELECT COUNT(DISTINCT place)
        FROM entries
        WHERE user_id = ?
        AND LOWER(name) LIKE '%matcha%'
    """, (user_id,))

    total_places = cursor.fetchone()[0]

    if total_places >= 50:
        return unlock_quest(cursor, conn, user_id,"Perfect Performative")

    return False

def check_bevs4life(cursor, conn, user_id):

    cursor.execute("""
        SELECT DISTINCT date(timestamp, 'unixepoch')
        FROM entries
        WHERE user_id = ?
        ORDER BY date(timestamp, 'unixepoch') DESC
    """, (user_id,))

    rows = cursor.fetchall()

    if len(rows) < 7:
        return False

    dates = [
        datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
        for row in rows
    ]

    streak = 1

    for i in range(len(dates) - 1):

        diff = (dates[i] - dates[i + 1]).days

        if diff == 1:
            streak += 1
        else:
            break

    if streak >= 7:
        return unlock_quest(cursor, conn, user_id, "Bevs4Life")

    return False

QUEST_CHECKS = [
    check_heavens_chosen,
    check_perfect_performative,
    check_bevs4life
]

def check_all_quests(cursor, conn, user_id):

    unlocked = []

    for quest_check in QUEST_CHECKS:
        result = quest_check(cursor, conn, user_id)
        if result:
            unlocked.append(result)

    return unlocked