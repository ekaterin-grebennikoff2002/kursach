import os
import time
import psycopg2
import asyncio
import logging
import sys
import pytz
import schedule
from datetime import datetime, timedelta
from croniter import croniter
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hlink
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F


postgresUser = os.environ.get("POSTGRES_USER")
postgresPassword = os.environ.get("POSTGRES_PASSWORD")
postgresHost = os.environ.get("POSTGRES_HOST")
postgresPort = os.environ.get("POSTGRES_PORT")
postgresDatabase = os.environ.get("POSTGRES_DATABASE")

API_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

connection = psycopg2.connect(
    host=postgresHost,
    database=postgresDatabase,
    user=postgresUser,
    password=postgresPassword,
)

dp = Dispatcher()

bot = Bot(API_TOKEN, parse_mode=ParseMode.HTML)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    kb = [
        [
            types.KeyboardButton(text="Напоминания"),
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выберите способ подачи"
    )
    await message.answer(f"""Чтобы добавить напоминание введи команду, аналогичную следующей:
напоминание
-название лекарства-
-строка в {hlink('cron-формате', 'https://crontab.guru/')}-

Чтобы просмотреть список напоминаний введи
напоминания
    """, reply_markup=keyboard)
    
    
@dp.message(F.text.lower() != "напоминания")
async def set_reminder(message: types.Message):
    chatId = str(message.chat.id)
    text = message.text.split('\n')
    if len(text) != 3:
        await message.answer("Неизвестная команда")
        return
    if (text[1] == 'напоминание'):
        await message.answer("Неизвестная команда")
        return
    medication_name = text[1]
    cron_expression = text[2]        
    
    now = utc_to_moscow(datetime.now(pytz.utc))
    try:
        iter = croniter(cron_expression, now)
        nextDate = iter.get_next()
        nextDateMoscow = utc_to_moscow(datetime.fromtimestamp(nextDate))
        insert_query = "INSERT INTO notifications (text, chat, template, nextDate, isDone) VALUES (%s, %s, %s, %s, %s)"
        values = (medication_name, chatId, cron_expression, nextDateMoscow, False)

        cursor = connection.cursor()    
        cursor.execute(insert_query, values)
        connection.commit()
        cursor.close()
        await message.answer(f"Установлено напоминание {medication_name} с расписанием: {cron_expression}, следующее {nextDateMoscow}")
    except Exception:
        await message.answer("Ошибка в cron-выражении")
        return
    
def utc_to_moscow(d: datetime): 
    moscow_timezone = pytz.timezone('Europe/Moscow')
    return d.astimezone(moscow_timezone)

@dp.message(F.text.lower() == "напоминания")
async def list_reminders(message: types.Message):
    cursor = connection.cursor()
    cursor.execute(f"SELECT id, text, template, nextDate FROM notifications WHERE chat = '{message.chat.id}' ORDER BY id ASC")
    records = cursor.fetchall()
    cursor.close()
    if len(records) > 0: 
        for record in records:
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Удалить",
                callback_data="Удалить|"+record[0])
            )
            builder.add(types.InlineKeyboardButton(
                text="Отменить на один раз",
                callback_data="Отменить|"+record[0])
            )
            await message.answer(f"""
Лекарство: {record[1]}
Шаблон: {record[2]}
Следующее напоминание: {utc_to_moscow(record[3])}""", reply_markup=builder.as_markup())
    else: 
        await message.answer("Напоминаний нет")
    
@dp.callback_query(F.data.startswith('Удалить'))
async def deleteNotification(callback: types.CallbackQuery):
    cursor = connection.cursor()
    primary_key_value = callback.data.split('|')[1]
    query = "SELECT id, text, template FROM notifications WHERE id = %s"
    cursor.execute(query, (primary_key_value,))
    record = cursor.fetchone()
    
    if record:
        deleteQuery = "DELETE FROM notifications WHERE id = %s"
        cursor.execute(deleteQuery, (primary_key_value,))
        connection.commit()
        await callback.message.answer(f"""
Напоминание удалено!
{record[1]}
{record[2]}""",)
    else:
        await callback.answer("Напоминание не найдено")
        
@dp.callback_query(F.data.startswith('Отменить'))
async def cancelNotification(callback: types.CallbackQuery):
    cursor = connection.cursor()
    primary_key_value = callback.data.split('|')[1]
    query = "SELECT id, text, template, nextDate FROM notifications WHERE id = %s"
    cursor.execute(query, (primary_key_value,))
    record = cursor.fetchone()
    
    if record:
        now = utc_to_moscow(record[3])
        iter = croniter(record[2], now)
        nextDate = datetime.fromtimestamp(iter.get_next())
        nextDateMoscow = utc_to_moscow(nextDate)
        deleteQuery = "UPDATE notifications SET nextDate = %s, isDone = TRUE WHERE id = %s"
        cursor.execute(deleteQuery, (nextDateMoscow, primary_key_value,))
        connection.commit()
        await callback.message.answer(f"""
Напоминание отменено на один раз!
{record[1]}
{record[2]}
{nextDateMoscow}""",)
    else:
        await callback.answer("Напоминание не найдено")
        



@dp.callback_query(F.data.startswith('Выпита'))
async def doneNotification(callback: types.CallbackQuery):
    cursor = connection.cursor()
    primary_key_value = callback.data.split('|')[1]
    query = "SELECT id, text, template, nextDate FROM notifications WHERE id = %s"
    cursor.execute(query, (primary_key_value,))
    record = cursor.fetchone()
    
    if record:
        now = utc_to_moscow(datetime.now(pytz.utc))
        iter = croniter(record[2], now)
        nextDate = iter.get_next()
        nextDateMoscow = utc_to_moscow(datetime.fromtimestamp(nextDate))
        updateQuery = "UPDATE notifications SET nextDate = %s, isDone = TRUE WHERE id = %s"
        cursor.execute(updateQuery, (nextDateMoscow, primary_key_value,))
        connection.commit()
        await callback.message.answer(f"""
Таблетка выпита! 
Следующий раз {nextDateMoscow}""",)
    else:
        await callback.answer("Напоминание не найдено")


@dp.callback_query(F.data.startswith('Отложена'))
async def delayNotification(callback: types.CallbackQuery):
    cursor = connection.cursor()
    primary_key_value = callback.data.split('|')[1]
    query = "SELECT id, text, template, nextDate FROM notifications WHERE id = %s"
    cursor.execute(query, (primary_key_value,))
    record = cursor.fetchone()
    
    if record:
        nextDateMoscow = utc_to_moscow(datetime.now(pytz.utc) + timedelta(minutes=10))
        updateQuery = "UPDATE notifications SET nextDate = %s, isDone = TRUE WHERE id = %s"
        cursor.execute(updateQuery, (nextDateMoscow, primary_key_value,))
        connection.commit()
        await callback.message.answer(f"""
Таблетка отложена! 
Следующий раз {nextDateMoscow}""",)
    else:
        await callback.answer("Напоминание не найдено")

async def routine():
    print('routin started')
    cursor = connection.cursor()
    select_query = """
SELECT id, text, chat
FROM notifications
WHERE isDone = FALSE OR nextDate < %s;"""
    current_datetime = datetime.now()
    try:
        cursor.execute(select_query, (current_datetime,))
        records = cursor.fetchall()
        for record in records:
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Таблетка выпита",
                callback_data="Выпита|"+record[0])
            )
            builder.add(types.InlineKeyboardButton(
                text="Отложить на 10 минут",
                callback_data="Отложена|"+record[0])
            )
            await bot.send_message(chat_id=record[2], text=record[2], reply_markup=builder.as_markup())
        for record in records:
            update_query = """
                UPDATE notifications
                SET isDone = TRUE
                WHERE id = %s;"""
            cursor.execute(update_query, (record[0],))
        connection.commit()
    except psycopg2.Error as e:
        print(f"Error selecting records: {e}")


async def main():
    await dp.start_polling(bot)
    

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
    


