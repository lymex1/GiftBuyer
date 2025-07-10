import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, LabeledPrice
)

API_TOKEN      = os.getenv("BOT_TOKEN")
ADMIN_ID       = int(os.getenv("ADMIN_ID"))
CHECK_INTERVAL = 5        
PRICE      = 500    
PROVIDER_STAR  = "STARS"  

bot = Bot(API_TOKEN)
dp  = Dispatcher()

# ────────── /start ──────────
@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить подарок за 15 ⭐", callback_data="buy15")],
        [InlineKeyboardButton(text=f"💸 Донат {PRICE} ⭐",               callback_data="donate15")],
        [InlineKeyboardButton(text="💰 Баланс бота",              callback_data="bal")]
    ])
    await m.answer("Выберите действие:", reply_markup=kb)

# ────────── подарок за 15 ⭐ ──────────
@dp.callback_query(F.data == "buy15")
async def buy15(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("Доступно только владельцу бота.", show_alert=True)
        return

    gifts = await bot.get_available_gifts()
    gift15 = next((g for g in gifts.gifts if g.star_count == 15), None)

    if not gift15:
        await c.message.answer("😢 Сейчас нет подарка за 15 звёзд.")
        print("INFO  |  Нет подарка за 15 XTR")
    else:
        try:
            await bot.send_gift(user_id=ADMIN_ID, gift_id=gift15.id)
            await c.message.answer("🎉 Подарок отправлен!")
            print("OK    |  15-звёздочный подарок отправлен админу")
        except Exception as e:
            await c.message.answer(f"❌ Не удалось подарить: {e}")
            print(f"ERR   |  Не удалось подарить 15 ⭐: {e}")
    await c.answer()

# ────────── донат 15 ⭐ ──────────
@dp.callback_query(F.data == "donate15")
async def donate15(c: CallbackQuery):
    prices = [LabeledPrice(label="Пополнить бота на 15 ⭐", amount=PRICE)]
    await bot.send_invoice(
        chat_id=c.from_user.id,
        title="Донат 15 звёзд",
        description="Эти звёзды помогут боту выкупать редкие подарки.",
        payload="donate15",
        provider_token=PROVIDER_STAR,
        currency="XTR",
        prices=prices
    )
    print(f"INFO  |  Invoice 15 ⭐ → user {c.from_user.id}")
    await c.answer()

@dp.pre_checkout_query()
async def pre_checkout(q):           # подтверждаем любую оплату
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def thanks(m: Message):
    amount = m.successful_payment.total_amount  # уже 15, без /100
    await m.answer(f"✅ Спасибо за донат в {amount} XTR!")
    print(f"OK    |  Получен донат {amount} XTR от {m.from_user.id}")

# ────────── баланс ──────────
@dp.callback_query(F.data == "bal")
async def bal(c: CallbackQuery):
    bal = await bot.get_my_star_balance()
    await c.message.answer(f"💫 Баланс бота: {bal.amount} XTR")
    await c.answer()
    print(f"INFO  |  Баланс запрошен: {bal.amount} XTR")

# ────────── авто-монитор редких подарков ──────────
async def monitor_gifts():
    depleted: set[str] = set()                 # уже выкупленные «в ноль»

    while True:
        try:
            # ─ 1. свежие данные ─
            gifts_resp = await bot.get_available_gifts()
            balance    = (await bot.get_my_star_balance()).amount  # целые XTR

            rare = [
                g for g in gifts_resp.gifts
                if g.total_count is not None
                   and g.remaining_count > 0
                   and g.id not in depleted
            ]
            if not rare:
                print("INFO | редких подарков нет – жду…")
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            rare.sort(key=lambda g: g.star_count, reverse=True)
            print(f"INFO | редкие {[g.star_count for g in rare]}, баланс {balance}")

            # ─ 2. идём по подаркам от дорогих к дешёвым ─
            for gift in rare:
                price = gift.star_count
                if balance < price:
                    print(f"SKIP | {gift.id}: цена {price} ⭐, баланс {balance}")
                    continue    # возможно, хватит на более дешёвый

                while balance >= price:
                    # 2а. уточняем актуальный остаток
                    fresh = await bot.get_available_gifts()
                    fresh_gift = next((g for g in fresh.gifts if g.id == gift.id), None)
                    if not fresh_gift or fresh_gift.remaining_count == 0:
                        print(f"DONE | {gift.id} закончился (кто-то выкупил)")
                        depleted.add(gift.id)
                        break

                    try:
                        await bot.send_gift(user_id=ADMIN_ID, gift_id=gift.id)
                        balance -= price
                        print(f"OK   | {gift.id} −{price} ⭐, баланс {balance}")
                        await asyncio.sleep(1)      # anti-flood
                    except Exception as e:
                        # если подарок внезапно кончился — отметим и выйдем
                        if "GIFT" in str(e).upper():
                            print(f"GONE | {gift.id} недоступен: {e}")
                            depleted.add(gift.id)
                        else:
                            print(f"ERR  | {gift.id}: {e}")
                        break

        except Exception as e:
            print(f"ERR  | monitor_gifts: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# ────────── запуск ──────────
async def main():
    asyncio.create_task(monitor_gifts())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
   
