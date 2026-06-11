from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from services.db import (
    get_user, get_open_reports, get_closed_reports,
    get_report, get_latest_version, get_all_versions,
    add_version, close_report,
)
from services.groq_service import generate_update
from utils import format_full_report, format_report_card, parse_brief_with_new_tags

# Update states
SELECTING_REPORT, ENTERING_UPDATE, ENTERING_UPDATE_FU, CONFIRMING_UPDATE = range(4)


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Run /start to set up your profile first.")
        return

    open_reports = get_open_reports(update.effective_user.id)
    closed_reports = get_closed_reports(update.effective_user.id)

    lines = [f"📊 *DASHBOARD — {user['battalion']} · {user['coy']}*\n"]

    if open_reports:
        lines.append(f"🟢 *OPEN ({len(open_reports)})*")
        for r in open_reports:
            lines.append(format_report_card(r))
    else:
        lines.append("🟢 *OPEN*\nNo open reports.")

    lines.append("")

    if closed_reports:
        lines.append(f"⚫ *CLOSED ({len(closed_reports)})*")
        for r in closed_reports[:5]:  # Show last 5 closed
            lines.append(format_report_card(r))
    else:
        lines.append("⚫ *CLOSED*\nNo closed reports.")

    lines.append("\n━━━━━━━━━━━━━━━━")
    lines.append("To view a report: `/view REPORT-ID`")
    lines.append("To update a report: /update")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def view_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View a specific report by ID. Usage: /view IR-0626-ABCD"""
    if not context.args:
        await update.message.reply_text("Usage: `/view REPORT-ID`\ne.g. `/view IR-0626-ABCD`", parse_mode="Markdown")
        return

    report_id = context.args[0].upper()
    report = get_report(report_id)

    if not report:
        await update.message.reply_text(f"❌ Report `{report_id}` not found.", parse_mode="Markdown")
        return

    version = get_latest_version(report_id)
    if not version:
        await update.message.reply_text("⚠️ Report found but no version data.")
        return

    full_text = format_full_report(report, version)
    status = "🟢 OPEN" if report["status"] == "open" else "⚫ CLOSED"
    versions = get_all_versions(report_id)

    header = (
        f"{status} | `{report_id}` | v{len(versions)}\n"
        f"━━━━━━━━━━━━━━━━\n"
    )

    # Send full report as a formatted code block for easy copying
    await update.message.reply_text(
        header + f"```\n{full_text}\n```",
        parse_mode="Markdown",
    )

    if report["status"] == "open":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ File Update", callback_data=f"view_update_{report_id}"),
                InlineKeyboardButton("✓ Close Report", callback_data=f"view_close_{report_id}"),
            ]
        ])
        await update.message.reply_text("Actions:", reply_markup=keyboard)


async def view_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("view_close_"):
        report_id = query.data.replace("view_close_", "")
        close_report(report_id)
        await query.edit_message_text(f"✅ Report `{report_id}` closed and archived.", parse_mode="Markdown")

    elif query.data.startswith("view_update_"):
        report_id = query.data.replace("view_update_", "")
        context.user_data["updating_report_id"] = report_id
        await query.edit_message_text(
            f"✏️ *Filing update for `{report_id}`*\n\n"
            "Describe what happened — text or voice note.\n"
            "Shorthand is fine.",
            parse_mode="Markdown",
        )
        return ENTERING_UPDATE


# ── UPDATE FLOW ───────────────────────────────────────────────────────────────

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show open reports to select one for updating."""
    open_reports = get_open_reports(update.effective_user.id)

    if not open_reports:
        await update.message.reply_text("✅ No open reports to update.")
        return ConversationHandler.END

    buttons = []
    for r in open_reports:
        label = f"{r['id']} | {r['serviceman_name']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"upd_select_{r['id']}")])

    await update.message.reply_text(
        "✏️ *FILE UPDATE*\n\nWhich report are you updating?",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )
    return SELECTING_REPORT


async def select_report_for_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    report_id = query.data.replace("upd_select_", "")
    report = get_report(report_id)
    version = get_latest_version(report_id)

    if not report or not version:
        await query.edit_message_text("❌ Report not found.")
        return ConversationHandler.END

    context.user_data["updating_report_id"] = report_id
    context.user_data["updating_report"] = report
    context.user_data["updating_version"] = version

    # Check for outstanding items
    brief_lower = version["brief_description"].lower()
    pending = []
    if "mc" not in brief_lower and "hospitalisation" not in brief_lower:
        pending.append("🟠 MC / HL details")
    if "return" not in brief_lower and "returned" not in brief_lower:
        pending.append("🟠 Return to camp")
    if "diagnos" not in brief_lower:
        pending.append("🟠 Hospital diagnosis & treatment")

    pending_text = ""
    if pending:
        pending_text = "\n\n*Outstanding items:*\n" + "\n".join(pending)

    await query.edit_message_text(
        f"✏️ *Update — {report_id}*\n"
        f"_{report['serviceman_name']} | {report['type']}_"
        f"{pending_text}\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "Describe what happened.\n"
        "Text or voice note — shorthand is fine.\n\n"
        "e.g. `1245 ntfgh temp 38.3, 3 iv 3 bcu temp down 36.8, 1315 doc 7d mc 010626 to 070626`",
        parse_mode="Markdown",
    )
    return ENTERING_UPDATE


async def enter_update_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["update_dump"] = update.message.text.strip()
    await update.message.reply_text(
        "Updated follow-up action?\n_(Send - to keep existing)_",
        parse_mode="Markdown",
    )
    return ENTERING_UPDATE_FU


async def enter_update_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice note for update."""
    import os, tempfile
    from services.groq_service import transcribe_voice

    await update.message.reply_text("🎙️ Transcribing...")

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    await file.download_to_drive(tmp_path)

    try:
        transcript = transcribe_voice(tmp_path)
        context.user_data["update_dump"] = transcript
        await update.message.reply_text(
            f"✅ *Transcribed:*\n_{transcript}_\n\n"
            "Updated follow-up action?\n_(Send - to keep existing)_",
            parse_mode="Markdown",
        )
        return ENTERING_UPDATE_FU
    except Exception as e:
        await update.message.reply_text(f"⚠️ Transcription failed: {e}\nPlease type your update instead.")
        return ENTERING_UPDATE
    finally:
        os.unlink(tmp_path)


async def enter_update_fu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    version = context.user_data["updating_version"]
    context.user_data["update_fu"] = version.get("follow_up_action", "NIL") if text == "-" else text

    await update.message.reply_text("⚡ *Generating update...*", parse_mode="Markdown")

    existing_brief = version["brief_description"]
    raw_update = context.user_data["update_dump"]

    try:
        new_brief = generate_update(existing_brief, raw_update)
        context.user_data["new_brief"] = new_brief

        # Show new paragraphs highlighted
        formatted = parse_brief_with_new_tags(new_brief)
        await update.message.reply_text(
            "📋 *New paragraphs to be added:*\n_(Bold = new)_\n\n"
            f"{formatted}\n\n"
            "━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Confirm", callback_data="upd_confirm"),
                    InlineKeyboardButton("🔄 Redo", callback_data="upd_redo"),
                ]
            ]),
            parse_mode="Markdown",
        )
        return CONFIRMING_UPDATE

    except Exception as e:
        await update.message.reply_text(f"⚠️ Generation failed: {e}\n\nTry /update again.")
        return ConversationHandler.END


async def confirm_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "upd_redo":
        await query.edit_message_text(
            "🔄 Send your update again (text or voice):"
        )
        return ENTERING_UPDATE

    if query.data == "upd_confirm":
        report_id = context.user_data["updating_report_id"]
        version = context.user_data["updating_version"]

        try:
            add_version(
                report_id=report_id,
                new_brief=context.user_data["new_brief"],
                follow_up_action=context.user_data.get("update_fu", "NIL"),
                reporting_officer=version.get("reporting_officer", ""),
            )
            await query.edit_message_text(
                f"✅ *Report `{report_id}` updated.*\n\n"
                "Use /dashboard to view all reports.",
                parse_mode="Markdown",
            )
        except Exception as e:
            await query.edit_message_text(f"⚠️ Failed to save: {e}")

        context.user_data.clear()
        return ConversationHandler.END


async def cancel_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Update cancelled.")
    return ConversationHandler.END


def update_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("update", update_command)],
        states={
            SELECTING_REPORT: [CallbackQueryHandler(select_report_for_update, pattern="^upd_select_")],
            ENTERING_UPDATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_update_text),
                MessageHandler(filters.VOICE, enter_update_voice),
            ],
            ENTERING_UPDATE_FU: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_update_fu)],
            CONFIRMING_UPDATE: [CallbackQueryHandler(confirm_update, pattern="^upd_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_update)],
        name="update",
        persistent=False,
    )
