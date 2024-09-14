import logging
import requests
import filetype
import os
import asyncio
import json
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from plugins.config import Config
from plugins.functions.forcesub import handle_force_subscribe
from plugins.functions.display_progress import humanbytes
from plugins.functions.help_uploadbot import DownLoadFile
from plugins.functions.display_progress import progress_for_pyrogram, humanbytes, TimeFormatter
from plugins.functions.ran_text import random_char
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
    if not update.from_user:
        return await update.reply_text("I don't know about you sar :(")
    await add_user_to_database(bot, update)

    if Config.UPDATES_CHANNEL:
      fsub = await handle_force_subscribe(bot, update)
      if fsub == 400:
        return
    
    logger.info(update.from_user)
    url = update.text.strip()
    file_name = None

    if "|" in url:
        url_parts = url.split("|")
        if len(url_parts) == 2:
            url = url_parts[0]
            file_name = url_parts[1]
        elif len(url_parts) == 4:
            url = url_parts[0]
            file_name = url_parts[1]
            youtube_dl_username = url_parts[2]
            youtube_dl_password = url_parts[3]
    else:
        for entity in update.entities:
            if entity.type == "text_link":
                url = entity.url
            elif entity.type == "url":
                o = entity.offset
                l = entity.length
                url = url[o:o + l]
    
    # Handle direct file URLs
    logger.info(f"Processing URL: {url}")
    chk = await bot.send_message(
        chat_id=update.chat.id,
        text='Processing your link ⌛',
        disable_web_page_preview=True,
        reply_to_message_id=update.id,
        parse_mode=enums.ParseMode.HTML
    )
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        file_path = f"{Config.DOWNLOAD_LOCATION}/{random_char(5)}.{filetype.guess_extension(response.content[:128])}"
        
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        
        kind = filetype.guess(file_path)
        if kind is None:
            raise ValueError("Cannot determine file type")

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
        if os.path.exists(file_path):
            os.remove(file_path)
        await chk.delete()

@Client.on_callback_query()
async def handle_callback_query(bot, query):
    data = query.data.decode("UTF-8").split("|")
    file_type = data[0]
    format_id = data[1]
    format_ext = data[2]
    randem = data[3]

    await query.answer()
    await query.message.edit_text(
        text=f"Processing {file_type} with format ID {format_id} and extension {format_ext}.",
        parse_mode=enums.ParseMode.HTML
    )

    # Handle download process based on selected format
    # Define the command to download in the selected format
    if file_type == "video":
        download_command = [
            "yt-dlp",
            "--no-warnings",
            "--format",
            format_id,
            "--output",
            f"{Config.DOWNLOAD_LOCATION}/{randem}.%(ext)s",
            url
        ]
    elif file_type == "audio":
        download_command = [
            "yt-dlp",
            "--no-warnings",
            "--format",
            format_id,
            "--output",
            f"{Config.DOWNLOAD_LOCATION}/{randem}.%(ext)s",
            url
        ]
    elif file_type == "file":
        download_command = [
            "yt-dlp",
            "--no-warnings",
            "--format",
            format_id,
            "--output",
            f"{Config.DOWNLOAD_LOCATION}/{randem}.%(ext)s",
            url
        ]

    # Execute the download command
    process = await asyncio.create_subprocess_exec(
        *download_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if stderr:
        await query.message.edit_text(
            text=f"Error occurred: {stderr.decode()}",
            parse_mode=enums.ParseMode.HTML
        )
        return

    # Prepare the file for upload
    download_path = f"{Config.DOWNLOAD_LOCATION}/{randem}.{format_ext}"
    if os.path.exists(download_path):
        # Check file type and handle accordingly
        kind = filetype.guess(download_path)
        if kind is None:
            await query.message.edit_text(
                text="Failed to determine file type.",
                parse_mode=enums.ParseMode.HTML
            )
            return

        file_mime_type = kind.mime
        if "video" in file_mime_type:
            await bot.send_video(
                chat_id=query.message.chat.id,
                video=download_path,
                caption=f"Here is your video in {format_ext} format.",
                parse_mode=enums.ParseMode.HTML
            )
        elif "audio" in file_mime_type:
            await bot.send_audio(
                chat_id=query.message.chat.id,
                audio=download_path,
                caption=f"Here is your audio in {format_ext} format.",
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await bot.send_document(
                chat_id=query.message.chat.id,
                document=download_path,
                caption=f"Here is your file in {format_ext} format.",
                parse_mode=enums.ParseMode.HTML
            )

        os.remove(download_path)  # Clean up the file after sending
    else:
        await query.message.edit_text(
            text="Downloaded file not found.",
            parse_mode=enums.ParseMode.HTML
        )
