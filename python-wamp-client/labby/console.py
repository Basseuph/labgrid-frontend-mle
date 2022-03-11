from typing import Optional
from attr import attrs, attrib
import paramiko


@attrs
class Console:
    _is_open: bool = attrib(init=False, default=False)
    host: str = attrib()
    port: int = attrib(default=22)
    username: str = attrib(default=None)
    ssh: Optional[paramiko.SSHClient] = attrib(default=None, init=False)
    channel: Optional[paramiko.Channel] = attrib(default=None, init=False)

    def open(self):
        if self.ssh:
            self.ssh.close()
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.connect(self.host,
                         self.port,)
        self.channel = self.ssh.invoke_shell("/dev/tty11")
        self._is_open = True

    def close(self):
        if self._is_open and self.ssh:
            self.ssh.close()
            self._is_open = False

    def send(self, data: str):
        assert self._is_open, "Console not connected"
        assert self.channel, "No valid channel open"
        self.channel.send(bytes(data, 'utf-8'))

    def recv(self):
        assert self._is_open, "Console not connected"
        assert self.channel, "No valid channel open"
        return self.channel.recv(1024**2).decode('utf-8')

    def __enter__(self):
        if not self._is_open:
            self.open()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
