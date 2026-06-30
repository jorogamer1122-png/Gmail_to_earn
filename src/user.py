"""
user.py
User-facing command and callback handlers: /start, /balance, /tasks, /history,
task submission flow.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database import DB
from utils import new_id, format_balance

AWAITING_PROOF = 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referred_by = None
    if args and args[0].isdigit():
        ref_id = int(args[0])
        if ref_id != user.id and DB.get_user(ref_id):
            referred_by = ref_id

    existing = DB.get_user(user.id)
    if not existing:
        DB.upsert_user(user.id, username=user.username or "", referred_by=referred_by)
        if referred_by:
            ref_user = DB.get_user(referred_by)
            referrals = ref_user.get("referrals", [])
            referrals.append(user.id)
            DB.upsert_user(referred_by, referrals=referrals)

    await update.message.reply_text(
        f"Welcome, {user.first_name}! 👋\n\n"
        "This bot lets you complete tasks and earn rewards.\n\n"
        "Commands:\n"
        "/tasks – view available tasks\n"
        "/balance – check your reward balance\n"
        "/history – view your completed tasks\n"
        "/referral – get your referral link"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record = DB.get_user(user_id) or DB.upsert_user(user_id, username=update.effective_user.username or "")
    await update.message.reply_text(f"💰 Your balance: {format_balance(record['balance'])} points")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = DB.list_active_tasks()
    if not tasks:
        await update.message.reply_text("No active tasks right now. Check back later!")
        return
    for task in tasks:
        text = f"📋 *{task['title']}*\n{task['description']}\n💰 Reward: {task['reward']} points"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Complete this task", callback_data=f"do_task:{task['id']}")
        ]])
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = query.data.split(":", 1)[1]
    task = DB.get_task(task_id)
    if not task or not task.get("active"):
        await query.message.reply_text("This task is no longer available.")
        return ConversationHandler.END

    context.user_data["pending_task_id"] = task_id
    await query.message.reply_text(
        "Please send proof of completion (text, screenshot, or link)."
    )
    return AWAITING_PROOF


async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_id = context.user_data.get("pending_task_id")
    if not task_id:
        await update.message.reply_text("No task in progress. Use /tasks to start one.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    proof_text = update.message.text or update.message.caption or ""
    proof_file_id = ""
    if update.message.photo:
        proof_file_id = update.message.photo[-1].file_id
    elif update.message.document:
        proof_file_id = update.message.document.file_id

    submission_id = new_id("sub_")
    DB.create_submission(submission_id, task_id, user_id, proof_text, proof_file_id)

    await update.message.reply_text(
        "✅ Submission received! An admin will review it shortly. "
        "You'll be notified once it's approved or rejected."
    )
    context.user_data.pop("pending_task_id", None)
    return ConversationHandler.END


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record = DB.get_user(user_id)
    if not record or not record.get("completed_tasks"):
        await update.message.reply_text("You haven't completed any tasks yet.")
        return
    lines = [f"• {t}" for t in record["completed_tasks"]]
    await update.message.reply_text("📜 Completed tasks:\n" + "\n".join(lines))


async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"
    record = DB.get_user(user_id) or {}
    count = len(record.get("referrals", []))
    await update.message.reply_text(
        f"🔗 Your referral link:\n{link}\n\n👥 Referrals so far: {count}"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_task_id", None)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END
