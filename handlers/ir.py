import os
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from services.db import get_user, save_report
from services.groq_service import generate_brief, transcribe_voice
from utils import format_report_preview, format_full_report

# States
(
    SELECTING_TYPE,
    ENTERING_NAME,
    ENTERING_DATETIME,
    ENTERING_LOCATION,
    ENTERING_DESCRIPTION,
    ENTERING_ADDITIONAL,
    CONFIRMING_REPORT,
) = range(7)

INCIDENT_TYPES = [
    ("🧠 IMH Incident", "IMH Incident"),
    ("🌡️ Heat Injury", "Suspected Heat Related Injury"),
    ("⚖️ Civil Offence", "Civil Offence"),
    ("🚗 Road Traffic Accident", "Road Traffic Accident"),
    ("📦 Loss of Equipment", "Loss of Equipment"),
    ("📋 Other", "Other"),
]


def type_keyboard():
    buttons = []
    for i in range(0, len(INCIDENT_TYPES), 2):
        row = []
        for label, data in INCIDENT_TYPES[i:i+2]:
            row.append(InlineKeyboardButton(label, callback_data=f"irtype_{data}"))
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm & File", callback_data="ir_confirm"),
            InlineKeyboardButton("✏️ Edit Dump", callback_data="ir_edit"),
        ],
        [InlineKeyboardButton("🔄 Regenerate", callback_data="ir_regen")],
    ])


async def require_profile(update: Update) -> dict | None:
    """Check user has a profile. Returns user dict or None."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text(
            "You haven't set up your profile yet.\n\nRun /start to get started."
        )
        return None
    return user


async def new_ir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await require_profile(update)
    if not user:
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["profile"] = user

    await update.message.reply_text(
        "📋 *NEW INCIDENT REPORT*\n\nSelect the type of incident:",
        reply_markup=type_keyboard(),
        parse_mode="Markdown",
    )
    return SELECTING_TYPE


async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    incident_type = query.data.replace("irtype_", "")
    context.user_data["type"] = incident_type

    await query.edit_message_text(
        f"✅ *{incident_type}*\n\n"
        "Who is the affected serviceman?\n"
        "_Rank + Full Name_\n\n"
        "e.g. `3SG SEAN TAN WEI LIANG`",
        parse_mode="Markdown",
    )
    return ENTERING_NAME


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip().upper()

    await update.message.reply_text(
        f"✅ *{context.user_data['name']}*\n\n"
        "Date and time of incident?\n"
        "_Format: DDMMYY HHMM_\n\n"
        "e.g. `010626 1816`",
        parse_mode="Markdown",
    )
    return ENTERING_DATETIME


async def enter_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip().replace("/", "").replace("-", "")
    parts = raw.split()

    if len(parts) != 2:
        await update.message.reply_text(
            "⚠️ Please use the format: `DDMMYY HHMM`\ne.g. `010626 1816`",
            parse_mode="Markdown",
        )
        return ENTERING_DATETIME

    context.user_data["date"] = parts[0]
    context.user_data["time"] = parts[1]

    await update.message.reply_text(
        f"✅ *{parts[0]}, {parts[1]}H*\n\n"
        "Location of incident?",
        parse_mode="Markdown",
    )
    return ENTERING_LOCATION


async def enter_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["location"] = update.message.text.strip()
    profile = context.user_data["profile"]

    await update.message.reply_text(
        f"✅ *{context.user_data['location']}*\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "💡 *Describe what happened*\n\n"
        "Type in shorthand, point form, or broken English — anything goes.\n"
        "Include: what happened, times, who was involved, where they went, outcome, MC dates.\n\n"
        "🎙️ *Voice notes supported* — just send a voice message.\n\n"
        "*Example:*\n"
        "`3sg sean 1816 felt blurred vision faint asked pc rso. went ntfgh 2038 ct scan done awaiting result.`",
        parse_mode="Markdown",
    )
    return ENTERING_DESCRIPTION


async def enter_description_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text description input."""
    context.user_data["raw_dump"] = update.message.text.strip()
    return await _ask_additional(update, context)


async def enter_description_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice note input — transcribe with Groq Whisper."""
    await update.message.reply_text("🎙️ Transcribing your voice note...")

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    await file.download_to_drive(tmp_path)

    try:
        transcript = transcribe_voice(tmp_path)
        context.user_data["raw_dump"] = transcript

        await update.message.reply_text(
            f"✅ *Transcribed:*\n_{transcript}_\n\n"
            "If this looks wrong, send another voice note or type it out.",
            parse_mode="Markdown",
        )
        return await _ask_additional(update, context)
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Transcription failed: {e}\n\nPlease type out what happened instead."
        )
        return ENTERING_DESCRIPTION
    finally:
        os.unlink(tmp_path)


async def _ask_additional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for optional additional fields after description is captured."""
    await update.message.reply_text(
        "✅ Got it.\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "A few more optional details.\n"
        "_(Send a dash — to skip any field)_\n\n"
        "*Follow-up action:*\n"
        "e.g. `2LT TAN will update BDO after appt on 080626`",
        parse_mode="Markdown",
    )
    return ENTERING_ADDITIONAL


async def enter_additional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect follow-up, verbal report time, written report time, officer."""
    text = update.message.text.strip()

    # Walk through fields sequentially using a step counter
    step = context.user_data.get("additional_step", 0)

    if step == 0:
        context.user_data["follow_up_action"] = "" if text == "-" else text
        await update.message.reply_text(
            "*Verbal report to GSOC date/time:*\ne.g. `010626 1830H`\n_(Send - to skip)_",
            parse_mode="Markdown",
        )
        context.user_data["additional_step"] = 1
        return ENTERING_ADDITIONAL

    elif step == 1:
        context.user_data["verbal_report"] = "—" if text == "-" else text
        await update.message.reply_text(
            "*Written report to GSOC date/time:*\ne.g. `010626 2100H`\n_(Send - to skip)_",
            parse_mode="Markdown",
        )
        context.user_data["additional_step"] = 2
        return ENTERING_ADDITIONAL

    elif step == 2:
        context.user_data["written_report"] = "—" if text == "-" else text
        profile = context.user_data["profile"]
        await update.message.reply_text(
            f"*Reporting Officer:*\n_(Default: {profile['default_officer']})_\n\nSend - to use default.",
            parse_mode="Markdown",
        )
        context.user_data["additional_step"] = 3
        return ENTERING_ADDITIONAL

    elif step == 3:
        profile = context.user_data["profile"]
        if text == "-" or not text:
            context.user_data["reporting_officer"] = profile["default_officer"]
        else:
            context.user_data["reporting_officer"] = text

        context.user_data.pop("additional_step", None)
        return await _generate_report(update, context)


async def _generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Call Groq to generate the IR and show for confirmation."""
    await update.message.reply_text("⚡ *Generating your report...*", parse_mode="Markdown")

    profile = context.user_data["profile"]

    try:
        brief = generate_brief(
            battalion=profile["battalion"],
            coy=profile["coy"],
            incident_type=context.user_data["type"],
            name=context.user_data["name"],
            date=context.user_data["date"],
            raw_dump=context.user_data["raw_dump"],
        )
        context.user_data["generated_brief"] = brief

        # Build preview
        mock_report = {
            "battalion": profile["battalion"],
            "coy": profile["coy"],
            "type": context.user_data["type"],
            "serviceman_name": context.user_data["name"],
            "date": context.user_data["date"],
            "time": context.user_data["time"],
            "location": context.user_data["location"],
            "ops_impact": "NIL",
            "causal_a": "NIL",
            "causal_b": "NIL",
            "causal_c": "NIL",
            "verbal_report": context.user_data.get("verbal_report", "—"),
            "written_report": context.user_data.get("written_report", "—"),
        }
        mock_version = {
            "brief_description": brief,
            "follow_up_action": context.user_data.get("follow_up_action", "NIL"),
            "reporting_officer": context.user_data.get("reporting_officer", ""),
        }

        preview = format_report_preview(mock_report, mock_version)

        # Warn if transcript may be incomplete
        if "⚠️" in brief:
            preview += "\n\n⚠️ *Check carefully — transcript may be incomplete.*"

        await update.message.reply_text(
            preview + "\n\n━━━━━━━━━━━━━━━━\nDoes this look correct?",
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown",
        )
        return CONFIRMING_REPORT

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Generation failed: {e}\n\nTry again with /newir"
        )
        return ConversationHandler.END


async def confirm_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the confirmed report."""
    query = update.callback_query
    await query.answer()

    if query.data == "ir_edit":
        await query.edit_message_text(
            "✏️ Send your updated description (text or voice note):"
        )
        context.user_data.pop("generated_brief", None)
        return ENTERING_DESCRIPTION

    if query.data == "ir_regen":
        await query.edit_message_text("🔄 Regenerating...")
        context.user_data.pop("generated_brief", None)
        # Re-run generation
        profile = context.user_data["profile"]
        try:
            brief = generate_brief(
                battalion=profile["battalion"],
                coy=profile["coy"],
                incident_type=context.user_data["type"],
                name=context.user_data["name"],
                date=context.user_data["date"],
                raw_dump=context.user_data["raw_dump"],
            )
            context.user_data["generated_brief"] = brief
            mock_report = {
                "battalion": profile["battalion"],
                "coy": profile["coy"],
                "type": context.user_data["type"],
                "serviceman_name": context.user_data["name"],
                "date": context.user_data["date"],
                "time": context.user_data["time"],
                "location": context.user_data["location"],
                "ops_impact": "NIL",
                "causal_a": "NIL", "causal_b": "NIL", "causal_c": "NIL",
                "verbal_report": context.user_data.get("verbal_report", "—"),
                "written_report": context.user_data.get("written_report", "—"),
            }
            mock_version = {
                "brief_description": brief,
                "follow_up_action": context.user_data.get("follow_up_action", "NIL"),
                "reporting_officer": context.user_data.get("reporting_officer", ""),
            }
            preview = format_report_preview(mock_report, mock_version)
            await query.message.reply_text(
                preview + "\n\n━━━━━━━━━━━━━━━━\nDoes this look correct?",
                reply_markup=confirm_keyboard(),
                parse_mode="Markdown",
            )
            return CONFIRMING_REPORT
        except Exception as e:
            await query.message.reply_text(f"⚠️ Regeneration failed: {e}")
            return ConversationHandler.END

    if query.data == "ir_confirm":
        profile = context.user_data["profile"]
        report_data = {
            "type": context.user_data["type"],
            "name": context.user_data["name"],
            "date": context.user_data["date"],
            "time": context.user_data["time"],
            "location": context.user_data["location"],
            "battalion": profile["battalion"],
            "coy": profile["coy"],
            "ops_impact": "NIL",
            "follow_up_action": context.user_data.get("follow_up_action", "NIL"),
            "verbal_report": context.user_data.get("verbal_report", "—"),
            "written_report": context.user_data.get("written_report", "—"),
            "reporting_officer": context.user_data.get("reporting_officer", profile["default_officer"]),
            "raw_dump": context.user_data.get("raw_dump", ""),
        }
        brief = context.user_data["generated_brief"]

        try:
            report_id = save_report(
                filed_by=query.from_user.id,
                report_data=report_data,
                brief=brief,
            )
            await query.edit_message_text(
                f"✅ *IR Filed Successfully*\n\n"
                f"*Report ID:* `{report_id}`\n"
                f"*Individual:* {context.user_data['name']}\n"
                f"*Type:* {context.user_data['type']}\n\n"
                f"Use /dashboard to view all reports.\n"
                f"Use /update to file a follow-up.",
                parse_mode="Markdown",
            )
        except Exception as e:
            await query.edit_message_text(f"⚠️ Failed to save: {e}\n\nTry again with /newir")

        context.user_data.clear()
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled. Use /newir to start again.")
    return ConversationHandler.END


def new_ir_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("newir", new_ir)],
        states={
            SELECTING_TYPE: [CallbackQueryHandler(select_type, pattern="^irtype_")],
            ENTERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTERING_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_datetime)],
            ENTERING_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_location)],
            ENTERING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_description_text),
                MessageHandler(filters.VOICE, enter_description_voice),
            ],
            ENTERING_ADDITIONAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_additional)],
            CONFIRMING_REPORT: [CallbackQueryHandler(confirm_report, pattern="^ir_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="new_ir",
        persistent=False,
    )
