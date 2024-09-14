# ©️ LISA-KOREA | @LISA_FAN_LK | NT_BOT_CHANNEL

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
import requests, urllib.parse, filetype, os, time, shutil, tldextract, asyncio, json, math
from PIL import Image
from plugins.config import Config
import time
from plugins.script import Translation
logging.getLogger("pyrogram").setLevel(logging.WARNING)
from pyrogram import filters
from pyrogram import Client, enums
from plugins.functions.forcesub import handle_force_subscribe
from plugins.functions.display_progress import humanbytes
from plugins.functions.help_uploadbot import DownLoadFile
from plugins.functions.display_progress import progress_for_pyrogram, humanbytes, TimeFormatter
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from plugins.functions.ran_text import random_char
from plugins.database.add import add_user_to_database
from pyrogram.types import Thumbnail

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
        # https://stackoverflow.com/a/761825/4723940
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
    if Config.HTTP_PROXY != "":
        command_to_exec = [
            "yt-dlp",
            "--no-warnings",
            "--youtube-skip-hls-manifest",
            "-j",
            url,
            "--proxy", Config.HTTP_PROXY
        ]
    else:
        command_to_exec = [
            "yt-dlp",
            "--no-warnings",
            "--youtube-skip-hls-manifest",
            "-j",
            url
        ]
    if youtube_dl_username is not None:
        command_to_exec.append("--username")
        command_to_exec.append(youtube_dl_username)
    if youtube_dl_password is not None:
        command_to_exec.append("--password")
        command_to_exec.append(youtube_dl_password)
    logger.info(command_to_exec)
    chk = await bot.send_message(
            chat_id=update.chat.id,
            text=f'ᴘʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ʟɪɴᴋ ⌛',
            disable_web_page_preview=True,
            reply_to_message_id=update.id,
            parse_mode=enums.ParseMode.HTML
          )
    process = await asyncio.create_subprocess_exec(
        *command_to_exec,
        # stdout must a pipe to be accessible as process.stdout
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    logger.info(e_response)
    t_response = stdout.decode().strip()
    if e_response and "nonnumeric port" not in e_response:
        error_message = e_response.replace("please report this issue on https://yt-dl.org/bug . Make sure you are using the latest version; see  https://yt-dl.org/update  on how to update. Be sure to call youtube-dl with the --verbose flag and include its complete output.", "")
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
        save_ytdl_json_path = Config.DOWNLOAD_LOCATION + \
            "/" + str(update.from_user.id) + f'{randem}' + ".json"
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
                
                # Generating callback data
                cb_string_video = "{}|{}|{}|{}".format(
                    "video", format_id, format_ext, randem)
                cb_string_audio = "{}|{}|{}|{}".format(
                    "audio", format_id, format_ext, randem)
                cb_string_file = "{}|{}|{}|{}".format(
                    "file", format_id, format_ext, randem)

                # Append video format button
                ikeyboard = [
                    InlineKeyboardButton(
                        "🎬 " + format_string + " " + format_ext + " " + approx_file_size + " ",
                        callback_data=(cb_string_video).encode("UTF-8")
                    )
                ]
                inline_keyboard.append(ikeyboard)

                # Append option to choose upload format
                inline_keyboard.append([
                    InlineKeyboardButton("Upload as Video", callback_data=(cb_string_video).encode("UTF-8")),
                    InlineKeyboardButton("Upload as Audio", callback_data=(cb_string_audio).encode("UTF-8")),
                    InlineKeyboardButton("Upload as Document", callback_data=(cb_string_file).encode("UTF-8"))
                ])

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
        
        # Send options to user
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text="Choose the format and quality for your download:",
            reply_to_message_id=update.id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard),
            parse_mode=enums.ParseMode.HTML
        )
    else:
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text="No available formats found for the provided link.",
            reply_to_message_id=update.id,
            parse_mode=enums.ParseMode.HTML
        )

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

    # Handle the download process based on selected format
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
                        
