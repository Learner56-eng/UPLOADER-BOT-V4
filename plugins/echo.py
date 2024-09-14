import asyncio
import time
import math
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import enums
from plugins.script import Translation

# Progress bar function
async def progress_for_pyrogram(current, total, ud_type, message, start, bar_width=20, status=""):
    now = time.time()
    diff = now - start
    percentage = current * 100 / total
    speed = current / diff
    elapsed_time = round(diff) * 1000
    time_to_completion = round((total - current) / speed) * 1000
    estimated_total_time = elapsed_time + time_to_completion

    elapsed_time = TimeFormatter(milliseconds=elapsed_time)
    estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

    progress = "[{0}{1}] \n".format(
        ''.join(["█" for _ in range(math.floor(percentage / (100 / bar_width)))]),
        ''.join(["░" for _ in range(bar_width - math.floor(percentage / (100 / bar_width)))])
    )

    tmp = progress + Translation.PROGRESS.format(
        round(percentage, 2),
        humanbytes(current),
        humanbytes(total),
        humanbytes(speed),
        estimated_total_time if estimated_total_time != '' else "0 s"
    )

    status_message = f"**{ud_type}**\n\n{status}\n\n{tmp}"

    try:
        await message.edit(
            text=status_message,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [
                    [ 
                        InlineKeyboardButton('⛔️ Cancel', callback_data='close')
                    ]
                ]
            )
        )
    except Exception as e:
        print(f"Error updating progress: {e}")

def humanbytes(size):
    if not size:
        return ""
    power = 2 ** 10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
          ((str(hours) + "h, ") if hours else "") + \
          ((str(minutes) + "m, ") if minutes else "") + \
          ((str(seconds) + "s, ") if seconds else "") + \
          ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2]

# Example usage in the file download process
@Client.on_message(filters.private & filters.regex(pattern=".*http.*"))
async def handle_download(bot, update):
    # Your existing logic for parsing the URL and preparing the download command
    url = update.text.strip()
    file_name = "example.mp4"  # Replace with your actual file name

    # Sending initial message with progress bar
    start_time = time.time()
    progress_message = await bot.send_message(
        chat_id=update.chat.id,
        text="Starting download...",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [ 
                    InlineKeyboardButton('⛔️ Cancel', callback_data='close')
                ]
            ]
        )
    )

    # Replace this block with your actual file download logic
    total_size = 1000000  # Example total size in bytes
    downloaded_size = 0

    # Simulate downloading file
    while downloaded_size < total_size:
        # Simulate download progress
        downloaded_size += 10000
        await asyncio.sleep(0.5)  # Simulate network delay

        # Update progress bar
        await progress_for_pyrogram(downloaded_size, total_size, "Downloading", progress_message, start_time)

    # Finalize message when download completes
    await progress_message.edit(
        text="Download completed!",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [ 
                    InlineKeyboardButton('✅ Done', callback_data='done')
                ]
            ]
        )
    )
