def run_text_llm(llm, params):
    ## 設定
    ## Setup

    if llm.execution_instructions:
        try:
            # 加入 system message
            # Add the system message
            params["messages"][0][
                "content"
            ] += "\n" + llm.execution_instructions
        except:
            print('params["messages"][0]', params["messages"][0])
            raise

    ## 將輸出轉換為 LMC 格式
    ## Convert output to LMC format

    inside_code_block = False
    accumulated_block = ""
    language = None

    for chunk in llm.completions(**params):
        if llm.interpreter.verbose:
            print("Chunk in coding_llm", chunk)

        if "choices" not in chunk or len(chunk["choices"]) == 0:
            # 有時會發生這種情況
            # This happens sometimes
            continue

        content = chunk["choices"][0]["delta"].get("content", "")

        if content == None:
            continue

        accumulated_block += content

        if accumulated_block.endswith("`"):
            # 我們可能正在一次一個 token 地寫 "```"
            # We might be writing "```" one token at a time.
            continue

        # 我們剛進入程式碼區塊了嗎？
        # Did we just enter a code block?
        if "```" in accumulated_block and not inside_code_block:
            inside_code_block = True
            accumulated_block = accumulated_block.split("```")[1]

        # 我們剛離開程式碼區塊了嗎？
        # Did we just exit a code block?
        if inside_code_block and "```" in accumulated_block:
            return

        # 若我們在程式碼區塊中，
        # If we're in a code block,
        if inside_code_block:
            # 若還沒有 `language`，找出它
            # If we don't have a `language`, find it
            if language is None and "\n" in accumulated_block:
                language = accumulated_block.split("\n")[0]

                # 若未指定，預設為 python
                # Default to python if not specified
                if language == "":
                    if llm.interpreter.os == False:
                        language = "python"
                    elif llm.interpreter.os == False:
                        # OS 模式下經常這樣做，用 markdown 程式碼區塊做筆記
                        # OS mode does this frequently. Takes notes with markdown code blocks
                        language = "text"
                else:
                    # 移除包含空格或非字母字元的幻覺輸出
                    # Removes hallucinations containing spaces or non letters.
                    language = "".join(char for char in language if char.isalpha())

            # 若已有 `language`，則送出
            # If we do have a `language`, send it out
            if language:
                yield {
                    "type": "code",
                    "format": language,
                    "content": content.replace(language, ""),
                }

        # 若不在程式碼區塊中，以訊息形式送出輸出
        # If we're not in a code block, send the output as a message
        if not inside_code_block:
            yield {"type": "message", "content": content}
