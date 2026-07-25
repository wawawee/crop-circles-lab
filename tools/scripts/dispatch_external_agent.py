#!/usr/bin/env python3
"""
Dispatch a prompt to an external coding agent outside Cursor.

Backends
  opencode  — headless `opencode run` (sync or background job)
  freebuff  — queue + clipboard; optionally inject into running Terminal.app TUI
  auto      — freebuff if a live process exists, else opencode

Cursor / Auto usage
  python tools/scripts/dispatch_external_agent.py "Investigate X…"
  python tools/scripts/dispatch_external_agent.py --backend opencode --cwd . "…"
  python tools/scripts/dispatch_external_agent.py --backend freebuff --inject "…"
  python tools/scripts/dispatch_external_agent.py status <job_id>
  python tools/scripts/dispatch_external_agent.py await <job_id>

Also: tools/scripts/freebuff-dispatch (thin wrapper).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = ROOT / "outputs" / "agent_dispatch"
DEFAULT_OPENCODE_MODEL = os.environ.get(
    "DISPATCH_OPENCODE_MODEL", "opencode/deepseek-v4-flash-free"
)
DEFAULT_OPENCODE_ATTACH = os.environ.get("DISPATCH_OPENCODE_ATTACH", "").strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"job_{stamp}_{uuid.uuid4().hex[:8]}"


def ensure_jobs_dir() -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    (JOBS_DIR / ".gitkeep").touch(exist_ok=True)
    return JOBS_DIR


def job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def write_job(job: dict[str, Any]) -> Path:
    ensure_jobs_dir()
    path = job_path(job["id"])
    path.write_text(json.dumps(job, indent=2, ensure_ascii=False) + "\n")
    return path


def read_job(job_id: str) -> dict[str, Any]:
    path = job_path(job_id)
    if not path.exists():
        raise SystemExit(f"job not found: {job_id} ({path})")
    return json.loads(path.read_text())


def which_or(path_hint: str, names: list[str]) -> Optional[str]:
    if path_hint and Path(path_hint).exists():
        return path_hint
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    home = Path.home()
    candidates = [
        home / ".config" / "manicode" / "freebuff",
        home / ".opencode" / "bin" / "opencode",
        Path("/opt/homebrew/bin/opencode"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def find_freebuff_pid() -> Optional[int]:
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,command="], text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # Prefer the real binary over the node wrapper.
        if "/.config/manicode/freebuff" in line or re.search(
            r"(^|\s)freebuff(\s|$)", line
        ):
            if "dispatch_external_agent" in line:
                continue
            try:
                return int(line.split(None, 1)[0])
            except ValueError:
                continue
    return None


def resolve_prompt(args: argparse.Namespace) -> str:
    parts = list(args.prompt or [])
    if args.file:
        parts.append(Path(args.file).read_text())
    if args.stdin or (not parts and not sys.stdin.isatty()):
        piped = sys.stdin.read()
        if piped.strip():
            parts.append(piped)
    text = "\n\n".join(p.strip() for p in parts if p and p.strip())
    if not text:
        raise SystemExit("empty prompt — pass text, --file, or pipe stdin")
    return text


def pbcopy(text: str) -> None:
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def notify(title: str, body: str) -> None:
    # Best-effort macOS notification; ignore failures.
    script = (
        f'display notification "{_as_escape(body[:180])}" '
        f'with title "{_as_escape(title)}"'
    )
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def _as_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def inject_freebuff_terminal(prompt: str) -> dict[str, Any]:
    """Copy prompt to clipboard and paste+enter into front Terminal.app window."""
    if sys.platform != "darwin":
        return {
            "ok": False,
            "error": "inject only supported on macOS (Terminal.app + pbcopy)",
        }
    pbcopy(prompt)
    # Activate Terminal, paste, submit. User should have Freebuff tab frontmost.
    script = """
tell application "Terminal" to activate
delay 0.35
tell application "System Events"
  tell process "Terminal"
    set frontmost to true
    keystroke "v" using command down
    delay 0.15
    keystroke return
  end tell
end tell
"""
    r = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True
    )
    if r.returncode != 0:
        return {
            "ok": False,
            "error": (r.stderr or r.stdout or "osascript failed").strip(),
            "clipboard": True,
        }
    return {"ok": True, "clipboard": True, "injected": True}


def spawn_freebuff_terminal(cwd: str, prompt: str) -> dict[str, Any]:
    if sys.platform != "darwin":
        return {"ok": False, "error": "spawn only supported on macOS Terminal.app"}
    freebuff = which_or(
        os.environ.get("FREEBUFF_BIN", ""),
        ["freebuff"],
    )
    if not freebuff:
        return {
            "ok": False,
            "error": "freebuff not found — npm i -g freebuff",
        }
    pbcopy(prompt)
    # Open a new Terminal tab running freebuff in cwd, then paste after settle.
    cmd = f"cd {json.dumps(cwd)} && {json.dumps(freebuff)}"
    script = f'''
tell application "Terminal"
  activate
  do script {json.dumps(cmd)}
end tell
delay 2.5
tell application "System Events"
  tell process "Terminal"
    set frontmost to true
    keystroke "v" using command down
    delay 0.2
    keystroke return
  end tell
end tell
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        return {
            "ok": False,
            "error": (r.stderr or r.stdout or "osascript failed").strip(),
            "clipboard": True,
        }
    return {"ok": True, "clipboard": True, "spawned": True}


def dispatch_freebuff(
    prompt: str,
    cwd: str,
    *,
    inject: bool,
    spawn: bool,
    dry_run: bool,
) -> dict[str, Any]:
    job_id = new_job_id()
    job: dict[str, Any] = {
        "id": job_id,
        "backend": "freebuff",
        "status": "queued",
        "prompt": prompt,
        "cwd": cwd,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "freebuff_pid": find_freebuff_pid(),
        "result_path": None,
        "log_path": None,
        "notes": [],
    }
    prompt_file = JOBS_DIR / f"{job_id}.prompt.md"
    if dry_run:
        job["status"] = "dry_run"
        job["notes"].append("dry-run: no clipboard / inject / spawn")
        ensure_jobs_dir()
        write_job(job)
        return job

    ensure_jobs_dir()
    prompt_file.write_text(prompt + "\n")
    job["prompt_file"] = str(prompt_file)

    if spawn:
        result = spawn_freebuff_terminal(cwd, prompt)
        job["inject"] = result
        job["status"] = "dispatched" if result.get("ok") else "awaiting_paste"
        if not result.get("ok"):
            job["notes"].append(result.get("error", "spawn failed"))
            pbcopy(prompt)
            job["notes"].append("prompt copied to clipboard — paste into Freebuff")
            notify("Freebuff dispatch", f"{job_id}: paste Cmd+V in Freebuff")
    elif inject:
        if not find_freebuff_pid():
            job["notes"].append(
                "no live freebuff process — copied to clipboard; start freebuff then paste"
            )
            pbcopy(prompt)
            job["status"] = "awaiting_paste"
            notify("Freebuff dispatch", f"{job_id}: start freebuff, then Cmd+V")
        else:
            result = inject_freebuff_terminal(prompt)
            job["inject"] = result
            if result.get("ok"):
                job["status"] = "dispatched"
                notify("Freebuff dispatch", f"{job_id}: injected into Terminal")
            else:
                pbcopy(prompt)
                job["status"] = "awaiting_paste"
                job["notes"].append(result.get("error", "inject failed"))
                notify("Freebuff dispatch", f"{job_id}: paste Cmd+V in Freebuff")
    else:
        pbcopy(prompt)
        job["status"] = "awaiting_paste"
        job["notes"].append("queue-only: prompt on clipboard + prompt_file")
        notify("Freebuff dispatch", f"{job_id}: paste Cmd+V in Freebuff")

    job["updated_at"] = utc_now()
    write_job(job)
    return job


def build_opencode_cmd(
    prompt: str,
    cwd: str,
    *,
    model: Optional[str],
    agent: Optional[str],
    attach: Optional[str],
    auto: bool,
) -> list[str]:
    opencode = which_or(os.environ.get("OPENCODE_BIN", ""), ["opencode"])
    if not opencode:
        raise SystemExit(
            "opencode not found — install from https://opencode.ai "
            "or brew install opencode-ai"
        )
    cmd = [opencode, "run", prompt, "--dir", cwd, "--format", "json"]
    if model:
        cmd.extend(["--model", model])
    if agent:
        cmd.extend(["--agent", agent])
    if attach:
        cmd.extend(["--attach", attach])
    if auto:
        cmd.append("--auto")
    return cmd


def dispatch_opencode(
    prompt: str,
    cwd: str,
    *,
    model: Optional[str],
    agent: Optional[str],
    attach: Optional[str],
    auto: bool,
    wait: bool,
    dry_run: bool,
) -> dict[str, Any]:
    job_id = new_job_id()
    ensure_jobs_dir()
    result_path = JOBS_DIR / f"{job_id}.result.jsonl"
    log_path = JOBS_DIR / f"{job_id}.log"
    cmd = build_opencode_cmd(
        prompt, cwd, model=model, agent=agent, attach=attach, auto=auto
    )
    job: dict[str, Any] = {
        "id": job_id,
        "backend": "opencode",
        "status": "queued",
        "prompt": prompt,
        "cwd": cwd,
        "model": model,
        "agent": agent,
        "attach": attach or None,
        "auto": auto,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "cmd": cmd,
        "result_path": str(result_path),
        "log_path": str(log_path),
        "pid": None,
        "exit_code": None,
        "notes": [],
    }
    if dry_run:
        job["status"] = "dry_run"
        write_job(job)
        return job

    if wait:
        job["status"] = "running"
        write_job(job)
        with result_path.open("w") as out, log_path.open("w") as err:
            proc = subprocess.run(
                cmd, cwd=cwd, stdout=out, stderr=err, text=True
            )
        job["exit_code"] = proc.returncode
        job["status"] = "done" if proc.returncode == 0 else "failed"
        job["updated_at"] = utc_now()
        write_job(job)
        return job

    # Background
    with result_path.open("w") as out, log_path.open("w") as err:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
    job["pid"] = proc.pid
    job["status"] = "running"
    job["updated_at"] = utc_now()
    write_job(job)
    return job


def refresh_job_status(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("backend") != "opencode" or job.get("status") not in {
        "running",
        "queued",
    }:
        return job
    pid = job.get("pid")
    if not pid:
        return job
    try:
        os.kill(pid, 0)
        alive = True
    except OSError:
        alive = False
    if alive:
        return job
    # Process exited — infer from log/result presence.
    result = Path(job["result_path"]) if job.get("result_path") else None
    log = Path(job["log_path"]) if job.get("log_path") else None
    # Without waitpid we don't have exit code; treat non-empty result as done.
    if result and result.exists() and result.stat().st_size > 0:
        job["status"] = "done"
    elif log and log.exists() and "error" in log.read_text(errors="ignore").lower():
        job["status"] = "failed"
    else:
        job["status"] = "done"
    job["updated_at"] = utc_now()
    write_job(job)
    return job


def cmd_status(job_id: str) -> int:
    job = refresh_job_status(read_job(job_id))
    print(json.dumps(job, indent=2, ensure_ascii=False))
    return 0


def cmd_await(job_id: str, timeout: float, poll: float) -> int:
    deadline = time.time() + timeout
    while True:
        job = refresh_job_status(read_job(job_id))
        if job.get("status") in {"done", "failed", "dispatched", "awaiting_paste", "dry_run"}:
            # For freebuff, "dispatched" is terminal enough for await.
            if job.get("backend") == "freebuff" or job["status"] in {
                "done",
                "failed",
                "dry_run",
            }:
                print(json.dumps(job, indent=2, ensure_ascii=False))
                return 0 if job.get("status") != "failed" else 1
        if time.time() >= deadline:
            print(json.dumps(job, indent=2, ensure_ascii=False))
            print(f"timeout after {timeout}s waiting for {job_id}", file=sys.stderr)
            return 2
        time.sleep(poll)


def cmd_list(limit: int) -> int:
    ensure_jobs_dir()
    jobs = sorted(JOBS_DIR.glob("job_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    for path in jobs[:limit]:
        try:
            job = json.loads(path.read_text())
            rows.append(
                {
                    "id": job.get("id"),
                    "backend": job.get("backend"),
                    "status": job.get("status"),
                    "created_at": job.get("created_at"),
                    "cwd": job.get("cwd"),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    print(json.dumps(rows, indent=2))
    return 0


def pick_backend(requested: str) -> str:
    if requested != "auto":
        return requested
    if find_freebuff_pid():
        return "freebuff"
    return "opencode"


def build_dispatch_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dispatch_external_agent",
        description="Dispatch a prompt to OpenCode or Freebuff outside Cursor.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s --dry-run "Probe Linear A entropy"
  %(prog)s --backend opencode --wait "Add NOTES.md for G13"
  %(prog)s --backend freebuff --inject "Continue G13 from MISSION_BOARD"
  %(prog)s status job_20260725T120000_abcd1234
  %(prog)s await job_20260725T120000_abcd1234 --timeout 600
  %(prog)s list
""",
    )
    p.add_argument("prompt", nargs="*", help="Prompt text (or use --file / stdin)")
    p.add_argument("--file", "-f", help="Read prompt from file")
    p.add_argument("--stdin", action="store_true", help="Force read prompt from stdin")
    p.add_argument(
        "--backend",
        choices=["auto", "opencode", "freebuff"],
        default="auto",
        help="Target agent (default: auto)",
    )
    p.add_argument(
        "--cwd",
        default=str(ROOT),
        help=f"Working directory (default: {ROOT})",
    )
    p.add_argument("--model", "-m", default=DEFAULT_OPENCODE_MODEL, help="OpenCode model")
    p.add_argument("--agent", help="OpenCode agent name")
    p.add_argument(
        "--attach",
        default=DEFAULT_OPENCODE_ATTACH or None,
        help="Attach to opencode serve URL (e.g. http://localhost:4096)",
    )
    p.add_argument(
        "--auto",
        action="store_true",
        help="OpenCode: auto-approve permissions (dangerous)",
    )
    p.add_argument(
        "--wait",
        action="store_true",
        help="OpenCode: run foreground and wait for completion",
    )
    p.add_argument(
        "--no-inject",
        action="store_true",
        help="Freebuff: clipboard + queue only (skip Terminal paste)",
    )
    p.add_argument(
        "--spawn",
        action="store_true",
        help="Freebuff: open a new Terminal tab and paste",
    )
    p.add_argument("--dry-run", action="store_true", help="Plan only; write job JSON")
    return p


def build_status_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dispatch_external_agent status")
    p.add_argument("job_id")
    return p


def build_await_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dispatch_external_agent await")
    p.add_argument("job_id")
    p.add_argument("--timeout", type=float, default=1800)
    p.add_argument("--poll", type=float, default=2.0)
    return p


def build_list_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dispatch_external_agent list")
    p.add_argument("--limit", type=int, default=20)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"-h", "--help"}:
        build_dispatch_parser().print_help()
        return 0
    if argv and argv[0] == "dispatch":
        argv = argv[1:]
    if argv and argv[0] == "status":
        args = build_status_parser().parse_args(argv[1:])
        return cmd_status(args.job_id)
    if argv and argv[0] == "await":
        args = build_await_parser().parse_args(argv[1:])
        return cmd_await(args.job_id, args.timeout, args.poll)
    if argv and argv[0] == "list":
        args = build_list_parser().parse_args(argv[1:])
        return cmd_list(args.limit)

    args = build_dispatch_parser().parse_args(argv)
    prompt = resolve_prompt(args)
    cwd = str(Path(args.cwd).expanduser().resolve())
    backend = pick_backend(args.backend)

    if backend == "freebuff":
        job = dispatch_freebuff(
            prompt,
            cwd,
            inject=not args.no_inject and not args.spawn,
            spawn=bool(args.spawn),
            dry_run=bool(args.dry_run),
        )
    else:
        job = dispatch_opencode(
            prompt,
            cwd,
            model=args.model,
            agent=args.agent,
            attach=args.attach,
            auto=bool(args.auto),
            wait=bool(args.wait),
            dry_run=bool(args.dry_run),
        )

    # Human one-liner on stderr first so stdout stays pure JSON for piping.
    print(
        f"# job_id={job['id']} backend={job['backend']} status={job['status']}",
        file=sys.stderr,
    )
    if job.get("result_path"):
        print(f"# result: {job['result_path']}", file=sys.stderr)
    if job.get("prompt_file"):
        print(f"# prompt_file: {job['prompt_file']}", file=sys.stderr)
    if job["backend"] == "opencode" and job["status"] == "running":
        print(
            f"# await: python tools/scripts/dispatch_external_agent.py await {job['id']}",
            file=sys.stderr,
        )
    print(json.dumps(job, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
