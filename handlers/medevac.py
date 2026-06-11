from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from services.groq_service import generate_medevac_sentence

# States
(
    MEV_NATURE, MEV_NAME, MEV_CONTACT, MEV_UNIT,
    MEV_LOC_TYPE, MEV_LOC_DETAIL, MEV_CAS, MEV_AVPU,
    MEV_POC_NAME, MEV_POC_CONTACT,
) = range(10)


def avpu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Alert", callback_data="avpu_Alert"),
            InlineKeyboardButton("🗣️ Voice", callback_data="avpu_Voice"),
        ],
        [
            InlineKeyboardButton("😣 Pain", callback_data="avpu_Pain"),
            InlineKeyboardButton("😴 Unresponsive", callback_data="avpu_Unresponsive"),
        ],
    ])


def loc_type_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏕️ In Camp", callback_data="loc_camp"),
            InlineKeyboardButton("🌲 Training Area", callback_data="loc_trg"),
        ]
    ])


async def medevac_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🚑 *1733 MEDEVAC GUIDE*\n\n"
        "I'll generate your voice procedure script.\n\n"
        "What is the *nature of the incident*?\n"
        "e.g. `Heat injury during VOC Test`",
        parse_mode="Markdown",
    )
    return MEV_NATURE


async def mev_nature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mev_nature"] = update.message.text.strip()
    await update.message.reply_text("Your *Rank & Full Name*?", parse_mode="Markdown")
    return MEV_NAME


async def mev_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mev_name"] = update.message.text.strip().upper()
    await update.message.reply_text("Your *contact number*?", parse_mode="Markdown")
    return MEV_CONTACT


async def mev_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mev_contact"] = update.message.text.strip()
    await update.message.reply_text(
        "*Battalion & Coy/Branch?*\ne.g. `10 C4I BN, S3 Branch`",
        parse_mode="Markdown",
    )
    return MEV_UNIT


async def mev_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mev_unit"] = update.message.text.strip().upper()
    await update.message.reply_text(
        "Where is the incident?",
        reply_markup=loc_type_keyboard(),
    )
    return MEV_LOC_TYPE


async def mev_loc_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["mev_loc_type"] = query.data

    if query.data == "loc_camp":
        await query.edit_message_text("*Camp name?*\ne.g. `Stagmont Camp`", parse_mode="Markdown")
    else:
        await query.edit_message_text(
            "*CCP Code and Training Area?*\ne.g. `A3, Mandai Training Area`",
            parse_mode="Markdown",
        )
    return MEV_LOC_DETAIL


async def mev_loc_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    loc_type = context.user_data["mev_loc_type"]

    if loc_type == "loc_camp":
        context.user_data["mev_linkup"] = f"{text} Guardroom"
    else:
        parts = text.split(",", 1)
        ccp = parts[0].strip()
        area = parts[1].strip() if len(parts) > 1 else text
        context.user_data["mev_linkup"] = f"CCP {ccp}, {area}"

    await update.message.reply_text(
        "*Number of casualties?*\ne.g. `1`",
        parse_mode="Markdown",
    )
    return MEV_CAS


async def mev_casualties(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mev_cas"] = update.message.text.strip()
    await update.message.reply_text(
        "*AVPU Status of casualty?*",
        reply_markup=avpu_keyboard(),
    )
    return MEV_AVPU


async def mev_avpu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["mev_avpu"] = query.data.replace("avpu_", "")
    await query.edit_message_text(
        f"✅ AVPU: *{context.user_data['mev_avpu']}*\n\n*POC Rank & Full Name?*",
        parse_mode="Markdown",
    )
    return MEV_POC_NAME


async def mev_poc_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mev_poc_name"] = update.message.text.strip().upper()
    await update.message.reply_text("*POC contact number?*", parse_mode="Markdown")
    return MEV_POC_CONTACT


async def mev_poc_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mev_poc_contact"] = update.message.text.strip()

    await update.message.reply_text("⚡ *Generating script...*", parse_mode="Markdown")

    d = context.user_data
    try:
        sentence = generate_medevac_sentence(d["mev_nature"], d["mev_avpu"])
    except Exception:
        sentence = f"a serviceman who has suffered {d['mev_nature'].lower()}"

    unit_parts = d["mev_unit"].split(",", 1)
    bn = unit_parts[0].strip()
    coy = unit_parts[1].strip() if len(unit_parts) > 1 else ""
    cas = d["mev_cas"]
    cas_word = "casualty" if cas == "1" else "casualties"
    requires = "requires" if cas == "1" else "require"

    script = (
        f'"Hello GSOC, I am {d["mev_name"]} from {bn}'
        f'{", " + coy if coy else ""} speaking.\n\n'
        f"I would like to report a medical incident.\n\n"
        f"I have {cas} {cas_word} that {requires} immediate assistance. {sentence}\n\n"
        f"Casualty is {d['mev_avpu']}.\n\n"
        f"Link up at {d['mev_linkup']}.\n\n"
        f"My contact number is {d['mev_contact']}.\n\n"
        f'POC details are {d["mev_poc_name"]}, contact number {d["mev_poc_contact"]}."'
    )

    ref = (
        f"*Quick Reference*\n"
        f"`Incident   ` {d['mev_nature']}\n"
        f"`Casualties ` {cas}\n"
        f"`AVPU       ` {d['mev_avpu']}\n"
        f"`Link Up    ` {d['mev_linkup']}\n"
        f"`Your No.   ` {d['mev_contact']}\n"
        f"`POC        ` {d['mev_poc_name']} — {d['mev_poc_contact']}"
    )

    await update.message.reply_text(
        "🚨 *CALL 1733 — READ THIS ALOUD*\n\n"
        f"```\n{script}\n```\n\n"
        f"{ref}",
        parse_mode="Markdown",
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_medevac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


def medevac_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("medevac", medevac_start)],
        states={
            MEV_NATURE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mev_nature)],
            MEV_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, mev_name)],
            MEV_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mev_contact)],
            MEV_UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mev_unit)],
            MEV_LOC_TYPE: [CallbackQueryHandler(mev_loc_type, pattern="^loc_")],
            MEV_LOC_DETAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, mev_loc_detail)],
            MEV_CAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, mev_casualties)],
            MEV_AVPU: [CallbackQueryHandler(mev_avpu, pattern="^avpu_")],
            MEV_POC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, mev_poc_name)],
            MEV_POC_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mev_poc_contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel_medevac)],
        name="medevac",
        persistent=False,
    )
