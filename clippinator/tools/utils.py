from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any, Union

import inquirer  # type: ignore
import langchain
import langchain.agents.openai_functions_agent.base as oai_func_ag
import rich
from beartype import beartype as typed
from beartype.typing import Callable
from langchain.agents.output_parsers.openai_functions import (
    OpenAIFunctionsAgentOutputParser,
)
from langchain.schema import AgentAction


@typed
def get_input_from_editor(initial_text: str | None = None) -> str:
    editor = os.environ.get("EDITOR", "vi")  # defaults to 'vi' if EDITOR is not set

    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False, mode="w+t") as tf:
        # Write the initial text to the file
        if initial_text is not None:
            tf.write(initial_text)
            tf.flush()

        tf.close()
        subprocess.call([editor, tf.name])

        # Read the file
        with open(tf.name, "r") as f:
            input_string = f.read()

        # Clean up the temp file
        os.unlink(tf.name)

    return input_string


@typed
def skip_file(filename: str) -> bool:
    filename = filename.strip("/").split("/")[-1]
    if filename.startswith("."):
        return True
    return (
        filename
        in (".git", ".idea", "__pycache__", "venv", "node_modules", "data", "coverage")
        or "venv" in filename
    )


@typed
def skip_file_summary(filename: str) -> bool:
    return (
        filename.endswith(".svg")
        or "tsconfig" in filename
        or "-lock" in filename
        or filename.endswith(".lock")
    )


@typed
def trim_extra(content: str, max_length: int = 4000, end_length: int = 1300) -> str:
    if len(content) > max_length:
        content = (
            content[: max_length - end_length]
            + f"\n...[skipped {len(content) - max_length} chars]\n"
            + content[-end_length:]
        )
    return content


@typed
def unjson(data: str | Any) -> Any:
    if isinstance(data, str):
        return json.loads(data)
    return data


_parse_ai_message = OpenAIFunctionsAgentOutputParser._parse_ai_message


@typed
def parse_openai_function_message_custom(
    msg: oai_func_ag.BaseMessage,
) -> Union[oai_func_ag.AgentAction, oai_func_ag.AgentFinish]:
    try:
        return _parse_ai_message(msg)
    except langchain.schema.OutputParserException as e:
        if msg.additional_kwargs.get("function_call", {}).get("arguments"):
            try:
                args = json.dumps(
                    eval(msg.additional_kwargs["function_call"]["arguments"])
                )
                msg.additional_kwargs["function_call"]["arguments"] = args
                return _parse_ai_message(msg)
            except SyntaxError:
                pass
        raise e


setattr(
    OpenAIFunctionsAgentOutputParser,
    "_parse_ai_message",
    parse_openai_function_message_custom,
)


@typed
def yes_no_prompt(prompt: str, default: bool = False) -> bool:
    answer = inquirer.prompt(
        [inquirer.Confirm("yes_no", message=prompt, default=default)]
    )
    if not answer or not answer.get("yes_no"):
        return default
    return answer["yes_no"]


@typed
def text_prompt(prompt: str) -> str:
    answer = inquirer.prompt([inquirer.Text("text", message=prompt)])
    if not answer or not answer.get("text"):
        return ""
    return answer["text"]


@typed
def select(options: list[str], prompt: str, default: str | None = None) -> int:
    if default is None:
        default = options[0]
    answer = inquirer.prompt(
        [inquirer.List("selected", message=prompt, choices=options, default=default)]
    )
    return options.index(answer["selected"])


@typed
def ask_for_feedback(menu: Callable | None = None) -> tuple[AgentAction, str] | None:
    rich.print(
        "\n[bold green]Agent paused, enter feedback"
        + ' or "menu"/"m"' * (menu is not None)
        + ' or "exit" or press enter[/bold green]'
    )
    feedback = text_prompt("Feedback")
    if feedback in ("menu", "m"):
        if menu is not None:
            menu()
        return None
    if feedback == "exit":
        raise KeyboardInterrupt
    if feedback:
        return (
            AgentAction(
                tool="AgentFeedback",
                tool_input="",
                log="Here is feedback from your supervisor: ",
            ),
            feedback,
        )
    return None
