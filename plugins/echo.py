import logging
import os
import requests
import json
import asyncio
import math
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from plugins.config import Config
from plugins.functions.forcesub import handle_force_subscribe
from plugins.functions.display_progress import humanbytes
from plugins.functions.help_uploadbot import DownLoadFile
from plugins.functions.display_progress import progress_for_pyrogram, humanbytes, TimeFormatter
from plugins.functions.ran_text import random_char
from plugins.database.add import add_user_to_database
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
            logger.error(error)
    if not update.from_user:
        return await update.reply_text("I don't know about you, sorry :(")
    await add_user_to_database(bot, update)

    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, update)
        if fsub == 400:
            return

    url = update.text
    youtube_dl_username = None
    youtube_dl_password = None
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
        url = url.strip() if url else None
        file_name = file_name.strip() if file_name else None
        youtube_dl_username = youtube_dl_username.strip() if youtube_dl_username else None
        youtube_dl_password = youtube_dl_password.strip() if youtube_dl_password else None
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
    
    if Config.HTTP_PROXY:
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
    if youtube_dl_username:
        command_to_exec.append("--username")
        command_to_exec.append(youtube_dl_username)
    if youtube_dl_password:
        command_to_exec.append("--password")
        command_to_exec.append(youtube_dl_password)
    logger.info(command_to_exec)
    
    chk = await bot.send_message(
        chat_id=update.chat.id,
        text='Processing your link ⌛',
        disable_web_page_preview=True,
        reply_to_message_id=update.id,
        parse_mode=enums.ParseMode.HTML
    )
    process = await asyncio.create_subprocess_exec(
        *command_to_exec,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    logger.info(e_response)
    t_response = stdout.decode().strip()

    if e_response and "nonnumeric port" not in e_response:
        error_message = e_response.replace(
            "please report this issue on https://yt-dl.org/bug . Make sure you are using the latest version; see https://yt-dl.org/update on how to update. Be sure to call youtube-dl with the --verbose flag and include its complete output.", ""
        )
        if "This video is only available for registered users." in error_message:
            error_message += Translation.SET_CUSTOM_USERNAME_PASSWORD
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.NO_VOID_FORMAT_FOUND.format(str(error_message)),
            reply_to_message_id=update.id,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        return

    if t_response:
        response_json = json.loads(t_response)
        randem = random_char(5)
        save_ytdl_json_path = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}{randem}.json")
        with open(save_ytdl_json_path, "w", encoding="utf8") as outfile:
            json.dump(response_json, outfile, ensure_ascii=False)
        
        inline_keyboard = []
        duration = response_json.get("duration")
        if "formats" in response_json:
            for formats in response_json["formats"]:
                format_id = formats.get("format_id")
                format_string = formats.get("format_note") or formats.get("format")
                format_ext = formats.get("ext")
                approx_file_size = humanbytes(formats.get("filesize", 0))
                cb_string_video = f"video|{format_id}|{format_ext}|{randem}"
                ikeyboard = [
                    InlineKeyboardButton(
                        f"🎬 {format_string or ''} {format_ext} {approx_file_size}",
                        callback_data=cb_string_video.encode("UTF-8")
                    )
                ]
                inline_keyboard.append(ikeyboard)
            
            if duration:
                cb_string_64 = f"audio|64k|mp3|{randem}"
                cb_string_128 = f"audio|128k|mp3|{randem}"
                cb_string = f"audio|320k|mp3|{randem}"
                inline_keyboard.append([
                    InlineKeyboardButton(
                        f"🎵 MP3 (64kbps)",
                        callback_data=cb_string_64.encode("UTF-8")
                    ),
                    InlineKeyboardButton(
                        f"🎵 MP3 (128kbps)",
                        callback_data=cb_string_128.encode("UTF-8")
                    )
                ])
                inline_keyboard.append([
                    InlineKeyboardButton(
                        f"🎵 MP3 (320kbps)",
                        callback_data=cb_string.encode("UTF-8")
                    )
                ])
                inline_keyboard.append([
                    InlineKeyboardButton(
                        "⛔️ Close",
                        callback_data='close'
                    )
                ])

        else:
            format_id = response_json["format_id"]
            format_ext = response_json["ext"]
            cb_string_video = f"video|{format_id}|{format_ext}|{randem}"
            inline_keyboard.append([
                InlineKeyboardButton(
                    "🎬 Media",
                    callback_data=cb_string_video.encode("UTF-8")
                )
            ])

        reply_markup = InlineKeyboardMarkup(inline_keyboard)
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.FORMAT_SELECTION.format(Thumbnail) + "\n" + Translation.SET_CUSTOM_USERNAME_PASSWORD,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=update.id
        )
    else:
        inline_keyboard = [
            [InlineKeyboardButton(
                "🎬 Media",
                callback_data="file=NONE=NONE".encode("UTF-8")
            )]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.FORMAT_SELECTION,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=update.id
        )

@Client.on_callback_query()
async def handle_callback_query(bot, query):
    query_data = query.data.decode("UTF-8")
    query_parts = query_data.split("|")
    
    if len(query_parts) == 4:
        file_type, format_id, file_ext, randem = query_parts
        file_name = f"{randem}.{file_ext}"
        download_url = f"{Config.BASE_URL}/download/{file_type}/{format_id}/{file_name}"

        progress_msg = await bot.send_message(
            chat_id=query.message.chat.id,
            text="Starting download...",
            parse_mode=enums.ParseMode.HTML
        )

        # Download file
        file_response = requests.get(download_url, stream=True)
        file_size = int(file_response.headers.get('content-length', 0))
        if not file_size:
            file_size = 0

        # Progress bar setup
        def get_progress_bar(progress):
            completed = math.floor(progress * 10)
            remaining = 10 - completed
            return f"█" * completed + f"▒" * remaining

        def update_progress_message(current_size):
            percent_complete = current_size / file_size if file_size else 0
            progress_bar = get_progress_bar(percent_complete * 10)
            percent_complete = math.floor(percent_complete * 100)
            return f"Download Progress: {percent_complete}%\n{progress_bar}"

        # Write the file in chunks and update progress
        temp_file_path = os.path.join(Config.DOWNLOAD_LOCATION, f"temp_{randem}.{file_ext}")
        with open(temp_file_path, 'wb') as file:
            current_size = 0
            for chunk in file_response.iter_content(chunk_size=8192):
                file.write(chunk)
                current_size += len(chunk)
                if file_size > 0 and current_size / file_size * 10 % 1 == 0:
                    await progress_msg.edit_text(update_progress_message(current_size))

        await progress_msg.edit_text("Download complete!")

        # Upload file
        await progress_msg.edit_text("Starting upload...", parse_mode=enums.ParseMode.HTML)

        # Here you would add the logic for uploading the file
        # This example assumes you're using Pyrogram to upload the file
        uploaded_file_msg = await bot.send_document(
            chat_id=query.message.chat.id,
            document=temp_file_path,
            caption="Here is your file!",
            parse_mode=enums.ParseMode.HTML
        )

        # Cleanup
        os.remove(temp_file_path)
        await progress_msg.edit_text("Upload complete!")

        await bot.answer_callback_query(
            callback_query_id=query.id,
            text="Process complete!",
            show_alert=False
        )
    else:
        await bot.answer_callback_query(
            callback_query_id=query.id,
            text="Invalid callback data!",
            show_alert=True
        )

# Ensure to run the bot

