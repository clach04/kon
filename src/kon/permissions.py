import os
import shlex
from enum import Enum

from kon import config

from .tools.base import BaseTool


class PermissionDecision(Enum):
    ALLOW = "allow"
    PROMPT = "prompt"


class ApprovalResponse(Enum):
    APPROVE = "approve"
    DENY = "deny"


SAFE_COMMANDS: frozenset[str] = frozenset(
    {
        "cat",
        "head",
        "tail",
        "ls",
        "pwd",
        "wc",
        "diff",
        "which",
        "file",
        "stat",
        "du",
        "df",
        "whoami",
        "id",
        "uname",
        "date",
        "realpath",
        "dirname",
        "basename",
    }
)

SAFE_GIT_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "rev-parse",
        "describe",
        "ls-files",
        "ls-tree",
        "blame",
        "shortlog",
    }
)

_PUNCTUATION_CHARS = frozenset(";|&()><")


def check_permission(tool: BaseTool, arguments: dict) -> PermissionDecision:
    if config.permissions.mode == "auto":
        return PermissionDecision.ALLOW
    if not tool.mutating:
        return PermissionDecision.ALLOW
    # So this is a mutating tool
    if config.permissions.mode == "write_local" and tool.name in ("edit", "write"):
        # check arguments for filename(s?) and check if in "project directory
        # kon --prompt "create a file called `hello.md` with contents `hello`"  ## ooohhh this happened with no permission prompt, so this looks like a bug!? It did create the file!?
        # can't figure out how to get project path, so maybe nbew permissions.writeable_paths[] ? - problem is there a local settings file that could then be edited by the model... For now, lets use an environment variable... singular for now; create a file called `hello.md` with contents `hello`
        writeable_path = os.environ.get('KON_WRITEABLE_PATH')  # singular for now  -- set KON_WRITEABLE_PATH=C:\code\py\hf_ls
        if writeable_path:  # revisit this, end up with a bunch of nesting...
            #import web_pdb; web_pdb.set_trace()
            writeable_path = os.path.abspath(writeable_path)
            tmp_tn = tool.name
            tmp_v = arguments
            requested_write_path = os.path.abspath(arguments['path'])  # seen with edit tool, write not seen yet (but code walk shows it is also path). TODO can this dict lookup fail?
            for allowed_writeable_path in (writeable_path,):  # loop for future proofing...
                if requested_write_path.startswith(allowed_writeable_path):
                    # TODO is there a simple printf() like call we can make here to make clear what happened?
                    return PermissionDecision.ALLOW

    if tool.name == "bash":
        command = arguments.get("command", "")
        if _is_safe_bash_command(command):
            return PermissionDecision.ALLOW
    return PermissionDecision.PROMPT


def _is_safe_bash_command(command: str) -> bool:
    if "\n" in command or "`" in command or "$(" in command or "<(" in command or ">(" in command:
        return False

    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";|&()><")
        tokens = list(lexer)
    except ValueError:
        return False

    if not tokens:
        return False

    for token in tokens:
        if token and all(c in _PUNCTUATION_CHARS for c in token):
            return False

    base = tokens[0]
    if "/" in base:
        base = base.rsplit("/", 1)[-1]

    if base == "git":
        return _is_safe_git_command(tokens)

    return base in SAFE_COMMANDS


def _is_safe_git_command(tokens: list[str]) -> bool:
    i = 1
    while i < len(tokens):
        if tokens[i] in ("-c", "--config-env") or tokens[i].startswith("--config-env="):
            return False
        if not tokens[i].startswith("-"):
            if tokens[i] not in SAFE_GIT_SUBCOMMANDS:
                return False
            # --output writes diff to a file, making it mutating
            return not any(t == "--output" or t.startswith("--output=") for t in tokens[i + 1 :])
        if tokens[i] in ("-C", "--git-dir", "--work-tree", "--namespace") and i + 1 < len(tokens):
            i += 2
            continue
        i += 1
    return False
