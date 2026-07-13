# -*- coding: utf-8 -*-
"""DataClaw 启动脚本

自动创建便携虚拟环境、安装依赖、校验配置并启动 DataClaw。

用法:
    python start.py            交互式 TUI 模式
    python start.py "查询"     单次查询模式
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MIN_PYTHON = (3, 10)

BASE_DIR = Path(__file__).parent.resolve()
VENV_DIR = BASE_DIR / ".venv"
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / ".env.example"
REQUIREMENTS = BASE_DIR / "requirements.txt"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _banner():
    print("=" * 52)
    print("  DataClaw 启动器")
    print("=" * 52)
    print()


def _is_in_venv() -> bool:
    if sys.prefix != sys.base_prefix:
        return True
    if os.environ.get("VIRTUAL_ENV"):
        return True
    if os.environ.get("CONDA_PREFIX"):
        return True
    return False


def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


# ---------------------------------------------------------------------------
# 阶段一：Python 版本 & 虚拟环境
# ---------------------------------------------------------------------------

def check_python_version() -> bool:
    if sys.version_info >= MIN_PYTHON:
        return True
    print(
        f"[!] 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，"
        f"当前版本 {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    print(f"    请安装 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ 后重试。")
    print(f"    下载地址: https://www.python.org/downloads/")
    return False


def create_venv() -> bool:
    if VENV_DIR.exists():
        if _venv_python().exists():
            return True
        print(f"[!] 虚拟环境目录已损坏: {_venv_python()} 不存在")
        print(f"    目录位置: {VENV_DIR}")
        choice = input("是否删除并重建？(Y/n): ").strip().lower()
        if choice in ("n", "no"):
            print("[!] 已取消，无法继续。")
            return False
        shutil.rmtree(VENV_DIR)

    print("[*] 正在 .venv/ 下创建虚拟环境 ...")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[!] 创建虚拟环境失败: {exc}")
        return False

    # 升级 venv 内的 pip
    venv_py = _venv_python()
    if venv_py.exists():
        print("[*] 正在升级 pip ...")
        result = subprocess.run(
            [str(venv_py), "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("[!] pip 升级失败，可能影响后续依赖安装。")
            if result.stderr.strip():
                print(f"    {result.stderr.strip()}")

    print("[+] 虚拟环境创建完成。\n")
    return True


def relaunch_with_venv():
    venv_py = _venv_python()
    if not venv_py.exists():
        print(f"[!] 虚拟环境 Python 未找到: {venv_py}")
        sys.exit(1)

    print("[*] 正在使用虚拟环境 Python 重新启动 ...\n")
    result = subprocess.run(
        [str(venv_py), str(BASE_DIR / "start.py")] + sys.argv[1:],
        cwd=str(BASE_DIR),
    )
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# 阶段二：依赖安装
# ---------------------------------------------------------------------------

def _check_pip() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    print("[!] pip 不可用，虚拟环境可能已损坏。")
    print(f"    请删除 {VENV_DIR} 后重新运行本脚本。")
    return False


def check_dependencies() -> bool:
    if not REQUIREMENTS.exists():
        print("[!] 未找到 requirements.txt，跳过依赖检查。")
        return True

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "-r", str(REQUIREMENTS)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("[!] 依赖检查失败，请检查 requirements.txt 是否格式正确。")
        if result.stderr.strip():
            print(f"    {result.stderr.strip()}")
        return False

    if "Would install" in result.stdout:
        print("[*] 存在未安装的依赖")
        return False

    return True


def install_dependencies():
    if not REQUIREMENTS.exists():
        print("[!] 未找到 requirements.txt，跳过依赖安装。")
        return

    print("[*] 正在从 requirements.txt 安装依赖 ...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[!] 安装依赖失败: {exc}")
        sys.exit(1)

    print("[+] 所有依赖安装完成。\n")


# ---------------------------------------------------------------------------
# 阶段三：配置文件 & API Key 校验
# ---------------------------------------------------------------------------

def ensure_env_file():
    if ENV_FILE.exists():
        return

    try:
        if ENV_EXAMPLE.exists():
            shutil.copy2(ENV_EXAMPLE, ENV_FILE)
            print("[+] 已从 .env.example 创建 .env")
        else:
            ENV_FILE.write_text("MAIN_MODEL=deepseek\nDEEPSEEK_API_KEY=\n", encoding="utf-8")
            print("[+] 已创建 .env（最小配置）")
    except OSError as exc:
        print(f"[!] 创建 .env 失败: {exc}")
        sys.exit(1)


def _load_config():
    try:
        from core.config import reload_config
        return reload_config()
    except Exception:
        try:
            from core.config import get_config
            return get_config()
        except Exception as exc:
            print(f"[!] 加载配置失败: {exc}")
            return None


def validate_api_keys() -> bool:
    config = _load_config()
    if config is None:
        return False
    errors = config.validate_api_keys()
    if not errors:
        return True
    for err in errors:
        print(f"[!] {err}")
    return False


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _write_env_key(key: str, value: str):
    try:
        if not ENV_FILE.exists():
            ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
            return

        lines = ENV_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                lines[i] = f"{key}={value}\n"
                found = True
                break

        if not found:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"{key}={value}\n")

        ENV_FILE.write_text("".join(lines), encoding="utf-8")
    except OSError as exc:
        print(f"[!] 写入 .env 失败: {exc}")
        sys.exit(1)


def _install_dashscope():
    try:
        import dashscope
        return
    except ImportError:
        pass

    print("[*] Qwen 模型需要 dashscope 依赖，正在安装 ...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "dashscope", "--upgrade"],
            check=True,
        )
        print("[+] dashscope 安装完成。")
    except subprocess.CalledProcessError as exc:
        print(f"[!] dashscope 安装失败: {exc}")
        print("    你可以稍后手动运行: pip install dashscope --upgrade")
        sys.exit(1)


def prompt_api_key_config() -> bool:
    print()
    print("是否现在配置 API Key？")
    print("  [1] 现在配置（推荐）")
    print("  [2] 稍后手动编辑 .env")
    print()

    choice = input("请选择 (1/2): ").strip()
    if choice != "1":
        print()
        print("请手动编辑 .env 配置 API Key 后重新运行。")
        print("  DeepSeek 申请: https://platform.deepseek.com/api_keys")
        print("  通义千问 申请: https://bailian.console.aliyun.com/")
        return False

    print()
    print("选择模型：")
    print("  [1] DeepSeek（默认）")
    print("  [2] Qwen 通义千问")
    print()

    model_choice = input("请选择 (1/2): ").strip()
    is_qwen = model_choice == "2"

    if is_qwen:
        env_key = "DASHSCOPE_API_KEY"
        model_value = "qwen"
        prompt_label = "请输入 DashScope API Key (sk-...): "
        apply_url = "https://bailian.console.aliyun.com/"
    else:
        env_key = "DEEPSEEK_API_KEY"
        model_value = "deepseek"
        prompt_label = "请输入 DeepSeek API Key (sk-...): "
        apply_url = "https://platform.deepseek.com/api_keys"

    while True:
        api_key = getpass.getpass(prompt_label).strip()
        if not api_key:
            print("[!] API Key 不能为空，请重新输入。")
            continue
        if api_key in ("sk-", "sk-your-key-here"):
            print("[!] 请输入真实的 API Key，不是占位符。")
            continue
        break

    print()
    print("确认写入以下配置到 .env？")
    print(f"  MAIN_MODEL={model_value}")
    print(f"  {env_key}={_mask_key(api_key)}")
    print()

    confirm = input("确认写入？(Y/n): ").strip().lower()
    if confirm in ("n", "no"):
        print("[!] 已取消配置。")
        return False

    _write_env_key("MAIN_MODEL", model_value)
    _write_env_key(env_key, api_key)
    print("[+] API Key 已写入 .env。")

    if is_qwen:
        _install_dashscope()

    print("[*] 正在校验配置 ...")
    if validate_api_keys():
        print("[+] API Key 校验通过。")
        return True

    print("[!] 校验失败，请检查 API Key 是否正确。")
    print(f"    你可以编辑 .env 修改，或前往重新申请: {apply_url}")
    return False


# ---------------------------------------------------------------------------
# 阶段四：启动
# ---------------------------------------------------------------------------

def launch_claw():
    print("[*] 正在启动 DataClaw ...\n")
    try:
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "Claw.py")] + sys.argv[1:],
            cwd=str(BASE_DIR),
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(0)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    try:
        _main()
    except KeyboardInterrupt:
        print("\n[!] 已中断。")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[!] 启动过程中出现未预期的错误: {exc}")
        print("    你可以尝试删除 .venv 目录后重新运行。")
        print("    如果问题持续，请联系开发者或提交问题报告并附带以下信息：")
        print(f"    Python: {sys.version}")
        print(f"    平台: {sys.platform}")
        sys.exit(1)


def _main():
    _banner()

    # 步骤 1：Python 版本检查
    if not check_python_version():
        sys.exit(1)

    # 步骤 2：虚拟环境
    if not _is_in_venv():
        if not create_venv():
            sys.exit(1)
        relaunch_with_venv()
        return

    print(f"[+] 当前虚拟环境: {sys.prefix}")

    # 步骤 3：pip 可用性检查
    if not _check_pip():
        sys.exit(1)

    # 步骤 4：依赖检查
    if check_dependencies():
        print("[+] 依赖已齐全。")
    else:
        install_dependencies()

    # 步骤 5：.env 文件
    ensure_env_file()
    print("[+] 配置文件就绪。")

    # 步骤 6：API Key 校验
    if validate_api_keys():
        print("[+] API Key 校验通过。")
    else:
        if not prompt_api_key_config():
            sys.exit(1)

    # 步骤 7：启动
    launch_claw()


if __name__ == "__main__":
    main()