import json
import os
import re
import time
import traceback

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm

from ..terminal_interface.utils.display_markdown_message import display_markdown_message
from .render_message import render_message


def respond(interpreter):
    """
    主對話迴圈：產生 chunk，直到不需要再執行程式或不再有後續輸出為止。
    """

    last_unsupported_code = ""
    insert_loop_message = False

    while True:
        ## 組裝 SYSTEM MESSAGE ##

        system_message = interpreter.system_message

        # 各「語言執行器」若自帶 system_message 則一併附加
        for language in interpreter.computer.terminal.languages:
            if hasattr(language, "system_message"):
                system_message += "\n\n" + language.system_message

        if interpreter.custom_instructions:
            system_message += "\n\n" + interpreter.custom_instructions

        if interpreter.computer.import_computer_api:
            if interpreter.computer.system_message not in system_message:
                system_message = (
                    system_message + "\n\n" + interpreter.computer.system_message
                )

        # 曾考慮 sync 整包 messages 到 computer，因效能已停用
        # if interpreter.sync_computer:
        #     output = interpreter.computer.run(
        #         "python", f"messages={interpreter.messages}"
        #     )

        ## render_message（可含 {{ }} 動態段）↓
        rendered_system_message = render_message(interpreter, system_message)
        ## render_message ↑

        rendered_system_message = {
            "role": "system",
            "type": "message",
            "content": rendered_system_message,
        }

        messages_for_llm = interpreter.messages.copy()
        messages_for_llm = [rendered_system_message] + messages_for_llm

        if insert_loop_message:
            messages_for_llm.append(
                {
                    "role": "user",
                    "type": "message",
                    "content": loop_message,
                }
            )
            yield {"role": "assistant", "type": "message", "content": "\n\n"}
            insert_loop_message = False

        ### 呼叫 LLM ###

        assert (
            len(interpreter.messages) > 0
        ), "User message was not passed in. You need to pass in at least one message."

        if (
            interpreter.messages[-1]["type"] != "code"
        ):  # 最後一則為 code 時改走下方執行分支
            try:
                for chunk in interpreter.llm.run(messages_for_llm):
                    yield {"role": "assistant", **chunk}

            except litellm.exceptions.BudgetExceededError:
                interpreter.display_message(
                    f"""> Max budget exceeded

                    **Session spend:** ${litellm._current_cost}
                    **Max budget:** ${interpreter.max_budget}

                    Press CTRL-C then run `interpreter --max_budget [higher USD amount]` to proceed.
                """
                )
                break

            except Exception as e:
                error_message = str(e).lower()
                if (
                    interpreter.offline == False
                    and ("auth" in error_message or
                         "api key" in error_message)
                ):
                    output = traceback.format_exc()
                    raise Exception(
                        f"{output}\n\nThere might be an issue with your API key(s).\n\nTo reset your API key (we'll use OPENAI_API_KEY for this example, but you may need to reset your ANTHROPIC_API_KEY, HUGGINGFACE_API_KEY, etc):\n        Mac/Linux: 'export OPENAI_API_KEY=your-key-here'. Update your ~/.zshrc on MacOS or ~/.bashrc on Linux with the new key if it has already been persisted there.,\n        Windows: 'setx OPENAI_API_KEY your-key-here' then restart terminal.\n\n"
                    )
                elif (
                    isinstance(e, litellm.exceptions.RateLimitError)
                    and ("exceeded" in str(e).lower() or
                         "insufficient_quota" in str(e).lower())
                ):
                    display_markdown_message(
                        f""" > You ran out of current quota for OpenAI's API, please check your plan and billing details. You can either wait for the quota to reset or upgrade your plan.

                        To check your current usage and billing details, visit the [OpenAI billing page](https://platform.openai.com/settings/organization/billing/overview).

                        You can also use `interpreter --max_budget [higher USD amount]` to set a budget for your sessions.
                        """
                    )

                elif (
                    interpreter.offline == False and "not have access" in str(e).lower()
                ):
                    if (
                        "invalid model" in error_message
                        or "model does not exist" in error_message
                    ):
                        provider_message = f"\n\nThe model '{interpreter.llm.model}' does not exist or is invalid. Please check the model name and try again.\n\nWould you like to try Open Interpreter's hosted `i` model instead? (y/n)\n\n  "
                    elif "groq" in error_message:
                        provider_message = f"\n\nYou do not have access to {interpreter.llm.model}. Please check with Groq for more details.\n\nWould you like to try Open Interpreter's hosted `i` model instead? (y/n)\n\n  "
                    else:
                        provider_message = f"\n\nYou do not have access to {interpreter.llm.model}. If you are using an OpenAI model, you may need to add a payment method and purchase credits for the OpenAI API billing page (this is different from ChatGPT Plus).\n\nhttps://platform.openai.com/account/billing/overview\n\nWould you like to try Open Interpreter's hosted `i` model instead? (y/n)\n\n"

                    print(provider_message)

                    response = input()
                    print("")

                    if response.strip().lower() == "y":
                        interpreter.llm.model = "i"
                        interpreter.display_message(f"> Model set to `i`")
                        interpreter.display_message(
                            "***Note:*** *Conversations with this model will be used to train our open-source model.*\n"
                        )

                    else:
                        raise
                elif interpreter.offline and not interpreter.os:
                    raise
                else:
                    raise

        ### 執行最後一則 code（若為 code 類型）###

        if interpreter.messages[-1]["type"] == "code":
            if interpreter.verbose:
                print("Running code:", interpreter.messages[-1])

            try:
                language = interpreter.messages[-1]["format"].lower().strip()
                code = interpreter.messages[-1]["content"]

                if code.startswith("`\n"):
                    code = code[2:].strip()
                    if interpreter.verbose:
                        print("Removing `\n")
                    # 讓 LLM 可以看到修正後的程式碼
                    interpreter.messages[-1]["content"] = code  # 供下一輪 LLM 讀取修正結果

                # 模型常見幻覺格式 functions.execute(...)
                if code.startswith("functions.execute("):
                    edited_code = code.replace("functions.execute(", "").rstrip(")")
                    try:
                        code_dict = json.loads(edited_code)
                        language = code_dict.get("language", language)
                        code = code_dict.get("code", code)
                        # 讓 LLM 可以看到修正後的程式碼
                        interpreter.messages[-1][
                            "content"
                        ] = code  # 供下一輪 LLM 讀取修正結果
                        # 讓 LLM 可以看到修正後的語言
                        interpreter.messages[-1][
                            "format"
                        ] = language  # 供下一輪 LLM 讀取修正結果
                    except:
                        pass

                # print(code)
                # print("---")
                # time.sleep(2)

                if code.strip().endswith("executeexecute"):
                    code = code.replace("executeexecute", "")
                    try:
                        # 讓 LLM 可以看到修正後的程式碼
                        interpreter.messages[-1][
                            "content"
                        ] = code  # 供下一輪 LLM 讀取修正結果
                    except:
                        pass

                if code.replace("\n", "").replace(" ", "").startswith('{"language":'):
                    try:
                        code_dict = json.loads(code)
                        if set(code_dict.keys()) == {"language", "code"}:
                            language = code_dict["language"]
                            code = code_dict["code"]
                            # 讓 LLM 可以看到修正後的程式碼
                            interpreter.messages[-1][
                                "content"
                            ] = code  # 供下一輪 LLM 讀取修正結果
                            # 讓 LLM 可以看到修正後的語言
                            interpreter.messages[-1][
                                "format"
                            ] = language  # 供下一輪 LLM 讀取修正結果
                    except:
                        pass

                if code.replace("\n", "").replace(" ", "").startswith("{language:"):
                    try:
                        code = code.replace("language: ", '"language": ').replace(
                            "code: ", '"code": '
                        )
                        code_dict = json.loads(code)
                        if set(code_dict.keys()) == {"language", "code"}:
                            language = code_dict["language"]
                            code = code_dict["code"]
                            # 讓 LLM 可以看到修正後的程式碼
                            interpreter.messages[-1][
                                "content"
                            ] = code  # 供下一輪 LLM 讀取修正結果
                            # 讓 LLM 可以看到修正後的語言
                            interpreter.messages[-1][
                                "format"
                            ] = language  # 供下一輪 LLM 讀取修正結果
                    except:
                        pass

                if (
                    language == "text"
                    or language == "markdown"
                    or language == "plaintext"
                ):
                    # 模型有時以 text/markdown 當筆記；暫時允許。未來可不視為可執行 code。
                    real_content = interpreter.messages[-1]["content"]
                    interpreter.messages[-1] = {
                        "role": "assistant",
                        "type": "message",
                        "content": f"```\n{real_content}\n```",
                    }
                    continue

                if interpreter.computer.terminal.get_language(language) is None:
                    output = f"`{language}` disabled or not supported."

                    yield {
                        "role": "computer",
                        "type": "console",
                        "format": "output",
                        "content": output,
                    }

                    # 繼續對話讓模型換方式；若同一小段 code 反覆則 break 防無限迴圈
                    if code != last_unsupported_code:
                        last_unsupported_code = code
                        continue
                    else:
                        break

                if code.strip() == "":
                    yield {
                        "role": "computer",
                        "type": "console",
                        "format": "output",
                        "content": "Code block was empty. Please try again, be sure to write code before executing.",
                    }
                    continue

                try:
                    yield {
                        "role": "computer",
                        "type": "confirmation",
                        "format": "execution",
                        "content": {
                            "type": "code",
                            "format": language,
                            "content": code,
                        },
                    }
                except GeneratorExit:
                    break

                # 確認步驟後使用者可能已改編輯區內 code，改抓最新內容
                code = [m for m in interpreter.messages if m["type"] == "code"][-1][
                    "content"
                ]

                if interpreter.computer.import_computer_api and language == "python":
                    code = code.replace("import computer\n", "pass\n")
                    code = re.sub(
                        r"import computer\.(\w+) as (\w+)", r"\2 = computer.\1", code
                    )
                    code = re.sub(
                        r"from computer import (.+)",
                        lambda m: "\n".join(
                            f"{x.strip()} = computer.{x.strip()}"
                            for x in m.group(1).split(", ")
                        ),
                        code,
                    )
                    code = re.sub(r"import computer\.\w+\n", "pass\n", code)
                    # 避免最後一行是 view/screenshot 時在 Jupyter 重複顯示截圖
                    if any(
                        code.strip().split("\n")[-1].startswith(text)
                        for text in [
                            "computer.display.view",
                            "computer.display.screenshot",
                            "computer.view",
                            "computer.screenshot",
                        ]
                    ):
                        code = code + "\npass"

                interpreter.computer.verbose = interpreter.verbose
                interpreter.computer.debug = interpreter.debug
                interpreter.computer.emit_images = interpreter.llm.supports_vision
                interpreter.computer.max_output = interpreter.max_output

                try:
                    if interpreter.sync_computer and language == "python":
                        computer_dict = interpreter.computer.to_dict()
                        if "_hashes" in computer_dict:
                            computer_dict.pop("_hashes")
                        if "system_message" in computer_dict:
                            computer_dict.pop("system_message")
                        computer_json = json.dumps(computer_dict)
                        sync_code = f"""import json\ncomputer.load_dict(json.loads('''{computer_json}'''))"""
                        interpreter.computer.run("python", sync_code)
                except Exception as e:
                    if interpreter.debug:
                        raise
                    print(str(e))
                    print("Failed to sync iComputer with your Computer. Continuing...")

                ## ↓ 實際執行 code
                for line in interpreter.computer.run(language, code, stream=True):
                    yield {"role": "computer", **line}

                ## ↑ 執行結束

                try:
                    if interpreter.sync_computer and language == "python":
                        result = interpreter.computer.run(
                            "python",
                            """
                            import json
                            computer_dict = computer.to_dict()
                            if '_hashes' in computer_dict:
                                computer_dict.pop('_hashes')
                            if "system_message" in computer_dict:
                                computer_dict.pop("system_message")
                            print(json.dumps(computer_dict))
                            """,
                        )
                        result = result[-1]["content"]
                        interpreter.computer.load_dict(
                            json.loads(result.strip('"').strip("'"))
                        )
                except Exception as e:
                    if interpreter.debug:
                        raise
                    print(str(e))
                    print("Failed to sync your Computer with iComputer. Continuing.")

                yield {
                    "role": "computer",
                    "type": "console",
                    "format": "active_line",
                    "content": None,
                }

            except KeyboardInterrupt:
                break
            except:
                yield {
                    "role": "computer",
                    "type": "console",
                    "format": "output",
                    "content": traceback.format_exc(),
                }

        else:
            ## loop 模式：必要時插入 loop_message 逼模型繼續或結束語

            loop_message = interpreter.loop_message
            if interpreter.os:
                loop_message = loop_message.replace(
                    "If the entire task I asked for is done,",
                    "If the entire task I asked for is done, take a screenshot to verify it's complete, or if you've already taken a screenshot and verified it's complete,",
                )
            loop_breakers = interpreter.loop_breakers

            if (
                interpreter.loop
                and interpreter.messages
                and interpreter.messages[-1].get("role", "") == "assistant"
                and not any(
                    task_status in interpreter.messages[-1].get("content", "")
                    for task_status in loop_breakers
                )
            ):
                interpreter.messages = [
                    message
                    for message in interpreter.messages
                    if message.get("content", "") != loop_message
                ]
                combined_messages = []
                for message in interpreter.messages:
                    if (
                        combined_messages
                        and message["role"] == "assistant"
                        and combined_messages[-1]["role"] == "assistant"
                        and message["type"] == "message"
                        and combined_messages[-1]["type"] == "message"
                    ):
                        combined_messages[-1]["content"] += "\n" + message["content"]
                    else:
                        combined_messages.append(message)
                interpreter.messages = combined_messages

                insert_loop_message = True

                continue

            # 最後一則非可執行 code，或 loop 不繼續：結束 respond
            break

    return
