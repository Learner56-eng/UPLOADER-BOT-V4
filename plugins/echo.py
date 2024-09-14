import os
import json
import asyncio
import requests
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import InputMediaVideo, InputMediaAudio
from config import Config
from utils import progress_for_pyrogram, Translation
import time
import logging

logger = logging.getLogger(__name__)

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
            # Download and process thumbnail if video
            if "thumbnail" in response_json and format_ext in ["mp4", "mkv"]:
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

            # Determine file type based on extension
            if format_ext in ["mp4", "mkv"]:
                # Treat as video
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
            elif format_ext in ["mp3", "m4b"]:
                # Treat as audio
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
                # Treat as document for other file types
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
            # Clean up downloaded files
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
