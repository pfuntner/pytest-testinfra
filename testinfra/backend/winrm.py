# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from typing import Any, Optional

from testinfra.backend import base

try:
    import winrm
except ImportError:
    raise RuntimeError(
        "You must install the pywinrm package (pip install pywinrm) "
        "to use the winrm backend"
    ) from None

import winrm.protocol

_find_unsafe = re.compile(r"[^\w@%+=:,./-]", re.ASCII)


# (gtmanfred) This is copied from pipes.quote, but changed to use double quotes
# instead of single quotes.  This is used by the winrm backend.
def _quote(s: str) -> str:
    """Return a shell-escaped version of the string *s*."""
    if not s:
        return "''"
    if _find_unsafe.search(s) is None:
        return s

    # use single quotes, and put single quotes into double quotes
    # the string $'b is then quoted as '$'"'"'b'
    return '"' + s.replace('"', '"\'"\'"') + '"'


class WinRMBackend(base.BaseBackend):
    """Run command through winrm command"""

    NAME = "winrm"

    def __init__(
        self,
        hostspec: str,
        no_ssl: bool = False,
        no_verify_ssl: bool = False,
        read_timeout_sec: Optional[int] = None,
        operation_timeout_sec: Optional[int] = None,
        *args: Any,
        **kwargs: Any,
    ):
        self.host = self.parse_hostspec(hostspec)
        self.conn_args: dict[str, Any] = {
            "endpoint": "{}://{}{}/wsman".format(
                "http" if no_ssl else "https",
                self.host.name,
                f":{self.host.port}" if self.host.port else "",
            ),
            "transport": "ntlm",
            "username": self.host.user,
            "password": self.host.password,
        }
        if no_verify_ssl:
            self.conn_args["server_cert_validation"] = "ignore"
        if read_timeout_sec is not None:
            self.conn_args["read_timeout_sec"] = read_timeout_sec
        if operation_timeout_sec is not None:
            self.conn_args["operation_timeout_sec"] = operation_timeout_sec
        super().__init__(self.host.name, *args, **kwargs)

    def run(self, command: str, *args: str, **kwargs: Any) -> base.CommandResult:
        return self.run_winrm(self.get_command(command, *args))

    def run_winrm(self, command: str) -> base.CommandResult:
        p = winrm.protocol.Protocol(**self.conn_args)
        shell_id = p.open_shell()
        command_id = p.run_command(shell_id, command)
        stdout, stderr, rc = p.get_command_output(shell_id, command_id)
        p.cleanup_command(shell_id, command_id)
        p.close_shell(shell_id)
        return self.result(rc, self.encode(command), stdout, stderr)

    @staticmethod
    def quote(command: str, *args: str) -> str:
        if args:
            return command % tuple(_quote(a) for a in args)
        return command
