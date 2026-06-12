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
    CONFIRM_TRANSCRIPT,
    ENTERING_ADDITIONAL,
    CONFIRMING_REPORT,
) = range(8)

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


def transcript_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Looks good", callback_data="tr_ok"),
            InlineKeyboardButton("🔄 Redo voice note", callback_data="tr_redo"),
        ]
    ])


async def require_profile(update: Update) -> dict | None:
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
        f"✅ *{parts[0]}, {parts[1]}H*\n\nLocation of incident?",
        parse_mode="Markdown",
    )
    return ENTERING_LOCATION


async def enter_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["location"] = update.message.text.strip()

    await update.message.reply_text(
        f"✅ *{context.user_data['location']}*\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "💡 *Describe what happened*\n\n"
        "Shorthand or broken English is fine.\n"
        "Include: times, who was involved, where they went, outcome, MC dates.\n\n"
        "🎙️ *Send a voice note* — or type it out below.\n\n"
        "*Example (text):*\n"
        "`3sg sean 1816 blurred vision faint, asked pc rso. ntfgh 2038 ct scan awaiting result.`",
        parse_mode="Markdown",
    )
    return ENTERING_DESCRIPTION


async def enter_description_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle typed description."""
    context.user_data["raw_dump"] = update.message.text.strip()
    return await _ask_additional(update, context)


async def enter_description_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice note — transcribe with Groq Whisper, then confirm before proceeding."""
    await update.message.reply_text("🎙️ *Transcribing your voice note...*", parse_mode="Markdown")

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await file.download_to_drive(tmp_path)
        transcript = transcribe_voice(tmp_path)

        if not transcript or len(transcript.strip()) < 5:
            await update.message.reply_text(
                "⚠️ Transcript came back empty — the voice note may have been too short or unclear.\n\n"
                "Please *type* what happened instead, or send a longer voice note.",
                parse_mode="Markdown",
            )
            return ENTERING_DESCRIPTION

        context.user_data["raw_dump"] = transcript

        # Show transcript and WAIT for user confirmation before proceeding
        await update.message.reply_text(
            "✅ *Transcribed — does this look right?*\n\n"
            f"_{transcript}_\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "Tap ✅ to continue, or 🔄 to send a new voice note.\n"
            "You can also *type a correction* if something was missed.",
            reply_markup=transcript_keyboard(),
            parse_mode="Markdown",
        )
        return CONFIRM_TRANSCRIPT

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ *Transcription failed.*\n\n`{e}`\n\n"
            "Please *type* what happened instead.",
            parse_mode="Markdown",
        )
        return ENTERING_DESCRIPTION

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


async def confirm_transcript(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user confirming or redoing the transcript."""
    query = update.callback_query
    await query.answer()

    if query.data == "tr_redo":
        await query.edit_message_text(
            "🎙️ Send a new voice note — or type what happened:"
        )
        context.user_data.pop("raw_dump", None)
        return ENTERING_DESCRIPTION

    if query.data == "tr_ok":
        await query.edit_message_text(
            f"✅ *Captured:*\n_{context.user_data['raw_dump']}_",
            parse_mode="Markdown",
        )
        # Now ask for additional info
        await query.message.reply_text(
            "━━━━━━━━━━━━━━━━\n"
            "A few more optional details.\n"
            "_(Send a dash — to skip any field)_\n\n"
            "*[1/4] Follow-up action:*\n"
            "e.g. `2LT TAN will update BDO after appt on 080626`",
            parse_mode="Markdown",
        )
        context.user_data["additional_step"] = 0
        return ENTERING_ADDITIONAL


async def confirm_transcript_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User typed a correction to the transcript."""
    context.user_data["raw_dump"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ *Updated:*\n_{context.user_data['raw_dump']}_",
        parse_mode="Markdown",
    )
    return await _ask_additional(update, context)


async def _ask_additional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the optional additional fields section."""
    context.user_data["additional_step"] = 0
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━\n"
        "A few more optional details.\n"
        "_(Send a dash — to skip any field)_\n\n"
        "*[1/4] Follow-up action:*\n"
        "e.g. `2LT TAN will update BDO after appt on 080626`",
        parse_mode="Markdown",
    )
    return ENTERING_ADDITIONAL


async def enter_additional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect follow-up action, verbal/written report times, and reporting officer."""
    text = update.message.text.strip()
    step = context.user_data.get("additional_step", 0)

    if step == 0:
        context.user_data["follow_up_action"] = "" if text == "-" else text
        await update.message.reply_text(
            "*[2/4] Verbal report to GSOC date/time:*\n"
            "e.g. `010626 0750H`\n_(Send - to skip)_",
            parse_mode="Markdown",
        )
        context.user_data["additional_step"] = 1
        return ENTERING_ADDITIONAL

    elif step == 1:
        context.user_data["verbal_report"] = "—" if text == "-" else text
        await update.message.reply_text(
            "*[3/4] Written report to GSOC date/time:*\n"
            "e.g. `010626 0900H`\n_(Send - to skip)_",
            parse_mode="Markdown",
        )
        context.user_data["additional_step"] = 2
        return ENTERING_ADDITIONAL

    elif step == 2:
        context.user_data["written_report"] = "—" if text == "-" else text
        profile = context.user_data["profile"]
        await update.message.reply_text(
            f"*[4/4] Reporting Officer:*\n"
            f"_(Default: {profile['default_officer']})_\n\n"
            "Send - to use default.",
            parse_mode="Markdown",
        )
        context.user_data["additional_step"] = 3
        return ENTERING_ADDITIONAL

    elif step == 3:
        profile = context.user_data["profile"]
        context.user_data["reporting_officer"] = (
            profile["default_officer"] if text == "-" or not text else text
        )
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
            "follow_up_action": context.user_data.get("follow_up_action", "NIL") or "NIL",
            "reporting_officer": context.user_data.get("reporting_officer", ""),
        }

        preview = format_report_preview(mock_report, mock_version)

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
            f"⚠️ *Generation failed:* `{e}`\n\nUse /newir to try again.",
            parse_mode="Markdown",
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
        context.user_data.pop("additional_step", None)
        return ENTERING_DESCRIPTION

    if query.data == "ir_regen":
        await query.edit_message_text("🔄 *Regenerating...*", parse_mode="Markdown")
        context.user_data.pop("generated_brief", None)
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
                "follow_up_action": context.user_data.get("follow_up_action", "NIL") or "NIL",
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
            await query.message.reply_text(f"⚠️ Regeneration failed: `{e}`", parse_mode="Markdown")
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
            "follow_up_action": context.user_data.get("follow_up_action", "NIL") or "NIL",
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
                "Use /dashboard to view all reports.\n"
                "Use /update to file a follow-up.",
                parse_mode="Markdown",
            )
        except Exception as e:
            await query.edit_message_text(
                f"⚠️ Failed to save: `{e}`\n\nTry again with /newir",
                parse_mode="Markdown",
            )

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
            SELECTING_TYPE: [
                CallbackQueryHandler(select_type, pattern="^irtype_")
            ],
            ENTERING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)
            ],
            ENTERING_DATETIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_datetime)
            ],
            ENTERING_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_location)
            ],
            ENTERING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_description_text),
                MessageHandler(filters.VOICE, enter_description_voice),
            ],
            CONFIRM_TRANSCRIPT: [
                CallbackQueryHandler(confirm_transcript, pattern="^tr_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_transcript_text),
                MessageHandler(filters.VOICE, enter_description_voice),
            ],
            ENTERING_ADDITIONAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_additional)
            ],
            CONFIRMING_REPORT: [
                CallbackQueryHandler(confirm_report, pattern="^ir_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="new_ir",
        persistent=False,
    )
