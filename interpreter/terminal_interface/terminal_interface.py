"""
The terminal interface is just a view. Just handles the very top layer.
If you were to build a frontend this would be a way to do it.
"""

try:
    import readline
except ImportError:
    pass

import os
import platform
import random
import re
import subprocess
import tempfile
import time

from ..core.utils.scan_code import scan_code
from ..core.utils.system_debug_info import system_info
from ..core.utils.truncate_output import truncate_output
from .components.code_block import CodeBlock
from .components.message_block import MessageBlock
from .magic_commands import handle_magic_command
from .utils.check_for_package import check_for_package
from .utils.cli_input import cli_input
from .utils.display_output import display_output
from .utils.find_image_path import find_image_path

# 將範例加入 readline 歷史紀錄
# Add examples to the readline history
examples = [
    "How many files are on my desktop?",
    "What time is it in Seattle?",
    "Make me a simple Pomodoro app.",
    "Open Chrome and go to YouTube.",
    "Can you set my system to light mode?",
]
random.shuffle(examples)
try:
    for example in examples:
        readline.add_history(example)
except:
    # 若沒有 readline，沒關係
    # If they don't have readline, that's fine
    pass


def terminal_interface(interpreter, message):
    # auto_run 和 offline 模式（這……這樣不太對）不顯示訊息。
    # 將來或許值得將此抽象為類似 "debug_cli" 的東西。
    # 若 len(interpreter.messages) == 1，他們可能使用了進階的 "i {command}" 輸入方式，所以不應顯示訊息。
    # Auto run and offline (this.. this isn't right) don't display messages.
    # Probably worth abstracting this to something like "debug_cli" at some point.
    # If (len(interpreter.messages) == 1), they probably used the advanced "i {command}" entry, so no message should be displayed.
    if (
        not interpreter.auto_run
        and not interpreter.offline
        and not (len(interpreter.messages) == 1)
    ):
        interpreter_intro_message = [
            "**Open Interpreter** will require approval before running code."
        ]

        if interpreter.safe_mode == "ask" or interpreter.safe_mode == "auto":
            if not check_for_package("semgrep"):
                interpreter_intro_message.append(
                    f"**Safe Mode**: {interpreter.safe_mode}\n\n>Note: **Safe Mode** requires `semgrep` (`pip install semgrep`)"
                )
        else:
            interpreter_intro_message.append("Use `interpreter -y` to bypass this.")

        if (
            not interpreter.plain_text_display
        # 這是 standard in 模式的代理／啟發，目前沒有被追蹤（但也許應該要）
        ):  # A proxy/heuristic for standard in mode, which isn't tracked (but prob should be)
            interpreter_intro_message.append("Press `CTRL-C` to exit.")

        interpreter.display_message("\n\n".join(interpreter_intro_message) + "\n")

    if message:
        interactive = False
    else:
        interactive = True

    active_block = None
    voice_subprocess = None

    while True:
        if interactive:
            if (
                len(interpreter.messages) == 1
                and interpreter.messages[-1]["role"] == "user"
                and interpreter.messages[-1]["type"] == "message"
            ):
                # 使用者已傳入訊息，可能是透過 "i {command}" 輸入的！
                # They passed in a message already, probably via "i {command}"!
                message = interpreter.messages[-1]["content"]
                interpreter.messages = interpreter.messages[:-1]
            else:
                ### 這是 Open Interpreter 的主要輸入介面。
                ### This is the primary input for Open Interpreter.
                try:
                    message = (
                        cli_input("> ").strip()
                        if interpreter.multi_line
                        else input("> ").strip()
                    )
                except (KeyboardInterrupt, EOFError):
                    # 將空行上的 Ctrl-D 與 Ctrl-C 同等對待，優雅地退出
                    # Treat Ctrl-D on an empty line the same as Ctrl-C by exiting gracefully
                    interpreter.display_message("\n\n`Exiting...`")
                    raise KeyboardInterrupt

            try:
                # 讓使用者可以按上方向鍵查看過去的訊息
                # This lets users hit the up arrow key for past messages
                readline.add_history(message)
            except:
                # 若使用者沒有 readline（Windows 上可能如此），沒關係
                # If the user doesn't have readline (may be the case on windows), that's fine
                pass

        if isinstance(message, str):
            # 這是供 CLI 模式的終端介面使用的 — 訊息為字串。
            # 若使用者在 Python 套件中、display=True 且傳入了訊息陣列（例如），則此處不會觸發。
            # This is for the terminal interface being used as a CLI — messages are strings.
            # This won't fire if they're in the python package, display=True, and they passed in an array of messages (for example).

            if message == "":
                # 當使用者直接按 Enter 而不輸入任何內容時，忽略空訊息
                # Ignore empty messages when user presses enter without typing anything
                continue

            if message.startswith("%") and interactive:
                handle_magic_command(interpreter, message)
                continue

            # 很多使用者會這樣做
            # Many users do this
            if message.strip() == "interpreter --local":
                print("Please exit this conversation, then run `interpreter --local`.")
                continue
            if message.strip() == "pip install --upgrade open-interpreter":
                print(
                    "Please exit this conversation, then run `pip install --upgrade open-interpreter`."
                )
                continue

            if (
                interpreter.llm.supports_vision
                or interpreter.llm.vision_renderer != None
            ):
                # 輸入是圖片路徑嗎？例如直接拖曳圖片到終端機？
                # Is the input a path to an image? Like they just dragged it into the terminal?
                image_path = find_image_path(message)

                ## 若找到圖片，將其加入訊息
                ## If we found an image, add it to the message
                if image_path:
                    # 將文字加入 interpreter 的訊息歷史
                    # Add the text interpreter's message history
                    interpreter.messages.append(
                        {
                            "role": "user",
                            "type": "message",
                            "content": message,
                        }
                    )

                    # 稍後將圖片傳入 interpreter
                    # Pass in the image to interpreter in a moment
                    message = {
                        "role": "user",
                        "type": "image",
                        "format": "path",
                        "content": image_path,
                    }

        try:
            for chunk in interpreter.chat(message, display=False, stream=True):
                yield chunk

                # 這是給你看的嗎？
                # Is this for thine eyes?
                if "recipient" in chunk and chunk["recipient"] != "user":
                    continue

                if interpreter.verbose:
                    print("Chunk in `terminal_interface`:", chunk)

                # 遵守 PyAutoGUI 在 OS 模式下的安全機制
                # 使用者可以將滑鼠移到角落以關閉
                # Comply with PyAutoGUI fail-safe for OS mode
                # so people can turn it off by moving their mouse to a corner
                if interpreter.os:
                    if (
                        chunk.get("format") == "output"
                        and "failsafeexception" in chunk["content"].lower()
                    ):
                        print("Fail-safe triggered (mouse in one of the four corners).")
                        break

                if chunk["type"] == "review" and chunk.get("content"):
                    # 專用模型可以發出程式碼審查。
                    # Specialized models can emit a code review.
                    print(chunk.get("content"), end="", flush=True)

                # 執行通知
                # Execution notice
                if chunk["type"] == "confirmation":
                    if not interpreter.auto_run:
                        # OI 即將執行程式碼，使用者想要批准此操作

                        # 結束目前的程式碼區塊，以便在其下方執行 input()
                        # End the active code block so you can run input() below it
                        if active_block and not interpreter.plain_text_display:
                            active_block.refresh(cursor=False)
                            active_block.end()
                            active_block = None

                        code_to_run = chunk["content"]
                        language = code_to_run["format"]
                        code = code_to_run["content"]

                        should_scan_code = False

                        if not interpreter.safe_mode == "off":
                            if interpreter.safe_mode == "auto":
                                should_scan_code = True
                            elif interpreter.safe_mode == "ask":
                                response = input(
                                    "  Would you like to scan this code? (y/n)\n\n  "
                                )
                                # 美觀選擇（輸出空行）
                                print("")  # <- Aesthetic choice

                                if response.strip().lower() == "y":
                                    should_scan_code = True

                        if should_scan_code:
                            scan_code(code, language, interpreter)

                        if interpreter.plain_text_display:
                            response = input(
                                "Would you like to run this code? (y/n)\n\n"
                            )
                        else:
                            response = input(
                                "  Would you like to run this code? (y/n)\n\n  "
                            )
                        # 美觀選擇（輸出空行）
                        print("")  # <- Aesthetic choice

                        if response.strip().lower() == "y":
                            # 建立一個新的、相同的區塊來實際執行程式碼
                            # 方便的是，chunk 包含了執行所需的一切：
                            # Create a new, identical block where the code will actually be run
                            # Conveniently, the chunk includes everything we need to do this:
                            active_block = CodeBlock(interpreter)
                            # 美觀選擇
                            active_block.margin_top = False  # <- Aesthetic choice
                            active_block.language = language
                            active_block.code = code
                        elif response.strip().lower() == "e":
                            # 編輯
                            # Edit

                            # 建立暫存檔
                            # Create a temporary file
                            with tempfile.NamedTemporaryFile(
                                suffix=".tmp", delete=False
                            ) as tf:
                                tf.write(code.encode())
                                tf.flush()

                            # 以預設編輯器開啟暫存檔
                            # Open the temporary file with the default editor
                            subprocess.call([os.environ.get("EDITOR", "vim"), tf.name])

                            # 讀取修改後的程式碼
                            # Read the modified code
                            with open(tf.name, "r") as tf:
                                code = tf.read()

                            # 傳入程式碼
                            interpreter.messages[-1]["content"] = code  # Give it code

                            # 刪除暫存檔
                            # Delete the temporary file
                            os.unlink(tf.name)
                            active_block = CodeBlock()
                            # 美觀選擇
                            active_block.margin_top = False  # <- Aesthetic choice
                            active_block.language = language
                            active_block.code = code
                        else:
                            # 使用者拒絕執行程式碼。
                            # User declined to run code.
                            interpreter.messages.append(
                                {
                                    "role": "user",
                                    "type": "message",
                                    "content": "I have declined to run this code.",
                                }
                            )
                            break

                # 純文字模式
                # Plain text mode
                if interpreter.plain_text_display:
                    if "start" in chunk or "end" in chunk:
                        print("")
                    if chunk["type"] in ["code", "console"] and "format" in chunk:
                        if "start" in chunk:
                            print("```" + chunk["format"], flush=True)
                        if "end" in chunk:
                            print("```", flush=True)
                    if chunk.get("format") != "active_line":
                        print(chunk.get("content", ""), end="", flush=True)
                    continue

                if "end" in chunk and active_block:
                    active_block.refresh(cursor=False)

                    if chunk["type"] in [
                        "message",
                        "console",
                    # 不在程式碼結束時停止 — 程式碼 + 主控台輸出實際上是同一個區塊
                    ]:  # We don't stop on code's end — code + console output are actually one block.
                        active_block.end()
                        active_block = None

                # 助理訊息區塊
                # Assistant message blocks
                if chunk["type"] == "message":
                    if "start" in chunk:
                        active_block = MessageBlock()
                        render_cursor = True

                    if "content" in chunk:
                        active_block.message += chunk["content"]

                    if "end" in chunk and interpreter.os:
                        last_message = interpreter.messages[-1]["content"]

                        # 移除 markdown 列表及其上方的行
                        # Remove markdown lists and the line above markdown lists
                        lines = last_message.split("\n")
                        i = 0
                        while i < len(lines):
                            # 匹配以連字符、星號或數字開頭的 markdown 列表
                            # Match markdown lists starting with hyphen, asterisk or number
                            if re.match(r"^\s*([-*]|\d+\.)\s", lines[i]):
                                del lines[i]
                                if i > 0:
                                    del lines[i - 1]
                                    i -= 1
                            else:
                                i += 1
                        message = "\n".join(lines)
                        # 將換行替換為空格，跳脫雙引號和反斜線
                        # Replace newlines with spaces, escape double quotes and backslashes
                        sanitized_message = (
                            message.replace("\\", "\\\\")
                            .replace("\n", " ")
                            .replace('"', '\\"')
                        )

                        # 在 OS 模式下顯示通知
                        # Display notification in OS mode
                        interpreter.computer.os.notify(sanitized_message)

                        # 大聲朗讀訊息
                        # Speak message aloud
                        if platform.system() == "Darwin" and interpreter.speak_messages:
                            if voice_subprocess:
                                voice_subprocess.terminate()
                            voice_subprocess = subprocess.Popen(
                                [
                                    "osascript",
                                    "-e",
                                    f'say "{sanitized_message}" using "Fred"',
                                ]
                            )
                        else:
                            pass
                            # 使用者不在 Mac 上，所以我們無法這樣做。
                            # 當他們第一次設定時，你應該告訴他們這件事。
                            # 或者使用通用的 TTS 函式庫。
                            # User isn't on a Mac, so we can't do this. You should tell them something about that when they first set this up.
                            # Or use a universal TTS library.

                # 助理程式碼區塊
                # Assistant code blocks
                elif chunk["role"] == "assistant" and chunk["type"] == "code":
                    if "start" in chunk:
                        active_block = CodeBlock()
                        active_block.language = chunk["format"]
                        render_cursor = True

                    if "content" in chunk:
                        active_block.code += chunk["content"]

                # 電腦可以向使用者顯示視覺型別，
                # 這有時會產生更多電腦輸出（例如 HTML 錯誤，最終）
                # Computer can display visual types to user,
                # Which sometimes creates more computer output (e.g. HTML errors, eventually)
                if (
                    chunk["role"] == "computer"
                    and "content" in chunk
                    and (
                        chunk["type"] == "image"
                        or ("format" in chunk and chunk["format"] == "html")
                        or ("format" in chunk and chunk["format"] == "javascript")
                    )
                ):
                    if (interpreter.os == True) and (interpreter.verbose == False):
                        # 在 OS 控制模式下我們不向使用者顯示內容，因為我們使用視覺大量與 LLM 溝通螢幕畫面。
                        # 但若 verbose 為 True，我們確實會顯示！
                        # We don't display things to the user in OS control mode, since we use vision to communicate the screen to the LLM so much.
                        # But if verbose is true, we do display it!
                        continue

                    assistant_code_blocks = [
                        m
                        for m in interpreter.messages
                        if m.get("role") == "assistant" and m.get("type") == "code"
                    ]
                    if assistant_code_blocks:
                        code = assistant_code_blocks[-1].get("content")
                        if any(
                            text in code
                            for text in [
                                "computer.display.view",
                                "computer.display.screenshot",
                                "computer.view",
                                "computer.screenshot",
                            ]
                        ):
                            # 若程式碼最後一行是 computer.view 指令，則不顯示。
                            # LLM 會看到它，使用者不需要看。
                            # If the last line of the code is a computer.view command, don't display it.
                            # The LLM is going to see it, the user doesn't need to.
                            continue

                    # 顯示並將額外輸出回傳給 LLM
                    # Display and give extra output back to the LLM

                    # 我們將直接把它加入訊息，而不在此更改 `recipient`。
                    # 請注意，以此方式進行，若使用者查看對話歷史，此訊息會出現，
                    # 因為我們沒有在此區塊中加入 "recipient: assistant"。
                    # 但我認為這是個很好的簡單解決方案。
                    # 未來，一旦我們確定相鄰的 type:console 區塊會被正常渲染為文字給純文字 LLM，
                    # 以及我們在此用 "recipient: assistant" 建立新區塊不會對該區塊加入新主控台輸出（從而對使用者隱藏），
                    # 我們可能想要更改它。
                    # We're going to just add it to the messages directly, not changing `recipient` here.
                    # Mind you, the way we're doing this, this would make it appear to the user if they look at their conversation history,
                    # because we're not adding "recipient: assistant" to this block. But this is a good simple solution IMO.
                    # we just might want to change it in the future, once we're sure that a bunch of adjacent type:console blocks will be rendered normally to text-only LLMs
                    # and that if we made a new block here with "recipient: assistant" it wouldn't add new console outputs to that block (thus hiding them from the user)
                    extra_computer_output = display_output(chunk)

                    if (
                        interpreter.messages[-1].get("format") != "output"
                        or interpreter.messages[-1]["role"] != "computer"
                        or interpreter.messages[-1]["type"] != "console"
                    ):
                        # 若最後一則訊息不是主控台輸出，建立新區塊
                        # If the last message isn't a console output, make a new block
                        interpreter.messages.append(
                            {
                                "role": "computer",
                                "type": "console",
                                "format": "output",
                                "content": extra_computer_output,
                            }
                        )
                    else:
                        # 若最後一則訊息是主控台輸出，直接將額外輸出追加至其中
                        # If the last message is a console output, simply append the extra output to it
                        interpreter.messages[-1]["content"] += (
                            "\n" + extra_computer_output
                        )
                        interpreter.messages[-1]["content"] = interpreter.messages[-1][
                            "content"
                        ].strip()

                # 主控台
                # Console
                if chunk["type"] == "console":
                    render_cursor = False
                    if "format" in chunk and chunk["format"] == "output":
                        active_block.output += "\n" + chunk["content"]
                        # 美觀選擇
                        active_block.output = (
                            active_block.output.strip()
                        )  # ^ Aesthetic choice

                        # 截斷輸出
                        # Truncate output
                        active_block.output = truncate_output(
                            active_block.output,
                            interpreter.max_output,
                            add_scrollbars=False,
                        # 注意這裡不加入「捲軸」行，我認為這樣沒問題
                        )  # ^ Notice that this doesn't add the "scrollbars" line, which I think is fine
                    if "format" in chunk and chunk["format"] == "active_line":
                        active_block.active_line = chunk["content"]

                        # 若在 OS 模式下，顯示動作通知
                        # Display action notifications if we're in OS mode
                        if interpreter.os and active_block.active_line != None:
                            action = ""

                            code_lines = active_block.code.split("\n")
                            if active_block.active_line < len(code_lines):
                                action = code_lines[active_block.active_line].strip()

                            if action.startswith("computer"):
                                description = None

                                # 從動作中提取參數
                                # Extract arguments from the action
                                start_index = action.find("(")
                                end_index = action.rfind(")")
                                if start_index != -1 and end_index != -1:
                                    # 若兩者都找到了
                                    # (If we found both)
                                    arguments = action[start_index + 1 : end_index]
                                else:
                                    arguments = None

                                # 注意：不要把你在螢幕上點擊的文字放進去
                                # （除非我們能在截圖之後再這樣做）
                                # 否則它會嘗試點擊此通知！
                                # NOTE: Do not put the text you're clicking on screen
                                # (unless we figure out how to do this AFTER taking the screenshot)
                                # otherwise it will try to click this notification!

                                if any(
                                    action.startswith(text)
                                    for text in [
                                        "computer.screenshot",
                                        "computer.display.screenshot",
                                        "computer.display.view",
                                        "computer.view",
                                    ]
                                ):
                                    description = "Viewing screen..."
                                elif action == "computer.mouse.click()":
                                    description = "Clicking..."
                                elif action.startswith("computer.mouse.click("):
                                    if "icon=" in arguments:
                                        text_or_icon = "icon"
                                    else:
                                        text_or_icon = "text"
                                    description = f"Clicking {text_or_icon}..."
                                elif action.startswith("computer.mouse.move("):
                                    if "icon=" in arguments:
                                        text_or_icon = "icon"
                                    else:
                                        text_or_icon = "text"
                                    if (
                                        "click" in active_block.code
                                    # 這可以做得更好
                                    ):  # This could be better
                                        description = f"Clicking {text_or_icon}..."
                                    else:
                                        description = f"Mousing over {text_or_icon}..."
                                elif action.startswith("computer.keyboard.write("):
                                    description = f"Typing {arguments}."
                                elif action.startswith("computer.keyboard.hotkey("):
                                    description = f"Pressing {arguments}."
                                elif action.startswith("computer.keyboard.press("):
                                    description = f"Pressing {arguments}."
                                elif action == "computer.os.get_selected_text()":
                                    description = f"Getting selected text."

                                if description:
                                    interpreter.computer.os.notify(description)

                    if "start" in chunk:
                        # 若之前推出了 HTML 區塊（這會關閉我們的程式碼區塊），我們需要建立新的程式碼區塊。
                        # We need to make a code block if we pushed out an HTML block first, which would have closed our code block.
                        if not isinstance(active_block, CodeBlock):
                            if active_block:
                                active_block.end()
                            active_block = CodeBlock()

                if active_block:
                    active_block.refresh(cursor=render_cursor)

            # （有時 — 例如他們快速按 CTRL-C — active_block 在這裡仍然是 None）
            # (Sometimes -- like if they CTRL-C quickly -- active_block is still None here)
            if "active_block" in locals():
                if active_block:
                    active_block.end()
                    active_block = None
                    time.sleep(0.1)

            if not interactive:
                # 不循環
                # Don't loop
                break

        except KeyboardInterrupt:
            # 優雅退出
            # Exit gracefully
            if "active_block" in locals() and active_block:
                active_block.end()
                active_block = None

            if interactive:
                # （這會取消 LLM，回到互動的 "> " 輸入）
                # (this cancels LLM, returns to the interactive "> " input)
                continue
            else:
                break
        except:
            if interpreter.debug:
                system_info(interpreter)
            raise
