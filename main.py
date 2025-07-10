import asyncio, os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, LabeledPrice
)

API_TOKEN      = os.getenv("BOT_TOKEN")
ADMIN_ID       = int(os.getenv("ADMIN_ID"))
CHECK_INTERVAL = 5          
PRICE          = 500        
PROVIDER_STAR  = "STARS"
BOT_USER       = os.getenv("BOT_USER")

bot = Bot(API_TOKEN)
dp  = Dispatcher()

# ────────────────── единая «шапка» меню ──────────────────
def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Подарок за 15 ⭐", callback_data="buy15")],
        [InlineKeyboardButton(text=f"💸 Донат {PRICE} ⭐", callback_data="donate")],
        [InlineKeyboardButton(text="🔄 Перезапуск",       url=f"https://t.me/{BOT_USER}?start=go")]
    ])

# ────────── /start и /menu (для кнопки-меню Telegram) ──────────
@dp.message(Command("start", "menu"))
async def cmd_menu(m: Message):
    await m.answer("Выберите действие:", reply_markup=main_keyboard())

# ────────── подарок за 15 ⭐ ──────────
@dp.callback_query(F.data == "buy15")
async def buy15(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("Только владелец бота.", show_alert=True); return

    gifts = await bot.get_available_gifts()
    gift15 = next((g for g in gifts.gifts if g.star_count == 15), None)
    if not gift15:
        await c.message.answer("😢 Подарка за 15 ⭐ нет."); await c.answer(); return

    try:
        await bot.send_gift(user_id=ADMIN_ID, gift_id=gift15.id)
        await c.message.answer("🎉 Подарок отправлен!")
    except Exception as e:
        await c.message.answer(f"❌ Ошибка: {e}")
    await c.answer()

# ────────── донат (PRICE ⭐) ──────────
@dp.callback_query(F.data == "donate")
async def donate(c: CallbackQuery):
    prices = [LabeledPrice(label=f"Донат {PRICE} ⭐", amount=PRICE)]
    await bot.send_invoice(
        chat_id=c.from_user.id,
        title=f"Донат {PRICE} звёзд",
        description="Поддержка автоскупки подарков.",
        payload="donate",
        provider_token=PROVIDER_STAR,
        currency="XTR",
        prices=prices)
    await c.answer()

@dp.pre_checkout_query()
async def pre_checkout(q):  await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def thanks(m: Message):
    await m.answer(f"✅ Спасибо за донат {m.successful_payment.total_amount} XTR!")

# ────────── баланс ──────────
@dp.callback_query(F.data == "bal")
async def bal(c: CallbackQuery):
    bal = await bot.get_my_star_balance()
    await c.message.answer(f"💫 Баланс бота: {bal.amount} XTR"); await c.answer()

# ────────── авто-выкуп редких ──────────
async def monitor_gifts():
    depleted: set[str] = set()
    while True:
        try:
            gifts  = await bot.get_available_gifts()
            money  = (await bot.get_my_star_balance()).amount
            rare   = [g for g in gifts.gifts if g.total_count and g.remaining_count and g.id not in depleted]
            rare.sort(key=lambda g: g.star_count, reverse=True)

            for g in rare:
                price = g.star_count
                if money < price: continue
                while money >= price:
                    fresh = await bot.get_available_gifts()
                    fresh_g = next((x for x in fresh.gifts if x.id == g.id), None)
                    if not fresh_g or fresh_g.remaining_count == 0:
                        depleted.add(g.id); break
                    try:
                        await bot.send_gift(user_id=ADMIN_ID, gift_id=g.id)
                        money -= price
                        await asyncio.sleep(1)
                    except Exception: break
        except Exception as e:
            print("monitor error:", e)
        await asyncio.sleep(CHECK_INTERVAL)

# ────────── старт ──────────
async def main():
    asyncio.create_task(monitor_gifts())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
