from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from services.db import get_user, save_user, update_user_profile

# Conversation states
SETUP_BATTALION, SETUP_COY, SETUP_OFFICER = range(3)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    name = update.effective_user.first_name

    if user:
        await update.message.reply_text(
            f"👋 Welcome back, {name}.\n\n"
            f"*Unit:* {user['battalion']} · {user['coy']}\n\n"
            "What would you like to do?\n\n"
            "/newir — File a new incident report\n"
            "/update — Update an existing report\n"
            "/dashboard — View all reports\n"
            "/medevac — 1733 MEDEVAC guide\n"
            "/profile — Update your unit profile",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"👋 Welcome to *SITREP*, {name}.\n\n"
        "AI-powered incident reporting for the SAF.\n\n"
        "Let's set up your unit profile first — this is a one-time setup.\n\n"
        "What is your *Battalion*?",
        parse_mode="Markdown",
    )
    return SETUP_BATTALION


async def setup_battalion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup_battalion"] = update.message.text.strip().upper()
    await update.message.reply_text(
        f"✅ Battalion: *{context.user_data['setup_battalion']}*\n\n"
        "What is your *Coy / Branch*?",
        parse_mode="Markdown",
    )
    return SETUP_COY


async def setup_coy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup_coy"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Coy/Branch: *{context.user_data['setup_coy']}*\n\n"
        "What is your *default Reporting Officer*?\n"
        "_(Rank, Name, Appointment)_\n\n"
        "e.g. `2LT TAN WEI, TCO, S3 BRANCH`",
        parse_mode="Markdown",
    )
    return SETUP_OFFICER


async def setup_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    officer = update.message.text.strip()
    user = update.effective_user

    save_user(
        telegram_id=user.id,
        name=user.first_name,
        rank="",
        battalion=context.user_data["setup_battalion"],
        coy=context.user_data["setup_coy"],
        default_officer=officer,
    )

    await update.message.reply_text(
        "✅ *Profile saved.*\n\n"
        f"*Battalion:* {context.user_data['setup_battalion']}\n"
        f"*Coy/Branch:* {context.user_data['setup_coy']}\n"
        f"*Reporting Officer:* {officer}\n\n"
        "You're all set. Here's what you can do:\n\n"
        "/newir — File a new incident report\n"
        "/dashboard — View all reports\n"
        "/medevac — 1733 MEDEVAC guide\n"
        "/profile — Update your profile",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let user update their profile."""
    await update.message.reply_text(
        "Updating your unit profile.\n\nWhat is your *Battalion*?",
        parse_mode="Markdown",
    )
    return SETUP_BATTALION


async def profile_battalion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup_battalion"] = update.message.text.strip().upper()
    await update.message.reply_text(
        f"✅ Battalion: *{context.user_data['setup_battalion']}*\n\nWhat is your *Coy / Branch*?",
        parse_mode="Markdown",
    )
    return SETUP_COY


async def profile_coy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup_coy"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Coy/Branch: *{context.user_data['setup_coy']}*\n\nDefault *Reporting Officer*? (Rank, Name, Appointment)",
        parse_mode="Markdown",
    )
    return SETUP_OFFICER


async def profile_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    officer = update.message.text.strip()
    update_user_profile(
        telegram_id=update.effective_user.id,
        battalion=context.user_data["setup_battalion"],
        coy=context.user_data["setup_coy"],
        default_officer=officer,
    )
    await update.message.reply_text(
        "✅ *Profile updated.*\n\n"
        f"*Battalion:* {context.user_data['setup_battalion']}\n"
        f"*Coy/Branch:* {context.user_data['setup_coy']}\n"
        f"*Reporting Officer:* {officer}",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


def setup_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SETUP_BATTALION: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_battalion)],
            SETUP_COY: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_coy)],
            SETUP_OFFICER: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_officer)],
        },
        fallbacks=[CommandHandler("start", start)],
        name="setup",
        persistent=False,
    )


def profile_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("profile", profile_command)],
        states={
            SETUP_BATTALION: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_battalion)],
            SETUP_COY: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_coy)],
            SETUP_OFFICER: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_officer)],
        },
        fallbacks=[CommandHandler("start", start)],
        name="profile",
        persistent=False,
    )
