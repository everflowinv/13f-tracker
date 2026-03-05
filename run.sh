#!/bin/bash

# 获取当前脚本所在绝对目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# 1. 动态扫描并获取最高版本的 Homebrew Python
get_best_python() {
    # 遍历 M 芯片和 Intel 芯片的 Homebrew 默认路径
    for prefix in "/opt/homebrew/bin" "/usr/local/bin"; do
        if [ -d "$prefix" ]; then
            # 查找所有形如 python3.X 的文件，过滤掉 -config 等后缀
            # sort -V 能够聪明地按版本号大小自然排序（保证 3.10 大于 3.9，3.14 大于 3.12）
            local best_py=$(ls -1 "$prefix"/python3.* 2>/dev/null | grep -E "^$prefix/python3\.[0-9]+$" | sort -V | tail -n 1)
            
            # 如果找到了且有执行权限，就返回它
            if [ -n "$best_py" ] && [ -x "$best_py" ]; then
                echo "$best_py"
                return 0
            fi
        fi
    done
    # 如果都没找到，兜底使用系统环境变量里的 python3
    echo "python3"
}

BASE_PYTHON=$(get_best_python)

# 2. 自动化装配 (Auto-bootstrap)
if [ ! -d "$DIR/venv" ]; then
    echo "⚠️ First run detected! Initializing virtual environment using: $BASE_PYTHON"
    "$BASE_PYTHON" -m venv "$DIR/venv"
    echo "📦 Installing dependencies (this may take a minute)..."
    "$DIR/venv/bin/pip" install --upgrade pip -q
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt" -q
    echo "✅ Setup complete!"
fi

# 3. 使用专属虚拟环境执行 Python 脚本（抑制非关键 warning，避免污染 JSON）
"$DIR/venv/bin/python" -W ignore "$DIR/scripts/13f_skill.py" "$@"
