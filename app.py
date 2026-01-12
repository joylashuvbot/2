
import asyncio, math, re, aiosqlite, os, requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton
)
from geopy.geocoders import Nominatim
import spacy
from aiogram.filters import BaseFilter

from dotenv import load_dotenv
load_dotenv()

# ---------------- konfig ----------------
BOT_TOKEN  = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_ID   = set(int(i.strip()) for i in os.getenv("ADMIN_ID").split(","))


DB_FILE = "halal_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                text_user TEXT NOT NULL,
                text_channel TEXT NOT NULL
            )
        """)
        await db.commit()

async def load_places_from_db():
    await init_db()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM places") as cur:
            rows = await cur.fetchall()
            if not rows:
                return None
            return [
                {
                    "id": r[0],               # ← bu majburiy
                    "name": r[1],
                    "lat": r[2],
                    "lng": r[3],
                    "text_user": r[4],
                    "text_channel": r[5],
                    "text": r[4]              # eski kodlar uchun
                }
                for r in rows
            ]

async def add_place_to_db(name, lat, lng, text_user, text_channel):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO places (name, lat, lng, text_user, text_channel) VALUES (?, ?, ?, ?, ?)",
            (name, lat, lng, text_user, text_channel)
        )
        await db.commit()

async def delete_place_from_db(place_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM places WHERE id = ?", (place_id,))
        await db.commit()

async def update_place_field_in_db(place_id: int, field: str, new_value: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(f"UPDATE places SET {field} = ? WHERE id = ?", (new_value, place_id))
        await db.commit()

# Windows vs Linux ajratmasdan, har doim bot papkasida saqlaymiz


# ✅ app.py boshiga (allqachon bor, lekin to‘liq)
async def load_places():
    rows = await load_places_from_db()
    if rows is None:                       # birinchi marta
        for p in initial_places:
            await add_place_to_db(
                p["name"], p["lat"], p["lng"],
                p["text"],                 # text_user
                p["text"]                  # text_channel
            )
        rows = await load_places_from_db()
    return rows

# ✅ PLACES ni bot ishga tushishi bilan yuklaymiz
PLACES = []  # boshlang'ich qiymat



initial_places = [
            {
                "name": "CHAIHANA-AMIR",
                "lat": 38.61700400,
                "lng": -121.53797100,
                "text": (
                    "🍽️ <b>CHAIHANA-AMIR</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=38.61700400 ,-121.53797100">Sacramento, CA</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    "📞 +19167506977  +19169405677\n"
                    '📋 <a href="https://t.me/myhalalmenu/8 ">Меню</a>\n'
                    "📱 Telegram: @MYHALAL_FOOD"
                )          
            },
            {
                "name": "CALIKEBAB",
                "lat": 34.10675400,
                "lng": -117.28975700,
                "text": (
                    "🍽️ <b>CALIKEBAB - UZBEK HALAL KITCHEN</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/5n9mjK8yG5wPqiT7A ">San Bernardino, CA</a>\n'
                    '📍 <a href="https://maps.app.goo.gl/gg3z2rg3h9qQKgao6 ">Las Vegas, NV</a>\n'
                    '📍 <a href="https://maps.app.goo.gl/CjjAZP8Zai1yNkvs5 ">Salt Lake City, UT</a>\n'
                    "🏠 Сеть ресторанов и магазины\n"
                    "🧾 Продукты готовы, можно забрать сразу\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    "🅿️ Есть парковка для траков\n"
                    '🌐 <a href="https://t.me/myhalalmenu/7 ">Меню</a>: www.calikebab.la\n'
                    "📞 +17472027777\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "XADICHAI-KUBRO",
                "lat": 38.61708200,
                "lng": -121.53778900,
                "text": (
                    "🍽️ <b>XADICHAI-KUBRO</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=38.61708200 ,-121.53778900">Sacramento, CA</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 6–7 ч до доставки\n"
                    "⏰ 08:00 – 19:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/9 ">Меню</a> (в комментариях)\n'
                    "📞 +12797901986\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "UMAR-UZBEK-NATIONAL-FOOD",
                "lat": 38.61700400,
                "lng": -121.53797100,
                "text": (
                    "🍽️ <b>UMAR UZBEK NATIONAL FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=38.61700400 ,-121.53797100">Sacramento, CA</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Заказы за 4–5 ч до доставки\n"
                    "⏰ 10:00 – 20:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/10 ">Меню</a> (в комментариях)\n'
                    "📞 +19165333778\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "RANO-OPA-KITCHEN",
                "lat": 37.80681200,
                "lng": -122.41256100,
                "text": (
                    "🍽️ <b>RANO OPA KITCHEN – HALOL MILLIY UZBEK TAOMLARI</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=37.80681200 ,-122.41256100">San Francisco, CA</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/11 ">Меню</a> (в комментариях)\n'
                    "📞 +15107782614\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "DENVER-HALAL-FOOD",
                "lat": 39.79106000,
                "lng": -104.90467400,
                "text": (
                    "🍽️ <b>DENVER HALAL FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=39.79106000 ,-104.90467400">Denver, CO</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 09:00 – 00:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/12 ">Меню</a> (в комментариях)\n'
                    "📞 +17207564155\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "TRUCKERS-HALAL-FOOD",
                "lat": 39.73438200,
                "lng": -104.84645600,
                "text": (
                    "🍽️ <b>TRUCKERS HALAL FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=39.73438200 ,-104.84645600">Denver, CO</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 08:00 – 00:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/13 ">Меню</a> (в комментариях)\n'
                    "📞 +17209935823\n"
                    "📱 Telegram: @MYHALAL_FOOD, @Denverfood"
                )
            },
            {
                "name": "BAUYRSAQ-EXPRESS",
                "lat": 47.24476600,
                "lng": -122.38548700,
                "text": (
                    "🍽️ <b>BAUYRSAQ EXPRESS – Uzbek · Kazakh · Kirgiz kitchen</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=47.24476600 ,-122.38548700">Tacoma, WA</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/14 ">Меню</a> (в комментариях)\n'
                    "📞 +14257577206\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "ASIA-HALAL-FOOD",
                "lat": 47.24476600,
                "lng": -122.38548700,
                "text": (
                    "🍽️ <b>ASIA HALAL FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=47.24476600 ,-122.38548700">Tacoma, WA</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/15 ">Меню</a> (в комментариях)\n'
                    "📞 +18782294148  +18782294149\n"
                    "📱 Telegram: @MYHALAL_FOOD, @AsiaHalalFood"
                )
            },
            {
                "name": "UZBEK-HALOL-FOOD",
                "lat": 47.24476600,
                "lng": -122.38548700,
                "text": (
                    "🍽️ <b>UZBEK HALOL FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=47.24476600 ,-122.38548700">Tacoma, WA</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 08:00 – 22:00\n"
                    "🚘 Доставка бесплатно\n"
                    '📋 <a href="https://t.me/myhalalmenu/16 ">Меню</a> (в комментариях)\n'
                    "📞 +13609306392  +12534485190\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "AMIN-FOOD",
                "lat": 47.24476600,
                "lng": -122.38548700,
                "text": (
                    "🍽️ <b>AMIN FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=47.24476600 ,-122.38548700">Tacoma, WA</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 08:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/18 ">Меню</a> (в комментариях)\n'
                    "📞 +19167380322\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "CARAVAN-RESTAURANT-2",
                "lat": 47.66120600,
                "lng": -122.32378600,
                "text": (
                    "🍽️ <b>CARAVAN RESTAURANT – 2</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=47.66120600 ,-122.32378600">Seattle, WA</a>\n'
                    "🏠 Ресторан\n"
                    "🗺 Адреса:\n"
                    "— <a href=\"https://maps.app.goo.gl/RiKVT3aQoJbWZ3xg8 \">405 NE 45th St, Seattle, WA 98105</a>\n"
                    "— <a href=\"https://maps.app.goo.gl/LrTdvgjfGZzxe2mr6 \">7801 Detroit Ave SW, Seattle, WA 98106</a>\n"
                    "— <a href=\"https://maps.app.goo.gl/zs2dnzLgCF6h1SoC8 \">3215 4th Ave S, Seattle, WA</a>\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 11:00 – 23:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/19 ">Меню</a> (в комментариях)\n'
                    "📞 +12065457499\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "SADIYA-OSHXONASI",
                "lat": 39.27019000,
                "lng": -84.44163700,
                "text": (
                    "🍽️ <b>SADIYA OSHXONASI VA CAKE LAB</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=39.27019000 ,-84.44163700">Cincinnati, OH</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 09:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/20 ">Меню</a> (в комментариях)\n'
                    "📞 +15134449371\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "DELICIOUS-FOODS",
                "lat": 39.26986100,
                "lng": -84.43900900,
                "text": (
                    "🍽️ <b>DELICIOUS FOODS</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=39.26986100 ,-84.43900900">Cincinnati, OH</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 4 ч до доставки\n"
                    "⏰ 09:00 – 20:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/21 ">Меню</a> (в комментариях)\n'
                    "📞 +15134046762\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "ROBIYA-BAKERY",
                "lat": 39.26866500,
                "lng": -84.43942300,
                "text": (
                    "🍽️ <b>ROBIYA BAKERY</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=39.26866500 ,-84.43942300">Cincinnati, OH</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 4–5 ч до доставки\n"
                    "⏰ 09:00 – 21:00\n"
                    "🚘 Доставка по Dayton и Hebron\n"
                    '📋 <a href="https://t.me/myhalalmenu/22 ">Меню</a> (в комментариях)\n'
                    "📞 +15132249300\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "CHAYHANA-1",
                "lat": 39.31210400,
                "lng": -84.37738100,
                "text": (
                    "🍽️ <b>CHAYHANA №1</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=39.31210400 ,-84.37738100">Cincinnati, OH</a>\n'
                    "🍴 Ресторан\n"
                    "🧾 Блюда готовы, можно забрать\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/23 ">Меню</a> (в комментариях)\n'
                    "📞 +15137550596\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "SHEF-MOM",
                "lat": 39.38454100,
                "lng": -84.34233300,
                "text": (
                    "🍽️ <b>SHEF MOM – CAKE – SUSHI</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=39.38454100 ,-84.34233300">Cincinnati, OH</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 5 ч до доставки\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/24 ">Меню</a> (в комментариях)\n'
                    "📞 +14704000770\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "TAJIKSKO-UZBEKSKAYA-KUHNYA",
                "lat": 41.28132000,
                "lng": -96.21969700,
                "text": (
                    "🍽️ <b>Таджикско-узбекская Национальная кухня</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=41.28132000 ,-96.21969700">Omaha, NE</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/25 ">Меню</a> (в комментариях)\n'
                    "📞 +14026168772\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "ZARINA-FOOD",
                "lat": 40.28957100,
                "lng": -76.88458100,
                "text": (
                    "🍽️ <b>ZARINA FOOD UYGʻUR OSHXONASI</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=40.28957100 ,-76.88458100">Harrisburg, PA</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 08:00 – 18:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/26 ">Меню</a> (в комментариях)\n'
                    "📞 +17175626326\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "PIZZA-BARI",
                "lat": 40.44370500,
                "lng": -79.99612500,
                "text": (
                    "🍽️ <b>PIZZA BARI</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=40.44370500 ,-79.99612500">Pittsburgh, PA</a>\n'
                    "🏠 Кафе\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 10:00 – 02:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/28 ">Меню</a> (в комментариях)\n'
                    "📞 +14124020444  +14126090714\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "MUSOJON",
                "lat": 33.55247500,
                "lng": -112.15317400,
                "text": (
                    "🍽️ <b>MUSOJON</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=33.55247500 ,-112.15317400">Phoenix, AZ</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 05:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/29 ">Меню</a> (в комментариях)\n'
                    "📞 +16028201597\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "ARIZONA-HALAL-FOOD-1",
                "lat": 33.53869100,
                "lng": -112.18625700,
                "text": (
                    "🍽️ <b>ARIZONA HALAL FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=33.53869100 ,-112.18625700">Phoenix, AZ</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 4–5 ч до доставки\n"
                    "⏰ 08:00 – 20:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/30 ">Меню</a> (в комментариях)\n'
                    "📞 +14807891711\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "TOSHKENT-MILLIY-TAOMLARI",
                "lat": 33.49340800,
                "lng": -112.33416100,
                "text": (
                    "🍽️ <b>TOSHKENT MILLIY TAOMLARI</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=33.49340800 ,-112.33416100">Phoenix, AZ</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 07:00 – 21:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/31 ">Меню</a> (в комментариях)\n'
                    "📞 +16232056021  +16023489938\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "ALIS-KITCHEN",
                "lat": 33.46092400,
                "lng": -112.25515400,
                "text": (
                    "🍽️ <b>ALI'S KITCHEN</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=33.46092400 ,-112.25515400">Phoenix, AZ</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 09:00 – 00:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/32 ">Меню</a> (в комментариях)\n'
                    "📞 +16026997010\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "UZBEK-HALAL-FOODS-MEMPHIS",
                "lat": 35.04594700,
                "lng": -90.02337700,
                "text": (
                    "🍽️ <b>UZBEK HALAL FOODS</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/DxTwbfJaypEZvf647 ">Memphis, TN</a> (Arkansas border)\n'
                    "🏠 Фудтрак\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 09:00 – 23:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/33 ">Меню</a> (в комментариях)\n'
                    "📞 +15126693163\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "MADI-FOOD",
                "lat": 28.03012900,
                "lng": -82.45883800,
                "text": (
                    "🍽️ <b>MADI FOOD (Uygʻurcha taomlar)</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=28.03012900 ,-82.45883800">Tampa, FL</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/34 ">Меню</a> (в комментариях)\n'
                    "📞 +17178058368\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "CHAYHANA-ORLANDO",
                "lat": 28.66596900,
                "lng": -81.41681300,
                "text": (
                    "🍽️ <b>CHAYHANA ORLANDO</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=28.66596900 ,-81.41681300">Orlando, FL</a>\n'
                    "🏠 Ресторан\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 11:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/35 ">Меню</a> (в комментариях)\n'
                    "📞 +13214220143\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "CARAVAN-RESTAURANT-CHICAGO",
                "lat": 41.87811400,
                "lng": -87.62979800,
                "text": (
                    "🍽️ <b>CARAVAN RESTAURANT</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/gj72DoxeAVhTFgsy5 ">Chicago, IL</a>\n'
                    "🏠 Ресторан\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/36 ">Меню</a> (в комментариях)\n'
                    "📞 +17733673258\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "TAKU-FOOD",
                "lat": 41.98429200,
                "lng": -87.69751100,
                "text": (
                    "🍽️ <b>TAKU FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=41.98429200 ,-87.69751100">Chicago, IL</a>\n'
                    "🏠 Ресторан\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 08:00 – 23:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/37 ">Меню</a> (в комментариях)\n'
                    "📞 +12247600211  +17736812626\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "KAZAN-KEBAB",
                "lat": 41.77922600,
                "lng": -88.34295400,
                "text": (
                    "🍽️ <b>KAZAN KEBAB</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=41.77922600 ,-88.34295400">Chicago, IL</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/38 ">Меню</a> (в комментариях)\n'
                    "📞 +15517869980\n"
                    "📱 Telegram: @Ali071188, @MYHALAL_FOOD"
                )
            },
            {
                "name": "MAKSAT-FOOD-TRUCK",
                "lat": 45.52630600,
                "lng": -122.63703900,
                "text": (
                    "🍽️ <b>MAKSAT FOOD TRUCK</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=45.52630600 ,-122.63703900">Portland, OR</a>\n'
                    "🚛 Фудтрак\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 10:00 – 23:00\n"
                    "🚘 Доставка бесплатная\n"
                    '📋 <a href="https://t.me/myhalalmenu/39 ">Меню</a> (в комментариях)\n'
                    "📞 +13602108483\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "NAVAT-PDX",
                "lat": 45.54936400,
                "lng": -122.66185700,
                "text": (
                    "🍽️ <b>NAVAT PDX</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=45.54936400 ,-122.66185700">Portland, OR</a>\n'
                    "🚛 Фудтрак\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 11:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/40 ">Меню</a> (в комментариях)\n'
                    "📞 +14254282011  +17253774764\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "OSH-RESTAURANT-AND-GRILL",
                "lat": 36.11125400,
                "lng": -86.74126300,
                "text": (
                    "🍽️ <b>OSH RESTAURANT AND GRILL</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=36.11125400 ,-86.74126300">Nashville, TN</a>\n'
                    "🏠 Ресторан\n"
                    "🧾 Заказы до 21:00\n"
                    "⏰ Вт–Вс: 11:00 – 21:00 | Пн: выходной\n"
                    "🚘 Доставка: 10:00 – 02:00\n"
                    '📋 <a href="https://t.me/myhalalmenu/42 ">Меню</a> (в комментариях)\n'
                    "📞 +16157102288  +16159684444  +16157129985\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "BROOKLYN-PIZZA",
                "lat": 36.11934500,
                "lng": -86.74898100,
                "text": (
                    "🍽️ <b>BROOKLYN PIZZA</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=36.11934500 ,-86.74898100">Nashville, TN</a>\n'
                    "🏠 Кафе\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка: 24/7 — $1 за милю\n"
                    '📋 <a href="https://t.me/myhalalmenu/43 ">Меню</a> (в комментариях)\n'
                    "📞 +16159552222  +16159257070\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "KAMOLA-OSHXONASI",
                "lat": 35.96075200,
                "lng": -83.92075000,
                "text": (
                    "🍽️ <b>KAMOLA OSHXONASI</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/Z83tPnCtbYSxLuCL9 ">Knoxville, TN</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 4–5 ч до доставки\n"
                    "⏰ 09:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/44 ">Меню</a> (в комментариях)\n'
                    "📞 +18654100845\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "UZBEGIM-RESTAURANT",
                "lat": 36.16266400,
                "lng": -86.78160200,
                "text": (
                    "🍽️ <b>UZBEGIM RESTAURANT</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/9U3e96s2EmA6sUMG6 ">Nashville, TN</a>\n'
                    "🏠 Кафе\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ Время уточняется\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/45 ">Меню</a> (в комментариях)\n'
                    "📞 +13476138691\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "BARAKAT-HALAL-FOOD",
                "lat": 29.78456000,
                "lng": -95.80117000,
                "text": (
                    "🍽️ <b>BARAKAT HALAL FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=29.78456000 ,-95.80117000">Houston, TX</a>\n'
                    "🏠 Фудтрак\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка 24/7\n"
                    '📋 <a href="https://t.me/myhalalmenu/46 ">Меню</a> (в комментариях)\n'
                    "📞 +13463772939\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "DIYAR-HOUSTON-FOOD",
                "lat": 29.77985100,
                "lng": -95.88196500,
                "text": (
                    "🍽️ <b>DIYAR HOUSTON FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=29.77985100 ,-95.88196500">Houston, TX</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 4–5 ч до доставки\n"
                    "⏰ 09:30 – 23:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/47 ">Меню</a> (в комментариях)\n'
                    "📞 +13462740363\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "CARAVAN-HOUSE",
                "lat": 41.04526200,
                "lng": -81.58033400,
                "text": (
                    "🍽️ <b>CARAVAN HOUSE</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=41.04526200 ,-81.58033400">Akron, OH</a>\n'
                    "🏠 Ресторан рядом с AMAZON\n"
                    "🧾 Продукты готовы, можно купить сразу\n"
                    "⏰ 09:00 – 23:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/48 ">Меню</a> (в комментариях)\n'
                    "📞 +14405755555  +12344020202\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "CHAYHANA-PERRYSBURG",
                "lat": 41.57081200,
                "lng": -83.62053800,
                "text": (
                    "🍽️ <b>CHAYHANA</b>\n"
                    "📍 Perrysburg / Toledo, OH\n"
                    "🏠 Ресторан\n"
                    "🧾 Заказы за 4–5 ч до доставки\n"
                    "⏰ 08:00 – 00:00\n"
                    "🚘 Доставка через Uber / DoorDash\n"
                    '📋 <a href="https://t.me/myhalalmenu/49 ">Меню</a> (в комментариях)\n'
                    "📞 +14196034800\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "TASHKENTFOOD-HALAL",
                "lat": 39.44555600,
                "lng": -84.20035400,
                "text": (
                    "🍽️ <b>Tashkentfood Xalal</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/8aKnspJrH5vPfMq79 ">Lebanon, OH</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2 ч до получения\n"
                    "⏰ 08:00 – 21:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/50 ">Меню</a> (в комментариях)\n'
                    "📞 +15133321404\n"
                    "📱 Telegram: @MYHALAL_FOOD, @Tashkent halal food Ohio"
                )
            },
            {
                "name": "NUR-KITCHEN",
                "lat": 30.43137000,
                "lng": -97.75393400,
                "text": (
                    "🍽️ <b>NUR KITCHEN</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=30.43137000 ,-97.75393400">Austin, TX</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 09:00 – 21:00\n"
                    "🚘 Доставка: бесплатно по Austin, Pflugerville, San Marcos\n"
                    '📋 <a href="https://t.me/myhalalmenu/53 ">Меню</a> (в комментариях)\n'
                    "📞 +17377078330\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "MAZALI-CHARLOTTE-OSHXONASI",
                "lat": 35.23408200,
                "lng": -80.87282000,
                "text": (
                    "🍽️ <b>MAZALI CHARLOTTE OSHXONASI</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=35.23408200 ,-80.87282000">Charlotte, NC</a>\n'
                    "🏠 Ресторан\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ Пн–Пт: 11:00 – 20:00 | Сб–Вс: выходной\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/54 ">Меню</a> (в комментариях)\n'
                    "📞 +13477856222  +13476666930\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "NND-FOOD",
                "lat": 35.25497600,
                "lng": -80.97975000,
                "text": (
                    "🍽️ <b>N.N.D FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=35.25497600 ,-80.97975000">Charlotte, NC</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/55 ">Меню</a> (в комментариях)\n'
                    "📞 +17045764025  +17046191145  +19802393354\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "AFSONA",
                "lat": 40.63575300,
                "lng": -73.97448900,
                "text": (
                    "🍽️ <b>Afsona</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=40.63575300 ,-73.97448900">Brooklyn, NY</a>\n'
                    "🏠 Ресторан\n"
                    "🧾 Заказы заранее, еду можно забирать\n"
                    "⏰ 06:00 – 23:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/57 ">Меню</a> (в комментариях)\n'
                    "📞 +17186333006  +19296224444  +19294002252\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "UZBEKISTAN-TAOMLARI",
                "lat": 40.09541213,
                "lng": -75.04420414,
                "text": (
                    "🍽️ <b>UZBEKISTAN TAOMLARI</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=40.09541213 ,-75.04420414">Bustleton, PA</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы заранее\n"
                    "⏰ Время уточняется\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/58 ">Меню</a> (в комментариях)\n'
                    "📞 +12672442371\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "BARAKAT-KAZAKH-CUISINE",
                "lat": 34.11959200,
                "lng": -83.76195000,
                "text": (
                    "🍽️ <b>Barakat Казахская Cuisine</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=34.11959200 ,-83.76195000">Braselton, GA</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 09:00 – 18:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/59 ">Меню</a> (в комментариях)\n'
                    "📞 +14706689307\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "VIRGINIA-DC-UZBEK-HALAL",
                "lat": 38.79516300,
                "lng": -77.52366300,
                "text": (
                    "🍽️ <b>Virginia & DC Uzbek Halal Food</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=38.79516300 ,-77.52366300">Virginia / DC Area</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 07:00 – 00:00\n"
                    "🚘 Доставка: I-66, I-95, I-81\n"
                    '📋 <a href="https://t.me/myhalalmenu/60 ">Меню</a> (в комментариях)\n'
                    "📞 +15716327034\n"
                    "📱 Telegram: @MYHALAL_FOOD, @virginia_halal_food"
                )
            },
            {
                "name": "ISLOM-BALTIMORE-FOOD",
                "lat": 39.36578700,
                "lng": -76.75882500,
                "text": (
                    "🍽️ <b>ISLOM BALTIMORE FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=39.36578700 ,-76.75882500">Baltimore, MD</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 07:00 – 18:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/61 ">Меню</a> (в комментариях)\n'
                    "📞 +15677070708\n"
                    "📱 Telegram: @MYHALAL_FOOD, @Madinakhonmd"
                )
            },
            {
                "name": "IRODA-OSHXONASI",
                "lat": 30.41205600,
                "lng": -88.82872200,
                "text": (
                    "🍽️ <b>IRODA OSHXONASI</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/wCDtog9z5zeqyAeY8 ">Ocean Springs, MS</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за день до доставки\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/62 ">Меню</a> (в комментариях)\n'
                    "📞 +12282432635\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "TASHKENT-CUISINE",
                "lat": 40.44291300,
                "lng": -80.08243800,
                "text": (
                    "🍽️ <b>TASHKENT CUISINE</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=40.44291300 ,-80.08243800">Pittsburgh, PA</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/63 ">Меню</a> (в комментариях)\n'
                    "📞 +14125190156\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "ARIZONA-HALAL-FOOD-2",
                "lat": 33.46083600,
                "lng": -112.20724400,
                "text": (
                    "🍽️ <b>ARIZONA HALAL FOOD</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=33.46083600 ,-112.20724400">Phoenix, AZ</a>\n'
                    "🏠 Кухня на вынос из дома\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 08:00 – 00:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/64 ">Меню</a> (в комментариях)\n'
                    "📞 +14806343188\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "SILK-ROAD-UZBEK-KAZAKH",
                "lat": 34.05223500,
                "lng": -117.60254700,
                "text": (
                    "🍽️ <b>SILK ROAD UZBEK - KAZAKH kitchen</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/LbdR5qiVbxSYt4F49 ">Ontario, CA (TA Truck Stop)</a>\n'
                    "🚛 Фудтрак\n"
                    "🧾 Блюда готовы к выдаче\n"
                    "⏰ 08:00 – 23:00\n"
                    "🚘 Доставка до 50 миль\n"
                    '📋 <a href="https://t.me/myhalalmenu/65 ">Меню</a> (в комментариях)\n'
                    "📞 +18722221736\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "HALAL-FOOD-IN-NASHVILLE",
                "lat": 36.04294500,
                "lng": -86.74166700,
                "text": (
                    "🍽️ <b>HALAL FOOD IN NASHVILLE</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=36.04294500 ,-86.74166700">Nashville, TN</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 30 мин до доставки\n"
                    "⏰ 07:00 – 23:00\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/66 ">Меню</a> (в комментариях)\n'
                    "📞 +16156913309\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "HALOL-FOOD-MUHAMMADAMIN-ASAKA",
                "lat": 36.18959100,
                "lng": -86.47507800,
                "text": (
                    "🍽️ <b>HALOL FOOD MUHAMMADAMIN ASAKA</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=36.18959100 ,-86.47507800">Nashville, TN</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2 ч до доставки\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/67 ">Меню</a> (в комментариях)\n'
                    "📞 +12159296717  +18352059595\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "UZBEK-FOOD-MINNESOTA",
                "lat": 44.97775300,
                "lng": -93.26501100,
                "text": (
                    "🍽️ <b>UZBEK FOOD MINNESOTA</b>\n"
                    "📍 Minneapolis, MN\n"
                    "🏠 Кухня на вынос из дома\n"
                    "🧾 Заказы за 4–5 ч до доставки\n"
                    "⏰ 08:00 – 22:00\n"
                    "🚘 Доставка есть\n"
                    "📋 Меню: смотреть в комментариях\n"
                    "📞 +16513525551\n"
                    "📱 Telegram: @Manzura_Burkhan, @MYHALAL_FOOD"
                )
            },
            {
                "name": "OASIS-DLYA-TRAKEROV",
                "lat": 32.77666500,
                "lng": -96.79698900,
                "text": (
                    "🍽️ <b>ОАЗИС ДЛЯ ТРАКЕРОВ</b>\n"
                    "📍 Dallas, TX\n"
                    "🏠 Доставка свежей домашней еды к вашей парковке (до 30 миль)\n"
                    "✨ Условия доставки:\n"
                    "— Минимум $30\n"
                    "— Доставка $15\n"
                    "— Бесплатно от $250\n"
                    "🧾 100% халяль: борщи, плов, пельмени, салаты, выпечка\n"
                    "🚚 Заказ за 3–4 ч до получения\n"
                    "💰 Скидки постоянным\n"
                    '🌐 <a href="https://t.me/oasiseda ">Меню</a>\n'
                    "📞 +13478881927\n"
                    "📱 Telegram: https://t.me/oasiseda , @MYHALAL_FOOD"
                )
            },
            {
                "name": "GOLDEN-BY-NUSAYBA",
                "lat": 39.92883400,
                "lng": -74.23729300,
                "text": (
                    "🍽️ <b>GOLDEN BY NUSAYBA</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/N58gFq6UrewBrBWm7 ">New Jersey, Lakewood</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Готовлю по желанию клиента\n"
                    "⏰ 08:00 – 00:00\n"
                    "🚘 Доставка есть\n"
                    "📋 Меню: смотреть в Instagram\n"
                    "📞 +13478137000\n"
                    "📱 Instagram: @golden_by_nusayba_nj"
                )
            },
            {
                "name": "UZBEKISTAN-RESTAURANT-CINCINNATI",
                "lat": 39.10311800,
                "lng": -84.51202000,
                "text": (
                    "🍽️ <b>UZBEKISTAN RESTAURANT</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/28d42BXtNPUZ9D7GA ">Cincinnati Ohio</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 10:00 – 22:00\n"
                    "🚘 Доставка 24/7\n"
                    '📋 <a href="https://t.me/myhalalmenu/72 ">Меню</a>\n'
                    "📞 +12674230301\n"
                    "📱 Telegram: @MYHALAL_FOOD"
                )
            },
            {
                "name": "BISMILLAH-HALAL-FOOD",
                "lat": 41.87811400,
                "lng": -87.62979800,
                "text": (
                    "🍽️ <b>Bismillah HALAL FOOD</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/az7BJLtakcbejw4K6 ">Chicago IL</a>\n'
                    "🏠 Домашняя кухня\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/73 ">Меню</a>\n'
                    "📞 +14075957655\n"
                )
            },
            {
                "name": "KHOZYAYUSHKA-UZBEK-KITCHEN",
                "lat": 36.07954100,
                "lng": -86.69676900,
                "text": (
                    "🍽️ <b>Хозяюшка Uzbek kitchen</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=36.07954100 ,-86.69676900">Nashville, TN</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/78 ">Меню</a> (в комментариях)\n'
                    "📞 +16159799172\n"
                    "📱 Telegram: @Xozayush, @MYHALAL_FOOD"
                )
            },
            {                   
                "name": "ATLAS-KITCHEN",
                "lat": 38.85842400,
                "lng": -94.81290200,
                "text": (
                    "🍽️ <b>ATLAS KITCHEN</b>\n"
                    '📍 <a href="https://www.google.com/maps?q=38.85842400 ,-94.81290200">Kansas City, KS/MO</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 4–5 ч до доставки\n"
                    "⏰ 15:00 – 22:00\n"
                    "🚘 Доставка: Договорная\n"
                    '📋 <a href="https://t.me/myhalalmenu/81 ">Меню</a> (в комментариях)\n'
                    "📞 +19134869109  +19899544770\n"
                    "📱 Telegram: @Sabru_jamil1, @Bek_KC"
                )
            },    
            {
                "name": "RAIANA-HALAL-FOOD",
                "lat": 38.58157200,
                "lng": -121.49440000,
                "text": (
                    "🍽️ <b>RAIANA halal food</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/bgCVHfHMcR3hfdzx5 ">Sacramento, CA</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 2–3 ч до доставки\n"
                    "⏰ 24/7\n"
                    "🚘 Доставка есть\n"
                    '📋 <a href="https://t.me/myhalalmenu/79 ">Меню</a> (в комментариях)\n'
                    "📞 +17732567187  +1773256893\n"
                    "📱 Telegram: @Raiana_halal_food, @MYHALAL_FOOD"
                )
            },
            {
                "name": "HALAL-JASMIN-KITCHEN",
                "lat": 39.09972700,
                "lng": -94.57856700,
                "text": (
                    "🍽️ <b>Halal Jasmin Kitchen</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/MTc7JWSzKxafXtH27 ">Kansas</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 1.5–2 ч до доставки\n"
                    "⏰ 09:00 – 00:00\n"
                    "🚘 Бесплатная доставка по Kansas City\n"
                    '📋 <a href="https://t.me/myhalalmenu/80 ">Меню</a> (в комментариях)\n'
                    "📞 +18162991870\n"
                    "📱 Telegram: @Rozazhasmin, @MYHALAL_FOOD"
                )
            },
            {
                "name": "YASINA-FOOD",
                "lat": 28.53833600,
                "lng": -81.37923400,
                "text": (
                    "🍽️ <b>Yasina Food</b>\n"
                    '📍 <a href="https://maps.app.goo.gl/eVZw1iT74fqb9LSMA ">Orlando FL</a>\n'
                    "🏠 Домашняя кухня на вынос\n"
                    "🧾 Заказы за 3–4 ч до доставки\n"
                    "⏰ 09:00 – 22:00\n"
                    "🚘 Доставка по тракстопам\n"
                    '📋 <a href="https://t.me/myhalalmenu/82 ">Меню</a> (в комментариях)\n'
                    "📞 +16892389299\n"
                    "📱 Telegram: @yasishfood, @MYHALAL_FOOD"
                )
            }
        ]




async def add_place_to_db(name: str, lat: float, lng: float, text_user: str, text_channel: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO places (name, lat, lng, text_user, text_channel) VALUES (?, ?, ?, ?, ?)",
            (name, lat, lng, text_user, text_channel)
        )
        await db.commit()

# ---------------- global o'zgaruvchilar ---------------- 
# ---------------- bot va dispatcher ----------------
bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
geolocator = Nominatim(user_agent="halal_bot")



try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
    nlp = spacy.load("en_core_web_sm")

# ---------------- masofa (None xavfsiz) ----------------
# Agar siz haversine ichida print qo'shgan bo'lsangiz, uni ham olib tashlang:
def haversine(lat1, lon1, lat2, lon2):
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float('inf')
    R = 6371
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# ---------------- spaCy ----------------
def extract_city_spacy(text: str) -> str:
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "GPE":
            return ent.text
    return text.strip()

# ---------------- kordinata ----------------
async def coords_from_any(text: str):
    place = extract_city_spacy(text)
    try:
        loc = await asyncio.to_thread(geolocator.geocode, place, language="ru", timeout=10)
        if loc:
            return loc.latitude, loc.longitude
    except Exception:
        pass  # print o'rniga pass
    return None, None

# ---------------- havoladan lat/lng ----------------


def parse_gmaps_link(url: str):
    try:
        # 1) qisqa havolani ochamiz
        if "maps.app.goo.gl" in url:
            resp = requests.head(url, allow_redirects=True, timeout=10)
            url = resp.url  # oxirgi (haqiqiy) havola
        # 2) endi lat/lng izlaymiz
        m = re.search(r'[?&]q=([-0-9.]+),([-0-9.]+)', url)
        if m:
            return float(m.group(1)), float(m.group(2))
        m = re.search(r'@([-0-9.]+),([-0-9.]+)', url)
        if m:
            return float(m.group(1)), float(m.group(2))
    except Exception:
        pass
    return None, None

# ---------------- FSM ----------------
# ---------------- FSM ----------------
class AddRest(StatesGroup):
    number = State()
    name = State()
    city = State()
    map_link = State()
    details = State()
    menu_num = State()
    phone = State()
    telegram = State()
    extra_info = State()          # ← ixtiyoriy
    confirm = State()


class EditDeleteRest(StatesGroup):
    waiting_for_number = State()   # foydalanuvchi raqam kiritmoqda
    edit_index = State()           # tahrirlanayotgan restoran indeksi
    action = State()               # qaysi maydon tahrirlanmoqda
    waiting_location_link = State()  # ← NEW: havola kutilmoqda

class EditNumFilter(BaseFilter):
    pattern = re.compile(r"^edit_(\d+)$")

    async def __call__(self, call: types.CallbackQuery) -> bool | dict:
        match = self.pattern.match(call.data)
        return {"edit_index": int(match.group(1))} if match else False

class EditLocLinksFilter(BaseFilter):
    pattern = re.compile(r"^edit_location_links_(\d+)$")

    async def __call__(self, call: types.CallbackQuery) -> bool | dict:
        match = self.pattern.match(call.data)
        return {"edit_index": int(match.group(1))} if match else False

# ---------------- inline tugmalar ----------------
def confirm_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data="confirm_add"),
            InlineKeyboardButton(text="❌ Бекор қилиш", callback_data="cancel_add")
        ]
    ])

def admin_main_menu_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Yangi restoran qo‘shish", callback_data="start_add_rest")],
            [InlineKeyboardButton(text="📋 Barcha restoranlar", callback_data="show_all_restaurants")]
        ]
    )



# ---------------- admin panel ----------------
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("👋 Botdan foydalanish uchun joy yoki shahar nomini yuboring.")
        return
    await message.answer("🔐 Admin panelga xush kelibsiz!", reply_markup=admin_main_menu_ikb())

@dp.callback_query(F.data == "start_add_rest")
async def inline_add_rest(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AddRest.number)
    await call.message.answer("🔢 Restarant raqamini kiriting (faqat kanal uchun, masalan: 71):",
                              reply_markup=types.ReplyKeyboardRemove())

@dp.message(AddRest.number)
async def got_number(message: types.Message, state: FSMContext):
    await state.update_data(number=message.text.strip())
    await state.set_state(AddRest.name)
    await message.answer("🍽️ Restoran nomini kiriting:")

@dp.message(AddRest.name)
async def got_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddRest.city)
    await message.answer("📍 Shahar nomini kiriting (masalan: Orlando FL):")

@dp.message(AddRest.city)
async def got_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(AddRest.map_link)
    await message.answer("🔗 Joylashuv havolasini yuboring (Google Maps link):")

@dp.message(AddRest.map_link)
async def got_link(message: types.Message, state: FSMContext):
    await state.update_data(map_link=message.text)
    await state.set_state(AddRest.details)
    await message.answer(
        "🏠 Restarant haqida ma'lumot kiriting (1 xabarda):\n"
        "Masalan:\n"
        "Домашняя кухня на вынос\n"
        "Заказы за 3–4 ч до доставки\n"
        "Доставка по тракстопам\n"
        "⏰ 09:00-22:00"
    )

@dp.message(AddRest.details)
async def got_det(message: types.Message, state: FSMContext):
    await state.update_data(details=message.text)
    await state.set_state(AddRest.menu_num)
    await message.answer("📃 Menu havolasi raqamini kiriting (faqat raqam, masalan: 82):")

@dp.message(AddRest.menu_num)
async def got_menu(message: types.Message, state: FSMContext):
    await state.update_data(menu_num=message.text.strip())
    await state.set_state(AddRest.phone)
    await message.answer("📞 Telefon raqamini kiriting (masalan: +16892389299):")

@dp.message(AddRest.phone)
async def got_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await state.set_state(AddRest.telegram)
    await message.answer("📱 Telegram username’ni yuboring (@sizning_user shaklida):")


@dp.message(AddRest.telegram)
async def got_tg(message: types.Message, state: FSMContext):
    username = message.text.strip()
    # 1️⃣ format tekshiruvi
    if not username.startswith('@') or len(username) < 2:
        await message.answer("❌ Iltimos, to‘g‘ri formatda kiriting (@sizning_user shaklida):")
        return

    # 2️⃣ saqlaymiz
    await state.update_data(telegram=username)

    # 3️⃣ qo'shimcha bosqichiga o‘tamiz
    await state.set_state(AddRest.extra_info)
    await message.answer(
        "📝 Qo'shimcha ma’lumot kiriting (masalan: «Пн–Вс: 10:00–22:00» yoki bo'sh qoldirish uchun pastdagi tugmani bosing):",
        reply_markup=skip_extra_ikb()
    )    

def skip_extra_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Tashlab ketish", callback_data="skip_extra")]
        ]
    )


@dp.callback_query(AddRest.extra_info, F.data == "skip_extra")
async def skip_extra_handler(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(extra_info="")          # bo‘sh qoldirdik
    await show_confirmation(call, state)            # to‘liq ko‘rsatishga o‘tamiz   

# @dp.callback_query(F.data == "skip_extra", AddRest.extra_info)
# async def skip_extra(call: types.CallbackQuery, state: FSMContext):
#     await state.update_data(extra_info="")
#     await call.message.delete()
#     await show_confirmation(call, state)

@dp.message(AddRest.extra_info, F.text)
async def save_extra_info(message: types.Message, state: FSMContext):
    await state.update_data(extra_info=message.text.strip())
    await show_confirmation(message, state)


async def show_confirmation(src: types.Message | types.CallbackQuery,
                            state: FSMContext):
    data = await state.get_data()
    extra = data.get('extra_info', '').strip()

    # 1️⃣ Kanalga yuboriladigan TO‘LIQ matn (raqam bilan)
    channel_text = (
        f"#️⃣{data['number']}\n"
        f"🍽️ <b>{data['name']}</b>\n"
        f"📍 <a href='{data['map_link']}'>{data['city']}</a>\n"
        f"{data['details']}\n"
        f"📋 <a href='https://t.me/myhalalmenu/{data['menu_num']}'>Меню</a>\n"
        f"📞 {data['phone']}\n"
        f"📱 Telegram: {data['telegram']}\n"
    )
    if extra:
        channel_text += f"📝 Qoʻshimcha: {extra}\n"

    # 2️⃣ Foydalanuvchiga ko‘rsatiladigan TO‘LIQ matn (raqamsiz)
    user_text = re.sub(r'^#️⃣\d+\n', '', channel_text, flags=re.M)

    await state.update_data(channel_text=channel_text, user_text=user_text)

    # 3️⃣ To‘g‘ri yuborish metodini tanlaymiz
    send = (
        src.message.answer if isinstance(src, types.CallbackQuery) else src.answer
    )

    # 4️⃣ Agar matn 4096 belgidan oshsa – 2 qismga bo‘lib yuboramiz
    if len(user_text) > 4096:
        part1 = user_text[:4096]
        part2 = user_text[4096:]
        await send(part1)
        await send(part2 + "\n\n✅ Tasdiqlash uchun pastdagi tugmalardan foydalaning:", reply_markup=confirm_ikb())
    else:
        await send(
            f"📤 Quyidagi ko‘rinishda yuboriladi:\n\n{user_text}",
            reply_markup=confirm_ikb()
        )

@dp.callback_query(F.data == "cancel_edit")
async def cancel_edit(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Tahrirlash bekor qilindi.")
    await call.answer()



# ---------------- tasdiqlash/bekor qilish ----------------
@dp.callback_query(F.data == "cancel_add")
async def cancel_add(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Qo‘shish bekor qilindi.")
    await call.answer("Bekor qilindi", show_alert=False)

@dp.callback_query(F.data == "confirm_add")
async def confirm_add(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lat, lng = parse_gmaps_link(data['map_link'])
    if lat is None:
        lat, lng = await coords_from_any(data['city'])
    if lat is None:
        await call.answer("❌ Havola yaroqsiz! Qayta yuboring.", show_alert=True)
        await state.set_state(AddRest.map_link)
        await call.message.answer("🔗 Yangi Google-Maps havolasini yuboring:")
        return

    extra = data.get('extra_info', '').strip()

    channel_text = (
        f"#️⃣{data['number']}\n"
        f"🍽️ <b>{data['name']}</b>\n"
        f"📍 <a href='{data['map_link']}'>{data['city']}</a>\n"
        f"{data['details']}\n"
        f"📋 <a href='https://t.me/myhalalmenu/{data['menu_num']}'>Меню</a>\n"
        f"📞 {data['phone']}\n"
        f"📱 Telegram: {data['telegram']}\n"
    )
    if extra:
        channel_text += f"📝 Qoʻshimcha: {extra}\n"

    user_text = re.sub(r'^#️⃣\d+\n', '', channel_text, flags=re.M)

    new_place = {
        "name": data['name'],
        "lat": lat,
        "lng": lng,
        "text_user": user_text,
        "text_channel": channel_text,
        "text": user_text
    }

    # JSON emas, SQLite ga yozamiz
    await add_place_to_db(
        new_place["name"],
        new_place["lat"],
        new_place["lng"],
        new_place["text_user"],
        new_place["text_channel"]
    )

    # xotiraga ham qo‘shamiz (foydalanish oson)
    PLACES.append(new_place)

    await bot.send_message(CHANNEL_ID, channel_text, parse_mode=ParseMode.HTML)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("✅ Yangi restoran muvaffaqiyatli qo‘shildi va kanalga yuborildi!", show_alert=True)
    await state.clear()

# ---------------- barcha restoranlar ----------------
@dp.callback_query(F.data == "show_all_restaurants")
async def show_all_restaurants(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    if not PLACES:
        await call.message.answer("❌ Hech qanday restoran topilmadi.")
        return

    text = "📋 <b>Barcha restoranlar ro'yxati:</b>\n\n"
    for i, place in enumerate(PLACES, start=1):
        text += f"{i}. <b>{place['name']}</b>\n"

    await call.message.answer(text + "\n\n📌 Raqam kiriting:")
    await state.set_state(EditDeleteRest.waiting_for_number)

# ---------------- tahrirlash/ochirish uchun raqam kiritish ----------------
@dp.message(EditDeleteRest.waiting_for_number, F.text.isdigit())
async def handle_number_input(message: types.Message, state: FSMContext):
    num = int(message.text)
    if 1 <= num <= len(PLACES):
        place = PLACES[num - 1]
        await state.update_data(edit_index=num - 1)
        display_text = get_display_text(place)
        await message.answer(f"Siz tanladingiz:\n\n{display_text}", reply_markup=get_edit_delete_kb(num - 1))  # ← 0-bazadagi indeks
    else:
        await message.answer("❌ Noto‘g‘ri raqam. Iltimos, ro‘yxatdagi raqamdan birini kiriting.")

@dp.message(EditDeleteRest.waiting_for_number)
async def handle_invalid_input(message: types.Message):
    await message.answer("❌ Iltimos, faqat raqam kiriting.")

def get_edit_delete_kb(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_{index}"),InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"delete_{index}")]
    ])

# ---------------- tahrirlash ----------------
@dp.callback_query(EditNumFilter())
async def prompt_edit_rest(call: types.CallbackQuery, state: FSMContext, edit_index: int):
    if 0 <= edit_index < len(PLACES):
        place = PLACES[edit_index]
        await state.update_data(edit_index=edit_index)
        display_text = get_display_text(place)

        kb = [
            [InlineKeyboardButton(text="🍽 Restoran nomi", callback_data="edit_name")],
            [InlineKeyboardButton(text="📍 Joylashuv nomi", callback_data="edit_location_names")],
            [InlineKeyboardButton(text="🔗 Joylashuv havolasi", callback_data=f"edit_location_links_{edit_index}")],
            [InlineKeyboardButton(text="📋 Tafsilotlar", callback_data="edit_details")],
            [InlineKeyboardButton(text="📝 Menyu raqami", callback_data="edit_menu_num")],
            [InlineKeyboardButton(text="📞 Telefon raqami", callback_data="edit_phone")],
            [InlineKeyboardButton(text="📱 Telegram username", callback_data="edit_telegram")],
        ]

        # 📝 Qo'shimcha bormi?
        txt = place.get("text", "") or place.get("text_user", "") or place.get("text_channel", "")
        if re.search(r'^📝 Q.*?shimcha:', txt, flags=re.M):
            kb.append([InlineKeyboardButton(text="📝 Qoʻshimcha", callback_data="edit_extra")])

        kb.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_edit")])

        await call.message.answer(
            f"Tanlangan restoran:\n\n{display_text}\n\nQuyidagi ma'lumotlarni tahrirlash uchun tugmalardan foydalaning:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    else:
        await call.message.answer("❌ Noto‘g‘ri raqam.")

@dp.callback_query(F.data == "edit_name")
async def prompt_edit_name(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("🍽 Yangi restoran nomini kiriting:")
    await state.set_state(EditDeleteRest.action)
    await state.update_data(edit_action="name")


async def reload_single_place_in_memory(place_id: int):
    """
    SQLite'dan yangilangan yozuvni o‘qib, PLACES massividagi
    tegishli elementni almashtiradi.
    """
    global PLACES
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM places WHERE id = ?", (place_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return
            updated = {
                "id": row[0],
                "name": row[1],
                "lat": row[2],
                "lng": row[3],
                "text_user": row[4],
                "text_channel": row[5],
                "text": row[4]          # eski kodlar uchun
            }

    # PLACES massividagi tegishli elementni topib almashtiramiz
    for idx, p in enumerate(PLACES):
        if p["id"] == place_id:
            PLACES[idx] = updated
            break



def replace_name_everywhere(old: str, new: str, text: str) -> str:
    """
    Faqat boshidagi 🍽️ va <b> tegini ichidagi nomni almashtiradi.
    Matn ichidagi boshqa holatlarni buzmaysiz.
    """
    # 1. <b>ESKI</b> → <b>YANGI</b>
    text = re.sub(rf"<b>\s*{re.escape(old)}\s*</b>", f"<b>{new}</b>", text, flags=re.I)
    # 2. 🍽️ ESKI → 🍽️ YANGI (boshida)
    text = re.sub(rf"^🍽️\s*{re.escape(old)}", f"🍽️ {new}", text, flags=re.I | re.M)
    return text


@dp.message(EditDeleteRest.action, F.text)
async def save_edit_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    index = data["edit_index"]
    action = data["edit_action"]
    new_value = message.text.strip()

    if action == "name":
        old_name = PLACES[index]["name"]
        new_name = new_value

        # 1) PLACES va SQLite dagi nomni yangilaymiz
        PLACES[index]["name"] = new_name
        await update_place_field_in_db(PLACES[index]["id"], "name", new_name)

        # 2) Matn ichidagi barcha holatlardagi nomni almashtiramiz
        for key in ("text_user", "text_channel"):
            if key in PLACES[index]:
                PLACES[index][key] = replace_name_everywhere(old_name, new_name, PLACES[index][key])
                await update_place_field_in_db(PLACES[index]["id"], key, PLACES[index][key])

        await message.answer(f"✅ Restoran nomi va matn ichidagi nom yangilandi: {new_name}")

        # 3) PLACES massividagi elementni to‘liq yangilab chiqamiz
        await reload_single_place_in_memory(PLACES[index]["id"])

    elif action == "location_name_single" or action == "location_name_multi":
        for key in ('text_user', 'text_channel', 'text'):
            if key not in PLACES[index]:
                continue
            old_text = PLACES[index][key]
            new_text = re.sub(
                r'(📍 <a\s+href\s*=\s*["\'][^"\']*["\']\s*>)[^<]*?(</a>)',
                rf'\g<1>{new_value}\g<2>',
                old_text,
                flags=re.IGNORECASE
            )
            PLACES[index][key] = new_text
        await update_place_field_in_db(PLACES[index]["id"], "text_user", PLACES[index]["text_user"])
        await update_place_field_in_db(PLACES[index]["id"], "text_channel", PLACES[index]["text_channel"])
        await message.answer(f"✅ Joylashuv nomi yangilandi: {new_value}")
        await reload_single_place_in_memory(PLACES[index]["id"])

    elif action == "location_name_one":
        loc_idx = data['loc_idx']
        txt = PLACES[index]["text"]
        lines = txt.splitlines()
        loc_lines = [i for i, ln in enumerate(lines) if ln.strip().startswith("📍")]
        if loc_idx < len(loc_lines):
            old_line = lines[loc_lines[loc_idx]]
            new_line = re.sub(
                r'(📍\s*<a[^>]*>)[^<]*?(</a>)',
                rf'\g<1>{new_value}\g<2>',
                old_line,
                flags=re.I
            )
            lines[loc_lines[loc_idx]] = new_line
            for key in ('text', 'text_user', 'text_channel'):
                if key not in PLACES[index]:
                    continue
                PLACES[index][key] = "\n".join(lines)
        await update_place_field_in_db(PLACES[index]["id"], "text_user", PLACES[index]["text_user"])
        await update_place_field_in_db(PLACES[index]["id"], "text_channel", PLACES[index]["text_channel"])
        await message.answer(f"✅ {loc_idx + 1}-joylashuv nomi yangilandi: {new_value}")
        await reload_single_place_in_memory(PLACES[index]["id"])

    elif action == "details":
        for key in ('text', 'text_user', 'text_channel'):
            if key not in PLACES[index]:
                continue
            PLACES[index][key] = replace_after_location_link(PLACES[index][key], new_value)
        await update_place_field_in_db(PLACES[index]["id"], "text_user", PLACES[index]["text_user"])
        await update_place_field_in_db(PLACES[index]["id"], "text_channel", PLACES[index]["text_channel"])
        await message.answer("✅ Tafsilotlar yangilandi.")
        await reload_single_place_in_memory(PLACES[index]["id"])

    elif action == "phone":
        for key in ('text', 'text_user', 'text_channel'):
            if key not in PLACES[index]:
                continue
            PLACES[index][key] = re.sub(
                r'(📞\s*)[+\d\s()-]+',
                rf'\g<1>{new_value}\n',
                PLACES[index][key],
                flags=re.IGNORECASE
            )
        await update_place_field_in_db(PLACES[index]["id"], "text_user", PLACES[index]["text_user"])
        await update_place_field_in_db(PLACES[index]["id"], "text_channel", PLACES[index]["text_channel"])
        await message.answer(f"✅ Telefon raqami yangilandi: {new_value}")
        await reload_single_place_in_memory(PLACES[index]["id"])

    elif action == "telegram":
        for key in ('text', 'text_user', 'text_channel'):
            if key not in PLACES[index]:
                continue
            PLACES[index][key] = re.sub(
                r'(📱 Telegram:\s*)@[\w\d_]+',
                rf'\g<1>{new_value}',
                PLACES[index][key],
                flags=re.IGNORECASE
            )
        await update_place_field_in_db(PLACES[index]["id"], "text_user", PLACES[index]["text_user"])
        await update_place_field_in_db(PLACES[index]["id"], "text_channel", PLACES[index]["text_channel"])
        await message.answer(f"✅ Telegram username yangilandi: {new_value}")
        await reload_single_place_in_memory(PLACES[index]["id"])

    elif action == "menu_num":
        for key in ('text', 'text_user', 'text_channel'):
            if key not in PLACES[index]:
                continue
            PLACES[index][key] = re.sub(
                r'(<a\s+href\s*=\s*["\']https://t\.me/myhalalmenu/)[^"\']+(["\']\s*>Меню</a>)',
                rf'\g<1>{new_value}\g<2>',
                PLACES[index][key],
                flags=re.IGNORECASE
            )
        await update_place_field_in_db(PLACES[index]["id"], "text_user", PLACES[index]["text_user"])
        await update_place_field_in_db(PLACES[index]["id"], "text_channel", PLACES[index]["text_channel"])
        await message.answer(f"✅ Menyu raqami yangilandi: {new_value}")
        await reload_single_place_in_memory(PLACES[index]["id"])

    elif action == "extra":
        for key in ('text', 'text_user', 'text_channel'):
            if key not in PLACES[index]:
                continue
            if re.search(r'^📝 Q.*?shimcha:', PLACES[index][key], flags=re.M):
                PLACES[index][key] = re.sub(
                    r'^📝 Q.*?shimcha:.*$',
                    f'📝 Qoʻshimcha: {new_value}',
                    PLACES[index][key],
                    flags=re.M
                )
            else:
                PLACES[index][key] += f'\n📝 Qoʻshimcha: {new_value}'
        await update_place_field_in_db(PLACES[index]["id"], "text_user", PLACES[index]["text_user"])
        await update_place_field_in_db(PLACES[index]["id"], "text_channel", PLACES[index]["text_channel"])
        await message.answer("✅ Qoʻshimcha yangilandi.")
        await reload_single_place_in_memory(PLACES[index]["id"])

    else:
        await message.answer(f"✅ {action.capitalize()} yangilandi.")

    await state.clear()




# ---------------- 📍 3 ta joylashuv nomini alohida tahrirlash ----------------
@dp.callback_query(F.data.startswith("edit_loc_name_"))
async def pick_location_name_to_edit(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    loc_idx = int(parts[3]) - 1  # 0-bazada
    rest_idx = int(parts[4])

    await state.update_data(edit_index=rest_idx, loc_idx=loc_idx, edit_action="location_name_one")
    await call.message.answer(f"{loc_idx + 1}-joylashuv uchun yangi nom kiriting:")
    await state.set_state(EditDeleteRest.action)


@dp.callback_query(F.data == "edit_location_names")
async def prompt_edit_location_names(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    index = data["edit_index"]
    place = PLACES[index]

    # 📍 larni ajratamiz
    location_names = []
    for line in place["text"].splitlines():
        if line.strip().startswith("📍"):
            name = line.split("<a href")[0].replace("📍", "").strip()
            location_names.append(name)

    # bir nechta bo‘lsa – tanlash
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, name in enumerate(location_names, 1):
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📍 {i}. {name}",
                callback_data=f"edit_loc_name_{i}_{index}"  # ← alohida handler uchun
            )
        ])
    await call.message.answer("Qaysi joylashuv nomini tahrirlashni xohlaysiz?", reply_markup=kb)

# ---------------- tahrirlash jarayonida havola yuborilsa ----------------
@dp.message(EditDeleteRest.waiting_location_link, F.text.contains("maps.app.goo.gl") | F.text.contains("google.com/maps"))
async def save_edit_location_link(message: types.Message, state: FSMContext):
    new_link = message.text.strip()
    data = await state.get_data()
    idx = data['edit_index']
    loc_idx = data.get('location_idx', 1)

    # yangi havolani matnga joylashtirish
    for key in ('text_user', 'text_channel', 'text'):
        if key not in PLACES[idx]:
            continue
        old_text = PLACES[idx][key]
        new_text = re.sub(
            r'(📍 <a\s+href\s*=\s*["\'])[^"\']*(["\']\s*>[^<]*</a>)',
            rf'\g<1>{new_link}\g<2>',
            old_text,
            flags=re.IGNORECASE
        )
        PLACES[idx][key] = new_text


        await message.answer(f"✅ Joylashuv havolasi yangilandi:\n{new_link}")
        await update_place_field_in_db(PLACES[idx]["id"], "text_user",  PLACES[idx]["text_user"])
        await update_place_field_in_db(PLACES[idx]["id"], "text_channel", PLACES[idx]["text_channel"])
        await reload_single_place_in_memory(PLACES[idx]["id"])   # ← qo‘shing
        await state.clear()



@dp.message(EditDeleteRest.action, F.text)
async def save_edit_location_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    idx = data['edit_index']
    new_name = message.text.strip()

    for key in ('text', 'text_user', 'text_channel'):
        if key not in PLACES[idx]:
            continue

        old_text = PLACES[idx][key]
        # 📍 <a href="...">ESKI_NOM</a> → 📍 <a href="...">YANGI_NOM</a>
        new_text = re.sub(
            r'(📍 <a\s+href\s*=\s*["\'][^"\']*["\']\s*>)[^<]*?(</a>)',
            rf'\g<1>{new_name}\g<2>',
            old_text,
            flags=re.IGNORECASE
        )
        PLACES[idx][key] = new_text


    await message.answer(f"✅ Joylashuv nomi yangilandi: {new_name}")
    await update_place_field_in_db(PLACES[idx]["id"], "text_user",  PLACES[idx]["text_user"])
    await update_place_field_in_db(PLACES[idx]["id"], "text_channel", PLACES[idx]["text_channel"])
    await reload_single_place_in_memory(PLACES[idx]["id"])   # ← qo‘shing
    await state.clear()

def extract_links(text: str) -> list[str]:
    return re.findall(r'<a href="([^"]+)"', text)


# ---------------- location-link ni tahrirlash ----------------
@dp.callback_query(F.data.startswith("edit_location_links_"))
async def prompt_edit_location_links(call: types.CallbackQuery, state: FSMContext):
    _, _, index_str = call.data.rpartition("_")
    edit_index = int(index_str)
    place = PLACES[edit_index]

    txt = place.get("text", "") or place.get("text_user", "") or place.get("text_channel", "")
    links = extract_location_links(txt)

    if not links:
        await call.answer("📍 Joylashuv havolasi topilmadi!", show_alert=True)
        return

    await state.update_data(edit_index=edit_index)

    # havola bittagina bo‘lsa – darhol kiritish
    if len(links) == 1:
        await state.set_state(EditDeleteRest.waiting_location_link)  # ← NEW
        await call.message.answer(
            f"🔗 Hozirgi joylashuv havolasi:\n{links[0]}\n\nYangi havolani yuboring:"
        )
        return

    # bir nechta bo‘lsa – tanlash
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i, link in enumerate(links, 1):
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🔗 {i}. {link[:30]}...",
                callback_data=f"edit_location_link_{i}_{edit_index}"
            )
        ])
    await call.message.answer("Qaysi joylashuv havolasini tahrirlaysiz?", reply_markup=kb)

@dp.callback_query(F.data.startswith("edit_location_link_"))
async def select_location_link_to_edit(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    idx = int(parts[3])          # havola indeksi (1-bazada)
    index = int(parts[4])        # restoran indeksi (0-bazada)

    await state.update_data(edit_index=index, location_idx=idx)
    await state.set_state(EditDeleteRest.waiting_location_link)  # ← NEW
    await call.message.answer("Yangi joylashuv havolasini yuboring:")


# ---------------- yordamchi funksiyalar ----------------
def extract_location_links(text: str) -> list[str]:
    """📍 bilan boshlangan qatordagi barcha <a href="..." / '...'> havolalarini qaytaradi."""
    links = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("📍"):
            links.extend(re.findall(r'<a\s+href\s*=\s*["\'](.*?)["\']', line, flags=re.I))
    return links





@dp.callback_query(F.data == "edit_details")
async def prompt_edit_details(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📋 Yangi tafsilotlarni kiriting:")
    await state.set_state(EditDeleteRest.action)
    await state.update_data(edit_action="details")


@dp.message(EditDeleteRest.action, F.text)
async def save_edit_details(message: types.Message, state: FSMContext):
    idx = (await state.get_data())['edit_index']
    new_details = message.text.strip()

    for key in ('text', 'text_user', 'text_channel'):
        if key not in PLACES[idx]:
            continue
        PLACES[idx][key] = replace_after_location_link(PLACES[idx][key], new_details)
    await message.answer("✅ Tafsilotlar yangilandi.")
    await update_place_field_in_db(PLACES[idx]["id"], "text_user",  PLACES[idx]["text_user"])
    await update_place_field_in_db(PLACES[idx]["id"], "text_channel", PLACES[idx]["text_channel"])
    await reload_single_place_in_memory(PLACES[idx]["id"])   # ← qo‘shing
    await state.clear()

def replace_after_location_link(html: str, new_details: str) -> str:
    """
    📍 ... </a> dan keyingi matnni 📋 (yoki 🌐) gacha bo‘lgan qismni
    to‘liq yangi tafsilotlar bilan almashtiradi.
    """
    # 1-variant: 📋 bilan tugaydi
    if re.search(r'📍.*?</a>\s*\n.*?\n📋', html, flags=re.S):
        return re.sub(
            r'(📍.*?</a>)\s*\n.*?\n(📋)',
            rf'\1\n{new_details}\n\2',
            html,
            flags=re.S
        )
    # 2-variant: 🌐 bilan tugaydi
    if re.search(r'📍.*?</a>\s*\n.*?\n🌐', html, flags=re.S):
        return re.sub(
            r'(📍.*?</a>)\s*\n.*?\n(🌐)',
            rf'\1\n{new_details}\n\2',
            html,
            flags=re.S
        )
    # 3-variant: hech qanday belgi yo‘q – oxiriga qo‘shamiz
    return html




@dp.callback_query(F.data == "edit_menu_num")
async def prompt_edit_menu_num(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📝 Yangi menyu raqamini kiriting (faqat raqam):")
    await state.set_state(EditDeleteRest.action)
    await state.update_data(edit_action="menu_num")



@dp.message(EditDeleteRest.action, F.text.regexp(r'^\d+$'))
async def save_edit_menu_num(message: types.Message, state: FSMContext):
    idx = (await state.get_data())['edit_index']
    new_num = message.text.strip()

    for key in ('text', 'text_user', 'text_channel'):
        if key not in PLACES[idx]:
            continue
        # 🌐 yoki 📋 bilan boshlangan havolani topamiz
        PLACES[idx][key] = re.sub(
            r'(<a\s+href\s*=\s*["\']https://t\.me/myhalalmenu/)[^"\']+(["\']\s*>Меню</a>)',
            rf'\g<1>{new_num}\g<2>',
            PLACES[idx][key],
            flags=re.IGNORECASE
        )


    await message.answer(f"✅ Menyu raqami yangilandi: {new_num}")
    await update_place_field_in_db(PLACES[idx]["id"], "text_user",  PLACES[idx]["text_user"])
    await update_place_field_in_db(PLACES[idx]["id"], "text_channel", PLACES[idx]["text_channel"])
    await reload_single_place_in_memory(PLACES[idx]["id"])   # ← qo‘shing
    await state.clear()


@dp.callback_query(F.data == "edit_phone")
async def prompt_edit_phone(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📞 Yangi telefon raqamini kiriting:")
    await state.set_state(EditDeleteRest.action)
    await state.update_data(edit_action="phone")

@dp.message(EditDeleteRest.action, F.text)
async def save_edit_phone(message: types.Message, state: FSMContext):
    idx = (await state.get_data())['edit_index']
    new_p = message.text.strip()

    for key in ('text', 'text_user', 'text_channel'):
        if key not in PLACES[idx]:
            continue
        # 📞 ...  (ikkitalik raqam ham bo‘lishi mumkin)
        PLACES[idx][key] = re.sub(
            r'📞\s*[+\d\s–()-]+',
            f'📞 {new_p}',
            PLACES[idx][key],
            flags=re.M
        )


    await message.answer(f"✅ Telefon raqami yangilandi: {new_p}")
    await update_place_field_in_db(PLACES[idx]["id"], "text_user",  PLACES[idx]["text_user"])
    await update_place_field_in_db(PLACES[idx]["id"], "text_channel", PLACES[idx]["text_channel"])
    await reload_single_place_in_memory(PLACES[idx]["id"])   # ← qo‘shing
    await state.clear()

@dp.callback_query(F.data == "edit_telegram")
async def prompt_edit_telegram(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📱 Yangi Telegram usernameni kiriting (@sizning_user shaklida):")
    await state.set_state(EditDeleteRest.action)
    await state.update_data(edit_action="telegram")

@dp.message(EditDeleteRest.action, F.text)
async def save_edit_telegram(message: types.Message, state: FSMContext):
    idx = (await state.get_data())['edit_index']
    new_u = message.text.strip()

    # format tekshiruvi
    if not re.match(r'^@\w{3,}$', new_u):
        await message.answer("❌ Iltimos, to‘g‘ri formatda kiriting (@foydalanuvchi):")
        return

    for key in ('text', 'text_user', 'text_channel'):
        if key not in PLACES[idx]:
            continue
        # 📱 Telegram: ... (bir qator)
        PLACES[idx][key] = re.sub(
            r'📱 Telegram:\s*@\w+(?:,\s*@\w+)*',
            f'📱 Telegram: {new_u}',
            PLACES[idx][key],
            flags=re.M | re.I
        )


    await message.answer(f"✅ Telegram username yangilandi: {new_u}")
    await update_place_field_in_db(PLACES[idx]["id"], "text_user",  PLACES[idx]["text_user"])
    await update_place_field_in_db(PLACES[idx]["id"], "text_channel", PLACES[idx]["text_channel"])
    await reload_single_place_in_memory(PLACES[idx]["id"])   # ← qo‘shing
    await state.clear()

# ---------------- 📝 Qo'shimcha tahrirlash ----------------
@dp.callback_query(F.data == "edit_extra")
async def prompt_edit_extra(call: types.CallbackQuery, state: FSMContext):
    await call.answer()  # loading to‘xtatadi
    await call.message.answer("📝 Yangi qoʻshimcha ma’lumotni kiriting:")
    await state.set_state(EditDeleteRest.action)
    await state.update_data(edit_action="extra")

@dp.message(EditDeleteRest.action, F.text)
async def save_edit_extra(message: types.Message, state: FSMContext):
    idx = (await state.get_data())['edit_index']
    new_e = message.text.strip()

    for key in ('text', 'text_user', 'text_channel'):
        if key not in PLACES[idx]:
            continue
        if re.search(r'^📝 Q.*?shimcha:', PLACES[idx][key], flags=re.M):
            PLACES[idx][key] = re.sub(
                r'^📝 Q.*?shimcha:.*$',
                f'📝 Qoʻshimcha: {new_e}',
                PLACES[idx][key],
                flags=re.M
            )
        else:
            PLACES[idx][key] += f'\n📝 Qoʻshimcha: {new_e}'

    # SQLite ga yozamiz
    await update_place_field_in_db(PLACES[idx]["id"], "text_user", PLACES[idx]["text_user"])
    await update_place_field_in_db(PLACES[idx]["id"], "text_channel", PLACES[idx]["text_channel"])

    await message.answer("✅ Qoʻshimcha yangilandi.")
    await reload_single_place_in_memory(PLACES[idx]["id"])   # ← qo‘shing
    await state.clear() 


# ---------------- o'chirish ----------------
@dp.callback_query(F.data.startswith("delete_"))
async def confirm_delete_rest(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    index = int(call.data.split("_")[1])
    if 0 <= index < len(PLACES):
        place = PLACES[index]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"confirm_delete_{index}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_delete")]
        ])
        display_text = get_display_text(place)
        await call.message.answer(f"Quyidagi restoranni o'chirishni xohlaysizmi?\n\n{display_text}", reply_markup=keyboard)
    else:
        await call.message.answer("❌ Noto'g'ri raqam.")

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_rest_final(call: types.CallbackQuery, state: FSMContext):
    index = int(call.data.split("_")[2])
    if 0 <= index < len(PLACES):
        place = PLACES.pop(index)
        # SQLite dan ham o‘chiramiz
        await delete_place_from_db(place["id"])
        await call.message.edit_text(f"✅ {place['name']} o'chirildi.")
    else:
        await call.message.edit_text("❌ Noto‘g‘ri raqam.")
    await state.clear()

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("❌ O'chirish bekor qilindi.")
    await state.clear()

# ---------- yangi yordamchi ----------


def is_ad(text: str) -> bool:
    """True = reklama, hech qandov javob qaytarmaymiz."""
    if not text:
        return False

    t = text.lower()

    # 1) havola / username bo‘lsa → reklama
    if re.search(r'https?://|t\.me/|@', text):
        return True

    # 2) FAQAT biznes emoji-lari bilan yozilgan uzun matn
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines and all(re.match(r'^\s*(🍽|📍|📞|⏰|🚗|📃|📱|✨|•)', ln) for ln in lines):
        return True

    # 3) 300+ belgi va «Kansas City / Tashkent / ...» kabi shahar nomi
    #    ko‘rsatmasi BOR BO‘LSA HAM reklama deb hisoblaymiz
    if len(text) > 300 and re.search(r'\b(kansas city|tashkent|new york|chicago|houston|brooklyn|phoenix|orlando|denver|omaha|cincinnati|nashville|tampa|charlotte|austin|dallas|pittsburgh|akron|toledo|lebanon|dayton|hebron|minneapolis|portland|seattle|tacoma|salt lake city|las vegas|san bernardino|sacramento|san francisco|los angeles|san diego|miami|atlanta|philadelphia|detroit|baltimore|washington|virginia|mississippi|ocean springs|knoxville|memphis|jackson|wichita|oklahoma city|kansas|missouri|colorado|california|florida|texas|ohio|illinois|new jersey|pennsylvania|georgia|north carolina|south carolina|tennessee|utah|nevada|arizona|oregon|washington|virginia|maryland|mississippi|arkansas|alabama|louisiana|indiana|kentucky|west virginia|missouri|iowa|minnesota|wisconsin|michigan|nebraska|kansas|oklahoma|arkansas|louisiana|tennessee|mississippi|alabama|georgia|florida|south carolina|north carolina|virginia|west virginia|kentucky|indiana|illinois|ohio|pennsylvania|new york|new jersey|connecticut|rhode island|massachusetts|vermont|new hampshire|maine|delaware|maryland|district of columbia)\b', t):
        return True

    return False

# ---------------- mijozlar (xavfsiz o'qish) ----------------

def get_display_text(place):
    # Avval "text_user", keyin "text_channel", keyin esa eski "text" kalitini qidiradi
    return place.get("text_user", place.get("text_channel", place.get("text", "")))


def split_text(text: str, limit: int = 4000) -> list[str]:
    """Katta matnni Telegram chegarasiga mos bo‘laklarga bo‘lib beradi."""
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        split_at = text[:limit].rfind('\n\n')   # ikki yangi qator orqali bo‘lamiz
        if split_at == -1:
            split_at = limit
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()
    return parts

async def reply_long_text(message: types.Message, text: str) -> None:
    """Katta matnni 4000 belgi bo‘laklama, reply qilib yuboradi."""
    for part in split_text(text, limit=4000):
        await message.answer(
            part,
            reply_to_message_id=message.message_id,
            disable_web_page_preview=True
        )

@dp.message(F.content_type == "location")
async def location_handler(message: types.Message):
    await by_location(message)


async def by_location(message: types.Message):
    lat, lng = message.location.latitude, message.location.longitude
    near = [p for p in PLACES if haversine(lat, lng, p["lat"], p["lng"]) <= 100]
    if not near:
        await message.answer(
            "📍 100 km radiusda hech qanday muassasa yo'q.\n"
            "📍 There are no establishments within 100 km radius.\n"
            "📍 В радиусе 100 км нет никаких заведений.",
            reply_to_message_id=message.message_id
        )
        return

    out = "\n\n".join(get_display_text(p) for p in near)
    # uzun bo‘lsa bo‘laklama yuboramiz
    for part in split_text(out):
        await message.answer(
            part,
            reply_to_message_id=message.message_id,
            disable_web_page_preview=True
        )
# ---------------- guruhda joylashuvga o‘xshash matnmi? ----------------

# ---------- REKLAMA (is_ad) ----------


# ---------- STATE CODES (2-harfli shtat kodlari) ----------
STATE_CODES = {
    "id": "idaho", "ca": "california", "tx": "texas", "fl": "florida",
    "wa": "washington", "co": "colorado", "tn": "tennessee", "oh": "ohio",
    "pa": "pennsylvania", "il": "illinois", "ny": "new york", "nc": "north carolina",
    "nv": "nevada", "ut": "utah", "az": "arizona", "or": "oregon",
    "mo": "missouri", "mn": "minnesota", "ks": "kansas", "ky": "kentucky",
    "va": "virginia", "md": "maryland", "ms": "mississippi", "al": "alabama",
    "ga": "georgia", "sc": "south carolina", "la": "louisiana", "ar": "arkansas",
    "ok": "oklahoma", "nm": "new mexico", "ne": "nebraska", "ia": "iowa",
    "wi": "wisconsin", "mi": "michigan", "in": "indiana", "wv": "west virginia",
    "nj": "new jersey", "ct": "connecticut", "ri": "rhode island", "ma": "massachusetts",
    "vt": "vermont", "nh": "new hampshire", "me": "maine", "de": "delaware",
    "dc": "district of columbia", "ak": "alaska", "hi": "hawaii", "mt": "montana",
    "nd": "north dakota", "sd": "south dakota", "wy": "wyoming"
}

def normalize_text(text: str) -> str:
    """2-harfli shtat kodlarini to‘liq nomga almashtiradi va 2 harfdan kam so‘zlarni o‘chiradi."""
    words = re.findall(r'\b\w+\b', text.lower())
    out = []
    for w in words:
        if len(w) == 2 and w in STATE_CODES:
            out.append(STATE_CODES[w])
        elif len(w) <= 2:          # 2 harfdan kam boʻlsa tashlab yuboramiz
            continue
        else:
            out.append(w)
    return " ".join(out)


# ---------- MIJOZ SO‘ROVI (by_text) ----------
# ---------- MIJOZ SO‘ROVI (by_text) ----------
@dp.message(F.text)
async def by_text(message: types.Message):
    raw_text = message.text.strip()
    if not raw_text:
        await message.answer("❌ Matn kiriting.")
        return

    # REKLAMA FILTRI
    if is_ad(raw_text):
        return

    # 1) 2-harfli shtat kodlarini to‘liq nomga aylantiramiz
    raw_text = normalize_text(raw_text)
    text = raw_text.lower()

    # 2) Koordinata orqali qidirish (shahar nomi → lat,lng)
    lat, lng = await coords_from_any(text)
    if lat is not None:
        near = [p for p in PLACES if haversine(lat, lng, p["lat"], p["lng"]) <= 100]   # 100 km
        if near:
            out = "\n\n".join(get_display_text(p) for p in near)
            for part in split_text(out):
                await message.answer(part,
                                     reply_to_message_id=message.message_id,
                                     disable_web_page_preview=True)
            return

    # 3) SO‘Z BO‘YICHA QIDIRUV – faqat SHAHAR nomi orqali
    words = re.findall(r'\b\w{3,}\b', text)
    found, seen = [], set()

    for w in words:
        # shahar nomi (📍 ... <a>...</a>) bo‘yicha
        for p in PLACES:
            pid = id(p)
            if pid in seen:
                continue
            txt = p.get("text", "") + p.get("text_user", "") + p.get("text_channel", "")
            cities = re.findall(r'📍.*?<a[^>]*>([^<]+)</a>', txt, re.I)
            for c in cities:
                if w in c.lower():
                    seen.add(pid)
                    found.append(p)
                    break

    # 100 km radius (shahar koordinatasi bilan)
    for w in words:
        lat, lng = await coords_from_any(w)
        if lat is not None:
            for p in PLACES:
                pid = id(p)
                if pid in seen:
                    continue
                if haversine(lat, lng, p["lat"], p["lng"]) <= 100:
                    seen.add(pid)
                    found.append(p)

    if found:
        out = "\n\n".join(get_display_text(p) for p in found)
        await reply_long_text(message, f"🔍 Found:\n\n{out}")
        return

    # Topilmadi – javob yo‘q
    return




# ---------------- run ----------------
async def main():
    global PLACES
    
    await init_db()
    PLACES = await load_places_from_db()
    
    if not PLACES:
        for p in initial_places:
            await add_place_to_db(
                p["name"], p["lat"], p["lng"],
                p["text"], p["text"]
            )
        PLACES = await load_places_from_db()
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
