#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from telegram import replykeyboardmarkup, inlinekeyboardmarkup, inlinekeyboardbutton
from telegram.ext import Updater, CallbackQueryHandler, CommandHandler, MessageHandler, Filters, Job, JobQueue

from datetime import datetime
import dateutil.relativedelta as REL
import fileinput
from operator import itemgetter

import json
from botsettings import data as bot_data

TIME_SHIFT = bot_data["time_shift_server"]

linen_admin = bot_data["first_admin"]  # админ, отвечающий за смену постельного белья
water_admin = bot_data["second_admin"]  # админ, отвечающий за смену воды

locals = dict()
notifs = dict()
requests = []

linenTime = bot_data["linen_time"]
waterTime = bot_data["water_time"]

linenDays = {key: bot_data[key] for key in [1, 2, 4]}


class AdminUser(object):
    def __init__(self, id):
        self.status = "Present"
        self.ID = id
        self.users = []
        self.time_users = []
        self.timeset = False
        self.messages = []
        self.timer = None
        self.current_request = []

    def setstatus(self, stat):
        self.status = stat


def createinlinekeyboard(keylist):
    tmp = [[inlinekeyboardbutton.InlineKeyboardButton(text=k[0], callback_data=k[1]) for k in l] for l in keylist]
    return inlinekeyboardmarkup.InlineKeyboardMarkup(tmp)


def get_text(t1, t2):
    return localisation_data[t1][locals[t2][0]]


def alarm(bot, job):
    """Function to send the alarm message"""
    admin = job.context
    admin.setstatus("Not present")

    for user in admin.time_users:
        mess = bot.editMessageText(
            text=get_text("no_answer_users", user),
            chat_id=user,
            message_id=next((x for x in admin.messages if x.chat.id == user), None).message_id)
        admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))

    bot.editMessageText(
        text=get_text("no_answer_admins", user),
        chat_id=admin.ID,
        message_id=next((x for x in admin.messages if x.chat.id == admin.ID), None).message_id)
    admin.messages.remove(next((x for x in admin.messages if x.chat.id == admin.ID), None))

    for user in admin.time_users:
        if user not in admin.users:
            admin.users.append(user)
            write_reminder(admin.ID, user)
    admin.time_users = []


def settimer(bot, admin, chat_id, job_queue):
    """Adds a job to the queue"""
    if admin.timeset is not True:
        # Add job to queue
        job = Job(alarm, 300, repeat=False, context=admin)
        admin.timer = job
        job_queue.put(job)
        admin.timeset = True

    if chat_id not in admin.time_users:
        admin.time_users.append(chat_id)


def user_got(bot, query, text):
    chat = query.message.chat_id
    admin = next((x for x in admins if x.ID == text), None)
    mess = bot.editMessageText(text=get_text("item_changed", chat),
                               chat_id=chat,
                               message_id=query.message.message_id)
    admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))


def user_wait(bot, query, text):
    chat = query.message.chat_id
    admin = next((x for x in admins if x.ID == text), None)

    mark_up = createinlinekeyboard(
        [[[get_text("user_got", chat), "user_got" + "#" + str(admin.ID)]]])

    mess = bot.editMessageText(text=get_text("notification", chat),
                               chat_id=chat,
                               message_id=query.message.message_id,
                               reply_markup=mark_up)
    admin.messages.append(mess)

    mark_up = createinlinekeyboard(
        [[[get_text("walk_up", chat), "walk_up" + str(admin.ID)]]])

    if next((x for x in admin.messages if x.chat_id == admin.ID), None) is None:
        mess = bot.sendMessage(admin.ID, get_text("users_ready", admin.ID),
                               reply_markup=mark_up)
        admin.messages.append(mess)

    settimer(bot, admin, chat, JobQueue(bot, prevent_autostart=False))


def walk_up(bot, query, text):
    chat = query.message.chat_id
    admin = next((x for x in admins if x.ID == text), None)
    admin.timeset = False
    job = admin.timer
    job.schedule_removal()
    del admin.timer

    mark_up = createinlinekeyboard(
        [[[get_text("user_got", chat), "user_got" + "#" + str(admin.ID)]]])
    for user in admin.time_users:
        bot.editMessageText(text=get_text("admin_comes", user), chat_id=user,
                            message_id=next((x for x in admin.messages if x.chat.id == user), None).message_id,
                            reply_markup=mark_up)
    admin.time_users.clear()

    mess = bot.editMessageText(text=get_text("good_trip", admin.ID), chat_id=admin.ID,
                               message_id=next((x for x in admin.messages if x.chat.id == admin.ID),
                                               None).message_id)
    admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))


def no(bot, query, text):
    chat = query.message.chat_id
    bot.editMessageText(
        text=get_text("nice_day", chat),
        chat_id=chat,
        message_id=query.message.message_id)


def yes(bot, query, text):
    chat = query.message.chat_id
    campus = int(text)
    bot.editMessageText(
        text=get_text("next_weekday", chat) % (
            get_text(linenDays[campus][0], chat)),
        chat_id=chat,
        message_id=query.message.message_id)
    set_up_notification(bot, chat, campus)
    with open("notifications.txt", "a") as myfile:
        myfile.write(str(chat) + "\n")
    myfile.close()


def request(bot, query, text):
    chat = query.message.chat_id
    admin = next((x for x in admins if x.ID == chat), None)
    if query.data == "next_request":
        requests.append(admin.current_request)
        admin.current_request = requests.pop(0)
    else:
        requests.insert(0, admin.current_request)
        admin.current_request = requests.pop(len(requests) - 1)
    mark_up = createinlinekeyboard(
        [[[get_text("previous_request", admin.ID), "previous_request"],
          [get_text("next_request", admin.ID), "next_request"]],
         [[get_text("reject", admin.ID), "reject"],
          [get_text("approve", admin.ID), "approve"]],
         [[get_text("cancel_requests", admin.ID), "cancel_requests"]]])

    bot.editMessageText(
        text=get_text("get_request", admin.ID) % tuple(admin.current_request[-3:]),
        chat_id=admin.ID,
        reply_markup=mark_up,
        message_id=query.message.message_id)


def rej_app(bot, query, text):
    chat = query.message.chat_id
    admin = next((x for x in admins if x.ID == chat), None)
    if query.data == "reject":
        bot.send_message(int(admin.current_request[0]), get_text("rejected", admin.ID))
    else:
        bot.send_message(int(admin.current_request[0]), get_text("approved", admin.ID))
    bot.send_message(admin.ID,
                     get_text("get_request", admin.ID) % tuple(admin.current_request[-3:]))

    delete_request(admin.current_request)
    admin.current_request = []

    if len(requests) > 0:
        admin.current_request = requests.pop(0)

        mark_up = createinlinekeyboard(
            [[[get_text("previous_request", admin.ID), "previous_request"],
              [get_text("next_request", admin.ID), "next_request"]],
             [[get_text("reject", admin.ID), "reject"],
              [get_text("approve", admin.ID), "approve"]],
             [[get_text("cancel_requests", admin.ID), "cancel_requests"]]])

        bot.editMessageText(
            text=get_text("get_request", admin.ID) % tuple(admin.current_request[-3:]),
            chat_id=admin.ID,
            reply_markup=mark_up,
            message_id=query.message.message_id)
    else:
        bot.editMessageText(
            text=get_text("no_requests", admin.ID),
            chat_id=admin.ID,
            message_id=query.message.message_id)


def cancel_requests(bot, query, text):
    chat = query.message.chat_id
    admin = next((x for x in admins if x.ID == chat), None)
    if admin.current_request:
        requests.append(admin.current_request)
    bot.editMessageText(
        text=get_text("requests_canceled", admin.ID),
        chat_id=admin.ID,
        message_id=query.message.message_id)


comm_functions = {
    "user_got": user_got,
    "user_wait": user_wait,
    "walk_up": walk_up,
    "no": no,
    "yes": yes,
    "next_request": request,
    "previous_request": request,
    "reject": rej_app,
    "approve": rej_app,
    "cancel_requests": cancel_requests
}


# function is too huge


def button(bot, update):
    query = update.callback_query
    tmp = query.data.split("#")
    comm_functions[tmp[0]](bot, query, tmp[1] if len(tmp) == 2 else None)


def delete_request(request):
    for tmp in fileinput.input('requests.txt', inplace=True):
        if not tmp.startswith(" ".join(request)):
            print(tmp.rstrip())
    fileinput.close()


def set_up_notification(bot, chat, campus):
    rd = REL.relativedelta(days=1, weekday=linenDays[campus][1])
    today = datetime.now()
    time = int((datetime(*(today + rd).timetuple()[:3]) - today).total_seconds())
    job = Job(notify, time + 43200 + (TIME_SHIFT * 60 * 60), repeat=False, context=chat)
    notifs[job.context] = job
    JobQueue(bot, prevent_autostart=False).put(job)


def process_linen(bot, chat):
    admin = next((x for x in admins if x.ID == linen_admin), None)
    now = datetime.now()
    campus = 0
    with open("loc.txt") as search:
        for line in search:
            if line.startswith(str(chat)):
                campus = int(line.rstrip().split("#")[2])
                break
        search.close()

    time = now.replace(hour=18 + TIME_SHIFT, minute=0, second=0, microsecond=0)
    if datetime.now().weekday() == linenDays[campus][1] and now < time:
        bot.send_message(chat_id=chat, text=get_text("change_linen", chat))

        time1 = now.replace(hour=linenTime[0] + TIME_SHIFT, minute=0, second=0, microsecond=0)
        time2 = now.replace(hour=linenTime[1] + TIME_SHIFT, minute=0, second=0, microsecond=0)
        time3 = now.replace(hour=linenTime[2] + TIME_SHIFT, minute=0, second=0, microsecond=0)
        time4 = now.replace(hour=linenTime[3] + TIME_SHIFT, minute=0, second=0, microsecond=0)
        if (time1 <= now < time2) or (time3 <= now < time4):
            process_change(bot, admin, chat)
        else:
            if chat not in admin.users:
                admin.users.append(chat)
                write_reminder(admin.ID, chat)
            bot.send_message(chat, get_text("admin_not_works", chat))

    else:
        mark_up = createinlinekeyboard([[[get_text("yes", chat), "yes" + "#" + str(campus)],
                                         [get_text("no", chat), 'no']]])

        bot.send_message(
            chat_id=chat, text=get_text("linen_day_change", chat) % (
                get_text(linenDays[campus][0], chat)), reply_markup=mark_up)


def notify(bot, job):
    bot.send_message(job.context, get_text("change_today", job.context))

    for tmp in fileinput.input('notifications.txt', inplace=True):
        if not tmp.startswith(str(job.context)):
            print(tmp.rstrip())
    fileinput.close()


changing_time = False
setting_campus = False
sending_request = False


def process_message(bot, message):
    text = message.message.text
    chat = message.message.chat
    text = text.strip()
    admin = next((x for x in admins if x.ID == chat.id), None)

    if admin is not None:
        global changing_time;
        if changing_time:
            try:
                tmp = text.split("\n")
                tmplist = []
                for t in tmp:
                    t = [int(i) for i in t.split(" ")]
                    if len(t) != 4:
                        raise Exception()
                    tmplist.append(t)
                global linenTime, waterTime
                linenTime = tmplist[0]
                waterTime = tmplist[1]
                changing_time = False;
                bot.send_message(admin.ID, get_text("time_changed", admin.ID))
            except:
                bot.send_message(admin.ID, get_text("wrong_data", admin.ID))
        else:
            # possible changing?
            if text == get_text("Present", admin.ID) \
                    or text == get_text("Not present", admin.ID):
                admin.setstatus("Present" if text == "На месте" or text == "Present" else "Not present")
                bot.send_message(chat.id, get_text("current_status", chat.id) % (
                    get_text(admin.status, chat.id)))
                if text == get_text("Present", admin.ID):
                    for user in admin.users:
                        bot.send_message(user, get_text("admin_returned", user))
                    admin.users = []
                    remind(admin.ID)
            if text == get_text("Time", admin.ID):
                bot.send_message(admin.ID, get_text("set_time", admin.ID))
                changing_time = True
            if get_text("look_requests", admin.ID):
                if not requests:
                    bot.send_message(admin.ID, get_text("no_requests", admin.ID))
                else:
                    admin.current_request = requests.pop(0)
                    mark_up = createinlinekeyboard(
                        [[[get_text("previous_request", chat.id), "previous_request"],
                          [get_text("next_request", chat.id), "next_request"]],
                         [[get_text("reject", chat.id), "reject"],
                          [get_text("approve", chat.id), "approve"]],
                         [[get_text("cancel_requests", chat.id), "cancel_requests"]]])

                    list = admin.current_request[-3:]
                    bot.send_message(admin.ID, get_text("get_request", chat.id) % tuple(list),
                                     reply_markup=mark_up)

    else:

        global setting_campus
        if setting_campus:
            try:
                t = [int(i) for i in text.rstrip().split(" ")]
                if len(t) != 2:
                    raise Exception("")
                change_campus(message, t)
                setting_campus = False

                bot.send_message(chat.id, get_text("campus_set", chat.id))
            except Exception as exc:
                bot.send_message(chat.id, get_text("wrong_campus_data", chat.id))
                if exc.args[0] != "":
                    bot.send_message(chat.id, get_text(exc.args[0], chat.id))

        if not setting_campus and check_campus(bot, chat.id):
            global sending_request

            if sending_request:
                write_request(chat.id, locals[chat.id], text)
                bot.send_message(chat.id, get_text("request_sent", chat.id))
                sending_request = False

            if (text == "\U0001F4A4"):
                process_linen(bot, chat.id)

            if (text == "\U0001F4A7"):
                now = datetime.now()
                time1 = now.replace(hour=waterTime[0] + TIME_SHIFT, minute=0, second=0, microsecond=0)
                time2 = now.replace(hour=waterTime[1] + TIME_SHIFT, minute=0, second=0, microsecond=0)
                time3 = now.replace(hour=waterTime[2] + TIME_SHIFT, minute=0, second=0, microsecond=0)
                time4 = now.replace(hour=waterTime[3] + TIME_SHIFT, minute=0, second=0, microsecond=0)
                admin = next((x for x in admins if x.ID == water_admin), None)
                if ((time1 <= now < time2) or (time3 <= now < time4)) and now.today().weekday() < 5:
                    bot.send_message(chat.id, get_text("change_water", chat.id))
                    process_change(bot, admin, chat)
                else:
                    if chat.id not in admin.users:
                        admin.users.append(chat.id)
                        write_reminder(admin.ID, chat.id)
                    bot.send_message(chat.id, get_text("admin_not_works", chat.id))

            if text == get_text("change_campus", message.message.chat_id):
                locals[chat.id][1] = locals[chat.id][2] = ""
                check_campus(bot, chat.id)

            if text == get_text("leave_request", message.message.chat_id):
                process_request(bot, message.message.chat_id)

    print('Got message: \33[0;32m{0}\33[0m from chat: {1}'.format(text, chat))


def write_request(chat, lis, text):
    tmp = [str(chat), lis[1], lis[2], text]
    requests.append(tmp)
    with open("requests.txt", "a") as myfile:
        myfile.write((" ".join(tmp)))
    myfile.close()


def process_request(bot, chat):
    bot.send_message(chat, get_text("request", chat))
    global sending_request
    sending_request = True


def change_campus(message, t):
    if not (0 < t[0] < 5):
        raise Exception("campus")
    if not (99 < t[1] < 500):
        raise Exception("room")
    chat = message.message.chat_id
    locals[chat][1] = t[0]
    locals[chat][2] = t[1]
    for tmp in fileinput.input('loc.txt', inplace=True):
        if tmp.startswith(str(chat)):
            tmp = tmp.rstrip()
            print(tmp.replace(tmp, str(chat) + "#" + ('#'.join(map(str, locals[chat])))))
        else:
            print(tmp.rstrip())
    fileinput.close()


def process_change(bot, admin, chat):
    if admin.status == "Present":
        bot.send_message(chat.id, get_text("admin_workplace", chat.id))

        mark_up = createinlinekeyboard(
            [[[get_text("user_wait", chat.id), "user_wait" + "#" + str(admin.ID)],
              [get_text("user_got", chat.id), "user_got" + "#" + str(admin.ID)]]])
        bot.send_message(chat.id, get_text("right_place", chat.id), reply_markup=mark_up)
    else:
        bot.send_message(chat.id, get_text("admin_not_present", chat.id))
        bot.send_message(admin.ID,
                         get_text("user_wants", chat.id)
                         % (chat.last_name, chat.first_name,
                            get_text("water" if admin.ID == water_admin else "linen", admin.ID)))
        bot.send_message(chat.id, get_text("need_message", chat.id))
        if chat.id not in admin.users:
            admin.users.append(chat.id)
            write_reminder(admin.ID, chat.id)


def remind(admin):
    for tmp in fileinput.input('reminders.txt', inplace=True):
        if tmp.startswith(str(admin)):
            print(tmp.rstrip().split(" ")[0])
        else:
            print(tmp.rstrip())
    fileinput.close()


def write_reminder(admin, chat):
    boolean = False
    for tmp in fileinput.input('reminders.txt', inplace=True):
        if tmp.startswith(str(admin)):
            boolean = True
            print(tmp.rstrip() + " " + str(chat))
        else:
            print(tmp.rstrip())
    fileinput.close()

    if not boolean:
        with open("reminders.txt", "a") as myfile:
            myfile.write(str(admin) + " " + str(chat) + "\n")
        myfile.close()


def language(bot, message):
    locals[message.message.chat_id][0] = message.message.text[1:3]

    for tmp in fileinput.input('loc.txt', inplace=True):
        if tmp.startswith(str(message.message.chat_id)):
            tmp = tmp.rstrip()
            print(tmp.replace(tmp, str(message.message.chat_id) + "#" + (
                '#'.join(map(str, locals[message.message.chat_id])))))
        else:
            print(tmp.rstrip())
    fileinput.close()
    start(bot, message)


def addlocal(id):
    locals[id] = [""] * 3
    locals[id][0] = "en"
    with open("loc.txt", "a") as myfile:
        myfile.write(str(id) + "#en\n")
    myfile.close()


def check_campus(bot, chat):
    if locals[chat][1] == "" or locals[chat][2] == "":
        bot.send_message(chat, get_text("set_campus", chat))
        global setting_campus
        setting_campus = True
        return False
    else:
        return True


def start(bot, message):
    if message.message.chat_id not in locals:
        addlocal(message.message.chat_id)
    admin = next((x for x in admins if x.ID == message.message.chat_id), None)
    if admin is not None:

        reply_markup = replykeyboardmarkup.ReplyKeyboardMarkup(
            [[get_text("Present", admin.ID), get_text("Not present", admin.ID),
              get_text("Time", admin.ID)],
             [get_text("look_requests", admin.ID)]],
            resize_keyboard=True)
        bot.send_message(message.message.chat_id,
                         get_text("set_status", admin.ID) % (message.message.chat.first_name),
                         reply_markup=reply_markup)
    else:
        reply_markup = replykeyboardmarkup.ReplyKeyboardMarkup([["\U0001F4A4", "\U0001F4A7"],
                                                                [get_text("change_campus", message.message.chat_id)],
                                                                [get_text("leave_request", message.message.chat_id)]],
                                                               resize_keyboard=True)
        bot.send_message(message.message.chat_id,
                         get_text("user_start", message.message.chat_id) % (
                             message.message.chat.first_name),
                         reply_markup=reply_markup)
        check_campus(bot, message.message.chat_id)


token = bot_data["token"]
stack_list = []
admins = [AdminUser(linen_admin), AdminUser(water_admin)]

with open('loc.json', encoding='utf8') as data_file:
    localisation_data = json.load(data_file)
data_file.close()

with open("loc.txt") as search:
    for line in search:
        line = line.rstrip().split("#")
        if len(line) > 2:
            locals[int(line[0])] = [line[1], line[2], line[3]]
        else:
            locals[int(line[0])] = [line[1], "", ""]
search.close()

updater = Updater(token)

with open("notifications.txt") as search:
    for line in search:
        set_up_notification(updater.bot, int(line), linenDays[int(locals[int(line)][1])][1])
search.close()

with open("reminders.txt") as search:
    for line in search:
        tmp = line.rstrip().split(" ")
        admin = next((x for x in admins if x.ID == int(tmp.pop(0))), None)
        for user in tmp:
            admin.users.append(int(user))
search.close()

with open("requests.txt") as search:
    for line in search:
        requests.append(line.rstrip().split(" ", 3))
search.close()

mydict = {'one': 1, 'two': 2, 'three': 3}
mykeys = ['three', 'one']
myvalues = itemgetter(*mykeys)(mydict)
print(myvalues)

updater.dispatcher.add_handler(CallbackQueryHandler(button))
updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('english', language))
updater.dispatcher.add_handler(CommandHandler('russian', language))
updater.dispatcher.add_handler(MessageHandler([Filters.text], process_message))

updater.start_polling()

updater.idle()

# ПРОВЕРИТЬ ТРЕД СЕФЕТИ
