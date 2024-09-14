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
        # stdout must be a pipe to be accessible as process.stdout
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
        x_response = t_response
        if "\n" in x_response:
            x_response, _ = x_response.split("\n")
        response_json = json.loads(x_response)
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
                
                # Determine if the format is audio or video based on the extension
                if format_ext in ["mp4", "mkv", "webm"]:  # Add other video formats if needed
                    media_type = "video"
                elif format_ext in ["mp3", "m4a", "m4b"]:  # Add other audio formats if needed
                    media_type = "audio"
                else:
                    media_type = "unknown"

                cb_string = "{}|{}|{}|{}".format(media_type, format_id, format_ext, randem)

                ikeyboard = [
                    InlineKeyboardButton(
                        "🎬 " + format_string + " " + format_ext + " " + approx_file_size + " ",
                        callback_data=(cb_string).encode("UTF-8")
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
            inline_keyboard.append([
                InlineKeyboardButton(
                    "🎬 " + response_json["format"] + " " + format_ext + " ",
                    callback_data=(cb_string_file).encode("UTF-8")
                )
            ])
            inline_keyboard.append([
                InlineKeyboardButton(
                    "⛔️ ᴄʟᴏsᴇ", callback_data='close')
            ])
        reply_markup = InlineKeyboardMarkup(inline_keyboard)
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=f"ꜱᴇʟᴇᴄᴛ ᴛʜᴇ ꜰᴏʀᴍᴀᴛ ғᴏʀ {response_json.get('title')}",
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=update.id
        )
    else:
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.NO_VOID_FORMAT_FOUND.format(str(e_response)),
            reply_to_message_id=update.id,
            parse_mode=enums.ParseMode.HTML
        )

@Client.on_callback_query(filters.regex(pattern="(video|audio|file)"))
async def catch_ytdl_format(bot, update):
    try:
        yt_dl_format, format_id, format_ext, random_string = update.data.decode("UTF-8").split("|")
        save_ytdl_json_path = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + f'{random_string}' + ".json"
        if os.path.exists(save_ytdl_json_path):
            with open(save_ytdl_json_path, "r", encoding="utf8") as outfile:
                response_json = json.load(outfile)
        else:
            await update.message.delete()
            return
        yt_dlp_url = response_json["webpage_url"]
        custom_file_name = response_json["title"]
        user = update.from_user.id

        download_directory = Config.DOWNLOAD_LOCATION + "/"
        await bot.edit_message_text(
            text=f"ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ {yt_dl_format} ꜰɪʟᴇ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ⌛",
            chat_id=update.message.chat.id,
            message_id=update.message.id
        )
        download_cmd = [
            "yt-dlp",
            "-f", format_id,
            "--hls-prefer-ffmpeg",
            yt_dlp_url,
            "-o", download_directory + custom_file_name + "." + format_ext
        ]
        logger.info(download_cmd)
        process = await asyncio.create_subprocess_exec(
            *download_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        logger.info(stdout.decode())
        logger.info(stderr.decode())
        dl_path = download_directory + custom_file_name + "." + format_ext
        if os.path.exists(dl_path):
            thumb_image_path = None
            if "thumbnail" in response_json and yt_dl_format == "video":
                await bot.edit_message_text(
                    text=f"ɢᴇɴᴇʀᴀᴛɪɴɢ ᴛʜᴜᴍʙɴᴀɪʟ ꜰᴏʀ {custom_file_name}",
                    chat_id=update.message.chat.id,
                    message_id=update.message.id
                )
                thumbnail_url = response_json["thumbnail"]
                thumb_image_path = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + ".jpg"
                try:
                    thumb_resp = requests.get(thumbnail_url, allow_redirects=True)
                    with open(thumb_image_path, "wb") as thumb_f:
                        thumb_f.write(thumb_resp.content)
                    with Image.open(thumb_image_path) as img:
                        img.convert("RGB").save(thumb_image_path, "JPEG")
                        img.close()
                except Exception as e:
                    logger.error(f"Failed to download thumbnail: {e}")
                    thumb_image_path = None
            else:
                thumb_image_path = None

            if yt_dl_format == "video":
                await bot.send_video(
                    chat_id=update.message.chat.id,
                    video=dl_path,
                    caption=f"**{custom_file_name}**",
                    supports_streaming=True,
                    height=720,
                    width=1280,
                    duration=response_json.get("duration", 0),
                    thumb=thumb_image_path,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_MSG, update.message, time.time()
                    )
                )
            elif yt_dl_format == "audio":
                await bot.send_audio(
                    chat_id=update.message.chat.id,
                    audio=dl_path,
                    caption=f"**{custom_file_name}**",
                    thumb=thumb_image_path,
                    duration=response_json.get("duration", 0),
                    performer=response_json.get("uploader", ""),
                    title=custom_file_name,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_MSG, update.message, time.time()
                    )
                )
            else:
                await bot.send_document(
                    chat_id=update.message.chat.id,
                    document=dl_path,
                    caption=f"**{custom_file_name}**",
                    thumb=thumb_image_path,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_MSG, update.message, time.time()
                    )
                )

            await update.message.delete()
            if thumb_image_path is not None and os.path.isfile(thumb_image_path):
                os.remove(thumb_image_path)
            os.remove(dl_path)
        else:
            await update.message.edit_text("❌ ᴇʀʀᴏʀ: ꜰɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ!")
    except Exception as e:
        logger.error(e)
        await bot.send_message(
            chat_id=update.message.chat.id,
            text=f"❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ:\n\n`{str(e)}`",
            reply_to_message_id=update.message.id
        )
