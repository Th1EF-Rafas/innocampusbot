#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from telegram import replykeyboardmarkup, inlinekeyboardmarkup, inlinekeyboardbutton
from telegram.ext import Updater, CallbackQueryHandler, CommandHandler, MessageHandler, Filters, Job, JobQueue

from datetime import datetime
import dateutil.relativedelta as REL
import fileinput

import json

# insert exclamation mark and "two"

notifs = dict()
TIME_SHIFT = 0

firstAdmin = 98449438  # админ, отвечающий за смену постельного белья
secondAdmin = 98449438  # админ, отвечающий за смену воды

# 122762829 - мой
# 98449438 - Вера
# 188285490
# 234492255 - Галина, вода
# 94523403 - Артур

locals = dict()
notifs = dict()


class AdminUser(object):
    def __init__(self, id):
        self.status = "Present"
        self.ID = id
        self.users = []
        self.time_users = []
        self.timeset = False
        self.messages = []
        self.timers = None

    def setstatus(self, stat):
        self.status = stat


def createinlinekeyboard(list):
    tmp = []
    for l in list:
        tmp.append(inlinekeyboardbutton.InlineKeyboardButton(text=l[0], callback_data=l[1]))

    return inlinekeyboardmarkup.InlineKeyboardMarkup([tmp])


def alarm(bot, job):
    """Function to send the alarm message"""
    admin = job.context
    admin.setstatus("Not present")

    for user in admin.time_users:
        mess = bot.editMessageText(
            text=localisation_data["no_answer_users"][locals[user]],
            chat_id=user,
            message_id=next((x for x in admin.messages if x.chat.id == user), None).message_id)
        admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))

        bot.editMessageText(
            text=localisation_data["no_answer_admins"][locals[user]],
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
        admin.timers = job
        job_queue.put(job)
        admin.timeset = True

    if chat_id not in admin.time_users:
        admin.time_users.append(chat_id)


def button(bot, update):
    query = update.callback_query
    if query.data.startswith("Я жду вас!"):
        admin = next((x for x in admins if x.ID == int(query.data[+10:])), None)

        mark_up = createinlinekeyboard(
            [[localisation_data["user_got"][locals[query.message.chat_id]], "Я получил, что хотел" + str(admin.ID)]])

        mess = bot.editMessageText(text=localisation_data["notification"][locals[query.message.chat_id]],
                                   chat_id=query.message.chat_id,
                                   message_id=query.message.message_id,
                                   reply_markup=mark_up)
        admin.messages.append(mess)

        mark_up = createinlinekeyboard(
            [[localisation_data["walk_up"][locals[query.message.chat_id]], "Я выхожу" + str(admin.ID)]])

        if next((x for x in admin.messages if x.chat_id == admin.ID), None) is None:
            mess = bot.sendMessage(admin.ID, localisation_data["users_ready"][locals[admin.ID]], reply_markup=mark_up)
            admin.messages.append(mess)

        settimer(bot, admin, query.message.chat_id, JobQueue(bot, prevent_autostart=False))

    if query.data.startswith("Я получил, что хотел"):
        admin = next((x for x in admins if x.ID == int(query.data[+20:])), None)
        mess = bot.editMessageText(text=localisation_data["item_changed"][locals[query.message.chat_id]],
                                   chat_id=query.message.chat_id,
                                   message_id=query.message.message_id)
        admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))

    if query.data.startswith("Я выхожу"):
        admin = next((x for x in admins if x.ID == int(query.data[+8:])), None)
        admin.timeset = False
        job = admin.timers
        job.schedule_removal()
        del admin.timers

        mark_up = createinlinekeyboard(
            [[localisation_data["user_got"][locals[query.message.chat_id]], "Я получил, что хотел" + str(admin.ID)]])
        for user in admin.time_users:
            bot.editMessageText(text=localisation_data["admin_comes"][locals[user]], chat_id=user,
                                message_id=next((x for x in admin.messages if x.chat.id == user), None).message_id,
                                reply_markup=mark_up)
        admin.time_users.clear()

        mess = bot.editMessageText(text=localisation_data["good_trip"][locals[admin.ID]], chat_id=admin.ID,
                                   message_id=next((x for x in admin.messages if x.chat.id == admin.ID),
                                                   None).message_id)
        admin.messages.remove(next((x for x in admin.messages if x.message_id == mess.message_id), None))

    if query.data.startswith("first"):
        admin = next((x for x in admins if x.ID == int(query.data[+5:])), None)
        now = datetime.now()
        time = now.replace(hour=18 + TIME_SHIFT, minute=0, second=0, microsecond=0)
        if datetime.now().weekday() == 1 and now < time:
            bot.editMessageText(text=localisation_data["change_linen"][locals[query.message.chat_id]],
                                chat_id=query.message.chat_id,
                                message_id=query.message.message_id)

            time1 = now.replace(hour=9 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time2 = now.replace(hour=13 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time3 = now.replace(hour=14 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time4 = now.replace(hour=18 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            if (time1 <= now < time2) or (time3 <= now < time4):
                process_change(bot, admin, query.message.chat)
            else:
                if query.message.chat_id not in admin.users:
                    admin.users.append(query.message.chat_id)
                bot.send_message(query.message.chat_id,
                                 localisation_data["admin_not_works"][locals[query.message.chat_id]])

        else:
            mark_up = createinlinekeyboard([[localisation_data["Yes"][locals[query.message.chat_id]], "Yes1"],
                                            [localisation_data["No"][locals[query.message.chat_id]], 'No']])

            bot.editMessageText(
                text=localisation_data["tuesday_change"][locals[query.message.chat_id]],
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                reply_markup=mark_up)

    if query.data.startswith("second"):
        admin = next((x for x in admins if x.ID == int(query.data[+6:])), None)
        now = datetime.now()
        time = now.replace(hour=18 + TIME_SHIFT, minute=0, second=0, microsecond=0)
        if datetime.now().weekday() == 3 and now < time:
            bot.editMessageText(text=localisation_data["change_linen"][locals[query.message.chat_id]],
                                chat_id=query.message.chat_id,
                                message_id=query.message.message_id)

            time1 = now.replace(hour=9 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time2 = now.replace(hour=13 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time3 = now.replace(hour=14 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time4 = now.replace(hour=18 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            if (time1 <= now < time2) or (time3 <= now < time4):
                process_change(bot, admin, query.message.chat)
            else:
                if query.message.chat_id not in admin.users:
                    admin.users.append(query.message.chat_id)
                bot.send_message(query.message.chat_id,
                                 localisation_data["admin_not_works"][locals[query.message.chat_id]])

        else:
            mark_up = createinlinekeyboard([[localisation_data["Yes"][locals[query.message.chat_id]], "Yes2"],
                                            [localisation_data["No"][locals[query.message.chat_id]], 'No']])
            bot.editMessageText(
                text=localisation_data["thursday_change"][locals[query.message.chat_id]],
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                reply_markup=mark_up)

    if query.data == "No":
        bot.editMessageText(
            text=localisation_data["nice_day"][locals[query.message.chat_id]],
            chat_id=query.message.chat_id,
            message_id=query.message.message_id)

    if query.data.startswith("Yes"):
        camp = query.data[-1:]
        bot.editMessageText(
            text=localisation_data["next_weekday"][locals[query.message.chat_id]] + (
                localisation_data["tuesday"][locals[query.message.chat_id]] if camp == "1" else
                localisation_data["thursday"][locals[query.message.chat_id]]) + "!",
            chat_id=query.message.chat_id,
            message_id=query.message.message_id)

        rd = REL.relativedelta(days=1, weekday=(REL.TU if camp == "1" else REL.TH))
        today = datetime.now()
        time = int((datetime(*(today + rd).timetuple()[:3]) - today).total_seconds())
        job = Job(notify, time + 43200 + (TIME_SHIFT * 60 * 60), repeat=False, context=query.message.chat_id)

        notifs[job.context] = job
        JobQueue(bot, prevent_autostart=False).put(job)


def notify(bot, job):
    bot.send_message(job.context, localisation_data["change_today"][locals[job.context]])


def process_message(bot, message):
    text = message.message.text
    chat = message.message.chat
    text = text.strip()
    admin = next((x for x in admins if x.ID == chat.id), None)

    if admin is not None:
        if text == "На месте" or text == "Present" or text == "Не на месте" or text == "Not present":
            admin.setstatus("Present" if text == "На месте" or text == "Present" else "Not present")
            bot.send_message(chat.id, localisation_data["current_status"][locals[chat.id]] % (
                localisation_data[admin.status][locals[chat.id]]))
            if text == "На месте" or text == "Present":
                for user in admin.users:
                    bot.send_message(user, localisation_data["admin_returned"][locals[user]])
                admin.users = []

    else:

        if (text == "\U0001F4A4"):
            admin = next((x for x in admins if x.ID == firstAdmin), None)
            mark_up = createinlinekeyboard(
                [[localisation_data["first_campus"][locals[chat.id]], "first" + str(admin.ID)],
                 [localisation_data["second_campus"][locals[chat.id]], "second" + str(admin.ID)]])
            bot.send_message(chat.id, localisation_data["campus"][locals[chat.id]], reply_markup=mark_up)

        if (text == "\U0001F4A7"):
            now = datetime.now()
            time1 = now.replace(hour=12 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time2 = now.replace(hour=13 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time3 = now.replace(hour=17 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            time4 = now.replace(hour=18 + TIME_SHIFT, minute=0, second=0, microsecond=0)
            admin = next((x for x in admins if x.ID == secondAdmin), None)
            if ((time1 <= now < time2) or (time3 <= now < time4)) and now.today().weekday() < 5:
                bot.send_message(chat.id, localisation_data["change_water"][locals[chat.id]])
                process_change(bot, admin, chat)
            else:
                if chat.id not in admin.users:
                    admin.users.append(chat.id)
                bot.send_message(chat.id, localisation_data["admin_not_works"][locals[chat.id]])

    print('Got message: \33[0;32m{0}\33[0m from chat: {1}'.format(text, chat))


def process_change(bot, admin, chat):
    if admin.status == "Present":
        bot.send_message(chat.id, localisation_data["admin_workplace"][locals[chat.id]])

        mark_up = createinlinekeyboard(
            [[localisation_data["user_wait"][locals[chat.id]], "Я жду вас!" + str(admin.ID)],
             [localisation_data["user_got"][locals[chat.id]], "Я получил, что хотел" + str(admin.ID)]])
        bot.send_message(chat.id, localisation_data["right_place"][locals[chat.id]], reply_markup=mark_up)
    else:
        bot.send_message(chat.id, localisation_data["admin_not_present"][locals[chat.id]])
        bot.send_message(admin.ID,
                         localisation_data["user_wants"][locals[chat.id]] % (chat.last_name, chat.first_name,
                                                                             localisation_data["water"][locals[
                                                                                 admin.ID]] if admin.ID == secondAdmin else
                                                                             localisation_data["linen"][locals[
                                                                                 admin.ID]]))
        bot.send_message(chat.id, localisation_data["need_message"][locals[chat.id]])
        if chat.id not in admin.users:
            admin.users.append(chat.id)


def language(bot, message):
    locals[message.message.chat_id] = message.message.text[1:3]

    for tmp in fileinput.input('loc.txt', inplace=True):
        if tmp.startswith(str(message.message.chat_id)):
            print(tmp.rstrip().replace(tmp, str(message.message.chat_id) + "#" + locals[message.message.chat_id]))
        else:
            print((tmp.rstrip().replace(tmp, tmp)))
    fileinput.close()
    start(bot, message)


def addlocal(id):
    locals[id] = "en"
    with open("loc.txt", "a") as myfile:
        myfile.write(str(id) + "#en\n")


def start(bot, message):
    if message.message.chat_id not in locals:
        addlocal(message.message.chat_id)
    admin = next((x for x in admins if x.ID == message.message.chat_id), None)
    if admin is not None:

        reply_markup = replykeyboardmarkup.ReplyKeyboardMarkup(
            [[localisation_data["Present"][locals[admin.ID]], localisation_data["Not present"][locals[admin.ID]]]],
            resize_keyboard=True)
        bot.send_message(message.message.chat_id,
                         localisation_data["set_status"][locals[admin.ID]] % (message.message.chat.first_name),
                         reply_markup=reply_markup)
    else:
        reply_markup = replykeyboardmarkup.ReplyKeyboardMarkup([["\U0001F4A4", "\U0001F4A7"]], resize_keyboard=True)
        bot.send_message(message.message.chat_id,
                         localisation_data["user_start"][locals[message.message.chat_id]] % (
                             message.message.chat.first_name),
                         reply_markup=reply_markup)


token = '238900236:AAG_QHIiuYqIXwSiXHlnHb6WbTuDR2jJo30'
# test_token 234786021:AAE4ZysONnfLaV82kRTQaxluF7DAbfeDJ7k
# super_token 238900236:AAG_QHIiuYqIXwSiXHlnHb6WbTuDR2jJo30
stack_list = []
admins = [AdminUser(firstAdmin), AdminUser(secondAdmin)]

with open('loc.json', encoding='utf8') as data_file:
    localisation_data = json.load(data_file)
    data_file.close()

with open("loc.txt") as search:
    for line in search:
        line = line.rstrip().split("#")
        locals[int(line[0])] = line[1]
    search.close()

updater = Updater(token)

updater.dispatcher.add_handler(CallbackQueryHandler(button))
updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('english', language))
updater.dispatcher.add_handler(CommandHandler('russian', language))
updater.dispatcher.add_handler(MessageHandler([Filters.text], process_message))
# updater.dispatcher.add_handler(CommandHandler("set", set, pass_job_queue=True))

updater.start_polling()

updater.idle()