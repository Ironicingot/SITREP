import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from handlers.start import setup_conv_handler, profile_conv_handler
from handlers.ir import new_ir_conv_handler
from handlers.dashboard import dashboard, view_report, view_action_callback, update_conv_handler
from handlers.medevac import medevac_conv_handler

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN not set in .env")

    app = Application.builder().token(token).build()

    # Conversation handlers (order matters)
    app.add_handler(setup_conv_handler())
    app.add_handler(profile_conv_handler())
    app.add_handler(new_ir_conv_handler())
    app.add_handler(update_conv_handler())
    app.add_handler(medevac_conv_handler())

    # Simple command handlers
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("view", view_report))
    app.add_handler(CallbackQueryHandler(view_action_callback, pattern="^view_"))

    print("✅ SITREP Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
