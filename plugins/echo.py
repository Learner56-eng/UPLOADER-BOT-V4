import logging
import requests
import urllib.parse
import filetype
import os
import time
import shutil
import tldextract
import asyncio
import json
import math
from PIL import Image
from plugins.config import Config
from plugins.script import Translation
from pyrogram import filters, Client, enums
from plugins.functions.forcesub import handle_force_subscribe
from plugins.functions.display_progress import progress_for_pyrogram, humanbytes, TimeFormatter
from plugins.functions.help_uploadbot import DownLoadFile
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from plugins.functions.ran_text import random_char
from plugins.database.add import add_user_to_database
from pyrogram.types import Thumbnail

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    url = update.text
    youtube_dl_username = None
    youtube_dl_password = None
    file_name = None

    print(url)
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
        if url is not None:
            url = url.strip()
        if file_name is not None:
            file_name = file_name.strip()
        if youtube_dl_username is not None:
            youtube_dl_username = youtube_dl_username.strip()
        if youtube_dl_password is not None:
            youtube_dl_password = youtube_dl_password.strip()
        logger.info(url)
        logger.info(file_name)
    else:
        for entity in update.entities:
            if entity.type == "text_link":
                url = entity.url
            elif entity.type == "url":
                o = entity.offset
                l = entity.length
                url = url[o:o + l]

    command_to_exec = [
        "yt-dlp",
        "--no-warnings",
        "--youtube-skip-hls-manifest",
        "-j",
        url
    ]

    if Config.HTTP_PROXY != "":
        command_to_exec.append("--proxy")
        command_to_exec.append(Config.HTTP_PROXY)
    if youtube_dl_username is not None:
        command_to_exec.append("--username")
        command_to_exec.append(youtube_dl_username)
    if youtube_dl_password is not None:
        command_to_exec.append("--password")
        command_to_exec.append(youtube_dl_password)

    logger.info(command_to_exec)
    chk = await bot.send_message(
        chat_id=update.chat.id,
        text=f'Processing your link ⌛',
        disable_web_page_preview=True,
        reply_to_message_id=update.id,
        parse_mode=enums.ParseMode.HTML
    )
    
    process = await asyncio.create_subprocess_exec(
        *command_to_exec,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    logger.info(e_response)
    t_response = stdout.decode().strip()
    
    if e_response and "nonnumeric port" not in e_response:
        error_message = e_response.replace(
            "please report this issue on https://yt-dl.org/bug . Make sure you are using the latest version; see  https://yt-dl.org/update  on how to update. Be sure to call youtube-dl with the --verbose flag and include its complete output.", "")
        if "This video is only available for registered users." in error_message:
            error_message += Translation.SET_CUSTOM_USERNAME_PASSWORD
        await chk.delete()
        time.sleep(1)
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.NO_VOID_FORMAT_FOUND.format(str(error_message)),
            reply_to_message_id=update.id,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        return False

    if t_response:
        x_reponse = t_response
        if "\n" in x_reponse:
            x_reponse, _ = x_reponse.split("\n")
        response_json = json.loads(x_reponse)
        randem = random_char(5)
        save_ytdl_json_path = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + f'{randem}' + ".json"
        with open(save_ytdl_json_path, "w", encoding="utf8") as outfile:
            json.dump(response_json, outfile, ensure_ascii=False)
        
        inline_keyboard = []
        duration = None
        if "duration" in response_json:
            duration = response_json["duration"]
        if "formats" in response_json:
            for formats in response_json["formats"]:
                format_id = formats.get("format_id")
                format_string = formats.get("format_note")
                if format_string is None:
                    format_string = formats.get("format")
                format_ext = formats.get("ext")
                approx_file_size = ""
                if "filesize" in formats:
                    approx_file_size = humanbytes(formats["filesize"])
                cb_string_video = "{}|{}|{}|{}".format("video", format_id, format_ext, randem)
                cb_string_file = "{}|{}|{}|{}".format("file", format_id, format_ext, randem)
                if format_string is not None and not "audio only" in format_string:
                    ikeyboard = [
                        InlineKeyboardButton(
                            "🎬 " + format_string + " " + format_ext + " " + approx_file_size + " ",
                            callback_data=(cb_string_video).encode("UTF-8")
                        )
                    ]
                else:
                    ikeyboard = [
                        InlineKeyboardButton(
                            "🎬 [" + "] ( " + approx_file_size + " )",
                            callback_data=(cb_string_video).encode("UTF-8")
                        )
                    ]
                inline_keyboard.append(ikeyboard)
            if duration is not None:
                cb_string_64 = "{}|{}|{}|{}".format("audio", "64k", "mp3", randem)
                cb_string_128 = "{}|{}|{}|{}".format("audio", "128k", "mp3", randem)
                cb_string = "{}|{}|{}|{}".format("audio", "320k", "mp3", randem)
                inline_keyboard.append([
                    InlineKeyboardButton(
                        "🎵 ᴍᴘ𝟹 " + "(" + "64 ᴋʙᴘs" + ")", callback_data=cb_string_64.encode("UTF-8")),
                    InlineKeyboardButton(
                        "🎵 ᴍᴘ𝟹 " + "(" + "128 ᴋʙᴘs" + ")", callback_data=cb_string_128.encode("UTF-8"))
                ])
                inline_keyboard.append([
                    InlineKeyboardButton(
                        "🎵 ᴍᴘ𝟹 " + "(" + "320 ᴋʙᴘs" + ")", callback_data=cb_string.encode("UTF-8"))
                ])
                inline_keyboard.append([
                    InlineKeyboardButton(
                        "⛔️ ᴄʟᴏsᴇ", callback_data='close')
                ])
        else:
            format_id = response_json["format_id"]
            format_ext = response_json["ext"]
            cb_string_file = "{}={}={}".format("file", format_id, format_ext)
              cb_string_video = "{}={}={}".format("video", format_id, format_ext)
            cb_string_file = "{}={}={}".format("file", format_id, format_ext)
            inline_keyboard = [
                InlineKeyboardButton(
                    "🎬 " + format_id + " " + format_ext,
                    callback_data=(cb_string_video).encode("UTF-8")
                ),
                InlineKeyboardButton(
                    "🎵 " + format_ext,
                    callback_data=(cb_string_file).encode("UTF-8")
                ),
                InlineKeyboardButton(
                    "⛔️ ᴄʟᴏsᴇ", callback_data='close')
            ]

        await chk.delete()
        time.sleep(1)
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.FORMAT_FOUND,
            reply_to_message_id=update.id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        return True

    else:
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.NO_VOID_FORMAT_FOUND,
            reply_to_message_id=update.id,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        return False

@Client.on_callback_query()
async def callback_handler(bot, callback_query):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    if data.startswith("close"):
        await bot.delete_messages(chat_id, message_id)
        return

    # Parse callback data
    file_type, format_id, format_ext, randem = data.split("|")

    # Define a function to download the file with progress
    async def download_file(url, file_name):
        try:
            # Start the download and monitor progress
            async with bot.send_message(
                chat_id=chat_id,
                text="Downloading your file...",
                reply_to_message_id=callback_query.message.message_id,
                parse_mode=enums.ParseMode.HTML
            ) as msg:
                response = requests.get(url, stream=True)
                total_size = int(response.headers.get('content-length', 0))
                progress_bar = progress_for_pyrogram(msg, total_size)

                with open(file_name, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        progress_bar.update(len(chunk))
                
                await msg.edit_text("Download completed!")
                return file_name

        except Exception as e:
            await msg.edit_text(f"Failed to download the file. Error: {str(e)}")
            return None

    # Determine URL based on file type
    file_name = f"download_{randem}.{format_ext}"
    if file_type == "video":
        # Define your video download URL or logic here
        download_url = f"https://example.com/video/{format_id}.{format_ext}"
    elif file_type == "file":
        # Define your file download URL or logic here
        download_url = f"https://example.com/file/{format_id}.{format_ext}"
    elif file_type == "audio":
        # Define your audio download URL or logic here
        download_url = f"https://example.com/audio/{format_id}.{format_ext}"

    # Call the download function
    downloaded_file = await download_file(download_url, file_name)

    if downloaded_file:
        # Send the downloaded file to the user
        await bot.send_document(
            chat_id=chat_id,
            document=downloaded_file,
            caption="Here is your file!",
            reply_to_message_id=callback_query.message.message_id
        )
        # Clean up the downloaded file
        os.remove(downloaded_file)
    else:
        await bot.send_message(
            chat_id=chat_id,
            text="Error occurred while processing your request.",
            reply_to_message_id=callback_query.message.message_id,
            parse_mode=enums.ParseMode.HTML
        )
