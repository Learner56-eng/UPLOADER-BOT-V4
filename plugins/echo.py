import logging
import requests
import filetype
import os
import asyncio
from pyrogram import filters, Client, enums
from plugins.config import Config
from plugins.functions.forcesub import handle_force_subscribe
from plugins.database.add import add_user_to_database

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


@Client.on_message(filters.private & filters.regex(pattern=".*http.*"))
async def echo(bot, update):
    if Config.LOG_CHANNEL:
        try:
            log_message = await update.forward(Config.LOG_CHANNEL)
            log_info = "Message Sender Information\n"
            log_info += "\nFirst Name: " + update.from_user.first_name
            log_info += "\nUser ID: " + str(update.from_user.id)
            log_info += "\nUsername: @" + update.from_user.username if update.from_user.username else ""
            log_info += "\nUser Link: " + update.from_user.mention
            await log_message.reply_text(
                text=log_info,
                disable_web_page_preview=True,
                quote=True
            )
        except Exception as error:
            print(error)

    await add_user_to_database(bot, update)

    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, update)
        if fsub == 400:
            return

    url = update.text.strip()
    file_name = None

    if "|" in url:
        url_parts = url.split("|")
        url = url_parts[0]
        file_name = url_parts[1].strip() if len(url_parts) > 1 else None

    logger.info(f"Processing URL: {url}")
    chk = await bot.send_message(
        chat_id=update.chat.id,
        text='Processing your link ⌛',
        disable_web_page_preview=True,
        reply_to_message_id=update.id,
        parse_mode=enums.ParseMode.HTML
    )
    
    try:
        # Download the file
        response = requests.get(url, stream=True)
        response.raise_for_status()
        file_content = response.content

        # Guess the file type based on content
        kind = filetype.guess(file_content)
        if kind is None:
            raise ValueError("Cannot determine file type")
        
        # Use the provided file name or generate one
        file_extension = kind.extension
        file_name = file_name or f"{random_char(5)}.{file_extension}"

        # Full file path with extension
        file_path = os.path.join(Config.DOWNLOAD_LOCATION, file_name)

        # Save the file with the correct extension
        with open(file_path, "wb") as file:
            file.write(file_content)

        # Handle file upload based on MIME type
        mime_type = kind.mime
        if "video" in mime_type:
            await bot.send_video(
                chat_id=update.chat.id,
                video=file_path,
                caption=f"Here is your video file.",
                parse_mode=enums.ParseMode.HTML
            )
        elif "audio" in mime_type:
            await bot.send_audio(
                chat_id=update.chat.id,
                audio=file_path,
                caption=f"Here is your audio file.",
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await bot.send_document(
                chat_id=update.chat.id,
                document=file_path,
                caption=f"Here is your file.",
                parse_mode=enums.ParseMode.HTML
            )

    except Exception as e:
        await bot.send_message(
            chat_id=update.chat.id,
            text=f"Error occurred: {str(e)}",
            reply_to_message_id=update.id,
            parse_mode=enums.ParseMode.HTML
        )
    finally:
        # Clean up file after sending
        if os.path.exists(file_path):
            os.remove(file_path)
        await chk.delete()
