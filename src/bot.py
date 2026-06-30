"""
bot.py
Entry point — wires up handlers and starts polling.
Run with: python src/bot.py
"""
import logging
import os

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import user
import admin

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")


def build_app() -> Application:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN not set. Add it to your .env file.")

    app = Application.builder().token(TOKEN).build()

    # --- User commands ---
    app.add_handler(CommandHandler("start", user.start))
    app.add_handler(CommandHandler("balance", user.balance))
    app.add_handler(CommandHandler("tasks", user.list_tasks))
    app.add_handler(CommandHandler("history", user.history))
    app.add_handler(CommandHandler("referral", user.referral))

    # --- Task submission conversation ---
    submission_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(user.task_callback, pattern=r"^do_task:")],
        states={
            user.AWAITING_PROOF: [
                MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, user.receive_proof)
            ],
        },
        fallbacks=[CommandHandler("cancel", user.cancel)],
    )
    app.add_handler(submission_conv)

    # --- Admin: new task conversation ---
    new_task_conv = ConversationHandler(
        entry_points=[CommandHandler("newtask", admin.new_task_start)],
        states={
            admin.TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.new_task_title)],
            admin.DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.new_task_description)],
            admin.REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.new_task_reward)],
        },
        fallbacks=[CommandHandler("cancel", admin.cancel_new_task)],
    )
    app.add_handler(new_task_conv)

    # --- Admin commands ---
    app.add_handler(CommandHandler("queue", admin.queue))
    app.add_handler(CommandHandler("stats", admin.stats))
    app.add_handler(CommandHandler("mytasks", admin.list_my_tasks))
    app.add_handler(CommandHandler("deactivate", admin.deactivate_task))
    app.add_handler(CallbackQueryHandler(admin.review_callback, pattern=r"^review:"))

    return app


def main():
    app = build_app()
    logger.info("Bot starting (polling)...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
