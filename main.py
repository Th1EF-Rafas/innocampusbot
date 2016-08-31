#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from telegram import replykeyboardmarkup, inlinekeyboardmarkup, inlinekeyboardbutton
from telegram.ext import Updater, CallbackQueryHandler, CommandHandler, MessageHandler, Filters, Job, JobQueue

from datetime import datetime
import dateutil.relativedelta as REL
import fileinput

import json
from botsettings import data as bot_data

TIME_SHIFT = bot_data["time_shift_server"]

firstAdmin = bot_data["first_admin"]  # админ, отвечающий за смену постельного белья
secondAdmin = bot_data["second_admin"]  # админ, отвечающий за смену воды

locals = dict()
notifs = dict()

linenTime = bot_data["linen_time"]
waterTime = bot_data["water_time"]

linenDays = {key: bot_data[key] for key in [1, 2, 3]}


class AdminUser(object):
    def __init__(self, id):
        self.status = "Present"
        self.ID = id
        self.users = []
        self.time_users = []
        self.timeset = False
        self.messages = []
        self.timer = None

    def setstatus(self, stat):
        self.status = stat


def createinlinekeyboard(keylist):
    tmp = []
    for l in keylist:
        tmp.append(inlinekeyboardbutton.InlineKeyboardButton(text=l[0], callback_data=l[1]))
    return inlinekeyboardmarkup.InlineKeyboardMarkup([tmp])


def alarm(bot, job):
    """Function to send the alarm message"""
    admin = job.context
    admin.setstatus("Not present")

    for user in admin.time_users:
        mess = bot.editMessageText(
            text=localisation_data["no_answer_users"][locals[user][0]],
            chat_id=user,
            message_id=next((x for x in admin.messages if x.chat.id == user), None).message_id)
        admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))

    bot.editMessageText(
        text=localisation_data["no_answer_admins"][locals[user][0]],
        chat_id=admin.ID,
        message_id=next((x for x in admin.messages if x.chat.id == admin.ID), None).message_id)
    admin.messages.remove(next((x for x in admin.messages if x.chat.id == admin.ID), None))

    for user in admin.time_users:
        if user not in admin.users:
            admin.users.append(user)
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


# function is too huge
def button(bot, update):
    query = update.callback_query
    if query.data.startswith("Я жду вас!"):
        admin = next((x for x in admins if x.ID == int(query.data[+10:])), None)

        mark_up = createinlinekeyboard(
            [[localisation_data["user_got"][locals[query.message.chat_id][0]], "Я получил, что хотел" + str(admin.ID)]])

        mess = bot.editMessageText(text=localisation_data["notification"][locals[query.message.chat_id][0]],
                                   chat_id=query.message.chat_id,
                                   message_id=query.message.message_id,
                                   reply_markup=mark_up)
        admin.messages.append(mess)

        mark_up = createinlinekeyboard(
            [[localisation_data["walk_up"][locals[query.message.chat_id][0]], "Я выхожу" + str(admin.ID)]])

        if next((x for x in admin.messages if x.chat_id == admin.ID), None) is None:
            mess = bot.sendMessage(admin.ID, localisation_data["users_ready"][locals[admin.ID][0]],
                                   reply_markup=mark_up)
            admin.messages.append(mess)

        settimer(bot, admin, query.message.chat_id, JobQueue(bot, prevent_autostart=False))

    if query.data.startswith("Я получил, что хотел"):
        admin = next((x for x in admins if x.ID == int(query.data[+20:])), None)
        mess = bot.editMessageText(text=localisation_data["item_changed"][locals[query.message.chat_id][0]],
                                   chat_id=query.message.chat_id,
                                   message_id=query.message.message_id)
        admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))

    if query.data.startswith("Я выхожу"):
        admin = next((x for x in admins if x.ID == int(query.data[+8:])), None)
        admin.timeset = False
        job = admin.timer
        job.schedule_removal()
        del admin.timer

        mark_up = createinlinekeyboard(
            [[localisation_data["user_got"][locals[query.message.chat_id][0]], "Я получил, что хотел" + str(admin.ID)]])
        for user in admin.time_users:
            bot.editMessageText(text=localisation_data["admin_comes"][locals[user][0]], chat_id=user,
                                message_id=next((x for x in admin.messages if x.chat.id == user), None).message_id,
                                reply_markup=mark_up)
        admin.time_users.clear()

        mess = bot.editMessageText(text=localisation_data["good_trip"][locals[admin.ID][0]], chat_id=admin.ID,
                                   message_id=next((x for x in admin.messages if x.chat.id == admin.ID),
                                                   None).message_id)
        admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))

    if query.data == "No":
        bot.editMessageText(
            text=localisation_data["nice_day"][locals[query.message.chat_id][0]],
            chat_id=query.message.chat_id,
            message_id=query.message.message_id)

    if query.data.startswith("Yes"):
        campus = int(query.data[-1:])
        bot.editMessageText(
            text=localisation_data["next_weekday"][locals[query.message.chat_id][0]] % (
                localisation_data[linenDays[campus][0]][locals[query.message.chat_id][0]]),
            chat_id=query.message.chat_id,
            message_id=query.message.message_id)

        rd = REL.relativedelta(days=1, weekday=linenDays[campus][1])
        today = datetime.now()
        time = int((datetime(*(today + rd).timetuple()[:3]) - today).total_seconds())
        job = Job(notify, time + 43200 + (TIME_SHIFT * 60 * 60), repeat=False, context=query.message.chat_id)

        notifs[job.context] = job
        JobQueue(bot, prevent_autostart=False).put(job)


def process_water(bot, chat):
    admin = next((x for x in admins if x.ID == firstAdmin), None)
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
        bot.send_message(chat_id=chat, text=localisation_data["change_linen"][locals[chat][0]])

        time1 = now.replace(hour=linenTime[0] + TIME_SHIFT, minute=0, second=0, microsecond=0)
        time2 = now.replace(hour=linenTime[1] + TIME_SHIFT, minute=0, second=0, microsecond=0)
        time3 = now.replace(hour=linenTime[2] + TIME_SHIFT, minute=0, second=0, microsecond=0)
        time4 = now.replace(hour=linenTime[3] + TIME_SHIFT, minute=0, second=0, microsecond=0)
        if (time1 <= now < time2) or (time3 <= now < time4):
            process_change(bot, admin, chat)
        else:
            if chat not in admin.users:
                admin.users.append(chat)
            bot.send_message(chat, localisation_data["admin_not_works"][locals[chat][0]])

    else:
        mark_up = createinlinekeyboard([[localisation_data["Yes"][locals[chat][0]], "Yes" + str(campus)],
                                        [localisation_data["No"][locals[chat][0]], 'No']])

        bot.send_message(
            chat_id=chat, text=localisation_data["linen_day_change"][locals[chat][0]] % (
                localisation_data[linenDays[campus][0]][locals[chat][0]]), reply_markup=mark_up)


def notify(bot, job):
    bot.send_message(job.context, localisation_data["change_today"][locals[job.context][0]])


changing_time = False
setting_campus = False


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
                bot.send_message(admin.ID, localisation_data["time_changed"][locals[admin.ID][0]])
            except:
                bot.send_message(admin.ID, localisation_data["wrong_data"][locals[admin.ID][0]])
        else:
            # possible changing?
            if text == localisation_data["Present"][locals[admin.ID][0]] \
                    or text == localisation_data["Not present"][locals[admin.ID][0]]:
                admin.setstatus("Present" if text == "На месте" or text == "Present" else "Not present")
                bot.send_message(chat.id, localisation_data["current_status"][locals[chat.id][0]] % (
                    localisation_data[admin.status][locals[chat.id][0]]))
                if text == localisation_data["Present"][locals[admin.ID][0]]:
                    for user in admin.users:
                        bot.send_message(user, localisation_data["admin_returned"][locals[user][0]])
                    admin.users = []
            if text == localisation_data["Time"][locals[admin.ID][0]]:
                bot.send_message(admin.ID, localisation_data["set_time"][locals[admin.ID][0]])
                changing_time = True


    else:

        global setting_campus
        if setting_campus:
            try:
                t = [int(i) for i in text.rstrip().split(" ")]
                if len(t) != 2:
                    raise Exception()
                change_campus(message, t)
                setting_campus = False

                bot.send_message(chat.id, localisation_data["campus_set"][locals[chat.id][0]])
            except:
                bot.send_message(chat.id, localisation_data["wrong_campus_data"][locals[chat.id][0]])

        if not setting_campus and check_campus(bot, chat.id):
            if (text == "\U0001F4A4"):
                process_water(bot, chat.id)

            if (text == "\U0001F4A7"):
                now = datetime.now()
                time1 = now.replace(hour=waterTime[0] + TIME_SHIFT, minute=0, second=0, microsecond=0)
                time2 = now.replace(hour=waterTime[1] + TIME_SHIFT, minute=0, second=0, microsecond=0)
                time3 = now.replace(hour=waterTime[2] + TIME_SHIFT, minute=0, second=0, microsecond=0)
                time4 = now.replace(hour=waterTime[3] + TIME_SHIFT, minute=0, second=0, microsecond=0)
                admin = next((x for x in admins if x.ID == secondAdmin), None)
                if ((time1 <= now < time2) or (time3 <= now < time4)) and now.today().weekday() < 5:
                    bot.send_message(chat.id, localisation_data["change_water"][locals[chat.id][0]])
                    process_change(bot, admin, chat)
                else:
                    if chat.id not in admin.users:
                        admin.users.append(chat.id)
                    bot.send_message(chat.id, localisation_data["admin_not_works"][locals[chat.id][0]])

            if text == localisation_data["change_campus"][locals[message.message.chat_id][0]]:
                locals[chat.id][1] = locals[chat.id][2] = ""
                check_campus(bot, chat.id)

    print('Got message: \33[0;32m{0}\33[0m from chat: {1}'.format(text, chat))


def change_campus(message, t):
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
        bot.send_message(chat.id, localisation_data["admin_workplace"][locals[chat.id][0]])

        mark_up = createinlinekeyboard(
            [[localisation_data["user_wait"][locals[chat.id][0]], "Я жду вас!" + str(admin.ID)],
             [localisation_data["user_got"][locals[chat.id][0]], "Я получил, что хотел" + str(admin.ID)]])
        bot.send_message(chat.id, localisation_data["right_place"][locals[chat.id][0]], reply_markup=mark_up)
    else:
        bot.send_message(chat.id, localisation_data["admin_not_present"][locals[chat.id][0]])
        bot.send_message(admin.ID,
                         localisation_data["user_wants"][locals[chat.id][0]]
                         % (chat.last_name, chat.first_name,
                            localisation_data["water" if admin.ID == secondAdmin else "linen"][locals[admin.ID][0]]))
        bot.send_message(chat.id, localisation_data["need_message"][locals[chat.id][0]])
        if chat.id not in admin.users:
            admin.users.append(chat.id)


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
    locals[id][0] = "en"
    with open("loc.txt", "a") as myfile:
        myfile.write(str(id) + "#en\n")


def check_campus(bot, chat):
    if locals[chat][1] == "" or locals[chat][2] == "":
        bot.send_message(chat, localisation_data["set_campus"][locals[chat][0]])
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
            [[localisation_data["Present"][locals[admin.ID][0]], localisation_data["Not present"][locals[admin.ID][0]],
              localisation_data["Time"][locals[admin.ID][0]]]],
            resize_keyboard=True)
        bot.send_message(message.message.chat_id,
                         localisation_data["set_status"][locals[admin.ID][0]] % (message.message.chat.first_name),
                         reply_markup=reply_markup)
    else:
        if check_campus(bot, message.message.chat_id):
            reply_markup = replykeyboardmarkup.ReplyKeyboardMarkup([["\U0001F4A4", "\U0001F4A7"],
                                                                    [localisation_data["change_campus"][
                                                                         locals[message.message.chat_id][0]]]],
                                                                   resize_keyboard=True)
            bot.send_message(message.message.chat_id,
                             localisation_data["user_start"][locals[message.message.chat_id][0]] % (
                                 message.message.chat.first_name),
                             reply_markup=reply_markup)


token = bot_data["token"]
stack_list = []
admins = [AdminUser(firstAdmin), AdminUser(secondAdmin)]

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

updater.dispatcher.add_handler(CallbackQueryHandler(button))
updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('english', language))
updater.dispatcher.add_handler(CommandHandler('russian', language))
updater.dispatcher.add_handler(MessageHandler([Filters.text], process_message))

updater.start_polling()

updater.idle()
