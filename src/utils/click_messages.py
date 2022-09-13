import click

from typing import Optional


def error(message: str, *additional_messages: str) -> SystemExit:
    formatted_messages = []
    for additional_message in additional_messages:
        formatted_messages.append(f'  ↳ {additional_message}')
    built_message = f'{message}\n' + '\n'.join(formatted_messages)
    click.secho(built_message, fg='red')
    return SystemExit(1)


def warning(message: str, *additional_messages: str) -> None:
    formatted_messages = []
    for additional_message in additional_messages:
        formatted_messages.append(f'  ↳ {additional_message}')
    built_message = f'{message}\n' + '\n'.join(formatted_messages)
    click.secho(built_message, fg='yellow')


def message(
    message: str,
    *additional_messages: str,
    exit_after: bool = False,
) -> Optional[SystemExit]:
    formatted_messages = []
    for additional_message in additional_messages:
        formatted_messages.append(f'  ↳ {additional_message}')
    built_message = None
    if formatted_messages:
        built_message = f'{message}' + '\n'.join(formatted_messages)
    click.secho(built_message or message)
    if exit_after is True:
        return SystemExit(0)
