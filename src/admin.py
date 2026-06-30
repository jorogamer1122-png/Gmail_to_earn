"""
admin.py
Admin command handlers: task creation, submission review, analytics, payouts.
Restricted to IDs listed in config/admins.json.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database import DB
from utils import is_admin, new_id, format_balance

TITLE, DESCRIPTION, REWARD = range(3)


async def admin_only_guard(update: Update) -> bool:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admins only.")
        return False
    return True


async def new_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return ConversationHandler.END
    await update.message.reply_text("Enter the task title:")
    return TITLE


async def new_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_task_title"] = update.message.text
    await update.message.reply_text("Enter the task description:")
    return DESCRIPTION


async def new_task_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_task_description"] = update.message.text
    await update.message.reply_text("Enter the reward amount (number):")
    return REWARD


async def new_task_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reward = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Please send a valid number for the reward.")
        return REWARD

    task_id = new_id("task_")
    task = DB.create_task(
        task_id=task_id,
        title=context.user_data.pop("new_task_title"),
        description=context.user_data.pop("new_task_description"),
        reward=reward,
        created_by=update.effective_user.id,
    )
    await update.message.reply_text(
        f"✅ Task created!\nID: {task['id']}\nTitle: {task['title']}\nReward: {task['reward']}"
    )
    return ConversationHandler.END


async def cancel_new_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Task creation cancelled.")
    return ConversationHandler.END


async def queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    pending = DB.list_pending_submissions()
    if not pending:
        await update.message.reply_text("✅ No pending submissions.")
        return
    for sub in pending[:20]:  # avoid flooding chat
        task = DB.get_task(sub["task_id"]) or {}
        text = (
            f"🆔 {sub['id']}\n"
            f"Task: {task.get('title', 'Unknown')}\n"
            f"User: {sub['user_id']}\n"
            f"Proof: {sub['proof_text'] or '(file attached)'}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"review:approve:{sub['id']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"review:reject:{sub['id']}"),
        ]])
        if sub.get("proof_file_id"):
            await update.message.reply_photo(sub["proof_file_id"], caption=text, reply_markup=keyboard)
        else:
            await update.message.reply_text(text, reply_markup=keyboard)


async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.message.reply_text("⛔ Admins only.")
        return

    _, action, submission_id = query.data.split(":", 2)
    sub = DB.get_submission(submission_id)
    if not sub or sub["status"] != "pending":
        await query.message.reply_text("Already reviewed or not found.")
        return

    approve = action == "approve"
    DB.review_submission(submission_id, approve, query.from_user.id)

    if approve:
        task = DB.get_task(sub["task_id"])
        reward = task["reward"] if task else 0
        DB.adjust_balance(sub["user_id"], reward)
        DB.increment_task_completion(sub["task_id"])
        DB.log_reward(sub["user_id"], sub["task_id"], reward)
        user_record = DB.get_user(sub["user_id"])
        completed = user_record.get("completed_tasks", [])
        completed.append(sub["task_id"])
        DB.upsert_user(sub["user_id"], completed_tasks=completed)

        await context.bot.send_message(
            sub["user_id"],
            f"🎉 Your submission was approved! +{reward} points credited."
        )
    else:
        await context.bot.send_message(
            sub["user_id"],
            "❌ Your submission was rejected. Try again or contact an admin."
        )

    await query.message.edit_text(query.message.text + f"\n\n— {'APPROVED ✅' if approve else 'REJECTED ❌'}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    users = DB.all_users()
    pending = DB.list_pending_submissions()
    tasks = DB.list_active_tasks()
    total_balance = sum(u.get("balance", 0) for u in users.values())

    await update.message.reply_text(
        "📊 *Analytics Dashboard*\n\n"
        f"👥 Total users: {len(users)}\n"
        f"📋 Active tasks: {len(tasks)}\n"
        f"⏳ Pending submissions: {len(pending)}\n"
        f"💰 Total points distributed (current balances): {format_balance(total_balance)}",
        parse_mode="Markdown"
    )


async def list_my_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    tasks = DB.list_active_tasks()
    if not tasks:
        await update.message.reply_text("No active tasks.")
        return
    lines = [f"{t['id']} — {t['title']} ({t['reward']} pts, {t['completions']} completions)" for t in tasks]
    await update.message.reply_text("📋 Active tasks:\n" + "\n".join(lines))


async def deactivate_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /deactivate <task_id>")
        return
    task_id = context.args[0]
    ok = DB.set_task_active(task_id, False)
    await update.message.reply_text("✅ Deactivated." if ok else "Task not found.")
