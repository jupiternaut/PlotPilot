from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from itertools import count
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class CodexAppServerError(RuntimeError):
    """Raised when the Codex app-server adapter cannot complete a request."""


@dataclass
class CodexAccountStatus:
    available: bool
    authenticated: bool
    requires_openai_auth: bool = False
    email: Optional[str] = None
    plan_type: Optional[str] = None
    error: Optional[str] = None


class CodexAppServerClient:
    """Tiny JSON-RPC client for `codex app-server --listen stdio://`.

    The PoC intentionally treats Codex as a local sidecar owned by the official
    CLI. PlotPilot does not handle ChatGPT OAuth tokens itself.
    """

    def __init__(
        self,
        command: Optional[list[str]] = None,
        request_timeout: float = 300.0,
    ):
        self.command = command or ["codex", "app-server", "--listen", "stdio://"]
        self.request_timeout = request_timeout
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._stderr_task: Optional[asyncio.Task[None]] = None
        self._write_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._generation_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._notifications: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._ids = count(1)
        self._initialized = False

    @staticmethod
    def is_available() -> bool:
        return shutil.which("codex") is not None

    async def status(self) -> CodexAccountStatus:
        if not self.is_available():
            return CodexAccountStatus(
                available=False,
                authenticated=False,
                error="未找到 codex CLI，请先安装或确认 PATH 中可执行 codex。",
            )
        try:
            payload = await self.request(
                "account/read",
                {"refreshToken": False},
                timeout=30.0,
            )
        except Exception as exc:
            return CodexAccountStatus(
                available=True,
                authenticated=False,
                error=str(exc),
            )

        account = payload.get("account") if isinstance(payload, dict) else None
        if not isinstance(account, dict):
            return CodexAccountStatus(
                available=True,
                authenticated=False,
                requires_openai_auth=bool(payload.get("requiresOpenaiAuth"))
                if isinstance(payload, dict)
                else True,
            )

        return CodexAccountStatus(
            available=True,
            authenticated=True,
            requires_openai_auth=bool(payload.get("requiresOpenaiAuth")),
            email=str(account.get("email") or "") or None,
            plan_type=str(account.get("planType") or "") or None,
        )

    async def start_chatgpt_login(self) -> dict[str, str]:
        response = await self.request(
            "account/login/start",
            {"type": "chatgpt", "codexStreamlinedLogin": True},
            timeout=30.0,
        )
        auth_url = str(response.get("authUrl") or "")
        login_id = str(response.get("loginId") or "")
        if not auth_url or not login_id:
            raise CodexAppServerError("Codex app-server 未返回有效的登录 URL。")
        return {"auth_url": auth_url, "login_id": login_id}

    async def logout(self) -> None:
        await self.request("account/logout", {}, timeout=30.0)

    async def aclose(self) -> None:
        await self._stop_process()

    async def generate_text(
        self,
        *,
        system: str,
        user: str,
        model: str = "",
        timeout: Optional[float] = None,
        output_schema: Optional[dict[str, Any]] = None,
    ) -> str:
        chunks: list[str] = []
        async for chunk in self.stream_text(
            system=system,
            user=user,
            model=model,
            timeout=timeout,
            output_schema=output_schema,
        ):
            chunks.append(chunk)
        text = "".join(chunks).strip()
        if not text:
            raise CodexAppServerError("Codex app-server 返回了空内容。")
        return text

    async def stream_text(
        self,
        *,
        system: str,
        user: str,
        model: str = "",
        timeout: Optional[float] = None,
        output_schema: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        async with self._generation_lock:
            # Keep the adapter as a text generator, not a coding agent.
            safe_system = (
                "你正在作为 PlotPilot 的小说文本生成后端工作。"
                "只返回用户请求的最终文本；不要执行命令，不要修改文件，"
                "不要调用工具，不要输出过程说明。\n\n"
                f"{system}"
            )
            thread_params: dict[str, Any] = {
                "baseInstructions": safe_system,
                "environments": [],
                "ephemeral": True,
                "serviceName": "plotpilot-codex-app-server-poc",
            }
            if model.strip():
                thread_params["model"] = model.strip()

            thread_response = await self.request(
                "thread/start",
                thread_params,
                timeout=min(timeout or self.request_timeout, 60.0),
            )
            thread_id = self._extract_id(thread_response, "thread")
            if not thread_id:
                raise CodexAppServerError("Codex app-server 未返回 thread id。")

            turn_params: dict[str, Any] = {
                "threadId": thread_id,
                "input": [{"type": "text", "text": user}],
                "environments": [],
            }
            if model.strip():
                turn_params["model"] = model.strip()
            if output_schema:
                turn_params["outputSchema"] = output_schema

            turn_response = await self.request(
                "turn/start",
                turn_params,
                timeout=min(timeout or self.request_timeout, 60.0),
            )
            turn_id = self._extract_id(turn_response, "turn")
            if not turn_id:
                raise CodexAppServerError("Codex app-server 未返回 turn id。")

            while True:
                try:
                    notification = await asyncio.wait_for(
                        self._notifications.get(),
                        timeout=timeout or self.request_timeout,
                    )
                except asyncio.TimeoutError as exc:
                    raise CodexAppServerError("等待 Codex app-server 生成超时。") from exc

                method = str(notification.get("method") or "")
                params = notification.get("params") or {}
                if not isinstance(params, dict):
                    continue

                if params.get("turnId") and params.get("turnId") != turn_id:
                    continue
                if params.get("threadId") and params.get("threadId") != thread_id:
                    continue

                if method == "item/agentMessage/delta":
                    delta = params.get("delta")
                    if isinstance(delta, str) and delta:
                        yield delta
                    continue

                if method == "error":
                    message = params.get("message") or params.get("error") or "Codex app-server error"
                    raise CodexAppServerError(str(message))

                if method == "turn/completed":
                    break

    async def request(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        await self._ensure_started()
        return await self._request_once(method, params or {}, timeout)

    async def _request_once(
        self,
        method: str,
        params: dict[str, Any],
        timeout: Optional[float],
    ) -> Any:
        if self._process is None or self._process.stdin is None:
            raise CodexAppServerError("Codex app-server 未启动。")

        request_id = str(next(self._ids))
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending[request_id] = future

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        try:
            await self._write_json(payload)
            return await asyncio.wait_for(future, timeout=timeout or self.request_timeout)
        except (BrokenPipeError, ConnectionError) as exc:
            await self._stop_process()
            raise CodexAppServerError("Codex app-server 连接已断开。") from exc
        finally:
            self._pending.pop(request_id, None)

    async def _ensure_started(self) -> None:
        async with self._start_lock:
            if self._process and self._process.returncode is None and self._initialized:
                return
            await self._stop_process()
            if not self.is_available():
                raise CodexAppServerError("未找到 codex CLI，请确认 PATH 中可执行 codex。")

            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._reader_task = asyncio.create_task(self._read_loop())
            self._stderr_task = asyncio.create_task(self._stderr_loop())
            self._initialized = False
            await self._initialize()

    async def _initialize(self) -> None:
        response = await self._request_once(
            "initialize",
            {
                "clientInfo": {
                    "name": "plotpilot",
                    "title": "PlotPilot",
                    "version": "0.1.0",
                },
                "capabilities": {"experimentalApi": True},
            },
            timeout=30.0,
        )
        if not isinstance(response, dict):
            raise CodexAppServerError("Codex app-server initialize 返回异常。")
        self._initialized = True

    async def _read_loop(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        try:
            while True:
                raw = await self._process.stdout.readline()
                if not raw:
                    break
                try:
                    message = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    logger.debug("Ignoring non-JSON app-server stdout: %r", raw[:200])
                    continue
                await self._handle_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Codex app-server read loop failed: %s", exc)
        finally:
            self._initialized = False
            error = CodexAppServerError("Codex app-server 已退出。")
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(error)

    async def _stderr_loop(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        try:
            while True:
                raw = await process.stderr.readline()
                if not raw:
                    break
                logger.debug("codex app-server stderr: %s", raw.decode("utf-8", "replace").rstrip())
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Codex app-server stderr loop ended unexpectedly", exc_info=True)

    async def _handle_message(self, message: dict[str, Any]) -> None:
        if "id" in message and ("result" in message or "error" in message):
            future = self._pending.get(str(message.get("id")))
            if not future or future.done():
                return
            if "error" in message and message["error"]:
                error_payload = message["error"]
                if isinstance(error_payload, dict):
                    text = error_payload.get("message") or json.dumps(error_payload, ensure_ascii=False)
                else:
                    text = str(error_payload)
                future.set_exception(CodexAppServerError(text))
            else:
                future.set_result(message.get("result"))
            return

        # Server-initiated requests are denied by design for this text-only PoC.
        if "id" in message and "method" in message:
            await self._write_json({
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32000,
                    "message": "PlotPilot Codex adapter disables tools, file edits, commands, and user-input prompts.",
                },
            })
            return

        if "method" in message:
            await self._notifications.put(message)

    async def _write_json(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise CodexAppServerError("Codex app-server 未启动。")
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        async with self._write_lock:
            self._process.stdin.write(data)
            await self._process.stdin.drain()

    async def _stop_process(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._stderr_task:
            self._stderr_task.cancel()
            self._stderr_task = None
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None
        self._initialized = False

    @staticmethod
    def _extract_id(payload: Any, key: str) -> str:
        if not isinstance(payload, dict):
            return ""
        nested = payload.get(key)
        if isinstance(nested, dict):
            return str(nested.get("id") or "")
        return str(payload.get(f"{key}Id") or payload.get("id") or "")


_client: Optional[CodexAppServerClient] = None


def get_codex_app_server_client() -> CodexAppServerClient:
    global _client
    if _client is None:
        _client = CodexAppServerClient()
    return _client
