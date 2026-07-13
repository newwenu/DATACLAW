#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_VERSION="3.10.11"
PYTHON_STANDALONE_TAG="20241016"
PYTHON_DIR=".python"

# ---------------------------------------------------------------------------
# 查找 Python
# ---------------------------------------------------------------------------

if [ -f ".venv/bin/python" ]; then
    exec .venv/bin/python start.py "$@"
fi

if [ -f "${PYTHON_DIR}/bin/python3" ]; then
    exec "${PYTHON_DIR}/bin/python3" start.py "$@"
fi

if command -v python3 &>/dev/null; then
    exec python3 start.py "$@"
fi

if command -v python &>/dev/null; then
    exec python start.py "$@"
fi

# ---------------------------------------------------------------------------
# 未找到 Python，提示下载便携版
# ---------------------------------------------------------------------------

if [ ! -t 0 ]; then
    echo "[!] 未找到 Python，且当前为非交互模式，无法引导安装。"
    echo "    请先安装 Python 3.10+ 后重新运行。"
    exit 1
fi

echo "[!] 未找到 Python。"
echo ""
echo "请选择："
echo "  [1] 自动下载 Python ${PYTHON_VERSION} 便携版到 ${PYTHON_DIR}/（推荐）"
echo "  [2] 手动安装 Python 3.10+ 后重试"
echo ""

read -r -p "请选择 (1/2): " choice

if [ "$choice" != "1" ]; then
    echo ""
    echo "请手动安装 Python 3.10+ 后重新运行本脚本。"
    echo "  macOS:  brew install python@3.10"
    echo "  Ubuntu: sudo apt install python3.10"
    echo "  Fedora: sudo dnf install python3.10"
    echo "  下载地址: https://www.python.org/downloads/"
    exit 1
fi

# ---------------------------------------------------------------------------
# 检测平台
# ---------------------------------------------------------------------------

detect_platform() {
    local os arch
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    arch="$(uname -m)"

    case "${os}" in
        linux)
            case "${arch}" in
                x86_64)  echo "x86_64-unknown-linux-gnu" ;;
                aarch64) echo "aarch64-unknown-linux-gnu" ;;
                *)       echo "" ;;
            esac
            ;;
        darwin)
            case "${arch}" in
                x86_64)  echo "x86_64-apple-darwin" ;;
                arm64)   echo "aarch64-apple-darwin" ;;
                *)       echo "" ;;
            esac
            ;;
        *)
            echo ""
            ;;
    esac
}

PLATFORM="$(detect_platform)"
if [ -z "${PLATFORM}" ]; then
    OS_NAME="$(uname -s)"
    ARCH_NAME="$(uname -m)"
    echo "[!] 不支持的平台: ${OS_NAME} ${ARCH_NAME}"
    echo "    请手动安装 Python 3.10+ 后重新运行。"
    exit 1
fi

FILENAME="cpython-${PYTHON_VERSION}+${PYTHON_STANDALONE_TAG}-${PLATFORM}-install_only.tar.gz"
URL="https://github.com/indygreg/python-build-standalone/releases/download/${PYTHON_STANDALONE_TAG}/${FILENAME}"

# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------

echo ""
echo "[*] 正在下载 Python ${PYTHON_VERSION} 便携版 ..."
echo "    ${URL}"

TMPFILE="$(mktemp)"

if command -v curl &>/dev/null; then
    if ! curl -fSL -o "${TMPFILE}" "${URL}" 2>/dev/null; then
        echo "[!] 下载失败，请检查网络连接。"
        rm -f "${TMPFILE}"
        exit 1
    fi
elif command -v wget &>/dev/null; then
    if ! wget -q -O "${TMPFILE}" "${URL}"; then
        echo "[!] 下载失败，请检查网络连接。"
        rm -f "${TMPFILE}"
        exit 1
    fi
else
    echo "[!] 需要 curl 或 wget 来下载，请先安装其中一个。"
    rm -f "${TMPFILE}"
    exit 1
fi

# ---------------------------------------------------------------------------
# 解压
# ---------------------------------------------------------------------------

echo "[*] 正在解压到 ${PYTHON_DIR}/ ..."

if [ -d "${PYTHON_DIR}" ]; then
    rm -rf "${PYTHON_DIR}"
fi

mkdir -p "${PYTHON_DIR}"

if ! tar -xzf "${TMPFILE}" -C "${PYTHON_DIR}" --strip-components=1; then
    echo "[!] 解压失败，文件可能已损坏。"
    rm -f "${TMPFILE}"
    rm -rf "${PYTHON_DIR}"
    exit 1
fi

rm -f "${TMPFILE}"

# 确认 python 可执行
PYTHON_BIN="${PYTHON_DIR}/bin/python3"
if [ ! -f "${PYTHON_BIN}" ]; then
    echo "[!] 解压后未找到 ${PYTHON_BIN}，便携版可能格式有变。"
    rm -rf "${PYTHON_DIR}"
    exit 1
fi

chmod +x "${PYTHON_DIR}"/bin/*

# ---------------------------------------------------------------------------
# 安装 pip（便携版可能未包含）
# ---------------------------------------------------------------------------

if ! "${PYTHON_BIN}" -m pip --version &>/dev/null; then
    echo "[*] 正在安装 pip ..."
    GET_PIP="$(mktemp)"
    if command -v curl &>/dev/null; then
        if ! curl -fSL -o "${GET_PIP}" https://bootstrap.pypa.io/get-pip.py; then
            echo "[!] 下载 get-pip.py 失败。"
            rm -f "${GET_PIP}"
            exit 1
        fi
    else
        if ! wget -q -O "${GET_PIP}" https://bootstrap.pypa.io/get-pip.py; then
            echo "[!] 下载 get-pip.py 失败。"
            rm -f "${GET_PIP}"
            exit 1
        fi
    fi
    if ! "${PYTHON_BIN}" "${GET_PIP}"; then
        echo "[!] pip 安装失败，你可以稍后手动运行："
        echo "    ${PYTHON_BIN} -m ensurepip --upgrade"
        rm -f "${GET_PIP}"
        exit 1
    fi
    rm -f "${GET_PIP}"
fi

echo ""
echo "[+] Python ${PYTHON_VERSION} 便携版安装完成。"
echo "[*] 正在启动 DataClaw ..."
echo ""

exec "${PYTHON_BIN}" start.py "$@"