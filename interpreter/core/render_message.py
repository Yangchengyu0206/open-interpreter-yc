import re


def render_message(interpreter, message):
    """
    將含動態片段的訊息渲染成字串。
    `{{ ... }}` 內為 Python 片段，會經 computer 執行後以其輸出替換。
    """

    previous_save_skills_setting = interpreter.computer.save_skills
    interpreter.computer.save_skills = False

    # 以 {{ 與 }} 分段（含跨行）
    parts = re.split(r"({{.*?}})", message, flags=re.DOTALL)

    for i, part in enumerate(parts):
        if part.startswith("{{") and part.endswith("}}"):
            output = interpreter.computer.run(
                "python", part[2:-2].strip(), display=interpreter.verbose
            )

            outputs = (
                line["content"]
                for line in output
                if line.get("format") == "output"
                and "IGNORE_ALL_ABOVE_THIS_LINE" not in line["content"]
            )

            parts[i] = "\n".join(outputs)

    rendered_message = "".join(parts).strip()

    if (
        interpreter.debug == True and False  # DISABLED
    ):
        print("\n\n\nSYSTEM MESSAGE\n\n\n")
        print(rendered_message)
        print("\n\n\n")

    interpreter.computer.save_skills = previous_save_skills_setting

    return rendered_message
